# Template canônico de handler Lambda + suite de testes

> **Leia antes** de escrever qualquer handler API Gateway HTTP API v2.
> Este padrão emergiu de auditorias reais de produção e mantém:
> - Cada handler.doHandle ≤ ~18 linhas
> - Lifecycle (received → timing → completed) em UM ponto
> - Pattern matching for switch (JEP 441) para mapear exceções → response
> - Separação explícita prod vs local
> - Toda classe nova nasce com teste (cobertura ≥ 90%, ideal 97%)

---

## 1. Forma do handler

Todo handler HTTP segue exatamente esta forma:

```java
public class GetXxxHandler
    implements RequestHandler<APIGatewayV2HTTPEvent, APIGatewayV2HTTPResponse> {

    private static final JsonLogger LOG = JsonLogger.of(GetXxxHandler.class);
    private static final String OPERATION = "GET /xxx";

    private final XxxService service;
    private final ObjectMapper mapper;
    private final Metrics metrics;

    public GetXxxHandler() { this(AppConfig.service(), AppConfig.mapper(), AppConfig.metrics()); }
    GetXxxHandler(XxxService s, ObjectMapper m, Metrics mt) { /* eager-friendly */ }

    @Override
    public APIGatewayV2HTTPResponse handleRequest(APIGatewayV2HTTPEvent event, Context ctx) {
        return JsonLogger.withContext(
            ctx != null ? ctx.getAwsRequestId() : null,
            HttpRequests.extractTraceId(event),
            () -> doHandle(event));
    }

    private APIGatewayV2HTTPResponse doHandle(APIGatewayV2HTTPEvent event) {
        return LOG.instrument(OPERATION, metrics, () -> {
            try {
                // ✅ business logic — 4 a 10 linhas, sem try/finally manual
                var input  = parseInput(event);
                var output = service.execute(input);
                LOG.info("business.execute.success", Map.of(...));
                return ApiResponses.ok(mapper, output);
            } catch (Exception e) {
                return mapError(e);
            }
        });
    }

    /** Pattern matching for switch — exaustivo, declarativo, sem perder o tipo concreto. */
    private APIGatewayV2HTTPResponse mapError(Exception e) {
        return switch (e) {
            case JsonProcessingException badJson -> {
                LOG.warn("validation.failed", Map.of(
                    "operation", OPERATION, "reason", "invalid_json",
                    "error", JsonLogger.truncate(String.valueOf(badJson.getOriginalMessage()), 200)));
                yield ApiResponses.badRequest(mapper, badJson.getOriginalMessage());
            }
            case IllegalArgumentException bad -> {
                LOG.warn("validation.failed", Map.of(
                    "operation", OPERATION, "reason", "invalid_input",
                    "error", JsonLogger.truncate(String.valueOf(bad.getMessage()), 200)));
                yield ApiResponses.badRequest(mapper, bad.getMessage());
            }
            case ConcurrentBucketModificationException conflict -> {
                LOG.warn("business.execute.conflict", Map.of("operation", OPERATION));
                metrics.count(OPERATION, "ConcurrentBucketConflict");
                yield ApiResponses.conflict(mapper, conflict.getMessage());
            }
            default -> {
                LOG.error("business.execute.error", Map.of("operation", OPERATION), e);
                yield ApiResponses.internalError(mapper, e.getMessage());
            }
        };
    }
}
```

**Por que essa forma:**

- O `instrument()` envelopa o ciclo de vida (received → timing → completed) num único ponto. O handler não carrega mais `int statusCode = 500; boolean ok = false;` nem `try/finally` para tempo — esse estado mutável é cheiro.
- `mapError(Exception)` com pattern matching é pura, testável isoladamente, exaustiva por design. Adicionar uma exceção nova é uma linha no switch.
- `HttpRequests.extractTraceId(event)` evita duplicação entre handlers (DRY — qualquer código repetido entre 2+ handlers vira helper estático no pacote api).

## 2. `JsonLogger.instrument()` — o helper de lifecycle

Coloque este método no `JsonLogger` da app:

```java
/**
 * Envelopa o ciclo de vida de um handler HTTP: emite received, mede latência,
 * emite completed e despacha timing — tudo derivado do status code da resposta
 * (2xx = success).
 */
public <R extends APIGatewayV2HTTPResponse> R instrument(
        String operation, Metrics metrics, ThrowingSupplier<R> body) {
    received(operation);
    var t0 = System.nanoTime();
    try {
        R response = body.get();
        var ms = (System.nanoTime() - t0) / 1_000_000.0;
        var status = response.getStatusCode();
        var ok = status >= 200 && status < 300;
        metrics.timing(operation, ms, ok);
        completed(operation, status, ms, ok);
        return response;
    } catch (RuntimeException re) {
        emitFailure(operation, metrics, t0);
        throw re;
    } catch (Exception ex) {
        emitFailure(operation, metrics, t0);
        throw new RuntimeException(ex);
    }
}

@FunctionalInterface
public interface ThrowingSupplier<R> {
    R get() throws Exception;
}
```

**Por que `ThrowingSupplier` em vez de `Supplier`:** o body do handler chama `ApiResponses.ok(mapper, ...)` que lança `JsonProcessingException` (checked). Sem isso, cada handler precisaria envelopar a chamada num try-catch só para satisfazer o compilador.

## 3. `HttpRequests` — DRY entre handlers

```java
final class HttpRequests {
    private HttpRequests() {}

    /** X-Ray trace id via header x-amzn-trace-id (case-insensitive). */
    static String extractTraceId(APIGatewayV2HTTPEvent event) {
        var headers = event != null ? event.getHeaders() : null;
        if (headers == null) return null;
        var lower = HashMap.<String, String>newHashMap(headers.size());
        for (var e : headers.entrySet()) lower.put(e.getKey().toLowerCase(Locale.ROOT), e.getValue());
        return lower.get("x-amzn-trace-id");
    }
}
```

**Regra:** qualquer extração de atributo do `APIGatewayV2HTTPEvent` que apareça em 2+ handlers vai pra cá.

## 4. `LocalDdbBootstrap` — separar prod vs local

Código LOCAL-ONLY (auto-create de tabela, seeds, etc) NUNCA vive no repository de produção. Em produção a role IAM da Lambda não tem `dynamodb:DescribeTable`/`CreateTable` e o código falha com AccessDenied.

**Padrão:** se você se viu escrevendo um comentário "uso APENAS local" num método do repository, esse método não pertence ao repository — extraia para uma classe nomeada como tal. O nome substitui o comentário.

```java
public final class LocalDdbBootstrap {
    private LocalDdbBootstrap() {}

    /** Idempotente. Cria a tabela se não existir. NUNCA chamado em prd. */
    public static void ensureTableExists(DynamoDbClient client, String tableName) {
        try {
            client.describeTable(b -> b.tableName(tableName));
        } catch (ResourceNotFoundException e) {
            client.createTable(/* ... PK simples, PAY_PER_REQUEST ... */);
            client.waiter().waitUntilTableExists(b -> b.tableName(tableName));
        }
    }
}
```

Chame no `AppConfig.primeAll()` apenas quando `DDB_AUTO_CREATE_TABLE=true` (env local).

## 5. Suite de testes nasce JUNTO

**Regra inegociável:** toda classe nova abre PR com seu teste. Sem exceção.

### Estrutura padrão

```java
@ExtendWith(MockitoExtension.class)
@DisplayName("GET /xxx — validação + consulta")
class GetXxxHandlerTest {

    @Mock XxxService service;
    @Mock Context context;
    @Mock Metrics metrics;
    private GetXxxHandler handler;
    private ObjectMapper mapper;

    @BeforeEach
    void setUp() {
        mapper  = new ObjectMapper();
        handler = new GetXxxHandler(service, mapper, metrics);
    }

    @Nested @DisplayName("Validação → 400")
    class Validacao { /* params obrigatórios, valores fora de domínio, etc */ }

    @Nested @DisplayName("Happy path → 200")
    class HappyPath { /* sucesso, propagação de trace id, defaults */ }

    @Nested @DisplayName("mapError → 4xx/5xx")
    class MapError {
        @Test @DisplayName("ConcurrentBucketModificationException → 409 + métrica")
        void conflito_409_metrica() {
            when(service.execute(...)).thenThrow(new ConcurrentBucketModificationException("pk", 7L));
            var resp = handler.handleRequest(event, null);
            assertThat(resp.getStatusCode()).isEqualTo(409);
            verify(metrics).count(OPERATION, "ConcurrentBucketConflict");
        }
    }

    // Fixtures privadas estáticas no fim do arquivo
    private static APIGatewayV2HTTPEvent params(Map<String,String> p) { /* ... */ }
}
```

### Padrões consolidados

- `@DisplayName` em português descrevendo a regra de negócio (não a implementação).
- `@Nested` agrupa por cenário: `Validacao`, `HappyPath`, `MapError`.
- `@ParameterizedTest` + `@CsvSource` consolida variações (ex: `ativo` case-insensitive: 6 testes → 1 parametrizado).
- `@NullAndEmptySource` + `@ValueSource` cobre null, vazio e valores inválidos numa única assinatura.
- AAA explícito: stubs no topo, ação no meio, asserts no fim.
- Fixtures privadas estáticas no fim do arquivo (`params(...)`, `eventFor(cenario)`, `base()`).
- Asserts em **comportamento**, não em texto rígido de erro — `.contains("invalido")` é frágil; `.getStatusCode()).isEqualTo(400)` é estável.

### Cobertura

- Gate JaCoCo ≥ 97% em `domain/` e `api/`, ≥ 90% no projeto todo. Configure `mvn verify` para falhar abaixo disso (NÃO advisory).
- Toda branch de `mapError` precisa de teste. Toda regra de validação linear (`if (x == null) throw ...`) precisa de teste por regra.
- Testes de IT (LocalStack + Testcontainers) cobrem ao menos 1 caminho feliz por handler.

## 6. Checklist específico do handler

Quando gerar (ou revisar) um handler, garanta:

- [ ] `doHandle` ≤ 18 linhas.
- [ ] Usa `LOG.instrument(OPERATION, metrics, () -> { ... })` — não tem `try/finally` manual para tempo.
- [ ] Exceções tratadas via `mapError(Exception)` com pattern matching for switch.
- [ ] `HttpRequests.extractTraceId(event)` em vez de método privado duplicado.
- [ ] Construtor public no-args delega para `AppConfig.service()/mapper()/metrics()`.
- [ ] Construtor package-private adicional aceita dependências (para teste).
- [ ] Teste no mesmo PR com `@Nested` cobrindo Validação / HappyPath / MapError.
- [ ] Cobertura do handler ≥ 95% (todos os branches do mapError + ao menos 1 happy path).
- [ ] Se introduziu código LOCAL-ONLY, está em `LocalDdbBootstrap` (ou análogo), não no repository.

## 7. Anti-padrões específicos de handler

- ❌ `try/finally` no `doHandle` para medir tempo — use `instrument()`.
- ❌ `int statusCode = 500; boolean ok = false;` mutáveis — `instrument` deriva do response final.
- ❌ Cadeia `catch (X) { ... } catch (Y) { ... } catch (Exception) { ... }` — extraia `mapError`.
- ❌ Método `extractTraceId` privado duplicado em cada handler — vire `HttpRequests`.
- ❌ `ensureTableExists()` no repository de produção — vire `LocalDdbBootstrap`.
- ❌ Handler sem teste — bloqueia o PR.
