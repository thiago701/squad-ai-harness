# Referência — NoSQL — Quando e Como (matriz de decisão, DynamoDB single-table, MongoDB, Redis, PGVector)

> Parte da skill `especialista-banco`. Carregue sob demanda. Hub: `../SKILL.md`.
## 6. NoSQL — Quando e Como

### 6.1 Matriz de Decisão (quando SAIR do relacional)

| Sinal | RDBMS | DynamoDB | MongoDB | Redis | Cassandra | OpenSearch |
|-------|:-----:|:--------:|:-------:|:-----:|:---------:|:----------:|
| Transações ACID cross-row | ✅ | ⚠️ (TxWrite ≤100 itens) | ⚠️ (multi-doc 7+) | ❌ | ❌ | ❌ |
| Escala horizontal > 50k rps sustentados | ⚠️ (Aurora, sharding manual) | ✅ | ⚠️ | ✅ | ✅ | ✅ |
| Consultas ad-hoc (joins, agregações) | ✅ | ❌ | ⚠️ (aggregation pipeline) | ❌ | ❌ | ⚠️ (agg) |
| Schema rígido com evolução controlada | ✅ | ⚠️ (attr flexível) | ✅ (validator) | ❌ | ⚠️ | — |
| Full-text search / facetas | ⚠️ (tsvector) | ❌ | ⚠️ (text index) | ❌ | ❌ | ✅ |
| Vector similarity (RAG) | ✅ (PGVector) | ⚠️ (Bedrock KB) | ✅ (Atlas) | ⚠️ (RediSearch) | ❌ | ✅ (k-NN) |
| TTL nativo / expiração | ⚠️ (partitioning) | ✅ | ✅ (TTL index) | ✅ | ✅ | ✅ |
| Acesso chave-valor hot path | ⚠️ (+ cache) | ✅ | ⚠️ | ✅ | ✅ | ❌ |
| Relacionamentos profundos (grafo) | ⚠️ (recursive CTE) | ❌ | ⚠️ | ❌ | ❌ | ❌ |
| Caso óbvio | OLTP típico, <10TB | Hot path serverless, padrão de acesso fixo | Documentos flexíveis, MVP | Cache, rate limit, sessão | Escala write-heavy, time-series | Search, logs, analytics |

**Default da squad**: **PostgreSQL 16** até prova em contrário. Adicionar NoSQL somente com justificativa escrita (ver [[arquiteto-minimalista]] — anti-overengineering).

### 6.2 DynamoDB — Single-Table Design

Princípios para modelar DynamoDB a partir de casos de uso (não de entidades):

1. **Listar access patterns antes de modelar** (quem lê, quem escreve, filtros, ordenação)
2. **Chaves compostas** (`PK`, `SK`) codificando hierarquia: `PK=USER#<id>`, `SK=ORDER#<timestamp>`
3. **Overload** de PK/SK para múltiplas entidades na mesma tabela
4. **GSIs esparsos** para consultas alternativas (não abusar — cada GSI é uma réplica)
5. **TTL attribute** para expiração automática
6. **Streams** habilitados para CDC / outbox / read model

**Exemplo de DBML-extension para DynamoDB** (documentar como Note):

```dbml
Table dynamodb_circuitos {
  pk      varchar [pk, note: 'USER#<uuid> | CIRCUITO#<uuid>']
  sk      varchar [pk, note: 'ORDER#<iso> | PROFILE | PARTICIPANT#<uuid>']
  gsi1pk  varchar [note: 'STATUS#<status>']
  gsi1sk  varchar [note: 'CREATED#<iso>']
  ttl     bigint  [note: 'Epoch seconds, TTL enabled']
  payload jsonb   [note: 'Entidade serializada']

  indexes {
    (pk, sk)         [pk]
    (gsi1pk, gsi1sk) [name: 'GSI1', note: 'Listagem por status ordenada por data']
  }

  Note: '''
    Single-table design. Access patterns:
    1. getCircuito(id)          → PK=CIRCUITO#<id>, SK=PROFILE
    2. listParticipantes(cid)   → PK=CIRCUITO#<id>, SK begins_with PARTICIPANT#
    3. listByStatus(status)     → GSI1, gsi1pk=STATUS#<s>, sort by gsi1sk desc
  '''
}
```

**Java com AWS SDK v2 Enhanced Client**:

```java
@DynamoDbBean
public class CircuitoItem {
    private String pk, sk, gsi1pk, gsi1sk;
    private Long ttl;
    private Map<String, AttributeValue> payload;

    @DynamoDbPartitionKey public String getPk() { return pk; }
    @DynamoDbSortKey       public String getSk() { return sk; }

    @DynamoDbSecondaryPartitionKey(indexNames = "GSI1") public String getGsi1pk() { return gsi1pk; }
    @DynamoDbSecondarySortKey(indexNames = "GSI1")      public String getGsi1sk() { return gsi1sk; }

    // ... setters
}

@Repository
public class CircuitoDynamoRepository {
    private final DynamoDbEnhancedAsyncClient client;
    private final DynamoDbAsyncTable<CircuitoItem> table;

    public CircuitoDynamoRepository(DynamoDbEnhancedAsyncClient client) {
        this.client = client;
        this.table = client.table("circuitos", TableSchema.fromBean(CircuitoItem.class));
    }

    public CompletableFuture<List<CircuitoItem>> listByStatus(String status) {
        var q = QueryConditional.keyEqualTo(Key.builder().partitionValue("STATUS#" + status).build());
        return table.index("GSI1").query(r -> r.queryConditional(q))
                    .subscribe(p -> {}).toCompletableFuture()
                    .thenApply(v -> /* coletar items */ List.of());
    }
}
```

#### DynamoDB Enhanced Client Async + Virtual Threads (AWS SDK v2.32+)

Padrão canônico para OLTP com DynamoDB em Java 25. `DynamoDbEnhancedAsyncClient` + `AsyncTable` + Virtual Threads dá paralelismo leve sem custo de thread OS. Combinar com `StructuredTaskScope` para fanout de queries.

```java
// 1. Bean config
@Configuration
class DynamoConfig {

    @Bean(destroyMethod = "close")
    DynamoDbAsyncClient dynamoAsyncClient() {
        return DynamoDbAsyncClient.builder()
            .httpClientBuilder(NettyNioAsyncHttpClient.builder()
                .maxConcurrency(200))
            .overrideConfiguration(o -> o
                .addMetricPublisher(CloudWatchMetricPublisher.create())
                .apiCallTimeout(Duration.ofSeconds(2))
                .apiCallAttemptTimeout(Duration.ofMillis(800)))
            .build();
    }

    @Bean
    DynamoDbEnhancedAsyncClient enhancedAsyncClient(DynamoDbAsyncClient c) {
        return DynamoDbEnhancedAsyncClient.builder().dynamoDbClient(c).build();
    }

    @Bean
    DynamoDbAsyncTable<PedidoItem> pedidoTable(DynamoDbEnhancedAsyncClient eac) {
        return eac.table("pedidos", TableSchema.fromImmutableClass(PedidoItem.class));
    }
}

// 2. Bean mapeado (single-table — PK + SK)
@DynamoDbImmutable(builder = PedidoItem.Builder.class)
public record PedidoItem(
    @DynamoDbPartitionKey String pk,       // "TENANT#<t>#CLIENTE#<c>"
    @DynamoDbSortKey     String sk,        // "PEDIDO#<ulid>"
    String status,
    BigDecimal valor,
    Instant criadoEm,
    @DynamoDbSecondaryPartitionKey(indexNames = "GSI1") String gsi1pk,
    @DynamoDbSecondarySortKey(indexNames = "GSI1")     String gsi1sk
) { /* builder omitido */ }

// 3. Repository com Virtual Threads
@Repository
class PedidoDynamoRepository {

    private final DynamoDbAsyncTable<PedidoItem> table;

    PedidoDynamoRepository(DynamoDbAsyncTable<PedidoItem> table) {
        this.table = table;
    }

    /** Busca por PK exata — usa .join() porque VT não faz pinning em I/O não-bloqueante. */
    public Optional<PedidoItem> findById(String tenantId, String clienteId, String pedidoId) {
        var key = Key.builder()
            .partitionValue("TENANT#" + tenantId + "#CLIENTE#" + clienteId)
            .sortValue("PEDIDO#" + pedidoId)
            .build();
        return Optional.ofNullable(table.getItem(key).join());
    }

    /** Query paginada com limit. */
    public List<PedidoItem> pedidosDoCliente(String tenantId, String clienteId, int limit) {
        var pk = "TENANT#" + tenantId + "#CLIENTE#" + clienteId;
        var cond = QueryConditional.sortBeginsWith(
            Key.builder().partitionValue(pk).sortValue("PEDIDO#").build());
        var result = new ArrayList<PedidoItem>(limit);
        table.query(r -> r.queryConditional(cond).limit(limit))
             .items()
             .subscribe(result::add)
             .join();
        return result;
    }

    /** Fanout multi-PK usando StructuredTaskScope + VTs — latência = max(queries) não sum(). */
    public Map<String, List<PedidoItem>> pedidosMultiCliente(
            String tenantId, List<String> clienteIds) throws InterruptedException {
        try (var scope = StructuredTaskScope.open(
                StructuredTaskScope.Joiner.<Map.Entry<String, List<PedidoItem>>>allSuccessfulOrThrow(),
                cfg -> cfg.withName("dynamo-fanout")
                          .withTimeout(Duration.ofSeconds(2)))) {

            List<Subtask<Map.Entry<String, List<PedidoItem>>>> forks = clienteIds.stream()
                .map(cid -> scope.fork(() -> Map.entry(cid, pedidosDoCliente(tenantId, cid, 50))))
                .toList();

            scope.join();
            return forks.stream()
                .map(Subtask::get)
                .collect(Collectors.toUnmodifiableMap(Map.Entry::getKey, Map.Entry::getValue));
        }
    }
}
```

**Regras**:
- **`maxConcurrency=200`** no Netty cliente combina bem com VTs — 200 conexões HTTP/2 suportam milhares de requests concorrentes.
- **`apiCallAttemptTimeout` sempre < `apiCallTimeout`** — evita retries sobrepostos.
- **Timeout no `StructuredTaskScope`** fecha todas as subtasks ao estourar — não deixa VTs órfãs.
- **`.join()` em VT é OK** — não faz pinning porque AsyncClient usa Netty (I/O não-bloqueante, eventloop).
- **Métricas**: `CloudWatchMetricPublisher` emite `ApiCallDuration`, `ApiCallAttemptCount`, `HttpClientGetConnection` — dashboard obrigatório.

**Quando usar síncrono (`DynamoDbEnhancedClient`):**
- Lambda com poucos requests — overhead do AsyncClient não compensa.
- Script/CLI/job de migração.
- Caso contrário, **async + VTs é o default**.

---

### 6.3 MongoDB — Schema Flexível Controlado

```json
// schema-validator (MongoDB 7+)
{
  "$jsonSchema": {
    "bsonType": "object",
    "required": ["_id", "nome", "status", "createdAt"],
    "properties": {
      "_id":       { "bsonType": "binData" },
      "nome":      { "bsonType": "string", "maxLength": 100 },
      "status":    { "enum": ["ATIVA","INATIVA","SUSPENSA","CANCELADA"] },
      "createdAt": { "bsonType": "date" }
    }
  }
}
```

**Spring Data MongoDB**:

```java
@Document("instituicoes")
@CompoundIndexes({
    @CompoundIndex(name = "idx_status_created", def = "{'status': 1, 'createdAt': -1}")
})
public record InstituicaoDoc(
    @Id UUID id,
    @Indexed(unique = true) String nome,
    String status,
    @CreatedDate Instant createdAt,
    @Version Long version
) {}
```

### 6.4 Redis — Data Modeling

| Caso de uso | Estrutura | TTL sugerido |
|-------------|-----------|--------------|
| Cache read-aside | String (JSON) | 5-60 min + jitter |
| Rate limiting | Hash + INCR + EXPIRE | 60s sliding |
| Leaderboard | Sorted Set (ZADD/ZRANGE) | — |
| Pub/Sub | Streams (XADD/XREAD) | trim MAXLEN |
| Sessão | Hash | TTL = duração login |
| Idempotência | String + NX | 24h |

**Chave**: `app:env:bounded-context:entity:id:aspect` (ex.: `circuito:prod:billing:invoice:123:status`).

### 6.5 PGVector — Vector Store para RAG

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE embeddings (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id     UUID NOT NULL,
    chunk_idx  INT  NOT NULL,
    content    TEXT NOT NULL,
    embedding  VECTOR(1536) NOT NULL,  -- Titan Embeddings v2 dimensions
    metadata   JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (doc_id, chunk_idx)
);

CREATE INDEX idx_embeddings_hnsw ON embeddings
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_embeddings_doc ON embeddings (doc_id);
```

Integração via [[arquiteto-ia]] + Spring AI 2 + PGVector Store.

---

