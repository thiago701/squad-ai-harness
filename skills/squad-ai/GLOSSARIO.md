# Squad AI — Glossário de Termos Canônicos

> **Propósito.** Este arquivo é a fonte única de verdade para termos técnicos que
> aparecem em múltiplas skills. Quando houver divergência entre uma skill e este
> glossário, **este glossário prevalece** e a skill deve ser corrigida.
>
> Toda nova skill ou alteração em skill existente deve verificar este arquivo antes
> de cunhar ou redefinir um termo.

**Última atualização:** 2026-04-19 (v2 — adicionados §11 a §17 para DDD, CQRS, Outbox, Linguagem Ubíqua, Bounded Context e Idempotência)

---

## 1. Circuit Breaker

**Definição canônica.** Padrão de resiliência que **abre** um circuito (bloqueia
chamadas) quando a taxa de falhas ultrapassa um threshold, evitando cascata de
falhas em dependências downstream. Implementação de referência na squad:
**Resilience4j** com `@CircuitBreaker(name = "nomeDaDependencia", fallbackMethod = "fallback")`.

**Uso correto:**
- Sempre **automático** (Resilience4j decide abrir/fechar com base em métricas).
- Configurar `slidingWindowType`, `failureRateThreshold`, `waitDurationInOpenState`, `permittedNumberOfCallsInHalfOpenState`.
- Exportar métricas via Micrometer/OpenTelemetry (`resilience4j.circuitbreaker.*`).

**Anti-padrão.** Chamar de "circuit breaker" uma feature flag manual que desliga
integração em produção. Isso é um **operational kill switch** e tem nome próprio
(ver §2).

**Skills que o definem:**
- `java25-spring-boot/SKILL.md` — `@CircuitBreaker` declarativo
- `arquiteto-cloud-aws/SKILL.md` — proteção contra downstream (RDS, DynamoDB, APIs)
- `engenheiro-devops/SKILL.md` — métricas no Prometheus e alertas no CloudWatch

---

## 2. Operational Kill Switch (Ops Toggle)

**Definição canônica.** Feature flag manual, controlada por humanos via painel ops
(Unleash, AWS AppConfig), usada para **desligar** uma integração ou funcionalidade
em produção sem deploy. Não reage automaticamente a falhas.

**Quando usar:**
- Desligar uma integração problemática enquanto se investiga (ex: API externa caiu).
- Gating de feature em canary rollout.
- Circuit breaker manual de última instância quando o Resilience4j não está configurado.

**Não confundir com Circuit Breaker (§1).** Ops toggle é **manual e humano**;
circuit breaker é **automático e reativo a métricas**.

---

## 3. Correlation ID

**Definição canônica.** Identificador único (`UUID`) propagado por toda a cadeia
de uma request — do ingress HTTP até logs, mensagens SQS, invocações Lambda e
downstream services — para rastreabilidade fim a fim.

**Regra de propagação (end-to-end):**

```
HTTP Request
    │  header: X-Correlation-Id: <uuid>
    ▼
Filter/Interceptor  →  ScopedValue.where(CORRELATION_ID, value)
    │
    ▼
Virtual Thread (business logic)
    │
    ├──► SLF4J MDC.put("correlationId", value)  →  JSON structured log
    │
    ├──► HTTP outbound (RestClient + @HttpExchange)
    │      header: X-Correlation-Id propagado
    │
    ├──► SQS SendMessage
    │      messageAttribute: correlationId = value
    │
    ├──► SNS Publish
    │      messageAttribute: correlationId = value
    │
    └──► OpenTelemetry Span
           attribute: correlation.id = value
           (além do traceId nativo do OTel)

SQS Consumer (Lambda / ECS)
    │  lê messageAttribute.correlationId
    ▼
ScopedValue rebind → continua a cadeia
```

**Implementação canônica (Java 25 + Spring Boot 4).**

```java
public final class CorrelationIdContext {

    public static final ScopedValue<String> CORRELATION_ID = ScopedValue.newInstance();

    private CorrelationIdContext() {}

    public static String currentOrNew() {
        return CORRELATION_ID.isBound()
                ? CORRELATION_ID.get()
                : UUID.randomUUID().toString();
    }
}
```

```java
// Ingress HTTP
@Component
public class CorrelationIdFilter implements Filter {

    public static final String HEADER = "X-Correlation-Id";

    @Override
    public void doFilter(ServletRequest req, ServletResponse res, FilterChain chain)
            throws IOException, ServletException {

        HttpServletRequest http = (HttpServletRequest) req;
        String id = Optional.ofNullable(http.getHeader(HEADER))
                            .orElseGet(() -> UUID.randomUUID().toString());

        ((HttpServletResponse) res).setHeader(HEADER, id);

        try (var mdc = MDC.putCloseable("correlationId", id)) {
            ScopedValue.where(CorrelationIdContext.CORRELATION_ID, id)
                       .run(() -> {
                           try { chain.doFilter(req, res); }
                           catch (Exception e) { throw new RuntimeException(e); }
                       });
        }
    }
}
```

```java
// Egress SQS
sqsClient.sendMessage(req -> req
    .queueUrl(queueUrl)
    .messageBody(payload)
    .messageAttributes(Map.of(
        "correlationId", MessageAttributeValue.builder()
            .dataType("String")
            .stringValue(CorrelationIdContext.currentOrNew())
            .build()
    ))
);
```

**Anti-padrão.** Criar um novo UUID por camada (controller → service → adapter).
Isso quebra a rastreabilidade fim a fim.

---

## 4. Health Probes

**Definição canônica.** Endpoints HTTP usados por orquestradores (Kubernetes, ECS,
ALB) para decidir se um pod/task deve receber tráfego ou ser reiniciado.

| Probe | Endpoint | Semântica | Falha → ação |
|-------|----------|-----------|---------------|
| **Liveness** | `/actuator/health/liveness` | A JVM está viva e sem deadlock? | Pod/task é **reiniciado** |
| **Readiness** | `/actuator/health/readiness` | A app está pronta para receber tráfego (banco ok, cache quente, circuit breakers fechados)? | Pod/task é **removido do load balancer** (mas não reiniciado) |
| **Startup** | `/actuator/health/liveness` (ou custom) | App ainda está inicializando? Usado para aumentar `initialDelaySeconds`. | Pod/task continua em startup (não é killed) |

**Configuração canônica Spring Boot 4:**

```yaml
management:
  endpoint:
    health:
      probes:
        enabled: true          # habilita /liveness e /readiness
      show-details: when-authorized
  health:
    livenessState:
      enabled: true
    readinessState:
      enabled: true
```

**Kubernetes pod spec canônico:**

```yaml
livenessProbe:
  httpGet:
    path: /actuator/health/liveness
    port: 8080
  initialDelaySeconds: 30      # tempo para JVM + CDS + Spring subir
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 3           # 3 falhas consecutivas = restart

readinessProbe:
  httpGet:
    path: /actuator/health/readiness
    port: 8080
  initialDelaySeconds: 20
  periodSeconds: 5
  timeoutSeconds: 2
  failureThreshold: 2

startupProbe:
  httpGet:
    path: /actuator/health/liveness
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 5
  failureThreshold: 30          # 30 × 5s = 150s de startup tolerado
```

**ECS task definition equivalente:**

```json
"healthCheck": {
  "command": [ "CMD-SHELL", "curl -f http://localhost:8080/actuator/health/liveness || exit 1" ],
  "interval": 10,
  "timeout": 3,
  "retries": 3,
  "startPeriod": 30
}
```

**Regra:** liveness **nunca** deve checar dependências externas (banco, cache, APIs).
Senão uma instabilidade do banco reinicia todos os pods. Use **readiness** para isso.

---

## 5. Graceful Shutdown

**Definição canônica.** Processo de encerramento de uma instância sem derrubar
requests em voo. Dividido em 3 fases nomeadas:

| Fase | Nome | Ação | Duração típica |
|------|------|------|-----------------|
| 1 | **Reject** | Para de aceitar novas requests (readiness passa a falhar, LB drena) | 5-10 s |
| 2 | **Drain** | Aguarda requests em voo concluírem (até `timeout-per-shutdown-phase`) | 15-25 s |
| 3 | **Close** | Fecha conexões (HikariCP, Redis, brokers, HTTP clients) e encerra a JVM | 2-5 s |

**Configuração canônica Spring Boot 4:**

```yaml
server:
  shutdown: graceful
spring:
  lifecycle:
    timeout-per-shutdown-phase: 30s
management:
  endpoint:
    shutdown:
      access: none            # nunca expor /actuator/shutdown em prod
```

**SIGTERM handler:** Spring Boot intercepta `SIGTERM` automaticamente quando
`server.shutdown=graceful`. Kubernetes envia `SIGTERM` e aguarda `terminationGracePeriodSeconds`
antes de `SIGKILL`. **Regra:** `terminationGracePeriodSeconds` deve ser `timeout-per-shutdown-phase + 10s`.

---

## 6. Organização de Pacotes (Clean Architecture + Hexagonal)

**Estrutura canônica Java 25 + Spring Boot 4:**

```
com.example.bc.<bounded-context>
├── domain/
│   ├── model/             # Aggregate Root, entidades, value objects (records)
│   ├── event/             # Domain events (sealed interface + records)
│   ├── port/
│   │   ├── in/            # Use case interfaces (driver ports)
│   │   └── out/           # Repository, gateway, publisher interfaces (driven ports)
│   └── service/           # Domain services (lógica sem identidade)
│
├── application/
│   ├── usecase/           # Implementações de port.in, orquestram o domínio
│   └── dto/               # Command/Query (records)
│
├── adapter/
│   ├── in/
│   │   ├── http/          # @RestController + DTOs HTTP
│   │   ├── messaging/     # SQS/SNS listeners
│   │   └── scheduler/     # @Scheduled jobs
│   └── out/
│       ├── persistence/   # JPA Entity + JpaRepository + PersistenceAdapter
│       ├── messaging/     # SqsPublisher, SnsPublisher
│       ├── client/        # @HttpExchange clients para APIs externas
│       └── cache/         # Redis, Caffeine
│
└── config/                # @Configuration, beans, profiles
```

**Regras invariantes (validadas por ArchUnit):**

1. `domain/**` **nunca** importa `adapter/**`, `application/**`, `config/**`, `org.springframework.**`, `jakarta.persistence.**`, `com.fasterxml.jackson.**`.
2. `domain/port/out/**` define interfaces; `adapter/out/**` implementa.
3. `domain/port/in/**` define use cases; `application/usecase/**` implementa; `adapter/in/**` invoca.
4. `adapter/in/**` **nunca** importa `adapter/out/**` diretamente — só via `port/in`.
5. JPA Entity vive em `adapter/out/persistence/entity/` e **nunca** sai do pacote. Mapper converte `JpaEntity` ↔ `DomainModel`.

**Anti-padrões nomeados:**

- **Anêmico com JPA** — Domain Entity = JPA Entity. Viola isolamento; qualquer refactor de banco quebra o domínio.
- **Service gigante** — Use case com > 5 dependências injetadas. Sintoma de falta de decomposição (ISP).
- **Cross-adapter call** — `HttpController` chamando `JpaRepository` direto, pulando o use case.

**Skill canônica:** `engenheiro-clean-architect/SKILL.md` + `java25-spring-boot/references/clean-architecture-java.md` + `java25-spring-boot/references/archunit-rules.md`.

---

## 7. Virtual Threads vs Connection Pool

**Regra canônica.** Virtual Threads escalam I/O **externo** (HTTP, SQS, Lambda invoke,
Bedrock) mas **não** escalam chamadas a banco via `JpaRepository` se o pool HikariCP
estiver esgotado. O gargalo se move do thread para o pool.

**Dimensionamento:**

- `spring.datasource.hikari.maximum-pool-size` = **(RDS max_connections × 0.8) ÷ (número de instâncias)**.
- Virtual Threads: habilitar com `spring.threads.virtual.enabled=true`.
- Não dimensionar pool HikariCP em função do número de VTs (eles podem ser milhões). Dimensione em função da **capacidade do banco**.

**Carrier Thread Pinning.** Ocorre quando um VT entra em região `synchronized` ou
chama código nativo. Solução: trocar `synchronized` por `ReentrantLock`. Detectar com
`-Djdk.tracePinnedThreads=full`.

---

## 8. Métricas cobertas vs Mutation Score

**Cobertura de testes (JaCoCo/JaCoCo Report):** mede **quantidade** — linhas/branches
executadas pelos testes. Meta do domínio: `≥ 80%`; geral: `≥ 60%`.

**Mutation Score (PIT):** mede **qualidade** dos testes — capacidade de detectar
bugs injetados. Meta do domínio: `≥ 80%`.

**Regra de ouro:** as duas métricas são **complementares**, não substituíveis.
100% de cobertura com 20% de mutation score significa testes que executam o código
mas não validam comportamento (ex: faltam assertions).

**Classificação de mutantes:**

| Tipo de mutação | Sobrevivente é aceitável? | Ação |
|------------------|---------------------------|-------|
| Boundary (`>` → `>=`) | Às vezes (se trivial) | Adicionar teste de boundary exato |
| Null check removido | Nunca | Adicionar teste com null input |
| Return value mutation | Nunca | Adicionar assertion no teste |
| Conditional negation | Nunca | Adicionar teste do caminho ausente |
| Math operator (`+` → `-`) | Nunca | Adicionar teste com valores diferenciados |
| Void method call removed | Nunca | Verificar side effect (Mockito.verify) |

Ver `especialista-qualidade/SKILL.md` seção "Guia de Mutantes Aceitáveis vs Necessários".

---

## 9. Apache Maven 4 (vs Apache Maven 3 legado e vs Gradle histórico)

**Status canônico.** Apache Maven 4 (model 4.1.0) é o **padrão único** da squad. Gradle não é suportado — referências históricas aparecem apenas em contextos comparativos.

**Componentes canônicos:**

- `mvnd` — Maven Daemon. Processos residentes que eliminam cold start.
- **Build Cache Extension** (`maven-build-cache-extension` v1.2.0+) — cache de builds locais e remotos.
- **Consumer POM** (`maven.consumer.pom.flatten=true`) — POM publicado sem `${revision}` nem parents locais.
- **Model 4.1.0** — permite `<root>true</root>` no POM pai e inferência de `<parent>` em subprojetos.
- `mvnsh` — Maven Shell (processo persistente para sessions interativas).
- `mvnup` — migração automatizada Maven 3 → 4.

**Configuração mínima obrigatória** em todo projeto Java da squad:

```xml
<!-- .mvn/extensions.xml -->
<extensions>
  <extension>
    <groupId>org.apache.maven.extensions</groupId>
    <artifactId>maven-build-cache-extension</artifactId>
    <version>1.2.0</version>
  </extension>
</extensions>
```

```properties
# .mvn/maven.config
-T 1C
--batch-mode
--no-transfer-progress
```

Ver `java25-spring-boot/references/maven4-guide.md` para troubleshooting e benchmarks.

---

## 11. Value Object (DDD)

**Definição canônica.** Objeto de domínio **imutável** identificado pela combinação dos seus atributos (não por uma chave). Dois Value Objects com os mesmos valores são considerados iguais. Na squad, VOs são **records** Java 25 com **validação no compact constructor** — é ali que a regra de negócio sobre o tipo vive.

**Regra de ouro.** Nenhum dado primitivo (`String`, `BigDecimal`, `UUID`) cruza a fronteira do domínio sem estar encapsulado em um VO. Exemplos: `Email`, `CPF`, `CNPJ`, `Money`, `PedidoId`, `Quantidade`, `PorcentagemDesconto`.

**Implementação canônica (Java 25 + Records):**

```java
public record Email(String value) {
    private static final Pattern VALID =
        Pattern.compile("^[\\w.+\\-]+@[\\w\\-]+\\.[\\w\\-.]+$");

    public Email {
        Objects.requireNonNull(value, "email não pode ser nulo");
        if (!VALID.matcher(value).matches())
            throw new DomainException("email inválido: " + value);
    }
}

public record Money(BigDecimal amount, Currency currency) {
    public Money {
        Objects.requireNonNull(amount, "amount");
        Objects.requireNonNull(currency, "currency");
        if (amount.signum() < 0)
            throw new DomainException("Money não aceita valor negativo");
        amount = amount.setScale(currency.getDefaultFractionDigits(), RoundingMode.HALF_EVEN);
    }
    public Money add(Money other) {
        if (!currency.equals(other.currency))
            throw new DomainException("moedas diferentes");
        return new Money(amount.add(other.amount), currency);
    }
}
```

**Anti-padrões nomeados:**
- **Obsession Primitive** — usar `String email` ou `BigDecimal valor` em métodos do domínio em vez de `Email` / `Money`.
- **Validação em service** — checar formato de email no `UserService` em vez de dentro do record `Email`. Quebra encapsulamento.
- **Setter em VO** — Value Object com setters não é VO, é mutável. Use `with*()` retornando novo VO.

**Skill canônica:** `engenheiro-especificacao/SKILL.md` + `squad-ai/references/ddd-guide.md`.

---

## 12. Aggregate Root (DDD)

**Definição canônica.** Cluster de objetos de domínio tratado como **unidade de consistência**. O Aggregate Root é a **única porta de entrada** para mutação; toda modificação interna passa por um método dele que valida a invariante depois da mudança.

**Regras invariantes:**

1. **Sem setters públicos** em entidades dentro do aggregate. Mutação via métodos de negócio (`confirmar()`, `adicionarItem(...)`, `cancelar(motivo)`).
2. **Uma transação = um aggregate** por operação de escrita. Dois aggregates diferentes coordenam via eventos (não por transação distribuída).
3. **Identificador tipado** — o aggregate tem um `*Id` VO, não `UUID` cru (ex.: `PedidoId`, `ClienteId`).
4. **Emissão de eventos** — cada mutação relevante adiciona um `DomainEvent` à lista interna (`pullEvents()` na escrita).
5. **Construtor público é raro** — normalmente usa factory estática (`Pedido.criar(clienteId)`) que já emite o evento inicial (`PedidoCriado`).

**Exemplo canônico:**

```java
public final class Pedido {
    private final PedidoId id;
    private final ClienteId clienteId;
    private PedidoStatus status;
    private final List<ItemPedido> itens = new ArrayList<>();
    private final List<DomainEvent> events = new ArrayList<>();

    private Pedido(PedidoId id, ClienteId clienteId) { … }

    public static Pedido criar(ClienteId cliente) {
        var p = new Pedido(PedidoId.gerar(), cliente);
        p.status = new PedidoStatus.Rascunho();
        p.events.add(new PedidoCriado(p.id, cliente, Instant.now()));
        return p;
    }

    public void confirmar() {
        if (!(status instanceof PedidoStatus.Rascunho))
            throw new DomainException("só é possível confirmar pedido em rascunho");
        if (itens.isEmpty())
            throw new DomainException("pedido vazio não pode ser confirmado");
        status = new PedidoStatus.Confirmado(Instant.now());
        events.add(new PedidoConfirmado(id, valorTotal(), Instant.now()));
    }

    public List<DomainEvent> pullEvents() {
        var out = List.copyOf(events);
        events.clear();
        return out;
    }
}
```

**Skill canônica:** `squad-ai/references/ddd-guide.md`.

---

## 13. Invariante de Domínio

**Definição canônica.** Regra de negócio que **deve ser verdadeira antes e depois** de toda transação sobre o aggregate. Se uma operação violaria a invariante, a operação falha (`DomainException`) e o estado não é commitado.

**Como documentar.** No handoff do Especificador para o Arquiteto, cada aggregate tem uma lista numerada:

```
Aggregate: Pedido
  I1  Todo pedido confirmado tem ≥ 1 item.
  I2  Valor total = soma dos subtotais dos itens (nunca recalculado só na view).
  I3  Status segue a máquina: Rascunho → Confirmado → (Cancelado|Entregue).
  I4  Pedido cancelado após confirmação exige motivo não-vazio.
```

**Teste associado.** Toda invariante tem **pelo menos um teste unitário** que tenta violá-la e espera `DomainException`.

**Anti-padrão.** Deixar invariante em camada de serviço (`PedidoService.validar()`). A invariante vive no aggregate — é a razão dele existir.

---

## 14. Bounded Context

**Definição canônica.** Fronteira linguística e arquitetural em que um modelo de domínio é **coerente e consistente**. Dentro do contexto, `Pedido` significa uma coisa só. Fora dele, `Pedido` pode significar outra e **não compartilha classes** — cruzar a fronteira exige tradução.

**Organização canônica na squad:**

```
com.example.pedidos
├── domain/
│   ├── pedidos/      ← bounded context "pedidos"
│   │   ├── model/Pedido.java
│   │   ├── vo/PedidoId.java, ItemPedido.java
│   │   └── event/PedidoConfirmado.java
│   └── pagamentos/   ← bounded context "pagamentos"
│       ├── model/Pagamento.java
│       └── event/PagamentoAutorizado.java
```

**Regras invariantes (validadas por ArchUnit §6):**

1. Classes em `domain.pedidos..` **não** dependem de classes em `domain.pagamentos..` e vice-versa.
2. Comunicação entre contextos é por **Domain Event via Outbox** (§16) ou **Anti-Corruption Layer** (ACL) com DTOs próprios.
3. Cada contexto tem sua própria linguagem ubíqua (§15). Um termo usado em dois contextos precisa estar explícito na lista "Termos por Contexto" do glossário de domínio do projeto.
4. Ideal: schemas de banco lógicos distintos (`CREATE SCHEMA pedidos; CREATE SCHEMA pagamentos;`). Mínimo: prefixo de tabela.

**Anti-padrões nomeados:**
- **Shared Kernel Descontrolado** — 40 classes compartilhadas entre contextos sem critério. Vira monólito disfarçado.
- **Cross-context DTO import** — `PedidosController` retornando `PagamentoResponse`. Se há acoplamento por dados, há acoplamento por deploy.

**Spring Modulith** (opcional) pode validar essas fronteiras em tempo de build/teste via `@ApplicationModule`.

---

## 15. Linguagem Ubíqua (Ubiquitous Language)

**Definição canônica.** Vocabulário de negócio **compartilhado** entre produto, design, desenvolvimento e código. O mesmo termo é usado na story, no ADR, no nome da classe e na resposta HTTP.

**Onde vive.** O projeto tem um arquivo `docs/linguagem-ubiqua.md` atualizado pelo Especificador a cada story nova. Este glossário (`GLOSSARIO.md`) captura termos **técnicos da squad**, não termos de negócio do projeto — mas os dois são fontes vivas.

**Sinais de saúde:**

✅ "confirmar pedido" na story → `Pedido.confirmar()` no código → `POST /pedidos/{id}/confirmar` no HTTP → `PedidoConfirmado` no event.
❌ "confirmar pedido" na story → `OrderService.processOrder()` no código → `POST /orders/finalize` no HTTP → `OrderFinalizedEvent`.

**Anti-padrão.** Traduzir nomes para inglês "genérico" perdendo semântica (`clienteId` → `entityId`, `confirmarPedido` → `updateStatus`). Código vira indecifrável para o time de negócio.

**Skill canônica:** `engenheiro-especificacao/SKILL.md`.

---

## 16. CQRS in-process + Transactional Outbox

**Definição canônica.**

**CQRS** (Command Query Responsibility Segregation) na forma **in-process** usada pela squad: separação **dentro da mesma aplicação** entre:

- **Command side** — muda estado. `Command` + `CommandHandler` que carrega aggregate, aplica mutação, salva e emite eventos. Retorna `void`, `ID` ou ack mínimo — **nunca o agregado**.
- **Query side** — lê estado. `Query` + `QueryHandler` que lê via `JdbcClient` direto ou view materializada — **sem reidratar aggregate**.

**Transactional Outbox.** Tabela `outbox_events` gravada na **mesma transação** do command. Um relay (poller Spring `@Scheduled` ou Debezium CDC) lê a tabela e publica em SQS / Kafka / consumers externos. Garante *at-least-once delivery* mesmo em falhas de publicação.

**Esquema canônico da tabela:**

```sql
CREATE TABLE outbox_events (
    id UUID PRIMARY KEY,
    aggregate_type VARCHAR(100) NOT NULL,
    aggregate_id VARCHAR(100) NOT NULL,
    event_type VARCHAR(200) NOT NULL,
    payload JSONB NOT NULL,
    headers JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ
);
CREATE INDEX idx_outbox_unprocessed
  ON outbox_events (COALESCE(next_attempt_at, created_at))
  WHERE processed_at IS NULL;
```

**Quando usar.** Sempre que houver Domain Event relevante para consumidores **fora do aggregate** (outros contextos, integrações externas, auditoria, webhook). Evite eventos por "porque sim" — cada evento tem um consumidor ou é ruído.

**Quando NÃO usar.** Event Sourcing não é padrão da squad. Só com ADR explícito justificando — overhead (upcasting, rebuild de projeções) raramente compensa para a maioria dos domínios.

**Anti-padrões nomeados:**
- **Dual-write** — salvar aggregate e publicar em SQS em dois passos. Sem transação atômica = dados inconsistentes na falha.
- **Command que retorna aggregate** — leaky abstraction, incentiva o chamador a depender do write model.
- **Query que carrega aggregate** — overhead sem valor; use `JdbcClient` para projeções.

**Skill canônica:** `squad-ai/references/cqrs-outbox.md`.

---

## 17. Idempotência de Consumer

**Definição canônica.** Propriedade de um consumer de evento que, ao processar **o mesmo evento várias vezes**, produz o mesmo efeito final. Em sistemas com Outbox + relay (§16), *at-least-once delivery* é a norma — o consumer **precisa** aguentar duplicatas.

**Padrões canônicos:**

1. **Chave de idempotência = event_id (UUID do outbox)**. Consumer mantém tabela `processed_events (event_id UUID PRIMARY KEY, processed_at TIMESTAMPTZ)`.
2. **Insert-first pattern.** Na mesma transação do processamento: `INSERT INTO processed_events(event_id) VALUES (?) ON CONFLICT DO NOTHING`. Se `INSERT` retornou 0 linhas, já foi processado — pula.
3. **Operações naturalmente idempotentes** (preferível quando possível): `UPDATE ... WHERE status = 'PENDENTE'` em vez de `UPDATE ... status = status + 1`. Idempotência vira by-design.

**Anti-padrões:**
- Incrementar contador sem chave de idempotência → dobra métricas em retry.
- Enviar email de boas-vindas em handler de `UsuarioRegistrado` sem chave → usuário recebe 3 emails.
- Usar `correlation_id` (§3) como chave de idempotência — correlation_id identifica a **request**, não o **evento**. Evento único pode surgir de múltiplas requests e vice-versa.

---

## Referências cruzadas

| Termo | Skill primária | Referência detalhada |
|-------|----------------|----------------------|
| Circuit Breaker (§1) | `arquiteto-cloud-aws` | `java25-spring-boot/SKILL.md` (Resilience4j) |
| Ops Toggle (§2) | `engenheiro-devops` | `engenheiro-devops/SKILL.md` (Feature Flags) |
| Correlation ID (§3) | `arquiteto-cloud-aws` | `java25-spring-boot/SKILL.md` (Scoped Values) |
| Health Probes (§4) | `engenheiro-devops` | `java25-spring-boot/SKILL.md` (Spring Boot Actuator) |
| Graceful Shutdown (§5) | `engenheiro-devops` | `arquiteto-minimalista/SKILL.md` (12-Factor IX) |
| Organização de Pacotes (§6) | `engenheiro-clean-architect` | `java25-spring-boot/references/clean-architecture-java.md` |
| VT vs Pool (§7) | `java25-spring-boot` | `java25-spring-boot/references/virtual-threads-deep-dive.md` |
| Cobertura vs Mutation (§8) | `especialista-qualidade` | `especialista-qualidade/SKILL.md` |
| Maven 4 (§9) | `engenheiro-devops` | `java25-spring-boot/references/maven4-guide.md` |
| Value Object (§11) | `engenheiro-especificacao` | `squad-ai/references/ddd-guide.md` |
| Aggregate Root (§12) | `engenheiro-especificacao` | `squad-ai/references/ddd-guide.md` |
| Invariante de Domínio (§13) | `tech-lead-review` | `squad-ai/references/ddd-guide.md` |
| Bounded Context (§14) | `arquiteto-minimalista` | `squad-ai/references/ddd-guide.md` + `clean-architecture-java25.md` |
| Linguagem Ubíqua (§15) | `engenheiro-especificacao` | `squad-ai/references/ddd-guide.md` |
| CQRS + Outbox (§16) | `especialista-banco` | `squad-ai/references/cqrs-outbox.md` |
| Idempotência (§17) | `especialista-banco` | `squad-ai/references/cqrs-outbox.md` |

---

## Processo de Atualização

1. Qualquer skill que introduza ou redefina um termo canônico **deve** atualizar este arquivo **no mesmo commit**.
2. O `tech-lead-review` verifica aderência ao glossário no code review da skill.
3. O cofre Obsidian em `docs/obsidian-vault/Conceitos/` deve ter nota atômica para cada termo aqui listado.
