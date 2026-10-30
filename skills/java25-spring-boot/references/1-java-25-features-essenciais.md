# java25-spring-boot · 1. Java 25 — Features Essenciais

> Reference da skill `java25-spring-boot` (movida da SKILL.md em 11/10/2026 — hub + references, I3). Carregue só quando a tarefa pedir este tema.

## 1. Java 25 — Features Essenciais

### 1.1 Virtual Threads (Finalizados)

Virtual threads são threads leves gerenciadas pela JVM, não pelo SO. Permitem criar milhões de
threads concorrentes sem esgotar memória. Ideal para workloads I/O-bound.

**Padrão correto — Executor para aplicações:**
```java
// Spring Boot 4: basta ativar no application.properties
// spring.threads.virtual.enabled=true

// Ou programaticamente:
@Bean
Executor applicationTaskExecutor() {
    return Executors.newVirtualThreadPerTaskExecutor();
}
```

**Quando usar virtual threads:**
- Chamadas HTTP, queries ao banco, leitura de arquivos (I/O-bound)
- APIs que atendem milhares de requests simultâneos
- Fan-out para múltiplos serviços downstream

**Quando NÃO usar:**
- Tarefas CPU-bound intensivas (prefira ForkJoinPool ou parallel streams)
- Código com `synchronized` extenso que causa pinning no carrier thread
- Operações que já são rápidas e não bloqueiam

**Armadilhas comuns:**
- Virtual threads NÃO resolvem gargalos de banco — 10.000 VTs com 10 conexões HikariCP = fila
- ThreadLocal NÃO propaga para virtual threads em StructuredTaskScope — use ScopedValue
- `synchronized` **não pinna mais o carrier thread desde o JDK 24** (JEP 491, modo sync) —
  a antiga recomendação "prefira ReentrantLock" só vale para JDK < 24

### 1.2 Structured Concurrency (JEP 505 — ⚠️ PREVIEW; segue preview no Java 27)

> **Correção (verificada set/2026):** Structured Concurrency **NÃO é GA no Java 25** — foi a
> **5ª preview** no 25 e continua preview (7ª rodada) no Java 27, sem data de finalização.
> Usar em produção exige `--enable-preview` + decisão humana explícita (status completo em
> `java-modern-expert` → [`../java-modern-expert/references/feature-status-catalog.md`](../java-modern-expert/references/feature-status-catalog.md)).

Garante que tarefas concorrentes tenham ciclo de vida bem definido: tudo que inicia em um scope
deve terminar antes do scope fechar. Isso previne thread leaks e simplifica error handling.

```java
// Fan-out para 3 serviços em paralelo
try (var scope = StructuredTaskScope.open(Joiner.allSuccessfulOrThrow())) {
    Subtask<User>    userTask    = scope.fork(() -> userService.findById(id));
    Subtask<Orders>  ordersTask  = scope.fork(() -> orderService.findByUser(id));
    Subtask<Loyalty>  loyaltyTask = scope.fork(() -> loyaltyService.getPoints(id));

    scope.join(); // Aguarda TODOS completarem ou falha se algum lançar exceção

    return new UserProfile(
        userTask.get(),
        ordersTask.get(),
        loyaltyTask.get()
    );
}
// Se qualquer subtask falhar, as outras são canceladas automaticamente
```

**Joiners disponíveis:**

| Joiner | Comportamento |
|--------|--------------|
| `awaitAll()` | Aguarda todas, sem lançar exceção automática |
| `allSuccessfulOrThrow()` | Falha se qualquer subtask lançar exceção |
| `anySuccessfulResultOrThrow()` | Retorna no primeiro sucesso (short-circuit) |
| `allUntil(predicate)` | Continua até condição ser atendida |

**Joiner customizado (padrão avançado):**
```java
// Retorna o melhor resultado disponível, ignorando falhas parciais
Joiner<List<Quote>, Quote> bestEffort = Joiner.of(
    (subtask) -> { /* onComplete: acumula resultados bem-sucedidos */ },
    () -> { /* result: retorna lista acumulada */ }
);
```

### 1.3 Scoped Values (JEP 506 — Finalizado)

Substituição moderna para ThreadLocal, projetada para virtual threads.
Imutáveis dentro de um scope, propagam automaticamente para subtasks.

```java
// Definição
static final ScopedValue<RequestContext> REQUEST_CTX = ScopedValue.newInstance();

// Binding — o valor é visível em toda a call chain
ScopedValue.where(REQUEST_CTX, new RequestContext(correlationId, userId))
    .run(() -> {
        // Qualquer método chamado aqui pode acessar REQUEST_CTX.get()
        processOrder();
        sendNotification();
    });

// Propagação para Structured Concurrency — funciona automaticamente!
ScopedValue.where(REQUEST_CTX, ctx).run(() -> {
    try (var scope = StructuredTaskScope.open(Joiner.awaitAll())) {
        scope.fork(() -> {
            // REQUEST_CTX.get() retorna o mesmo ctx aqui
            return enrichOrder();
        });
        scope.join();
    }
});
```

**Vantagens sobre ThreadLocal:**
- Lookup O(1) vs hash table lookup
- Imutável — impossível poluir entre threads
- Propagação automática em StructuredTaskScope
- Sem memory leaks (não precisa de `.remove()`)

### 1.4 Pattern Matching Avançado

```java
// Primitive types em patterns (JEP 507/530 — Preview)
switch (statusCode) {
    case 200      -> handleSuccess();
    case int i when i >= 400 && i < 500 -> handleClientError(i);
    case int i when i >= 500            -> handleServerError(i);
    default       -> handleUnknown(statusCode);
}

// Record patterns com desconstrução profunda
record Order(Long id, Customer customer, List<Item> items) {}
record Customer(String name, Address address) {}
record Address(String city, String country) {}

if (order instanceof Order(var id, Customer(var name, Address(_, var country)), _)) {
    log.info("Pedido {} de {} no {}", id, name, country);
}

// Sealed interfaces + pattern matching exaustivo
sealed interface PaymentResult permits Approved, Declined, PendingReview {}
record Approved(String transactionId) implements PaymentResult {}
record Declined(String reason) implements PaymentResult {}
record PendingReview(Duration estimatedTime) implements PaymentResult {}

String message = switch (result) {
    case Approved(var txId)       -> "Aprovado: " + txId;
    case Declined(var reason)     -> "Recusado: " + reason;
    case PendingReview(var time)  -> "Em análise (~" + time.toMinutes() + " min)";
    // Exaustivo — compilador garante que todos os casos estão cobertos
};
```

#### Caso prático: `mapError(Exception)` em handlers HTTP

Pattern matching for switch (JEP 441, standard desde Java 21) é a substituição
canônica para cadeias de `catch` tipados que mapeiam exceção → response.
Cada `catch` repete o boilerplate (log + monta resposta); um método dedicado
`mapError(Exception)` com pattern switch elimina a duplicação e fica testável
isoladamente:

```java
// ❌ Antes — cadeia de catches em todo handler
try {
    return service.execute(...);
} catch (JsonProcessingException badJson) {
    log.warn("validation.failed", Map.of("reason", "invalid_json", ...));
    return Response.badRequest(badJson.getOriginalMessage());
} catch (IllegalArgumentException bad) {
    log.warn("validation.failed", Map.of("reason", "invalid_input", ...));
    return Response.badRequest(bad.getMessage());
} catch (ConcurrentBucketModificationException conflict) {
    log.warn("business.execute.conflict", ...);
    metrics.count(OPERATION, "ConcurrentBucketConflict");
    return Response.conflict(conflict.getMessage());
} catch (Exception e) {
    log.error("business.execute.error", e);
    return Response.internalError(e.getMessage());
}

// ✅ Depois — método puro, exaustivo, testável caso a caso
try {
    return service.execute(...);
} catch (Exception e) {
    return mapError(e);
}

private Response mapError(Exception e) {
    return switch (e) {
        case JsonProcessingException bj -> {
            // PII/segurança: NÃO devolver getOriginalMessage() — a mensagem do Jackson
            // ecoa trechos do payload (dados pessoais) e detalhes internos de parsing.
            log.warn("validation.failed", Map.of("reason", "invalid_json", ...));
            yield Response.badRequest("Corpo da requisição contém JSON inválido");
        }
        case IllegalArgumentException b -> {
            // OK devolver b.getMessage() SOMENTE se for mensagem de validação de domínio,
            // controlada por você — nunca a mensagem crua de uma lib de terceiros.
            log.warn("validation.failed", Map.of("reason", "invalid_input", ...));
            yield Response.badRequest(b.getMessage());
        }
        case ConcurrentBucketModificationException c -> {
            log.warn("business.execute.conflict", ...);
            metrics.count(OPERATION, "ConcurrentBucketConflict");
            yield Response.conflict("Conflito de concorrência — tente novamente");
        }
        default -> {
            // Detalhe vai para o log (com correlation id); cliente recebe mensagem genérica.
            log.error("business.execute.error", e);
            yield Response.internalError("Erro interno ao processar a requisição");
        }
    };
}
```

> **Segurança — não vaze exceções ao cliente.** `e.getMessage()`/`getOriginalMessage()` de
> bibliotecas costumam conter stack, SQL, caminhos internos ou trechos do payload com PII.
> A regra: logue o detalhe completo internamente (com correlation id) e devolva ao cliente
> apenas mensagens genéricas ou de validação de domínio controladas por você.

**Ganhos:**
- `mapError` é função pura (`Exception → Response`) — testável sem mock de business.
- Adicionar exceção nova é UMA linha no switch.
- Sem perda do tipo concreto: `case ConcurrentBucketModificationException c` mantém acesso a `c.getXxx()`.
- `default` exaustivo garante que nenhuma exceção escapa.

Esse pattern emergiu de auditoria real em Lambda Java 25 + AOT e
reduziu handlers de 41-52 linhas para 14-18 linhas. Aplica também a serviços
que precisam mapear erros de domínio para retornos tipados.

### 1.5 Outras Features Relevantes do JDK 25

- **Gatherers API (Stream):** Operações intermediárias customizadas em streams, habilitando
  windowing, scanning, folding com estado — impossíveis antes sem collectors terminais.
- **Foreign Function & Memory API (FFM):** Acesso seguro a memória nativa e bibliotecas C/C++
  sem JNI. Ideal para integrações com libs de ML, crypto, ou drivers nativos.
- **Vector API (Incubator):** SIMD operations para processamento numérico de alto desempenho.
- **Class-File API:** Manipulação programática de bytecode, substituindo ASM para frameworks.

---
