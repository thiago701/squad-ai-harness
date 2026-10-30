# CQRS in-process + Transactional Outbox

## Princípio

**Commands** mudam estado, não retornam dados (exceto ID gerado ou status).
**Queries** leem estado, não mudam nada.
Separação **na aplicação** (pacotes, handlers, modelos), não necessariamente em processos diferentes.

Para garantir consistência entre o write model e integrações externas (outros contextos, filas, webhooks), usamos **Transactional Outbox**: o evento é gravado na mesma transação do command e publicado depois por um relay.

## Modelo

```
   ┌───────────────────┐
   │ Controller REST    │
   └────────┬──────────┘
            │ ConfirmarPedidoCommand
            ▼
   ┌───────────────────┐     ┌──────────────┐
   │  Command Handler   │────▶│  Aggregate    │
   └────────┬──────────┘     └──────┬───────┘
            │                       │ pullEvents()
            │    MESMA TRANSAÇÃO     ▼
            │            ┌──────────────────┐
            ├──save()────▶│  pedidos table   │
            │            │  outbox_events   │
            └────────────▶│       table      │
                         └──────────────────┘

              ┌──────────────────┐
              │  Outbox Relay     │  (Spring @Scheduled ou Debezium)
              └────────┬─────────┘
                       ▼
              ┌──────────────────┐
              │  SQS / Kafka /    │
              │  in-process bus   │
              └──────────────────┘

   ┌───────────────────┐
   │ Controller REST    │
   └────────┬──────────┘
            │ ListarPedidosQuery
            ▼
   ┌───────────────────┐     ┌──────────────┐
   │  Query Handler     │────▶│  read model   │
   └───────────────────┘     │ (view ou tbl) │
                             └──────────────┘
```

## Commands

```java
// application/.../pedidos/command/
public record ConfirmarPedidoCommand(PedidoId pedidoId, String correlationId) {
    public ConfirmarPedidoCommand {
        Objects.requireNonNull(pedidoId, "pedidoId");
    }
}

public class ConfirmarPedidoHandler {
    private final PedidoRepositoryPort repo;
    private final OutboxPort outbox;

    public ConfirmarPedidoHandler(PedidoRepositoryPort repo, OutboxPort outbox) {
        this.repo = repo; this.outbox = outbox;
    }

    public void handle(ConfirmarPedidoCommand cmd) {
        Pedido pedido = repo.findById(cmd.pedidoId())
            .orElseThrow(() -> new DomainException("pedido não encontrado"));
        pedido.confirmar();
        repo.save(pedido);
        outbox.enqueue(pedido.pullEvents());
    }
}
```

O command handler **NÃO** retorna objeto de domínio. Retorna `void`, `ID`, ou DTO mínimo de confirmação. Quem quiser o estado atualizado faz uma query depois.

## Queries

Queries podem ir **direto ao banco via JDBC/JdbcClient/view**, pulando o aggregate. O overhead de reidratar aggregate para uma leitura não tem valor.

```java
// application/.../pedidos/query/
public record ListarPedidosPorClienteQuery(ClienteId clienteId, int limit) {}

public record PedidoResumoView(
    UUID id, UUID clienteId, String status, BigDecimal valorTotal, Instant criadoEm
) {}

public interface PedidoQueryPort {
    List<PedidoResumoView> listarPorCliente(ClienteId clienteId, int limit);
}

public class ListarPedidosPorClienteHandler {
    private final PedidoQueryPort queries;
    public ListarPedidosPorClienteHandler(PedidoQueryPort queries) { this.queries = queries; }
    public List<PedidoResumoView> handle(ListarPedidosPorClienteQuery q) {
        return queries.listarPorCliente(q.clienteId(), q.limit());
    }
}
```

Adapter com `JdbcClient` (Spring 6+/7, moderno):

```java
@Repository
class PedidoQueryJdbcAdapter implements PedidoQueryPort {
    private final JdbcClient jdbc;

    @Override
    public List<PedidoResumoView> listarPorCliente(ClienteId clienteId, int limit) {
        return jdbc.sql("""
            SELECT p.id, p.cliente_id, p.status, COALESCE(SUM(i.subtotal), 0) AS total, p.criado_em
              FROM pedidos p
              LEFT JOIN pedido_itens i ON i.pedido_id = p.id
             WHERE p.cliente_id = :clienteId
             GROUP BY p.id
             ORDER BY p.criado_em DESC
             LIMIT :limit
            """)
            .param("clienteId", clienteId.value())
            .param("limit", limit)
            .query(PedidoResumoView.class)
            .list();
    }
}
```

`JdbcClient` é fluente, tipado, e substitui `JdbcTemplate` com bem menos cerimônia — use **sempre** para queries de leitura quando não quiser ORM.

## Outbox

### Tabela

`infrastructure/.../flyway/V2__outbox.sql`:

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

### Port + Adapter

```java
// application/.../port/OutboxPort.java
public interface OutboxPort {
    void enqueue(List<? extends DomainEvent> events);
}
```

```java
// infrastructure/.../outbox/OutboxJpaAdapter.java
@Component
class OutboxJpaAdapter implements OutboxPort {
    private final OutboxEventJpaRepository repo;
    private final ObjectMapper mapper;

    @Override
    public void enqueue(List<? extends DomainEvent> events) {
        if (events.isEmpty()) return;
        var correlationId = CorrelationScope.current();
        var entities = events.stream()
            .map(e -> OutboxEventEntity.novo(e, mapper, correlationId))
            .toList();
        repo.saveAll(entities);
    }
}
```

`CorrelationScope` usa `ScopedValue` (Java 25) — ver próxima seção.

### Relay (poller Spring)

```java
@Component
class OutboxPollerRelay {
    private static final int BATCH = 100;

    private final OutboxEventJpaRepository repo;
    private final DomainEventPublisher publisher;

    @Scheduled(fixedDelayString = "${outbox.poll.delay:500}")
    @Transactional
    public void poll() {
        var batch = repo.findUnprocessed(BATCH);
        for (var evt : batch) {
            try {
                publisher.publish(evt);
                evt.markProcessed(Instant.now());
            } catch (Exception e) {
                evt.markFailure(e.getMessage());
            }
        }
    }
}
```

Alternativa: **Debezium + Kafka Connect** para streaming com baixa latência. Decisão via ADR dependendo de volume/latência.

### Idempotência

**Todo consumer** deve ser idempotente. Padrões:

- Chave de idempotência = `outbox_events.id` (UUID)
- Consumer mantém tabela `processed_events (event_id PRIMARY KEY)`
- Antes de processar: `INSERT ... ON CONFLICT DO NOTHING` → se conflito, pula
- Processamento e insert do marker na mesma transação do consumer

## Correlation com ScopedValue (Java 25)

Substituto moderno de `ThreadLocal` que não "vaza" entre Virtual Threads:

```java
public final class CorrelationScope {
    public static final ScopedValue<String> CORRELATION_ID = ScopedValue.newInstance();

    public static String current() {
        return CORRELATION_ID.orElse("unknown");
    }
}
```

Filter Spring:

```java
@Component
class CorrelationFilter extends OncePerRequestFilter {
    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain)
            throws ServletException, IOException {
        var cid = Optional.ofNullable(req.getHeader("X-Correlation-Id"))
                          .orElseGet(() -> UUID.randomUUID().toString());
        res.setHeader("X-Correlation-Id", cid);
        try {
            ScopedValue.where(CorrelationScope.CORRELATION_ID, cid)
                .run(() -> {
                    try { chain.doFilter(req, res); }
                    catch (Exception e) { throw new RuntimeException(e); }
                });
        } catch (RuntimeException e) {
            // unwrap e relança
        }
    }
}
```

Benefícios vs ThreadLocal:
- **Imutável** dentro do escopo — não muta por engano
- **Sem cleanup manual** — sai do escopo, some
- **Virtual Thread-safe** sem overhead

## Regras do CQRS nesta squad

1. Commands retornam `void` / `ID` / ack mínimo — **nunca** o agregado.
2. Commands são records em `application/.../command/`.
3. Queries são records em `application/.../query/`; retornam DTOs de leitura.
4. Queries podem usar `JdbcClient` direto; não reidratar aggregate.
5. Todo command que emite evento passa pelo Outbox na mesma transação.
6. Consumers são idempotentes (chave = event id).
7. Nunca um Command chama outro Command — use evento.
8. Teste de outbox é obrigatório (Testcontainers + assert em tabela).
