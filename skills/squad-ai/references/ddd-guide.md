# DDD Guide — Domínio Rico em Java 25

Guia operacional para aplicar DDD tático forte com recursos modernos do Java. Material prescritivo para a squad.

## Sumário

1. [Value Objects validados](#1-value-objects)
2. [Aggregates e invariantes](#2-aggregates-e-invariantes)
3. [Domain Events](#3-domain-events)
4. [Domain Services](#4-domain-services)
5. [Bounded Contexts](#5-bounded-contexts)
6. [Linguagem Ubíqua no código](#6-linguagem-ubíqua)
7. [Checklist de revisão](#7-checklist)

---

## 1. Value Objects

**Conceito:** objeto imutável identificado por valor (dois VOs com mesmo conteúdo são iguais). Representa conceitos do domínio: `Email`, `CPF`, `Money`, `Quantidade`, `OrderId`.

### Regra de ouro

Todo dado primitivo com significado de negócio **deve** ter VO. `String`, `BigDecimal`, `UUID` solto no domínio é indicador de modelagem anêmica — e será marcado 🔴 no review.

### Implementação canônica — Java 25

```java
package com.example.pedidos.domain.common.vo;

import java.util.Objects;

public record Email(String value) {
    public Email {
        Objects.requireNonNull(value, "email não pode ser nulo");
        String trimmed = value.trim();
        if (trimmed.isEmpty()) {
            throw new DomainException("email não pode ser vazio");
        }
        if (!trimmed.matches("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$")) {
            throw new DomainException("email inválido: " + trimmed);
        }
        value = trimmed.toLowerCase();
    }
}
```

**Por que `record` e não classe?**

- Imutabilidade por padrão
- `equals/hashCode/toString` automáticos corretos
- Validação no **compact constructor**, executada antes de atribuir os campos → falha rápida, invariante sempre verdadeira após construção
- Menos boilerplate — P1 Simplicidade

### VOs com múltiplos campos

```java
public record Money(BigDecimal amount, Currency currency) {
    public Money {
        Objects.requireNonNull(amount, "amount");
        Objects.requireNonNull(currency, "currency");
        if (amount.scale() > currency.getDefaultFractionDigits()) {
            throw new DomainException("scale incompatível com moeda " + currency);
        }
        if (amount.signum() < 0) {
            throw new DomainException("amount não pode ser negativo");
        }
    }

    public Money add(Money other) {
        if (!currency.equals(other.currency)) {
            throw new DomainException("moedas incompatíveis: " + currency + " vs " + other.currency);
        }
        return new Money(amount.add(other.amount), currency);
    }

    public Money multiply(int factor) {
        return new Money(amount.multiply(BigDecimal.valueOf(factor)), currency);
    }

    public static Money zero(Currency currency) {
        return new Money(BigDecimal.ZERO.setScale(currency.getDefaultFractionDigits()), currency);
    }
}
```

### Identidade como VO

```java
public record PedidoId(UUID value) {
    public PedidoId {
        Objects.requireNonNull(value, "pedidoId");
    }
    public static PedidoId novo() {
        return new PedidoId(UUID.randomUUID());
    }
}
```

### Pattern Matching em VOs para dispatch

```java
public sealed interface DocumentoFiscal permits CPF, CNPJ {}
public record CPF(String value) implements DocumentoFiscal { /* valida */ }
public record CNPJ(String value) implements DocumentoFiscal { /* valida */ }

String formatar(DocumentoFiscal doc) {
    return switch (doc) {
        case CPF c  -> "CPF: " + c.value();
        case CNPJ c -> "CNPJ: " + c.value();
    };
}
```

`sealed` + `switch` com pattern matching elimina visitors e garante exaustividade em tempo de compilação. **Use em vez de hierarquias abertas quando o conjunto é finito e conhecido.**

---

## 2. Aggregates e Invariantes

**Conceito:** cluster de objetos tratado como unidade de consistência. Tem um **Root**, e só o Root é acessível externamente.

### Regras

1. Toda mutação passa pelo Root.
2. Root valida invariantes **antes** de commitar estado.
3. Fora do aggregate: referências apenas por **ID**, nunca por objeto.
4. Uma transação → um aggregate (consistência forte apenas dentro; entre aggregates, consistência eventual via events).
5. Zero setters públicos. Mutações têm nomes do domínio.

### Implementação canônica

```java
package com.example.pedidos.domain.pedidos.model;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public final class Pedido {
    private final PedidoId id;
    private final ClienteId clienteId;
    private final List<ItemPedido> itens;
    private PedidoStatus status;
    private final Instant criadoEm;
    private final transient List<PedidoEvent> eventosPendentes = new ArrayList<>();

    private Pedido(PedidoId id, ClienteId clienteId, List<ItemPedido> itens,
                   PedidoStatus status, Instant criadoEm) {
        this.id = id; this.clienteId = clienteId;
        this.itens = itens; this.status = status; this.criadoEm = criadoEm;
    }

    public static Pedido criar(ClienteId clienteId) {
        var pedido = new Pedido(
            PedidoId.novo(), clienteId,
            new ArrayList<>(), new PedidoStatus.Rascunho(), Instant.now()
        );
        pedido.eventosPendentes.add(new PedidoCriado(pedido.id, clienteId, pedido.criadoEm));
        return pedido;
    }

    public void adicionarItem(ProdutoId produtoId, Quantidade quantidade, Money preco) {
        if (!(status instanceof PedidoStatus.Rascunho)) {
            throw new DomainException("só pedidos em rascunho aceitam itens");
        }
        var item = new ItemPedido(produtoId, quantidade, preco);
        itens.add(item);
        eventosPendentes.add(new ItemAdicionado(id, produtoId, quantidade, preco));
    }

    public void confirmar() {
        if (itens.isEmpty()) {
            throw new DomainException("não é possível confirmar pedido vazio");
        }
        if (!(status instanceof PedidoStatus.Rascunho)) {
            throw new DomainException("apenas rascunho pode ser confirmado");
        }
        this.status = new PedidoStatus.Confirmado(Instant.now());
        eventosPendentes.add(new PedidoConfirmado(id));
    }

    public Money valorTotal() {
        return itens.stream()
            .map(ItemPedido::subtotal)
            .reduce(Money.zero(itens.getFirst().subtotal().currency()), Money::add);
    }

    // accessors imutáveis
    public PedidoId id() { return id; }
    public ClienteId clienteId() { return clienteId; }
    public List<ItemPedido> itens() { return Collections.unmodifiableList(itens); }
    public PedidoStatus status() { return status; }
    public Instant criadoEm() { return criadoEm; }

    // extração de eventos (consumido pelo command handler)
    public List<PedidoEvent> pullEvents() {
        var copy = List.copyOf(eventosPendentes);
        eventosPendentes.clear();
        return copy;
    }
}
```

### Estados com sealed interface

Em vez de `enum` (finito mas sem estado associado) ou `String`/`int` (nenhuma garantia), use sealed types quando cada estado carrega dados próprios:

```java
public sealed interface PedidoStatus
    permits PedidoStatus.Rascunho, PedidoStatus.Confirmado,
            PedidoStatus.Cancelado, PedidoStatus.Finalizado {
    record Rascunho() implements PedidoStatus {}
    record Confirmado(Instant confirmadoEm) implements PedidoStatus {}
    record Cancelado(Instant canceladoEm, String motivo) implements PedidoStatus {}
    record Finalizado(Instant finalizadoEm) implements PedidoStatus {}
}
```

O compilador garante que `switch` trate todos os casos — invariante arquitetural validada estaticamente.

---

## 3. Domain Events

**Conceito:** fato de negócio que aconteceu no passado. Imutável. Emitido pelo Aggregate Root quando muda estado relevante.

```java
public sealed interface PedidoEvent extends DomainEvent
    permits PedidoCriado, ItemAdicionado, PedidoConfirmado, PedidoCancelado {
    PedidoId pedidoId();
    Instant ocorridoEm();
}

public record PedidoConfirmado(PedidoId pedidoId, Instant ocorridoEm) implements PedidoEvent {
    public PedidoConfirmado(PedidoId pedidoId) {
        this(pedidoId, Instant.now());
    }
}
```

### Fluxo de publicação

1. Aggregate acumula eventos em `eventosPendentes`
2. Command Handler chama `pullEvents()` após `save()`
3. Events são gravados em `outbox_events` na **mesma transação**
4. Outbox relay publica externamente (SQS / Kafka / listeners in-process)

Ver `cqrs-outbox.md` para detalhes.

---

## 4. Domain Services

Use quando a operação não pertence naturalmente a um aggregate (envolve vários, ou é cálculo puro de domínio).

```java
public interface CalculadoraFrete {  // port (interface em domain)
    Money calcular(Pedido pedido, CEP destino);
}
```

A implementação concreta pode viver em `infrastructure/` se depende de APIs externas, ou em `domain/` se for cálculo puro. Nunca use Domain Service como "sacola de lógica procedural" — só quando realmente não cabe em aggregate.

---

## 5. Bounded Contexts

**Cada contexto tem seu próprio modelo, linguagem, pacote Java e — idealmente — schema de banco.**

Pacotes:
```
com.example.pedidos.domain.pedidos.model        ← contexto "pedidos"
com.example.pedidos.domain.pagamentos.model     ← contexto "pagamentos"
com.example.pedidos.domain.catalogo.model       ← contexto "catalogo"
```

### Comunicação entre contextos

- **Domain Events** (consistência eventual, preferido)
- **Anti-Corruption Layer** (ACL) quando consumir modelo externo: traduz em `infrastructure/` antes de entrar no domínio

**Proibido:** `import com.example.pedidos.domain.pagamentos.*` dentro de `...domain.pedidos.*`. Se acontecer, o boundary está quebrado.

### Spring Modulith (opcional, altamente recomendado)

Spring Modulith (Spring 7) formaliza módulos e gera diagrama automaticamente. Adicione quando a app cresce:

```java
@Modulith(systemName = "pedidos-api")
@SpringBootApplication
public class Application { /* ... */ }
```

Testes de módulo:
```java
@ApplicationModuleTest
class PedidosModuleTest {
    @Test void cumpreRegrasDeModulo(ModuleTestExecution exec) {
        exec.verify();
    }
}
```

---

## 6. Linguagem Ubíqua

Código deve ecoar o glossário. Lista mental de smells:

- `UserService.process()` → o que "process" significa no domínio? Provavelmente vem de `autenticar`, `ativar`, `registrar`.
- `update()` → mutação sem nome do domínio. Prefira `confirmar()`, `suspender()`, `reagendar()`.
- `status: String` → falta VO/enum/sealed type.
- `quantity: int` → provavelmente quer `Quantidade` validado (> 0, máximo, etc.).

---

## 6.1 Recursos Java 25 Idiomáticos em DDD

DDD se beneficia diretamente de três JEPs do Java 25. Use-os explicitamente em VOs, ARs e handlers.

### JEP 492 — Flexible Constructor Bodies (GA)

**Antes do JEP 492**, qualquer código antes de `super(...)` / `this(...)` era proibido. Isso empurrava validações para fora do construtor ou exigia factory methods artificiais. **Agora**, você pode validar argumentos **antes** da chamada ao super-construtor:

```java
// Aggregate Root com herança controlada
public final class Pedido extends EntidadeAuditavel {

    private final PedidoId id;
    private final List<ItemPedido> itens;

    public Pedido(PedidoId id, Cliente cliente, List<ItemPedido> itens) {
        // ── prelude: validação ANTES de super (JEP 492) ───────────
        Objects.requireNonNull(id, "id obrigatório");
        Objects.requireNonNull(cliente, "cliente obrigatório");
        if (itens == null || itens.isEmpty()) {
            throw new IllegalArgumentException("pedido exige ao menos 1 item");
        }
        var total = itens.stream()
            .map(ItemPedido::subtotal)
            .reduce(Money.zero(cliente.moeda()), Money::soma);
        if (total.valor().compareTo(BigDecimal.valueOf(100_000)) > 0) {
            throw new LimiteCreditoExcedidoException(cliente.id(), total);
        }

        // ── só agora super é chamado, sabendo que estado é válido ─
        super(cliente.tenantId(), Instant.now());

        this.id = id;
        this.itens = List.copyOf(itens);
    }
}
```

**Para records**, o compact constructor já permite pré-validação desde Java 14. O JEP 492 **unifica a ergonomia**: classes normais agora se comportam como records no que importa.

**Sinais de saúde:**
- ✅ Validação de invariantes no prelude, ANTES de `super(...)`.
- ✅ Nunca mais construtor privado + factory apenas para validar.
- ❌ Se o prelude acessa `this` (não permitido): reorganizar em helper `static`.

### JEP 488 — Primitive Type Patterns (2ª Preview no 25, GA esperado no 26)

Permite usar **tipos primitivos diretamente em `switch`/`instanceof`** com pattern matching + guards. Casa perfeitamente com modelagem de estados finitos em domínio.

```java
// Sealed interface representando evento com código numérico legado
public sealed interface EventoLegado
    permits PedidoCriadoLegado, PedidoCanceladoLegado, PedidoEstornado {}

public record PedidoEstornado(int motivoCodigo, String descricao) implements EventoLegado {}

// Switch com primitive pattern + guard
public StatusPedido interpretar(EventoLegado ev) {
    return switch (ev) {
        case PedidoCriadoLegado c -> StatusPedido.Rascunho;
        case PedidoCanceladoLegado _ -> StatusPedido.Cancelado;

        // JEP 488: match no int primitivo direto, com guard
        case PedidoEstornado(int codigo, _) when codigo == 1 -> StatusPedido.EstornoFinanceiro;
        case PedidoEstornado(int codigo, _) when codigo == 2 -> StatusPedido.EstornoOperacional;
        case PedidoEstornado(int codigo, _) when codigo >= 90 -> StatusPedido.EstornoManual;
        case PedidoEstornado _ -> StatusPedido.EstornoDesconhecido;
    };
}
```

**Antes do JEP 488**, você tinha que **unbox** manualmente (`Integer motivo = ev.motivoCodigo(); switch (motivo) { ... }`) ou usar `if-else` encadeado. Agora o pattern matching funciona ponta a ponta.

**Uso canônico em DDD:**
- Decodificar status numéricos herdados de sistemas legados sem vazar `int` no domínio.
- Tradução de eventos externos em VOs tipados do domínio local.
- Matchers de faixas numéricas (scoring, risco, limites) com guards.

**Sinais de saúde:**
- ✅ Record deconstruction com tipos primitivos + guards explícitos.
- ✅ `default`/fallback sempre presente com tipo sealed.
- ❌ Se o código depende de `Integer`/`Long` apenas para pattern matching: substitua por primitivo agora.

### JEP 506 — Scoped Values (GA) em Command Handlers

`ScopedValue` GA substitui `ThreadLocal` em propagação de contexto. Em CQRS, use para correlation ID, tenant ID e audit context sem poluir a assinatura dos handlers:

```java
public final class Contexto {
    public static final ScopedValue<TenantId> TENANT = ScopedValue.newInstance();
    public static final ScopedValue<String> CORRELATION_ID = ScopedValue.newInstance();
}

// Interceptor HTTP popula o contexto por request
ScopedValue.where(Contexto.TENANT, tenantDoJwt)
           .where(Contexto.CORRELATION_ID, request.getHeader("X-Correlation-Id"))
           .run(() -> handler.handle(comando));

// Command handler consome sem parâmetro extra
public void handle(ConfirmarPedido cmd) {
    var tenant = Contexto.TENANT.get();  // imutável, seguro entre threads virtuais
    var pedido = repo.carregar(cmd.pedidoId(), tenant);
    pedido.confirmar();
    repo.salvar(pedido);
}
```

**Por que importa em DDD:** mantém assinaturas limpas do domínio (comando = intenção de negócio, não carrega infraestrutura) e é seguro com Virtual Threads (diferente de `ThreadLocal`, que causa pinning).

---

## 7. Checklist de Revisão DDD

```
□ Todo conceito de negócio tem Value Object dedicado
□ VO valida no construtor (compact constructor em record)
□ Aggregate Root sem setter público
□ Mutações nomeadas pelo domínio (verbos do glossário)
□ Invariantes validadas dentro do aggregate antes de mudar estado
□ Domain Events emitidos em toda mudança relevante
□ Estados finitos modelados com sealed types, não String/enum simples
□ Referências entre aggregates apenas por ID
□ Bounded contexts em pacotes separados, zero cross-import
□ Linguagem ubíqua consistente entre glossário e código
□ Zero import de framework em domain/
□ Construtores usam Flexible Constructor Bodies (JEP 492) para validar antes de super
□ Switch sobre código legado usa Primitive Type Patterns (JEP 488) com guards
□ Correlation/Tenant context propagados via ScopedValue (JEP 506), não ThreadLocal
```

Qualquer falha → 🔴 no review.
