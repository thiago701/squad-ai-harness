# Cookbook DBML → Java 25 + Spring Boot 4

Receitas práticas para traduzir construções DBML em código Java idiomático. Todos os exemplos compilam em Java 25 + Spring Boot 4 + Hibernate 7.1 + PostgreSQL 16.

---

## 1. Tabela simples com audit columns

```dbml
Table produtos {
  id         uuid         [pk, default: `gen_random_uuid()`]
  nome       varchar(100) [not null]
  preco      numeric(10,2)[not null]
  created_at timestamptz  [not null, default: `now()`]
  updated_at timestamptz  [not null, default: `now()`]
  version    bigint       [not null, default: 0]
}
```

### JPA Entity (com `AuditEntity` base via `@MappedSuperclass`)

```java
@MappedSuperclass
public abstract class AuditEntity {
    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    protected OffsetDateTime createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at", nullable = false)
    protected OffsetDateTime updatedAt;

    @Version
    @Column(name = "version", nullable = false)
    protected Long version;
}

@Entity @Table(name = "produtos")
public class ProdutoJpaEntity extends AuditEntity {
    @Id @Column(nullable = false, updatable = false) private UUID id;
    @Column(nullable = false, length = 100) private String nome;
    @Column(nullable = false, precision = 10, scale = 2) private BigDecimal preco;
}
```

---

## 2. Relacionamento 1:N com cascade correto

```dbml
Table circuitos {
  id   uuid [pk]
  nome varchar(100) [not null]
}

Table palestras {
  id          uuid [pk]
  circuito_id uuid [not null, ref: > circuitos.id]
  titulo      varchar(200) [not null]
}

Ref fk_palestras_circuito: palestras.circuito_id > circuitos.id [delete: cascade, update: cascade]
```

### Em JPA — **lado "N" (palestras)** é dono da FK

```java
@Entity @Table(name = "palestras")
public class PalestraJpaEntity {
    @Id private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "circuito_id", nullable = false,
                foreignKey = @ForeignKey(name = "fk_palestras_circuito"))
    private CircuitoJpaEntity circuito;

    @Column(nullable = false, length = 200) private String titulo;
}
```

No agregado raiz `CircuitoJpaEntity` **evite** `@OneToMany` default — prefira consulta explícita no repositório (`findAllByCircuitoId`) para não carregar coleção inteira.

---

## 3. Relacionamento N:M com tabela de junção explícita

```dbml
Table palestrantes { id uuid [pk] }
Table palestras    { id uuid [pk] }

Table palestra_palestrantes {
  palestra_id     uuid [not null, ref: > palestras.id]
  palestrante_id  uuid [not null, ref: > palestrantes.id]
  papel           varchar(30) [not null, note: 'PRINCIPAL | CONVIDADO | MODERADOR']

  indexes {
    (palestra_id, palestrante_id) [pk]
    (palestrante_id)              [name: 'idx_pp_palestrante']
  }
}
```

### JPA — materializar a tabela de junção quando houver atributos extras (`papel`)

```java
@Entity @Table(name = "palestra_palestrantes")
public class PalestraPalestranteJpaEntity {

    @EmbeddedId private PalestraPalestranteId id;

    @MapsId("palestraId")
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "palestra_id")
    private PalestraJpaEntity palestra;

    @MapsId("palestranteId")
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "palestrante_id")
    private PalestranteJpaEntity palestrante;

    @Column(nullable = false, length = 30)
    private String papel;
}

@Embeddable
public record PalestraPalestranteId(UUID palestraId, UUID palestranteId) implements Serializable {}
```

Se não houver atributos extras, usar `@ManyToMany` com `@JoinTable` é aceitável — porém o time padrão prefere **sempre** uma tabela de junção explícita para facilitar evolução.

---

## 4. Enum persistido como VARCHAR + CHECK

```dbml
Table pedidos {
  id     uuid [pk]
  status varchar(20) [not null, default: 'CRIADO', note: 'Enum: CRIADO|PAGO|CANCELADO']
}

Enum status_pedido { CRIADO PAGO CANCELADO }
```

### Migration

```sql
ALTER TABLE pedidos
  ADD CONSTRAINT chk_pedidos_status
  CHECK (status IN ('CRIADO','PAGO','CANCELADO'));
```

### JPA + Domain

```java
public enum StatusPedido { CRIADO, PAGO, CANCELADO }

@Entity @Table(name = "pedidos")
public class PedidoJpaEntity {
    @Enumerated(EnumType.STRING)                 // nunca ORDINAL
    @Column(nullable = false, length = 20)
    private StatusPedido status;
}
```

Pattern matching moderno no domínio:

```java
public sealed interface EventoPedido
    permits EventoPedido.Criado, EventoPedido.Pago, EventoPedido.Cancelado {

    record Criado(UUID id, Instant em) implements EventoPedido {}
    record Pago(UUID id, BigDecimal valor, Instant em) implements EventoPedido {}
    record Cancelado(UUID id, String motivo, Instant em) implements EventoPedido {}
}

String descricao = switch (evento) {
    case EventoPedido.Criado c     -> "criado em " + c.em();
    case EventoPedido.Pago p       -> "pago R$ " + p.valor();
    case EventoPedido.Cancelado x  -> "cancelado: " + x.motivo();
};
```

---

## 5. JSONB — Payload flexível com tipagem

```dbml
Table eventos {
  id      uuid [pk]
  tipo    varchar(50) [not null]
  payload jsonb [not null]
}
```

### Hibernate 7.1 com suporte nativo a JSON

```java
@Entity @Table(name = "eventos")
public class EventoJpaEntity {
    @Id private UUID id;
    @Column(nullable = false, length = 50) private String tipo;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(nullable = false, columnDefinition = "jsonb")
    private Map<String, Object> payload;
}
```

Para tipagem forte, desserializar com Jackson no mapper para um `sealed` record.

---

## 6. Soft delete + índice parcial

```dbml
Table usuarios {
  id         uuid [pk]
  email      varchar(320) [not null]
  deleted_at timestamptz  [null]

  indexes {
    (email) [unique, name: 'uk_usuarios_email_ativo', note: 'UNIQUE só onde deleted_at IS NULL']
  }
}
```

### Migration (PostgreSQL índice parcial)

```sql
CREATE UNIQUE INDEX uk_usuarios_email_ativo
  ON usuarios (email)
  WHERE deleted_at IS NULL;
```

### JPA com `@SQLRestriction`

```java
@Entity @Table(name = "usuarios")
@SQLRestriction("deleted_at IS NULL")
public class UsuarioJpaEntity {
    @Id private UUID id;
    @Column(nullable = false, length = 320) private String email;
    @Column(name = "deleted_at") private OffsetDateTime deletedAt;
}
```

---

## 7. Consulta paginada com projeção tipada (Record)

```java
public record ProdutoResumo(UUID id, String nome, BigDecimal preco) {}

public interface ProdutoRepo extends JpaRepository<ProdutoJpaEntity, UUID> {
    @Query("""
        SELECT new com.app.ProdutoResumo(p.id, p.nome, p.preco)
        FROM ProdutoJpaEntity p
        WHERE p.preco >= :min
        ORDER BY p.preco DESC
        """)
    Page<ProdutoResumo> resumoPorPreco(BigDecimal min, Pageable pageable);
}
```

---

## 8. Outbox Pattern — commit atômico entidade + evento

```java
@Service
@Transactional
public class PedidoService {

    private final PedidoRepo pedidos;
    private final OutboxRepo outbox;
    private final ObjectMapper json;

    public void criar(NovoPedidoCmd cmd) {
        var p = Pedido.novo(cmd);
        pedidos.save(toJpa(p));

        var evt = new OutboxEventoJpaEntity();
        evt.setId(UUID.randomUUID());
        evt.setAggregateId(p.id());
        evt.setAggregateType("pedido");
        evt.setEventType("PedidoCriado");
        evt.setPayload(json.writeValueAsString(new EventoPedido.Criado(p.id(), Instant.now())));
        outbox.save(evt);
        // Mesma transação — garantia atomicidade (sem dual-write)
    }
}
```

Um job separado consome `outbox_events WHERE processed_at IS NULL` e publica em SNS/Kafka, depois marca `processed_at`.

---

## 9. Virtual Threads + HikariCP

`application.yml`:

```yaml
spring:
  threads:
    virtual:
      enabled: true
  datasource:
    hikari:
      maximum-pool-size: 20        # ~2× nº de CPUs — pequeno, VTs não causam pinning no Postgres
      minimum-idle: 5
      connection-timeout: 3000
      validation-timeout: 2000
  jpa:
    hibernate:
      ddl-auto: validate           # NUNCA update em prod
    open-in-view: false            # evitar LazyInitialization fora de @Transactional
```

---

## 10. Teste de coerência DBML ↔ JPA ↔ Postgres

```java
@SpringBootTest
@Testcontainers
class SchemaCoerenciaTest {

    @Container
    static PostgreSQLContainer<?> db = new PostgreSQLContainer<>("postgres:16-alpine").withReuse(true);

    @Autowired DataSource ds;

    @Test
    void todasAsTabelasTemAuditColumns() throws Exception {
        var obrigatorias = Set.of("created_at","updated_at","version");
        try (var conn = ds.getConnection()) {
            var tabelas = new ArrayList<String>();
            try (var rs = conn.getMetaData().getTables(null, "public", "%", new String[]{"TABLE"})) {
                while (rs.next()) {
                    var t = rs.getString("TABLE_NAME");
                    if (t.startsWith("flyway_")) continue;
                    tabelas.add(t);
                }
            }
            for (var t : tabelas) {
                var cols = new HashSet<String>();
                try (var rs = conn.getMetaData().getColumns(null, "public", t, null)) {
                    while (rs.next()) cols.add(rs.getString("COLUMN_NAME"));
                }
                assertThat(cols).as("Tabela %s precisa de audit columns", t).containsAll(obrigatorias);
            }
        }
    }
}
```

---

## 11. Consultas paralelas com `StructuredTaskScope` (Java 25 GA)

Quando um endpoint precisa compor dados de múltiplas tabelas/APIs que **não têm dependência entre si**, use `StructuredTaskScope.open(Joiner.allSuccessfulOrThrow())` para disparar as queries em paralelo com propagação automática de cancelamento e Scoped Values (correlation-id, tenant-id).

```java
public sealed interface DashboardData {}
public record Dashboard(UserSummary user, List<Pedido> pedidos, Saldo saldo) implements DashboardData {}

@Transactional(readOnly = true)
public Dashboard carregar(UUID userId) throws InterruptedException {
    try (var scope = StructuredTaskScope.open(
            StructuredTaskScope.Joiner.<Object>allSuccessfulOrThrow(),
            cfg -> cfg.withName("dashboard-" + userId).withTimeout(Duration.ofSeconds(2)))) {

        Subtask<UserSummary> user    = scope.fork(() -> userRepo.findSummaryById(userId));
        Subtask<List<Pedido>> pedidos = scope.fork(() -> pedidoRepo.top10Recentes(userId));
        Subtask<Saldo> saldo         = scope.fork(() -> saldoRepo.getAtual(userId));

        scope.join();
        return new Dashboard(user.get(), pedidos.get(), saldo.get());
    }
}
```

**Regras**:
- HikariCP precisa ter `maximum-pool-size` ≥ nº de forks simultâneos × paralelismo esperado — dimensionar com `hikaricp_connections_pending` em produção.
- Nunca usar `StructuredTaskScope` **dentro** de um `@Transactional` com lock pessimista — cada fork abriria sua própria conexão, levando a deadlocks.
- Timeout por `cfg.withTimeout(...)` fecha todas as subtasks; combine com Circuit Breaker externo (Resilience4j) para falha rápida.

Ver também: [[Virtual Threads vs HikariCP]], [[Structured Concurrency]].

---

**Última atualização**: 2026-04-13
