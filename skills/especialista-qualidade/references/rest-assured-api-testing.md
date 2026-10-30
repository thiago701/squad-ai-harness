# RestAssured — Testes de API REST Black-Box em Nível Profissional (Java 25)

> **Quando ler:** ao escrever testes que exercem uma API HTTP **pela borda** (cliente externo real),
> em Java/Kotlin, com o DSL `given/when/then`. É a ferramenta canônica da Camada 3 (funcional) para
> APIs REST no stack JVM — complementar ao `RestTestClient`/`MockMvcTester` do Spring.

> **Princípio:** o teste conhece apenas o **contrato HTTP observável** (status, headers, corpo, SLA).
> Não importa `@Autowired`, não toca no banco pela lateral, não conhece a classe do controller.
> Se o contrato quebra, o teste falha; se a implementação interna muda mas o contrato se mantém, o
> teste sobrevive.

---

## 0. Onde RestAssured entra (e onde NÃO entra)

A squad já tem dois clientes de teste HTTP do próprio Spring. RestAssured **não os substitui** — ocupa
um nicho distinto. Escolha pela **fronteira do teste**, não por gosto:

| Ferramenta | Fronteira | Sobe servidor? | Use quando |
|---|---|---|---|
| `MockMvcTester` (Spring 6.2+) | Controller isolado, sem rede | Não (mock) | Slice `@WebMvcTest`: validação, serialização, tratamento de erro do controller — milissegundos |
| `RestTestClient` (Spring Boot 4) | App em processo, porta real | `RANDOM_PORT` | Integração in-process type-safe do próprio Spring; time já usa Spring end-to-end |
| **RestAssured (core)** | **Serviço em pé, HTTP de verdade** | Não (aponta p/ URL) | **E2E de API / smoke em ambiente real / teste de serviço já deployado / API poliglota (não-Spring)** |
| **RestAssuredMockMvc** (módulo `spring-mock-mvc`) | Controller isolado, DSL RestAssured | Não (mock) | Quer o DSL `given/when/then` no slice `@WebMvcTest` sem subir Tomcat |

Regra prática: **teste de contrato de um serviço rodando (local/staging/prod-like) ⇒ RestAssured core.**
**Teste de slice de controller ⇒ `MockMvcTester` nativo, ou `RestAssuredMockMvc` se preferir o DSL.**
Nunca escreva o mesmo caso nas duas ferramentas — é manutenção duplicada (anti-padrão "dois cérebros").

RestAssured **não** faz contract testing consumer-driven — isso é `Pact`/`Spring Cloud Contract`
(ver `functional-tests.md §3C`). RestAssured valida o contrato **de um lado só** (o provider, black-box).

---

## 1. Versões e dependências (2025-2026)

**Alvo da squad (Java 25 + Spring Boot 4 / Spring 7 / Jackson 3): RestAssured 6.0.0.**

- **6.0.0** (dez/2025): baseline **Java 17+**, Groovy 5, suporte a **Spring 7 + Jackson 3**. É a linha
  alinhada ao nosso stack — use-a em qualquer projeto novo.
- **5.5.7** (jan/2026): *backport* do suporte a Spring 7 MockMvc para quem ainda está preso na linha 5.x.
- **5.5.x**: linha legada Java 8–16 / Jackson 2. Só para módulos que ainda não migraram.

```xml
<!-- Java 25 / Spring Boot 4 / Jackson 3 -->
<properties>
  <rest-assured.version>6.0.0</rest-assured.version>
</properties>

<dependency>
  <groupId>io.rest-assured</groupId>
  <artifactId>rest-assured</artifactId>
  <version>${rest-assured.version}</version>
  <scope>test</scope>
</dependency>
<dependency>
  <groupId>io.rest-assured</groupId>
  <artifactId>json-schema-validator</artifactId>   <!-- validação de contrato por schema -->
  <version>${rest-assured.version}</version>
  <scope>test</scope>
</dependency>
<!-- Opcionais por cenário: -->
<!-- io.rest-assured:spring-mock-mvc        -> RestAssuredMockMvc (slice de controller MVC) -->
<!-- io.rest-assured:spring-web-test-client -> RestAssuredWebTestClient (WebFlux reativo)   -->
```

> ⚠️ **Nota de import.** Sempre `io.restassured.*` (a linha 4.x usava `com.jayway.restassured.*`, morta).
> Static import canônico: `import static io.restassured.RestAssured.*;` e
> `import static org.hamcrest.Matchers.*;`.

---

## 2. Anatomia given / when / then

```java
import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;

@Test
void confirma_pedido_pendente_retorna_200() {
    given()
        .baseUri("https://api.exemplo.com")
        .basePath("/v1")
        .contentType(ContentType.JSON)
        .auth().oauth2(token)                 // Authorization: Bearer <token>
    .when()
        .post("/pedidos/{id}/confirmar", 42)  // path param posicional (nunca concatene string)
    .then()
        .statusCode(200)
        .contentType(ContentType.JSON)
        .body("status", equalTo("CONFIRMADO"))
        .body("itens", hasSize(greaterThan(0)))
        .time(lessThan(2000L), MILLISECONDS); // SLA como asserção
}
```

O `body("...")` usa **GPath** (não JSONPath puro): `body("itens.sku", hasItems("SKU-1"))`,
`body("erros.findAll { it.campo == 'email' }", not(empty()))`. Para raiz repetida use `root("pedido.")`.

---

## 3. Especificações reutilizáveis — a espinha dorsal do framework (DRY)

Duplicar base URI, headers e auth em cada teste é o principal gerador de dívida. Centralize em
`RequestSpecBuilder` / `ResponseSpecBuilder`. Trocar de ambiente vira **uma linha**.

```java
public final class ApiSpecs {
    private ApiSpecs() {}

    // Requisição base — ambiente vem de env var/secret, NUNCA hardcoded
    public static RequestSpecification base() {
        return new RequestSpecBuilder()
            .setBaseUri(System.getenv().getOrDefault("API_BASE_URI", "http://localhost:8080"))
            .setBasePath("/v1")
            .setContentType(ContentType.JSON)
            .setAccept(ContentType.JSON)
            .addFilter(new RequestLoggingFilter(LogDetail.URI))
            .build();
    }

    public static RequestSpecification autenticada(String token) {
        return new RequestSpecBuilder()
            .addRequestSpecification(base())
            .setAuth(RestAssured.oauth2(token))
            .build();
    }

    // Contrato transversal de RESPOSTA: sempre JSON e sempre dentro do SLA — inclusive nos 4xx
    public static ResponseSpecification jsonComSla(long slaMs) {
        return new ResponseSpecBuilder()
            .expectContentType(ContentType.JSON)
            .expectResponseTime(lessThan(slaMs), MILLISECONDS)
            .build();
    }
}
```

```java
@Test
void usa_specs() {
    given().spec(ApiSpecs.autenticada(token))
    .when().get("/pedidos/{id}", 42)
    .then().spec(ApiSpecs.jsonComSla(1500)).statusCode(200);
}
```

> **Config global** (uma vez, em `@BeforeAll` ou base class): `RestAssured.requestSpecification`,
> `RestAssured.responseSpecification`, `RestAssured.config` (encoding, objectMapper, SSL). Evite estado
> global mutável entre testes que rodam em paralelo (ver §11).

---

## 4. Validação de contrato por JSON Schema

Asserção campo-a-campo verifica *valores*; **JSON Schema verifica a forma do contrato** (tipos,
obrigatoriedade, enums, `additionalProperties`). É a barreira mais barata contra "a API mudou o shape".

```java
import static io.restassured.module.jsv.JsonSchemaValidator.matchesJsonSchemaInClasspath;

given().spec(spec)
.when().post("/pedidos/{id}/confirmar", 1)
.then().statusCode(200)
    .body(matchesJsonSchemaInClasspath("schemas/confirmar-pedido-response.schema.json"));
```

> ⚠️ **Draft do schema.** O módulo `json-schema-validator` usa a lib `fge/java-json-tools`, que suporta
> **draft-04** (e -03). Em draft-04, `exclusiveMinimum` é **booleano** pareado com `minimum`
> (`"minimum": 0, "exclusiveMinimum": true`) — **não** o número do draft-07. Escrever o schema em
> draft-07 gera `InvalidSchemaException: invalid JSON Schema`. (Erro real reproduzido e corrigido no
> exemplo executável.) Se precisar de draft-07+, configure um validador customizado
> (`JsonSchemaValidator.settings()` com outra `JsonSchemaFactory`).

Gere o schema a partir do OpenAPI do serviço quando existir — assim contrato de documentação e contrato
de teste não divergem.

---

## 5. Serialização — POJO/record tipado, não navegação por string

Desserializar para um tipo dá segurança de compilação e asserções legíveis. RestAssured usa Jackson
automaticamente se estiver no classpath.

```java
public record ConfirmarPedidoResponse(long pedidoId, String status,
                                       OffsetDateTime confirmadoEm, BigDecimal valorTotal) {}

ConfirmarPedidoResponse r =
    given().spec(spec)
    .when().post("/pedidos/{id}/confirmar", 1)
    .then().statusCode(200)
    .extract().as(ConfirmarPedidoResponse.class);

assertThat(r.status()).isEqualTo("CONFIRMADO");
assertThat(r.valorTotal()).isEqualByComparingTo("150.00");  // BigDecimal exato, sem float
```

Serialização na ida também: `.body(new CriarPedidoRequest("c1", List.of(new Item("SKU-1", 2))))` —
RestAssured serializa o objeto conforme o `contentType`. Em Java 25 use `record` como request/response
DTO (zero boilerplate). Configure o `ObjectMapper` uma vez via `ObjectMapperConfig` (ex.: registrar
`JavaTimeModule`, ignorar propriedades desconhecidas).

---

## 6. Autenticação

```java
given().auth().oauth2(jwt)                 // Bearer <jwt> (preemptivo)
given().auth().preemptive().basic(u, p)    // Basic, sem esperar 401-challenge
given().header("Authorization", "Bearer " + jwt)  // controle manual
given().auth().none()                      // sobrescreve auth herdada da spec (cenário 401)
```

- **Token vem de variável de ambiente/secret**, jamais commitado. Em suíte real, obtenha o JWT uma vez
  por sessão (client-credentials/login) num `@BeforeAll` e injete na spec autenticada.
- **Sempre cubra o negativo:** sem token ⇒ 401; token de outro usuário ⇒ 403 (autorização/BOLA). São
  os eixos AUTH e AUTHORIZATION do protocolo dos 8 eixos.

---

## 7. Data-driven (JUnit 5)

Um método, muitos casos. Adicionar cenário = adicionar uma linha.

```java
static Stream<Arguments> payloadsInvalidos() {
    return Stream.of(
        Arguments.of("corpo vazio", "{}"),
        Arguments.of("sem itens", "{\"clienteId\":\"c1\"}"),
        Arguments.of("sem clienteId", "{\"itens\":[{\"sku\":\"S1\"}]}"));
}

@ParameterizedTest(name = "[{index}] {0} -> 400")
@MethodSource("payloadsInvalidos")
void payload_invalido_retorna_400(String desc, String body) {
    given().spec(base).body(body)
    .when().post("/pedidos")
    .then().statusCode(400).body("errors", not(empty()));
}
```

Prefira `@MethodSource` a `@CsvSource` quando o dado é JSON (evita inferno de escape de vírgula/aspas).
Para massa externa, `@CsvFileSource`/JSON em `src/test/resources`.

---

## 8. Filtros — logging, relatório e cross-cutting

Filtros interceptam request/response. Três usos profissionais:

```java
// 1) Log só quando a asserção falha — não polua o verde
RestAssured.enableLoggingOfRequestAndResponseIfValidationFails();

// 2) Allure: cada request vira passo no relatório visual
given().filter(new AllureRestAssured()) ... ;   // io.qameta.allure:allure-rest-assured

// 3) Filtro próprio (ex.: injetar X-Correlation-Id, capturar métricas)
RestAssured.filters(new CorrelationIdFilter());
```

**Anti-padrão:** `.log().all()` fixo em todo teste. Gera megabytes de ruído e esconde o sinal.
Logue no verde apenas o URI (ou nada); o corpo completo **só em falha**.

---

## 9. Integração com Spring — `RestAssuredMockMvc`

Quando você quer o DSL do RestAssured mas **sem subir servidor** (slice rápido de controller):

```java
@WebMvcTest(PedidoController.class)
class PedidoControllerTest {
    @Autowired MockMvc mockMvc;

    @BeforeEach void setup() { RestAssuredMockMvc.mockMvc(mockMvc); }

    @Test
    void cria_pedido_retorna_201() {
        RestAssuredMockMvc.given()
            .contentType(ContentType.JSON).body(criarPedidoJson)
        .when().post("/pedidos")
        .then().status(HttpStatus.CREATED).header("Location", notNullValue());
    }
}
```

- **Standalone** (`RestAssuredMockMvc.standaloneSetup(new PedidoController(...))`) = super rápido, só o
  controller. **WebAppContext** = mais fiel (filtros, security), mais lento. Escolha pela necessidade.
- **Spring Security Test:** integra `SecurityMockMvcRequestPostProcessors` — teste papéis/authorities
  com controle total do usuário: `.postProcessors(user("ana").roles("ADMIN"))`.
- WebFlux/reativo: módulo `spring-web-test-client` (`RestAssuredWebTestClient`), mesma pegada de DSL.

---

## 10. Os 8 eixos aplicados a uma API REST

Todo endpoint merece cobertura nos eixos (ver hub §2). Mapa canônico para `POST /pedidos/{id}/confirmar`:

| Eixo | Cenário de API | Asserção |
|---|---|---|
| HAPPY PATH | pedido pendente + token válido | 200, corpo conforme schema, dentro do SLA |
| INPUT VALIDATION | body malformado / campos faltando | 400 + `errors[]` |
| AUTH | sem token | 401 |
| AUTHORIZATION | token de outro usuário (BOLA) | 403 |
| NOT FOUND | id inexistente | 404 + mensagem |
| STATE CONFLICT | pedido já confirmado | 409 |
| IDEMPOTENCE | confirmar 2x | mesmo estado final (200/409 consistente) |
| EXTERNAL FAILURE | dependência fora (gateway) | 502/503 ou fallback (combine com WireMock) |

---

## 11. Robustez, paralelismo e configuração

- **Thread-safety:** RestAssured usa estado estático (`baseURI`, `filters`). Em execução paralela,
  prefira **specs locais por teste** (`given().spec(...)`) em vez de mutar os estáticos globais. Filtros
  com estado devem ser `ThreadLocal` ou stateless.
- **Timeouts/retry:** configure timeout de conexão/leitura no `RestAssuredConfig`
  (`HttpClientConfig` → `CONNECTION_MANAGER_TIMEOUT`, `SO_TIMEOUT`). **Nunca** faça retry cego que
  mascara flakiness da API; retry só em erro de infra transitório, com backoff explícito.
- **SSL/urlEncoding/logs de falha:** `RestAssured.config = config().sslConfig(...).logConfig(logConfig()
  .enableLoggingOfRequestAndResponseIfValidationFails())`.
- **CI (GitHub Actions):** roda como qualquer teste JVM. Publique o relatório Allure como artefato do job
  e trave o merge no gate de testes verdes (ver `coverage-90-strategy.md §quality gates`).

---

## 12. Anti-padrões nomeados

| # | Anti-padrão | Sintoma | Correção |
|---|---|---|---|
| A1 | **Só status code** | `.then().statusCode(200)` e nada mais | Asserte corpo + schema + SLA |
| A2 | **Base URI hardcoded** | `https://staging...` no teste | Env var + `RequestSpecBuilder` |
| A3 | **Log poluído** | `.log().all()` em todo teste | Log só em falha |
| A4 | **Sem schema** | contrato quebra silencioso | `matchesJsonSchemaInClasspath` |
| A5 | **Token vazado** | JWT/secret no código | Secret via env, `auth().oauth2` |
| A6 | **String de path** | `get("/pedidos/" + id)` | Path param `get("/pedidos/{id}", id)` |
| A7 | **Navegar JSON por string** | `body("valorTotal", ...)` com float | `extract().as(Record)` + BigDecimal |
| A8 | **Duplicar em MockMvc + RestAssured** | mesmo caso, 2 ferramentas | 1 fronteira por caso (§0) |
| A9 | **Ordem entre testes** | teste B depende de A | Cada teste isola seu dado (setup próprio) |
| A10 | **Só happy path** | 1 teste 200 e acabou | Os 8 eixos (§10) |

---

## 13. Checklist de PR (API REST com RestAssured)

- [ ] Base URI e credenciais vêm de env/secret (nada hardcoded)
- [ ] `RequestSpecBuilder`/`ResponseSpecBuilder` centralizam o comum (DRY)
- [ ] Happy path valida **corpo + JSON Schema + SLA**, não só status
- [ ] Cobre AUTH (401), AUTHORIZATION (403), NOT FOUND (404), CONFLICT (409), INPUT (400)
- [ ] Serialização via `record`/POJO tipado; dinheiro em `BigDecimal`
- [ ] Log apenas em falha; sem `.log().all()` fixo
- [ ] Versão alinhada ao stack (6.0.0 p/ Java 25/Jackson 3)
- [ ] Nenhum caso duplicado entre RestAssured e `MockMvcTester`/`RestTestClient`
- [ ] Testes independentes de ordem e seguros em paralelo

---

## 14. Exemplo executável (prova)

`examples/rest-assured-professional/` — projeto Maven **rodável** que materializa esta reference:
specs reutilizáveis, JSON Schema (draft-04), serialização POJO, auth OAuth2 e data-driven, com a "API
sob teste" simulada por **WireMock in-process** (sem Docker). Demonstra o ciclo **TDD RED→GREEN**
(`RED_PHASE=1` = contrato não implementado ⇒ 10/10 falham; sem a flag ⇒ 10/10 verdes).

```bash
cd examples/rest-assured-professional
mvn test                 # GREEN: 10/10
RED_PHASE=1 mvn test     # RED:   10/10 falham (contrato ausente)
```

> O exemplo compila em Java 11 (linha RestAssured 5.5.x) por restrição de ambiente; a reference e o
> alvo de produção são Java 25 + RestAssured 6.0.0. Ver `examples/.../README.md §Compatibilidade`.

---

## 15. Referências externas

- Wiki oficial (Usage, Spring, ReleaseNotes): https://github.com/rest-assured/rest-assured/wiki
- Site/Javadoc: https://rest-assured.io/ · https://javadoc.io/doc/io.rest-assured/rest-assured/latest/
- JSON Schema validation: https://www.baeldung.com/rest-assured-json-schema
- Spring + RestAssured (rieckpil): https://rieckpil.de/testing-spring-boot-applications-with-rest-assured/
- Spring MockMvc support (Baeldung): https://www.baeldung.com/spring-mock-mvc-rest-assured
