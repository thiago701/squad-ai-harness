# Referência — Camadas & DDD (Clean Architecture, Domain/Integration Events, Aggregate Roots)

> Parte da skill `engenheiro-clean-architect`. Carregue sob demanda. Hub: `../SKILL.md`.
## Clean Architecture — Regra da Dependência

```
┌─────────────────────────────────────────────┐
│           Frameworks & Drivers               │  ← Web, DB, UI, Devices
│  ┌───────────────────────────────────────┐   │
│  │        Interface Adapters             │   │  ← Controllers, Gateways, Presenters
│  │  ┌─────────────────────────────────┐  │   │
│  │  │      Application Layer          │  │   │  ← Use Cases
│  │  │  ┌───────────────────────────┐  │  │   │
│  │  │  │      Domain / Entities    │  │  │   │  ← Regras de negócio puras
│  │  │  └───────────────────────────┘  │  │   │
│  │  └─────────────────────────────────┘  │   │
│  └───────────────────────────────────────┘   │
└─────────────────────────────────────────────┘

REGRA ABSOLUTA: dependências apontam SEMPRE para dentro.
Domínio não conhece Use Case. Use Case não conhece Controller. Controller não conhece JPA.
```

### Estrutura de Pacotes — Java 25
```
com.empresa.produto/
├── domain/                    ← ZERO dependências externas
│   ├── model/
│   │   ├── Pedido.java        ← Aggregate Root
│   │   ├── PedidoId.java      ← Value Object (Record)
│   │   └── StatusPedido.java  ← Sealed interface
│   ├── port/
│   │   ├── in/                ← Use case interfaces (driven)
│   │   │   └── ConfirmarPedidoUseCase.java
│   │   └── out/               ← Repository/event interfaces (driving)
│   │       ├── PedidoRepository.java
│   │       └── EventosPedido.java
│   └── exception/
├── application/               ← Orquestra domínio, sem frameworks
│   └── usecase/
│       └── ConfirmarPedidoUseCaseImpl.java
├── adapter/
│   ├── in/
│   │   └── web/               ← Spring Controllers (depende de application)
│   │       └── PedidoController.java
│   └── out/
│       ├── persistence/       ← JPA Repositories (depende de domain.port.out)
│       │   └── PedidoJpaRepository.java
│       └── messaging/         ← Kafka Publishers
│           └── PedidoKafkaPublisher.java
└── config/                    ← Spring @Configuration, wiring de DI
```

### Estrutura de Pacotes — Python 3.12+
```
src/
├── domain/                    # ZERO imports de infra
│   ├── model/
│   │   ├── pedido.py          # Aggregate, dataclass ou Pydantic BaseModel
│   │   └── value_objects.py   # frozen dataclasses
│   ├── ports/
│   │   ├── repositories.py    # Protocols
│   │   └── events.py          # Protocols
│   └── exceptions.py
├── application/               # Orquestra domínio
│   └── use_cases/
│       └── confirmar_pedido.py
├── adapters/
│   ├── inbound/
│   │   └── http/              # FastAPI routers
│   │       └── pedido_router.py
│   └── outbound/
│       ├── persistence/       # SQLAlchemy repositories
│       └── messaging/         # Publishers
└── config/                    # Wiring de dependências
    └── container.py           # dependency-injector ou manual
```

---

## Domain Events vs Integration Events

Separação **obrigatória** em qualquer sistema com mensageria. Confundir os dois gera sistemas acoplados que se quebram a cada mudança de esquema interno.

### Matriz Decisional

| Aspecto | **Domain Event** | **Integration Event** |
|---|---|---|
| **Público** | Dentro do **mesmo bounded context** | Entre **bounded contexts** / serviços |
| **Transporte** | In-process (`ApplicationEventPublisher`, [[Spring Modulith]] Event Publication Registry) | Broker externo (SNS/SQS, EventBridge, Kafka) |
| **Payload** | Rico — inclui referências a aggregates ou valueObjects do domínio | **Contrato estável** — DTOs versionados, sem entidades internas |
| **Schema** | Pode mudar com refactoring interno livremente | **Versionado e backward-compatible** (v1, v2, sem breaking change) |
| **Acoplamento** | Compile-time (tipos internos do módulo) | Runtime (JSON/Avro/Protobuf), **contract tests obrigatórios** |
| **Ordem** | Síncrono após commit (transactional event listener) | Assíncrono, eventual consistency |
| **Exemplo** | `PedidoConfirmado(Pedido pedido)` | `pedido.confirmado.v1({orderId, amount, customerId})` |
| **Dono do schema** | Equipe do módulo | **Consumer-driven contracts** — consumidores votam mudanças |

### Regra Canônica

```
Domain Event NUNCA sai do bounded context.
Integration Event NUNCA entra no domínio.

Ponte: um Application Service (use case) CONVERTE Domain Event em Integration Event
       e publica via Outbox Pattern.
```

### Exemplo — Pedido Confirmado

**Domain Event (interno ao módulo `pedidos`):**

```java
// Domain — sem imports de infra
package com.empresa.pedido.domain.event;

import com.empresa.pedido.domain.model.Pedido;
import java.time.Instant;

public record PedidoConfirmado(Pedido pedido, Instant ocorridoEm) {
    public PedidoConfirmado(Pedido pedido) {
        this(pedido, Instant.now());
    }
}
```

**Handler in-process (mesmo processo, mesma transação lógica):**

```java
@Component
class PedidoConfirmadoHandler {

    private final OutboxWriter outbox;

    @TransactionalEventListener(phase = TransactionPhase.BEFORE_COMMIT)
    void on(PedidoConfirmado event) {
        // Converte para Integration Event e grava no Outbox
        var integration = PedidoConfirmadoV1.builder()
            .orderId(event.pedido().id().value())
            .amount(event.pedido().valor())
            .customerId(event.pedido().clienteId().value())
            .occurredAt(event.ocorridoEm())
            .schemaVersion("1.0")
            .build();
        outbox.record("pedido.confirmado.v1", integration);
    }
}
```

**Integration Event (contrato público, versionado):**

```java
// No pacote shared/integration — compartilhado com consumidores via artefato Maven
package com.empresa.contracts.pedido.v1;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

public record PedidoConfirmadoV1(
    UUID orderId,
    BigDecimal amount,
    UUID customerId,
    Instant occurredAt,
    String schemaVersion   // SEMPRE presente
) {}
```

**Publicação assíncrona via Outbox poller:**

```
[app]    Domain Event ───▶ Handler ───▶ Outbox (mesma TX do BD)
                                         │
                                         │ poller externo
                                         ▼
                               SNS/EventBridge/Kafka
                                         │
                                         ▼
                                  Outros serviços
```

Ver também: [[Outbox Pattern]] em `especialista-banco/SKILL.md` §9.1.

### Checklist de Review

- [ ] Domain Event **não vaza** para integração — sempre há um converter no boundary
- [ ] Integration Event tem **campo `schemaVersion`** obrigatório
- [ ] Integration Event é um **Record/DTO sem dependência** de domain model
- [ ] Mudanças no domain interno **não quebram** consumidores externos
- [ ] Consumer-driven contract tests (Pact ou equivalente) no CI
- [ ] Evolução de schema → `v1 + v2 coexistem` por janela de transição (mínimo 1 sprint)
- [ ] Outbox publica Integration Event, **não** Domain Event serializado

### Anti-padrões Nomeados

- **"Serializar o Aggregate"** — publicar o JSON de `Pedido` como integration event. Qualquer mudança interna quebra consumidores.
- **"Schema como documentação"** — versão única que evolui sem registro. Sempre `v1`, `v2` explícitos.
- **"Event storming contaminado"** — misturar pedido de integração no modelo de domínio. Cada cor no [[EventStorming]] tem seu papel.
- **"Outbox sem converter"** — gravar a entidade JPA direto no Outbox. Quebra na primeira renomeação de coluna.

### Conexões

- Ver também [[Outbox Pattern]], [[Aggregate Root]], [[EventStorming]], [[Spring Modulith]]
- Cross-reference: `especialista-banco/SKILL.md` (persistência do Outbox), `arquiteto-cloud-aws/SKILL.md` (SNS/EventBridge)

---

## Aggregate Roots — Design DDD com ArchUnit

Um **Aggregate Root** (raiz do agregado) é a única entidade visível de fora. Entidades internas são encapsuladas e invisíveis. O contrato é garantido: external caller → Root.method → invariante mantido.

**Regra fundamental:** Não existe `getItems()` mutável. Apenas `addItem(sku, qtd)` que valida invariantes.

### Exemplo: Pedido (Raiz) + ItemPedido (Interno)

```java
// Domain — ZERO imports de infra
package com.empresa.pedido.domain.model;

public class Pedido {
    private final PedidoId id;
    private final ClienteId clienteId;
    private StatusPedido status;
    private List<ItemPedido> itens;          // Lista interna — NUNCA exposta mutável
    private BigDecimal totalCalculado;

    // Construtor private — usar factory
    private Pedido(PedidoId id, ClienteId clienteId, List<ItemPedido> itens) {
        this.id = Objects.requireNonNull(id);
        this.clienteId = Objects.requireNonNull(clienteId);
        this.itens = new ArrayList<>(itens);  // cópia defensiva
        this.status = StatusPedido.PENDENTE;
        this.totalCalculado = calcularTotal();
    }

    // Factory — ponto de entrada
    public static Pedido novo(PedidoId id, ClienteId clienteId) {
        return new Pedido(id, clienteId, List.of());
    }

    // Comportamento: adicionar item — valida invariantes
    public void adicionarItem(Sku sku, Quantidade qtd, Preco preco) {
        if (status != StatusPedido.PENDENTE) {
            throw new TransicaoEstadoInvalidaException(status);
        }
        
        // Verificar duplicação
        var existente = itens.stream()
            .filter(it -> it.sku().equals(sku))
            .findFirst();
        
        if (existente.isPresent()) {
            existente.get().aumentarQuantidade(qtd);  // itemPedido também encapsula
        } else {
            itens.add(new ItemPedido(sku, qtd, preco));  // ItemPedido é internal
        }
        
        recalcularTotal();  // Manter invariante: total = soma dos itens
    }

    // Comportamento: confirmar pedido
    public void confirmar() {
        if (itens.isEmpty()) {
            throw new PedidoVazioException();
        }
        if (status != StatusPedido.PENDENTE) {
            throw new TransicaoEstadoInvalidaException(status);
        }
        
        this.status = StatusPedido.CONFIRMADO;
        // Invariante verificado: itens não estão vazios, valor > 0, etc.
    }

    // ⚠️ NUNCA: expor lista mutável
    // public List<ItemPedido> getItens() { return itens; }  // ❌ VIOLAÇÃO

    // ✅ CORRETO: retornar cópia imutável (Java 17+)
    public List<ItemPedido> itens() {
        return List.copyOf(itens);  // Cópia imutável — modificações não afetam o domínio
    }

    // ✅ CORRETO: retornar Collection imutável (Java 8+)
    public Collection<ItemPedido> obterItens() {
        return Collections.unmodifiableList(itens);
    }

    private void recalcularTotal() {
        this.totalCalculado = itens.stream()
            .map(ItemPedido::subtotal)
            .reduce(BigDecimal.ZERO, BigDecimal::add);
    }

    private BigDecimal calcularTotal() {
        return itens.stream()
            .map(ItemPedido::subtotal)
            .reduce(BigDecimal.ZERO, BigDecimal::add);
    }

    // Getters de identidade (permitidos)
    public PedidoId id() { return id; }
    public ClienteId clienteId() { return clienteId; }
    public StatusPedido status() { return status; }
    public BigDecimal total() { return totalCalculado; }
}

// Entidade interna — NUNCA acessível de fora do agregado
public class ItemPedido {
    private final Sku sku;
    private Quantidade quantidade;
    private final Preco preco;

    ItemPedido(Sku sku, Quantidade qtd, Preco preco) {
        this.sku = Objects.requireNonNull(sku);
        this.quantidade = Objects.requireNonNull(qtd);
        this.preco = Objects.requireNonNull(preco);
    }

    void aumentarQuantidade(Quantidade delta) {
        this.quantidade = quantidade.somar(delta);
    }

    BigDecimal subtotal() {
        return preco.valor().multiply(
            new BigDecimal(quantidade.valor())
        );
    }

    // Getters (package-private — só Pedido acessa)
    Sku sku() { return sku; }
    Quantidade quantidade() { return quantidade; }
    Preco preco() { return preco; }
}

// Sealed hierarchy para StatusPedido (domínio rico)
public sealed interface StatusPedido 
    permits StatusPendente, StatusConfirmado, StatusEnviado, StatusCancelado {
}

public record StatusPendente() implements StatusPedido {}
public record StatusConfirmado(Instant confirmadoEm) implements StatusPedido {}
public record StatusEnviado(String codigoRastreio) implements StatusPedido {}
public record StatusCancelado(String motivo) implements StatusPedido {}
```

### ArchUnit — Validar Encapsulamento de Agregado em Tempo de Build

```java
// test/java/.../ArchitectureTest.java
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.classes;

public class AggregateArchitectureTest {

    @ArchTest
    public static final ArchRule pedidoAggregateRule =
        classes()
            .that()
            .resideInAPackage("..pedido.domain.model..")
            .and()
            .haveSimpleNameEndingWith("Pedido")
            .should()
            .onlyBeAccessedByClassesThat()
                .resideInAPackage("..pedido..")
                .or()
                .resideInAPackage("..pedido.application..")
                .or()
                .resideInAPackage("..pedido.adapter..")
            .because("Pedido é aggregate root — acessível de qualquer camada, mas itens internos não");

    @ArchTest
    public static final ArchRule itemPedidoEncapsulationRule =
        classes()
            .that()
            .resideInAPackage("..pedido.domain.model..")
            .and()
            .haveSimpleNameStartingWith("Item")
            .should()
            .onlyBeAccessedByClassesThat()
                .resideInAPackage("..pedido.domain.model..")
            .because("ItemPedido é entidade interna — NUNCA acessível de fora do agregado");

    @ArchTest
    public static final ArchRule naoExporMutavelRule =
        methods()
            .that()
            .areDeclaredInClassesThat()
                .haveSimpleNameEndingWith("Pedido")
            .and()
            .haveNameMatching("getItens|getLinhas|getItems")
            .should()
            .haveRawReturnType(Collection.class)
            .orShould()
            .haveRawReturnType(List.class)
            .and()
            .should()
            .beAnnotatedWith(Deprecated.class) // ou Custom @Exposed warning
            .because("getItens() expõe lista mutável — use itens() que retorna copyOf()");
}
```

### Teste de Invariante — Garantir que Root Encapsula

```java
// test/java/.../model/PedidoTest.java
@Test
void naoPermitirAcessoMutavelAItens() {
    var pedido = Pedido.novo(PedidoId.novo(), ClienteId.novo());
    
    // Tentar modificar a lista retornada
    var itens = pedido.itens();
    
    // UnsupportedOperationException — lista é imutável
    assertThatThrownBy(() -> itens.add(new ItemPedido(...)))
        .isInstanceOf(UnsupportedOperationException.class);
}

@Test
void invarianteManterTotalAtualizado() {
    var pedido = Pedido.novo(PedidoId.novo(), ClienteId.novo());
    
    pedido.adicionarItem(
        Sku.de("SKU-001"),
        Quantidade.de(2),
        Preco.de(BigDecimal("50.00"))
    );
    pedido.adicionarItem(
        Sku.de("SKU-002"),
        Quantidade.de(1),
        Preco.de(BigDecimal("100.00"))
    );
    
    // Invariante: total = 100 + 100 = 200
    assertThat(pedido.total()).isEqualByComparingTo(BigDecimal("200.00"));
}

@Test
void naoPermitirConfirmarPedidoVazio() {
    var pedido = Pedido.novo(PedidoId.novo(), ClienteId.novo());
    
    assertThatThrownBy(pedido::confirmar)
        .isInstanceOf(PedidoVazioException.class)
        .hasMessageContaining("não pode ser vazio");
}
```

### Anti-padrão nomeado

```java
// ❌ VIOLAÇÃO — Controller acessando ItemPedido direto, bypass do aggregate
@RestController
@RequestMapping("/api/pedidos")
public class PedidoController {
    
    @PostMapping("/{pedidoId}/itens")
    public ResponseEntity<?> adicionarItem(@PathVariable Long pedidoId, @RequestBody ItemRequest req) {
        // VIOLAÇÃO: consultando JPA para buscar ItemPedido direto
        var item = itemRepository.findBySku(req.sku());  // ❌
        // ...
    }
}

// ✅ CORRETO — sempre via Aggregate Root
@RestController
@RequestMapping("/api/pedidos")
public class PedidoController {
    private final ConfirmarPedidoUseCase usecase;

    @PostMapping("/{pedidoId}/itens")
    public ResponseEntity<?> adicionarItem(@PathVariable Long pedidoId, @RequestBody ItemRequest req) {
        // Use case orquestra → repository busca Pedido (raiz) → Pedido.adicionarItem()
        usecase.adicionarItem(
            new PedidoId(pedidoId),
            Sku.de(req.sku()),
            Quantidade.de(req.quantidade()),
            Preco.de(req.preco())
        );
        return ResponseEntity.ok().build();
    }
}
```

**Checklist Aggregate Roots:**
- ✅ Existe uma classe "Raiz" — `Pedido`, `Empresa`, `Carrinho`, etc.
- ✅ Entidades internas NÃO são acessíveis de fora (package-private ou sealed)
- ✅ Factory methods constroem agregados válidos (`Pedido.novo(...)`)
- ✅ Invariantes de negócio são encapsulados (ex: `total = soma de itens`)
- ✅ Retorno de collections é imutável (`List.copyOf()`, `Collections.unmodifiableList()`)
- ✅ ArchUnit valida que ItemPedido só é acessado de dentro de Pedido
- ✅ Testes garantem que invariantes são mantidos em qualquer caminho de execução

---

