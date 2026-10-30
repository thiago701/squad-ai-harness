# Testes Modernos com Java 25 + Spring Boot 4 / Spring Framework 7

> **Quando ler este arquivo:** sempre que for testar código Java/Kotlin no stack 2025-2026 — Boot ≥ 3.4 / Spring ≥ 6.2, e principalmente Boot 4 (Spring 7). Aqui estão os padrões de teste que substituem `@MockBean`, `TestRestTemplate` e a configuração manual de Testcontainers.

---

## Tabela de Substituições (o que morreu, o que nasceu)

| Antes (≤ Boot 3.3 / Spring 6.1) | Agora (Boot 3.4+ / Spring 6.2+ / Boot 4 / Spring 7) | Por quê |
|---|---|---|
| `@MockBean` (deprecated) | `@MockitoBean` | Sem dependência do Spring Boot Test core, semântica explícita |
| `@SpyBean` (deprecated) | `@MockitoSpyBean` | idem |
| `TestRestTemplate` | `RestTestClient` (Boot 4) ou `RestClient` + assertions | Type-safe, fluente, sem reactor no classpath |
| `MockMvc` cru | `MockMvcTester` (Spring 6.2+) | Asserções AssertJ-native, sem `andExpect` aninhado |
| `@DynamicPropertySource` manual para Testcontainers | `@ServiceConnection` (Boot 3.1+) | Auto-wires Postgres/Kafka/Redis sem boilerplate |
| `Thread.sleep(...)` em testes async | `Awaitility` + `StructuredTaskScope` | Determinístico, cancelamento estruturado |
| Pool de threads custom em `@Async` | Virtual Threads (`spring.threads.virtual.enabled=true`) | I/O-bound testa-se com 10k tasks sem OOM |
| `Mockito.when(...)` para sealed interfaces | Pattern matching em assert + `switch` exaustivo | Compilador garante exaustividade, teste nunca esquece variante |
| `Map.of("k", "v")` em payload de teste | `record` DTO + `JSON Templates` (Java 25 preview) | Refactoring-safe, autocompletar |

---

## 1. `@SpringBootTest` Moderno (Boot 4 / Spring 7)

### 1.1 Setup canônico — slice mínimo + Testcontainers via `@ServiceConnection`

```java
package com.empresa.pedidos.application;

import com.empresa.pedidos.PedidosApplication;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(classes = PedidosApplication.class)
@Testcontainers
class ConfirmarPedidoIT {

    /* Sem @DynamicPropertySource. @ServiceConnection cuida de:
     *   spring.datasource.url, .username, .password, .driver-class-name
     * Spring Boot detecta o container e injeta a conexão automaticamente. */
    @Container
    @ServiceConnection
    static final PostgreSQLContainer<?> postgres =
        new PostgreSQLContainer<>("postgres:16-alpine").withReuse(true);

    @Autowired
    ConfirmarPedidoUseCase useCase;

    /* @MockitoBean substitui @MockBean. Idêntica semântica, sem dependência deprecated. */
    @MockitoBean
    NotificacaoGateway notificacaoGateway;

    @Test
    void deveConfirmarPedidoEDispararNotificacao() {
        var pedidoId = umPedidoPendentePersistido();

        var resultado = useCase.executar(pedidoId);

        assertThat(resultado.status()).isEqualTo(StatusPedido.CONFIRMADO);
        verify(notificacaoGateway).pedidoConfirmado(pedidoId);
    }
}
```

**Por que importa:** o boilerplate de `@DynamicPropertySource` era origem comum de testes flaky (registro de propriedade em ordem errada). `@ServiceConnection` elimina essa classe inteira de bugs.

### 1.2 `@ServiceConnection` para Kafka, Redis, MongoDB, RabbitMQ

```java
@Container @ServiceConnection
static KafkaContainer kafka = new KafkaContainer("apache/kafka:3.7.0");

@Container @ServiceConnection
static RedisContainer redis = new RedisContainer("redis:7.4-alpine");

@Container @ServiceConnection
static MongoDBContainer mongo = new MongoDBContainer("mongo:7");

@Container @ServiceConnection
static RabbitMQContainer rabbit = new RabbitMQContainer("rabbitmq:3.13-management");

@Container @ServiceConnection
static LocalStackContainer localstack = new LocalStackContainer(
    DockerImageName.parse("localstack/localstack:3.5"))
    .withServices(SQS, S3, DYNAMODB);
```

**Regra:** se o container tem `ServiceConnection` registrado (todos os principais têm), nunca escreva `@DynamicPropertySource` para ele. Se não tem, escreva um `ContainerConnectionDetails` próprio (uma classe de 30 linhas) — ainda melhor que registrar propriedade manual.

---

## 2. Slice Tests Modernos

Slice tests carregam só a fatia da aplicação que importa para o teste. São **10× mais rápidos** que `@SpringBootTest` completo. Use sempre que possível.

| Slice | O que carrega | Quando usar |
|---|---|---|
| `@WebMvcTest(MyController.class)` | MVC + Jackson + Validação. Sem JPA, sem services. | Testar controller isoladamente (status, body, headers, validação). |
| `@DataJpaTest` | JPA + Testcontainers via `@ServiceConnection`. Sem MVC. | Repositórios, queries customizadas, mappers, constraints. |
| `@JsonTest` | Jackson + JsonComponent. Sem nada mais. | Serialização/desserialização de DTOs, customizers. |
| `@RestClientTest(MyClient.class)` | RestClient/WebClient + MockRestServiceServer. | Testar adapters HTTP de saída. |
| `@DataRedisTest` | Spring Data Redis + container. | Operações Redis (cache, lock, stream). |
| `@DataMongoTest` | Spring Data Mongo + container. | Repositórios MongoDB, agregações. |
| `@SpringBootTest(webEnvironment = RANDOM_PORT)` | App inteira numa porta aleatória. | E2E de back-end (controller → DB → fila). Use parcimoniosamente. |

### 2.1 `@WebMvcTest` com `MockMvcTester` (Spring 6.2+)

`MockMvcTester` é a substituição AssertJ-native do `MockMvc` cru. Asserções fluentes, sem `andExpect(jsonPath(...))` aninhado.

```java
import org.springframework.test.web.servlet.assertj.MockMvcTester;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;

import static org.assertj.core.api.Assertions.assertThat;

@WebMvcTest(PedidoController.class)
class PedidoControllerTest {

    @Autowired MockMvcTester mvc;
    @MockitoBean ConfirmarPedidoUseCase useCase;

    @Test
    void postConfirmar_deveRetornar200ComBodyEsperado() {
        when(useCase.executar(42L))
            .thenReturn(new ConfirmacaoResultado(42L, "CONFIRMADO"));

        assertThat(mvc.post().uri("/pedidos/{id}/confirmar", 42))
            .hasStatus(HttpStatus.OK)
            .bodyJson()
                .convertTo(ConfirmacaoResponse.class)
                .satisfies(r -> {
                    assertThat(r.pedidoId()).isEqualTo(42L);
                    assertThat(r.status()).isEqualTo("CONFIRMADO");
                });
    }

    @Test
    void postConfirmar_validacaoFalhada_deveRetornar400ComProblemDetail() {
        assertThat(mvc.post().uri("/pedidos/{id}/confirmar", -1))
            .hasStatus(HttpStatus.BAD_REQUEST)
            .bodyJson().extractingPath("$.title").isEqualTo("Validation failed")
            .bodyJson().extractingPath("$.errors").asArray().hasSize(1);
    }
}
```

**Por que importa:** o `MockMvc` antigo encadeia métodos não-tipados. Erro de digitação em `jsonPath` só aparece em runtime. `MockMvcTester` é AssertJ — autocompletar, refactor-safe, mensagens de falha humanas.

### 2.2 `@DataJpaTest` com `@ServiceConnection`

```java
@DataJpaTest
@Testcontainers
class PedidoRepositoryTest {

    @Container @ServiceConnection
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine");

    @Autowired PedidoRepository repo;
    @Autowired TestEntityManager em;

    @Test
    void devePersistirPedidoEPreservarTodosOsCampos() {
        var pedido = PedidoFixtures.pendente().comValor(new BigDecimal("250.75")).build();

        repo.save(pedido);
        em.flush(); em.clear();

        var recuperado = repo.findById(pedido.getId()).orElseThrow();
        assertThat(recuperado).usingRecursiveComparison()
            .ignoringFields("createdAt", "updatedAt")
            .isEqualTo(pedido);
    }

    @Test
    void deveRespeitarConstraintCheckValorPositivo() {
        var invalido = PedidoFixtures.pendente().comValor(new BigDecimal("-1.00")).build();

        assertThatThrownBy(() -> { repo.save(invalido); em.flush(); })
            .isInstanceOf(DataIntegrityViolationException.class)
            .hasRootCauseInstanceOf(PSQLException.class)
            .hasMessageContaining("CHECK");
    }
}
```

### 2.3 `@RestClientTest` para adapters HTTP de saída

```java
@RestClientTest(NotificacaoHttpAdapter.class)
class NotificacaoHttpAdapterTest {

    @Autowired NotificacaoHttpAdapter adapter;
    @Autowired MockRestServiceServer server;

    @Test
    void deveEnviarPayloadCorretoEParsearResposta() {
        server.expect(requestTo("/api/notificar"))
              .andExpect(method(POST))
              .andExpect(jsonPath("$.pedidoId").value(42))
              .andRespond(withSuccess("{\"ok\":true}", APPLICATION_JSON));

        var resultado = adapter.notificar(new NotificacaoRequest(42L, "joao@x.com"));

        assertThat(resultado.aceito()).isTrue();
        server.verify();
    }
}
```

---

## 3. Virtual Threads e Structured Concurrency em Testes

Java 21+ trouxe Virtual Threads. Java 25 estabilizou `StructuredTaskScope`. Ambos mudam **como testamos código concorrente**.

### 3.1 Habilitar Virtual Threads no teste

```yaml
# src/test/resources/application-test.yml
spring:
  threads:
    virtual:
      enabled: true       # @Async, @Scheduled, Tomcat workers viram virtual threads
  task:
    execution:
      thread-name-prefix: vt-test-
```

### 3.2 Testar carga concorrente real (sem ThreadPool gambiarra)

Antes (frágil, lento, com risco de deadlock por pool exhaustion):

```java
// ❌ Antes — pool fixo, OOM se passar do limite
ExecutorService pool = Executors.newFixedThreadPool(50);
List<Future<?>> futures = new ArrayList<>();
for (int i = 0; i < 10_000; i++) {
    futures.add(pool.submit(() -> useCase.executar(pedidoId)));
}
for (var f : futures) f.get();
```

Agora (Virtual Threads + StructuredTaskScope):

```java
// ✅ Agora — virtual thread por task, falha estruturada
@Test
void devePermitir10kConfirmacoesConcorrentesSemPerda() throws Exception {
    var pedidoIds = umLoteDePedidosPersistidos(10_000);

    try (var scope = StructuredTaskScope.open(Joiner.<ConfirmacaoResultado>allSuccessfulOrThrow())) {
        for (Long id : pedidoIds) {
            scope.fork(() -> useCase.executar(id));
        }
        var resultados = scope.join().toList();

        assertThat(resultados)
            .hasSize(10_000)
            .allSatisfy(r -> assertThat(r.status()).isEqualTo("CONFIRMADO"));
    }

    assertThat(repository.contarPorStatus(StatusPedido.CONFIRMADO)).isEqualTo(10_000L);
}
```

**Por que importa:** o teste antigo escondia deadlocks (pool exhaustion mascara contenção real no domínio). Virtual Threads + StructuredTaskScope expõem o que vai acontecer em produção sob carga.

### 3.3 Testar idempotência sob corrida

```java
@Test
void confirmacaoConcorrenteDoMesmoPedido_apenasUmaSucesso() throws Exception {
    var pedidoId = umPedidoPendentePersistido();

    try (var scope = StructuredTaskScope.open(Joiner.<ConfirmacaoResultado>allSuccessful())) {
        for (int i = 0; i < 50; i++) {
            scope.fork(() -> useCase.executar(pedidoId));
        }
        var resultados = scope.join().toList();

        long sucessos = resultados.stream()
            .filter(r -> r instanceof ConfirmacaoResultado.Sucesso)
            .count();
        long jaConfirmados = resultados.stream()
            .filter(r -> r instanceof ConfirmacaoResultado.JaConfirmado)
            .count();

        assertThat(sucessos).isEqualTo(1L);              // invariante
        assertThat(jaConfirmados).isEqualTo(49L);        // resto é idempotente, não erro
        assertThat(sucessos + jaConfirmados).isEqualTo(50L);
    }
}
```

### 3.4 Awaitility para esperas assíncronas (zero `Thread.sleep`)

```java
import static org.awaitility.Awaitility.await;
import static java.time.Duration.ofSeconds;

@Test
void eventoDeveAparecerNoKafkaEm5s() {
    useCase.executar(pedidoId);

    await().atMost(ofSeconds(5))
           .pollInterval(ofMillis(100))
           .untilAsserted(() -> {
               var msg = consumer.poll(Duration.ofMillis(50)).records("pedidos.confirmados");
               assertThat(msg).isNotEmpty();
           });
}
```

`Thread.sleep(5000)` em teste é antipattern: ou é lento demais (espera quando não precisa) ou flaky (timeout pequeno demais). `Awaitility` polla até a condição valer ou o timeout estourar.

---

## 4. Sealed Types, Records e Pattern Matching em Testes

### 4.1 Sealed result types tornam asserções exaustivas

Domínio:

```java
public sealed interface ConfirmacaoResultado
    permits ConfirmacaoResultado.Sucesso,
            ConfirmacaoResultado.JaConfirmado,
            ConfirmacaoResultado.Falha {

    record Sucesso(long pedidoId, Instant confirmadoEm) implements ConfirmacaoResultado {}
    record JaConfirmado(long pedidoId) implements ConfirmacaoResultado {}
    record Falha(String motivo, ErrorCode codigo) implements ConfirmacaoResultado {}
}
```

Teste com switch exaustivo (compilador garante que toda variante é tratada):

```java
@Test
void deveTratarTodasAsVariantesDoResultado() {
    var resultado = useCase.executar(pedidoId);

    String descricao = switch (resultado) {
        case ConfirmacaoResultado.Sucesso s ->
            "ok em " + s.confirmadoEm();
        case ConfirmacaoResultado.JaConfirmado j ->
            "já confirmado: " + j.pedidoId();
        case ConfirmacaoResultado.Falha f ->
            "falha: " + f.motivo();
        // Sem default! Se domínio adicionar variante, compilador acusa AQUI.
    };

    assertThat(descricao).isNotBlank();
}
```

**Por que importa:** quando alguém adicionar `ConfirmacaoResultado.Bloqueado`, este teste **não compila** até ser atualizado. Refactoring vira algoritmo, não arqueologia.

### 4.2 Pattern matching em asserções com AssertJ

```java
@Test
void confirmacaoNoLimite_deveProduzirSucessoComTimestamp() {
    var resultado = useCase.executar(pedidoNoLimite);

    assertThat(resultado).isInstanceOfSatisfying(
        ConfirmacaoResultado.Sucesso.class,
        sucesso -> {
            assertThat(sucesso.pedidoId()).isPositive();
            assertThat(sucesso.confirmadoEm()).isCloseTo(Instant.now(), within(2, ChronoUnit.SECONDS));
        });
}
```

### 4.3 Records como DTOs de teste (zero builder boilerplate)

```java
record CenarioPedido(
    long id,
    BigDecimal valor,
    StatusPedido status,
    int quantidadeItens
) {
    static CenarioPedido pendente(BigDecimal valor) {
        return new CenarioPedido(nextId(), valor, StatusPedido.PENDENTE, 1);
    }
}

@ParameterizedTest
@MethodSource("cenariosDeBoundary")
void deveAplicarRegrasDeBoundaryCorretamente(CenarioPedido cenario, boolean deveConfirmar) {
    var resultado = useCase.executar(persistir(cenario));
    if (deveConfirmar) {
        assertThat(resultado).isInstanceOf(ConfirmacaoResultado.Sucesso.class);
    } else {
        assertThat(resultado).isInstanceOf(ConfirmacaoResultado.Falha.class);
    }
}

static Stream<Arguments> cenariosDeBoundary() {
    return Stream.of(
        arguments(CenarioPedido.pendente(new BigDecimal("9.99")),  false),  // abaixo
        arguments(CenarioPedido.pendente(new BigDecimal("10.00")), true),   // exato
        arguments(CenarioPedido.pendente(new BigDecimal("10.01")), true),   // acima
        arguments(CenarioPedido.pendente(new BigDecimal("9999999.99")), true)  // máximo
    );
}
```

---

## 5. Spring Modulith — `ApplicationModules.verify()` como Teste Arquitetural

Se o projeto adota Spring Modulith, **um único teste** valida que módulos respeitam fronteiras de pacote:

```java
import org.springframework.modulith.core.ApplicationModules;
import org.springframework.modulith.docs.Documenter;
import org.junit.jupiter.api.Test;

class ArquiteturaModulosTest {

    static final ApplicationModules MODULES = ApplicationModules.of(PedidosApplication.class);

    @Test
    void modulosNaoQuebramFronteiras() {
        MODULES.verify();  // falha se algum módulo importa interno de outro
    }

    @Test
    void documentacaoDeArquiteturaAtualizada() {
        new Documenter(MODULES)
            .writeModulesAsPlantUml()
            .writeIndividualModulesAsPlantUml()
            .writeDocumentation();
    }
}
```

`@ApplicationModuleTest` para slice por módulo:

```java
@ApplicationModuleTest
class PedidosModuleTest {
    @Autowired ConfirmarPedidoUseCase useCase;

    @Test
    void usecasePodeSerInjetadoSemDependenciasDeOutroModulo() {
        assertThat(useCase).isNotNull();
    }
}
```

### 5.1 Spring Modulith **+** ArchUnit no MESMO teste — guarda dupla

Spring Modulith verifica **fronteiras de módulo** (pacote → pacote, declarado em `package-info.java`). ArchUnit verifica **regras arquiteturais transversais** (Domain não conhece JPA, Use Case não chama Controller, Repository é sempre interface no domínio). Os dois são **complementares, não concorrentes** — execute juntos no mesmo teste para que a falha aponte exatamente o tipo de violação.

```java
package com.empresa.pedidos.architecture;

import com.empresa.pedidos.PedidosApplication;
import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;
import com.tngtech.archunit.library.Architectures;
import com.tngtech.archunit.library.dependencies.SlicesRuleDefinition;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.springframework.modulith.core.ApplicationModules;
import org.springframework.modulith.docs.Documenter;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.*;

@DisplayName("Arquitetura: Spring Modulith + ArchUnit (guarda dupla)")
@AnalyzeClasses(packages = "com.empresa.pedidos", importOptions = ImportOption.DoNotIncludeTests.class)
class ArquiteturaIT {

    /* Mesma representação carregada uma vez para os 2 motores. */
    static final ApplicationModules MODULES = ApplicationModules.of(PedidosApplication.class);
    static final JavaClasses CLASSES = new ClassFileImporter()
        .withImportOption(ImportOption.Predefined.DO_NOT_INCLUDE_TESTS)
        .importPackages("com.empresa.pedidos");

    // ── 1. Spring Modulith: fronteiras de módulo declaradas ───────────────────
    @Test
    @DisplayName("Modulith: módulos respeitam fronteiras declaradas em package-info.java")
    void modulosRespeitamFronteiras() {
        MODULES.verify();  // falha se módulo A acessa internals de módulo B
    }

    @Test
    @DisplayName("Modulith: documentação PlantUML está atualizada")
    void documentacaoArquiteturaGerada() {
        new Documenter(MODULES)
            .writeModulesAsPlantUml()
            .writeIndividualModulesAsPlantUml()
            .writeDocumentation();
    }

    // ── 2. ArchUnit: Clean Architecture 4 camadas (transversal aos módulos) ──
    @Nested
    @DisplayName("ArchUnit: Clean Architecture 4 camadas")
    class CleanArchitectureLayers {

        @ArchTest
        static final ArchRule CAMADAS_RESPEITADAS = Architectures.layeredArchitecture()
            .consideringAllDependencies()
            .layer("Domain").definedBy("..domain..")
            .layer("Application").definedBy("..application..")
            .layer("Infrastructure").definedBy("..infrastructure..")
            .layer("Adapter").definedBy("..adapter..")
            .whereLayer("Adapter").mayNotBeAccessedByAnyLayer()
            .whereLayer("Infrastructure").mayOnlyBeAccessedByLayers("Adapter")
            .whereLayer("Application").mayOnlyBeAccessedByLayers("Adapter", "Infrastructure")
            .whereLayer("Domain").mayOnlyBeAccessedByLayers("Application", "Adapter", "Infrastructure");

        @ArchTest
        static final ArchRule DOMAIN_NAO_DEPENDE_DE_FRAMEWORK =
            noClasses().that().resideInAPackage("..domain..")
                .should().dependOnClassesThat().resideInAnyPackage(
                    "jakarta.persistence..",       // sem JPA no domínio
                    "org.springframework..",       // sem Spring no domínio
                    "com.fasterxml.jackson..",     // sem Jackson no domínio
                    "org.hibernate..");

        @ArchTest
        static final ArchRule USE_CASE_NAO_CHAMA_CONTROLLER =
            noClasses().that().resideInAPackage("..application..")
                .should().dependOnClassesThat().resideInAnyPackage(
                    "..adapter.web..", "..controller..");

        @ArchTest
        static final ArchRule REPOSITORY_INTERFACE_NO_DOMINIO =
            classes().that().haveSimpleNameEndingWith("Repository")
                .and().resideInAPackage("..domain..")
                .should().beInterfaces();
    }

    // ── 3. ArchUnit: ciclos entre slices (cross-validation com Modulith) ──────
    @Nested
    @DisplayName("ArchUnit: ausência de ciclos entre módulos top-level")
    class NoCycles {

        @ArchTest
        static final ArchRule SEM_CICLOS_ENTRE_TOP_LEVEL_PACKAGES =
            SlicesRuleDefinition.slices()
                .matching("com.empresa.pedidos.(*)..")
                .should().beFreeOfCycles();
    }

    // ── 4. ArchUnit: convenções de naming (suporte ao DDD) ────────────────────
    @Nested
    @DisplayName("ArchUnit: convenções DDD")
    class DddConventions {

        @ArchTest
        static final ArchRule AGGREGATE_ROOT_TEM_ID =
            classes().that().areAnnotatedWith("com.empresa.pedidos.shared.AggregateRoot")
                .should().haveSimpleNameNotEndingWith("DTO")
                .andShould().haveSimpleNameNotEndingWith("Entity");

        @ArchTest
        static final ArchRule USE_CASE_TERMINA_COM_USECASE =
            classes().that().resideInAPackage("..application..")
                .and().areAnnotatedWith("org.springframework.stereotype.Service")
                .should().haveSimpleNameEndingWith("UseCase");
    }
}
```

#### Por que rodar os dois juntos

| Quem detecta o quê | Modulith | ArchUnit |
|---|---|---|
| Módulo A acessa pacote interno de módulo B (não exposto via `package-info.java`) | ✅ | parcial |
| Domain importa `jakarta.persistence.*` | ❌ (não é fronteira de módulo) | ✅ |
| Existe ciclo `application → infrastructure → application` | parcial | ✅ |
| Use case anotado `@Service` mas sem sufixo `UseCase` | ❌ | ✅ |
| Aggregate Root anotado mas com nome `*Entity` | ❌ | ✅ |
| Documentação PlantUML dos módulos desatualizada | ✅ | ❌ |

**Regra prática:** Modulith descreve **o que cada módulo expõe**; ArchUnit descreve **o que cada classe pode/não pode fazer**. Sem os dois, alguma violação real escapa.

#### Mensagem de falha — ler é metade do trabalho

A falha do `MODULES.verify()` aponta exatamente o package importer e o package importado. A falha do ArchUnit aponta classe + linha + dependência proibida. Quando ambos falham no mesmo PR, leia primeiro o Modulith (problema de fronteira de módulo) e depois o ArchUnit (problema de regra transversal) — geralmente o segundo é consequência do primeiro.

#### Regra 80/20 sobre custo

Este teste roda em **< 5 segundos** mesmo em projeto grande (não sobe Spring, só inspeciona bytecode). Mantenha-o no pipeline `mvn verify` — não deve ser optional, não deve ser lento, não deve ser flaky.

---

## 6. ApplicationContextRunner — Slice de Configuração Sem Subir o Spring

Para testar autoconfiguração, beans condicionais, `@ConditionalOnProperty`:

```java
import org.springframework.boot.test.context.runner.ApplicationContextRunner;

class CacheAutoConfigurationTest {

    private final ApplicationContextRunner runner = new ApplicationContextRunner()
        .withConfiguration(AutoConfigurations.of(CacheAutoConfiguration.class));

    @Test
    void deveCriarRedisCacheManager_quandoPropriedadeAtiva() {
        runner.withPropertyValues("app.cache.type=redis", "spring.data.redis.host=localhost")
              .run(ctx -> assertThat(ctx).hasSingleBean(RedisCacheManager.class));
    }

    @Test
    void deveCriarCaffeineCacheManager_quandoPropriedadeAusente() {
        runner.run(ctx -> assertThat(ctx)
            .hasSingleBean(CaffeineCacheManager.class)
            .doesNotHaveBean(RedisCacheManager.class));
    }
}
```

**Vantagem:** sub-segundo. `@SpringBootTest` para isso seria 5-30s. Use Runner sempre que for testar wiring/autoconfig.

---

## 7. RestTestClient (Boot 4) e RestClient

`RestTestClient` é o cliente blocante type-safe que substitui `TestRestTemplate` no Boot 4. API espelhada em `WebTestClient` mas sem reactor.

```java
@SpringBootTest(webEnvironment = RANDOM_PORT)
@AutoConfigureRestTestClient
class PedidoControllerIT {
    @Autowired RestTestClient client;

    @Test void postConfirmar_201ComLocation() {
        client.post().uri("/pedidos")
              .contentType(APPLICATION_JSON)
              .bodyValue(new CriarPedidoRequest("cliente-1", List.of(new ItemRequest("SKU-1", 2))))
              .exchange()
              .expectStatus().isCreated()
              .expectHeader().exists(LOCATION)
              .expectBody(PedidoResponse.class)
                  .value(p -> assertThat(p.status()).isEqualTo("PENDENTE"));
    }
}
```

Para clientes externos, use `RestClient` (Spring 6.1+) com `MockRestServiceServer` em `@RestClientTest` (ver §2.3).

---

## 8. Spring AOT e Native Image — Testes que Cobrem o Caminho Nativo

GraalVM Native Image (Spring Native) tem reflection/proxy fechados. Bugs de hint só aparecem após `mvn -Pnative test`. Estratégia:

### 8.1 Testes JVM regulares + smoke test nativo no CI

```bash
# Execução local — JVM normal
./mvnw test

# Execução pré-merge — caminho AOT
./mvnw -Paot process-test-classes
./mvnw -Paot test            # roda testes na configuração AOT

# Smoke nativo — apenas para PRs em main
./mvnw -Pnative native:compile-no-fork
./test-native-binary.sh      # sobe o binário e bate o /actuator/health
```

### 8.2 Detectar hints faltando

`spring-aot-test` falha o build se uma classe acessada por reflection não tem hint registrado. Garanta:

```xml
<!-- pom.xml -->
<plugin>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-maven-plugin</artifactId>
    <executions>
        <execution>
            <id>process-test-aot</id>
            <goals><goal>process-test-aot</goal></goals>
        </execution>
    </executions>
</plugin>
```

Quando AOT processa testes, ele detecta uso de:
- Classes anotadas com `@Reflective`
- Beans criados por `BeanFactoryInitializationAotProcessor`
- Tipos passados a `Jackson`, `Hibernate`, `JPA`

E gera os reflect-config necessários. Se você customiza serialização/JPA queries nativas, escreva um teste que **execute** o caminho — só assim AOT registra os hints.

### 8.3 `@AotProcessor` customizado precisa ser testado

```java
@Test
void aotProcessorRegistraHintsParaConfirmacaoResultado() {
    var hints = new RuntimeHints();
    new ConfirmacaoResultadoAotProcessor().registerHints(hints, getClass().getClassLoader());

    assertThat(RuntimeHintsPredicates.reflection()
        .onType(ConfirmacaoResultado.Sucesso.class).withMemberCategory(MemberCategory.INVOKE_DECLARED_CONSTRUCTORS))
        .accepts(hints);
}
```

---

## 9. Asserções Modernas com AssertJ 3.26+

### 9.1 `usingRecursiveComparison()` — ignorar campos voláteis

```java
assertThat(salvo).usingRecursiveComparison()
    .ignoringFields("id", "createdAt", "updatedAt", "version")
    .isEqualTo(esperado);
```

### 9.2 `extracting` com lambdas type-safe

```java
assertThat(pedidos)
    .extracting(Pedido::getId, Pedido::getStatus, Pedido::getValor)
    .containsExactlyInAnyOrder(
        tuple(1L, CONFIRMADO, new BigDecimal("100.00")),
        tuple(2L, PENDENTE,    new BigDecimal("50.00"))
    );
```

### 9.3 Asserção customizada para domínio

```java
public class PedidoAssert extends AbstractAssert<PedidoAssert, Pedido> {
    public PedidoAssert(Pedido actual) { super(actual, PedidoAssert.class); }
    public static PedidoAssert assertThat(Pedido actual) { return new PedidoAssert(actual); }

    public PedidoAssert estaConfirmado() {
        isNotNull();
        if (actual.getStatus() != StatusPedido.CONFIRMADO)
            failWithMessage("Esperava pedido CONFIRMADO mas estava <%s>", actual.getStatus());
        return this;
    }

    public PedidoAssert temValorMaiorQue(BigDecimal minimo) {
        isNotNull();
        if (actual.getValor().compareTo(minimo) <= 0)
            failWithMessage("Esperava valor > %s mas era <%s>", minimo, actual.getValor());
        return this;
    }
}

// Uso
import static com.empresa.pedidos.test.PedidoAssert.assertThat;

@Test
void deveConfirmarComValorMinimo() {
    var pedido = useCase.executar(pedidoId);

    assertThat(pedido)
        .estaConfirmado()
        .temValorMaiorQue(new BigDecimal("9.99"));
}
```

Asserções de domínio leem como inglês especificado, e a mensagem de falha aponta o invariante exato.

---

## 10. JUnit 5.11+ — Recursos que Pouca Gente Usa

### 10.1 `@ParameterizedTest` com `@MethodSource` retornando Records

```java
record CenarioConfirmacao(BigDecimal valor, boolean deveAceitar, String descricao) {}

@ParameterizedTest(name = "[{index}] valor={0}, esperado={1}: {2}")
@MethodSource("cenarios")
void devesAplicarRegraDeValorMinimo(CenarioConfirmacao c) {
    var resultado = useCase.executar(persistir(c.valor()));
    if (c.deveAceitar()) {
        assertThat(resultado).isInstanceOf(ConfirmacaoResultado.Sucesso.class);
    } else {
        assertThat(resultado).isInstanceOf(ConfirmacaoResultado.Falha.class);
    }
}

static Stream<CenarioConfirmacao> cenarios() {
    return Stream.of(
        new CenarioConfirmacao(new BigDecimal("9.99"), false, "centavo abaixo do mínimo"),
        new CenarioConfirmacao(new BigDecimal("10.00"), true, "exato no limite"),
        new CenarioConfirmacao(new BigDecimal("10.01"), true, "centavo acima do mínimo"),
        new CenarioConfirmacao(BigDecimal.ZERO,         false, "zero"),
        new CenarioConfirmacao(new BigDecimal("-0.01"), false, "negativo limite"),
        new CenarioConfirmacao(new BigDecimal("999999"), true, "alto mas válido")
    );
}
```

### 10.2 `@TestTemplate` + `TestTemplateInvocationContextProvider`

Para testes que precisam variar configuração ou ambiente em cada invocação (multi-tenant, feature flags). Mais poderoso que `@ParameterizedTest` quando o "parâmetro" é o próprio contexto.

### 10.3 Dynamic Tests

```java
@TestFactory
Stream<DynamicTest> deveConfirmarTodosOsPedidosDoCsvDeRegressao() throws IOException {
    return Files.lines(Path.of("src/test/resources/pedidos-regressao.csv"))
        .skip(1)
        .map(linha -> linha.split(","))
        .map(cols -> dynamicTest(
            "Pedido " + cols[0],
            () -> {
                var resultado = useCase.executar(Long.parseLong(cols[0]));
                assertThat(resultado.status()).isEqualTo(cols[1]);
            }
        ));
}
```

Ideal para regressão dirigida por dados — adicionar nova linha no CSV cria novo caso sem tocar Java.

### 10.4 `@DisplayNameGeneration` + Nested

```java
@DisplayNameGeneration(DisplayNameGenerator.ReplaceUnderscores.class)
class ConfirmarPedidoTest {

    @Nested
    class Quando_pedido_esta_pendente {

        @Test void e_valor_atinge_minimo_deve_confirmar() { /* ... */ }
        @Test void e_valor_abaixo_do_minimo_deve_rejeitar() { /* ... */ }
    }

    @Nested
    class Quando_pedido_ja_esta_confirmado {

        @Test void deve_retornar_idempotente_sem_chamar_notificador() { /* ... */ }
    }
}
```

Saída no relatório lê como especificação executável.

---

## 11. Mockito Moderno (Java 21+ Support)

### 11.1 `@MockitoBean` / `@MockitoSpyBean` (Spring Test 6.2+)

Já visto em §1.1. Ponto adicional: ambos suportam `inheritedListeners = false` para testar herança.

### 11.2 Mockito-inline é default desde 5.x

Pode mockar finais, statics, construtores sem declaração extra:

```java
@Test
void deveUsarRelogioFixoParaTimestampDeterministico() {
    try (MockedStatic<Instant> inst = mockStatic(Instant.class)) {
        var fixo = Instant.parse("2026-04-29T10:00:00Z");
        inst.when(Instant::now).thenReturn(fixo);

        var resultado = useCase.executar(pedidoId);

        assertThat(resultado).isInstanceOfSatisfying(
            ConfirmacaoResultado.Sucesso.class,
            s -> assertThat(s.confirmadoEm()).isEqualTo(fixo));
    }
}
```

Mas: **prefira `Clock` injetado** ao mocking estático. Mocking de `Instant.now()` é último recurso.

### 11.3 ArgumentCaptor com Records

```java
@Test
void devePublicarEventoComPayloadCorreto() {
    useCase.executar(42L);

    var captor = ArgumentCaptor.forClass(PedidoConfirmadoEvent.class);
    verify(publisher).publish(captor.capture());

    assertThat(captor.getValue())
        .isEqualTo(new PedidoConfirmadoEvent(42L, "CONFIRMADO", anyInstant()));
}
```

---

## 12. Stack de Dependências de Teste — `pom.xml` / `build.gradle.kts`

### Maven

```xml
<dependencies>
    <!-- Spring Boot 4.0+ Starter Test puxa: JUnit 5.11+, AssertJ 3.26+, Mockito 5+, Testcontainers, MockMvcTester -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-test</artifactId>
        <scope>test</scope>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-testcontainers</artifactId>
        <scope>test</scope>
    </dependency>
    <dependency>
        <groupId>org.testcontainers</groupId>
        <artifactId>postgresql</artifactId>
        <scope>test</scope>
    </dependency>
    <dependency>
        <groupId>org.testcontainers</groupId>
        <artifactId>kafka</artifactId>
        <scope>test</scope>
    </dependency>
    <dependency>
        <groupId>org.awaitility</groupId>
        <artifactId>awaitility</artifactId>
        <scope>test</scope>
    </dependency>
    <dependency>
        <groupId>org.springframework.modulith</groupId>
        <artifactId>spring-modulith-starter-test</artifactId>
        <scope>test</scope>
    </dependency>
    <dependency>
        <groupId>net.jqwik</groupId>
        <artifactId>jqwik</artifactId>            <!-- property-based -->
        <version>1.9.2</version>
        <scope>test</scope>
    </dependency>

    <!-- Mutation testing -->
    <!-- plugin: org.pitest:pitest-maven com pitest-junit5-plugin -->

    <!-- Cobertura -->
    <!-- plugin: org.jacoco:jacoco-maven-plugin -->
</dependencies>
```

### Gradle Kotlin DSL

```kotlin
dependencies {
    testImplementation("org.springframework.boot:spring-boot-starter-test")
    testImplementation("org.springframework.boot:spring-boot-testcontainers")
    testImplementation("org.testcontainers:postgresql")
    testImplementation("org.testcontainers:kafka")
    testImplementation("org.awaitility:awaitility")
    testImplementation("org.springframework.modulith:spring-modulith-starter-test")
    testImplementation("net.jqwik:jqwik:1.9.2")
}

// PIT mutation
plugins {
    id("info.solidsoft.pitest") version "1.15.0"
}

pitest {
    targetClasses.set(listOf("com.empresa.pedidos.domain.*", "com.empresa.pedidos.application.*"))
    junit5PluginVersion.set("1.2.1")
    mutationThreshold.set(80)
    coverageThreshold.set(85)
    timestampedReports.set(false)
}

// JaCoCo
plugins { jacoco }

tasks.jacocoTestCoverageVerification {
    violationRules {
        rule {
            limit { minimum = "0.90".toBigDecimal() }
        }
        rule {
            element = "PACKAGE"
            includes = listOf("com.empresa.pedidos.domain.*")
            limit { counter = "BRANCH"; minimum = "0.95".toBigDecimal() }
        }
    }
}
tasks.check { dependsOn(tasks.jacocoTestCoverageVerification) }
```

---

## 13. Antipadrões a Evitar (Stack Moderno)

| Antipadrão | Por que é ruim | O que fazer |
|---|---|---|
| `@SpringBootTest` para tudo | Lento (10-30s), carrega beans desnecessários | Use slice (`@WebMvcTest`, `@DataJpaTest`) sempre que possível |
| `@MockBean` | Deprecated, será removido | `@MockitoBean` |
| `Thread.sleep(ms)` em assert async | Flaky garantido | `Awaitility.await().until(...)` |
| `H2` para testar Postgres | SQL diferente, constraints diferentes | Testcontainers com `@ServiceConnection` |
| Mock de `Instant.now()` | Acoplamento ao detalhe estático | Injete `Clock`, use `Clock.fixed()` |
| `default` em switch sobre sealed | Esconde nova variante adicionada | Switch exaustivo, deixa compilador acusar |
| Pool fixo gigante para teste de carga | Mascara contenção real | `StructuredTaskScope` + Virtual Threads |
| Asserção em propriedade não-determinística (`createdAt`) | Quebra quando cron muda | `usingRecursiveComparison().ignoringFields(...)` |
| `MockMvc` cru com `andExpect(jsonPath(...))` aninhado | Erro só em runtime | `MockMvcTester` AssertJ-native |
| Testar adapter HTTP via app inteira | Lento, prende rede | `@RestClientTest` + `MockRestServiceServer` |

---

**Próximos passos sugeridos** (continuar leitura conforme a tarefa):
- Quer detalhar a estratégia de cobertura 90%? → leia `references/coverage-90-strategy.md`
- Quer aprofundar em camada específica? → `references/unit-tests.md`, `integration-tests.md`, `functional-tests.md`, `performance-tests.md`
- Quer entender mutation scoring? → `references/mutation-specimen.md`
