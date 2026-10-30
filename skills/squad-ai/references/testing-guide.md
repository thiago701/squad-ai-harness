# Guia de Testes — JUnit 5 + Testcontainers + ArchUnit

## Pirâmide

```
     /\
    /E2\      5%  — fluxos críticos end-to-end (RestAssured/Karate) — opcional
   /____\
  /  BDD \   15% — cenários de aceitação da Discovery (Cucumber ou JUnit + AssertJ)
 /________\
/Integration\ 20% — Testcontainers (Postgres real + Outbox + REST)
/__________\
/Unit tests \ 60% — domínio puro + application com mocks em ports
/____________\
```

## Unitários (domain puro)

Sem Spring, sem Mockito se possível. Domínio é só código Java.

```java
class PedidoTest {

    @Test
    void deveCriarPedidoEmRascunhoComEventoEmitido() {
        var clienteId = new ClienteId(UUID.randomUUID());
        var pedido = Pedido.criar(clienteId);

        assertThat(pedido.status()).isInstanceOf(PedidoStatus.Rascunho.class);
        assertThat(pedido.itens()).isEmpty();
        assertThat(pedido.pullEvents())
            .singleElement()
            .isInstanceOf(PedidoCriado.class);
    }

    @Test
    void naoDeveConfirmarPedidoVazio() {
        var pedido = Pedido.criar(new ClienteId(UUID.randomUUID()));

        assertThatThrownBy(pedido::confirmar)
            .isInstanceOf(DomainException.class)
            .hasMessageContaining("vazio");
    }

    @Test
    void deveCalcularValorTotalSomandoItens() {
        var pedido = Pedido.criar(new ClienteId(UUID.randomUUID()));
        pedido.adicionarItem(new ProdutoId(UUID.randomUUID()), new Quantidade(2),
                             new Money(new BigDecimal("10.00"), Currency.getInstance("BRL")));
        pedido.adicionarItem(new ProdutoId(UUID.randomUUID()), new Quantidade(3),
                             new Money(new BigDecimal("5.50"), Currency.getInstance("BRL")));

        assertThat(pedido.valorTotal())
            .isEqualTo(new Money(new BigDecimal("36.50"), Currency.getInstance("BRL")));
    }
}
```

**Regra:** domínio roda sem classpath Spring e sem banco. Se o teste precisa disso, ele é de integração, não unitário.

## Value Objects — teste explícito de validação

```java
class EmailTest {
    @Test void deveAceitarEmailValido() {
        assertThat(new Email("foo@bar.com").value()).isEqualTo("foo@bar.com");
    }

    @ParameterizedTest
    @ValueSource(strings = {"", " ", "semarroba", "@semlocal", "sem@dominio", "a@b@c.com"})
    void deveRejeitarEmailInvalido(String invalido) {
        assertThatThrownBy(() -> new Email(invalido))
            .isInstanceOf(DomainException.class);
    }

    @Test void deveRejeitarNulo() {
        assertThatThrownBy(() -> new Email(null)).isInstanceOf(NullPointerException.class);
    }
}
```

## Application (use cases com mocks em ports)

```java
@ExtendWith(MockitoExtension.class)
class ConfirmarPedidoHandlerTest {

    @Mock PedidoRepositoryPort repo;
    @Mock OutboxPort outbox;
    @InjectMocks ConfirmarPedidoHandler handler;

    @Test
    void deveConfirmarEGravarEventosNoOutbox() {
        var pedido = Pedido.criar(new ClienteId(UUID.randomUUID()));
        pedido.adicionarItem(
            new ProdutoId(UUID.randomUUID()),
            new Quantidade(1),
            new Money(new BigDecimal("10.00"), Currency.getInstance("BRL"))
        );
        when(repo.findById(pedido.id())).thenReturn(Optional.of(pedido));

        handler.handle(new ConfirmarPedidoCommand(pedido.id(), "corr-1"));

        verify(repo).save(pedido);
        verify(outbox).enqueue(argThat(list ->
            list.stream().anyMatch(e -> e instanceof PedidoConfirmado)
        ));
    }
}
```

## Integração — Testcontainers

Dependências:
```xml
<dependency>
  <groupId>org.testcontainers</groupId>
  <artifactId>junit-jupiter</artifactId>
  <scope>test</scope>
</dependency>
<dependency>
  <groupId>org.testcontainers</groupId>
  <artifactId>postgresql</artifactId>
  <scope>test</scope>
</dependency>
<dependency>
  <groupId>org.springframework.boot</groupId>
  <artifactId>spring-boot-testcontainers</artifactId>
  <scope>test</scope>
</dependency>
```

### Teste de repositório + outbox

Use `@ServiceConnection` (Spring Boot 3.1+/4) — Testcontainers configura o datasource automaticamente:

```java
@SpringBootTest
@Testcontainers
class PedidoRepositoryIntegrationTest {

    @Container @ServiceConnection
    static PostgreSQLContainer<?> postgres =
        new PostgreSQLContainer<>("postgres:16-alpine");

    @Autowired PedidoRepositoryPort repo;
    @Autowired OutboxEventJpaRepository outboxRepo;
    @Autowired ConfirmarPedidoHandler handler;

    @Test
    void deveSalvarEPersistirEventoNoOutboxNaMesmaTransacao() {
        var pedido = Pedido.criar(new ClienteId(UUID.randomUUID()));
        pedido.adicionarItem(new ProdutoId(UUID.randomUUID()), new Quantidade(1),
                             new Money(new BigDecimal("10.00"), Currency.getInstance("BRL")));
        repo.save(pedido);

        handler.handle(new ConfirmarPedidoCommand(pedido.id(), "corr-1"));

        assertThat(repo.findById(pedido.id()))
            .isPresent()
            .hasValueSatisfying(p ->
                assertThat(p.status()).isInstanceOf(PedidoStatus.Confirmado.class));
        assertThat(outboxRepo.findAll())
            .extracting(OutboxEventEntity::eventType)
            .anyMatch("PedidoConfirmado"::equals);
    }
}
```

### Teste de Flyway

```java
@SpringBootTest
@Testcontainers
class FlywayMigrationTest {
    @Container @ServiceConnection
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine");

    @Autowired Flyway flyway;

    @Test void migrationsAplicamLimpas() {
        var info = flyway.info();
        assertThat(info.applied()).isNotEmpty();
        assertThat(info.pending()).isEmpty();
    }
}
```

### Teste de REST controller

```java
@SpringBootTest(webEnvironment = RANDOM_PORT)
@Testcontainers
class PedidoControllerTest {
    @Container @ServiceConnection
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine");

    @Autowired WebTestClient client;

    @Test
    void deveRetornar400ParaBodyInvalido() {
        client.post().uri("/pedidos")
            .bodyValue(Map.of())  // sem clienteId
            .exchange()
            .expectStatus().isBadRequest()
            .expectBody()
            .jsonPath("$.type").isNotEmpty()       // RFC 9457 ProblemDetail
            .jsonPath("$.title").isNotEmpty();
    }
}
```

## ArchUnit — regras vivas

`infrastructure/src/test/java/.../CleanArchitectureTest.java`:

```java
@AnalyzeClasses(packages = "com.example.pedidos",
    importOptions = ImportOption.DoNotIncludeTests.class)
class CleanArchitectureTest {

    @ArchTest static final ArchRule dominioSemFramework =
        noClasses().that().resideInAPackage("..domain..")
            .should().dependOnClassesThat().resideInAnyPackage(
                "jakarta..", "org.springframework..", "org.hibernate..",
                "com.fasterxml.jackson..", "software.amazon.."
            );

    @ArchTest static final ArchRule camadas =
        layeredArchitecture().consideringAllDependencies()
            .layer("Domain").definedBy("..domain..")
            .layer("Application").definedBy("..application..")
            .layer("Infrastructure").definedBy("..infrastructure..")
            .layer("Bootstrap").definedBy("..bootstrap..")
            .whereLayer("Domain").mayOnlyBeAccessedByLayers("Application","Infrastructure","Bootstrap")
            .whereLayer("Application").mayOnlyBeAccessedByLayers("Infrastructure","Bootstrap")
            .whereLayer("Infrastructure").mayOnlyBeAccessedByLayers("Bootstrap");

    @ArchTest static final ArchRule semThreadLocal =
        noClasses().should().dependOnClassesThat()
            .haveFullyQualifiedName("java.lang.ThreadLocal");

    @ArchTest static final ArchRule boundedContextsNaoCruzam =
        noClasses().that().resideInAPackage("..domain.pedidos..")
            .should().dependOnClassesThat().resideInAPackage("..domain.pagamentos..");
}
```

## Recomendações extras (via ADR)

### Mutation (PIT)

Quando estabilizou: roda menos frequente (nightly), score ≥ 80% em `domain/`.

```xml
<plugin>
  <groupId>org.pitest</groupId>
  <artifactId>pitest-maven</artifactId>
  <configuration>
    <targetClasses>com.example.pedidos.domain.*</targetClasses>
    <targetTests>com.example.pedidos.domain.*Test</targetTests>
  </configuration>
</plugin>
```

### Property-based (jqwik)

Regras com espaço grande de inputs — ex: cálculo de Money, validação de CPF.

```java
@Property
void addSempreIgualOuMaiorQueOperandos(
    @ForAll @Positive BigDecimal a, @ForAll @Positive BigDecimal b
) {
    var moeda = Currency.getInstance("BRL");
    var soma = new Money(a, moeda).add(new Money(b, moeda));
    assertThat(soma.amount()).isGreaterThanOrEqualTo(a);
    assertThat(soma.amount()).isGreaterThanOrEqualTo(b);
}
```

### Contract (Pact)

Quando há múltiplos serviços consumindo o mesmo contrato. Evita quebra silenciosa.

### Performance (k6)

Scripts em `test/k6/`. Roda em pipeline noturno ou sob demanda.

## Convenções obrigatórias

- Nomes de teste `deve<Comportamento>_quando<Situação>` ou `should<Behavior>_when<Situation>` em inglês.
- AssertJ em vez de JUnit asserts (API fluente, mensagens melhores).
- Um teste = um comportamento. Nada de "teste feliz" cobrindo 5 coisas.
- Dados de teste via **Object Mother** ou **Test Data Builder**, não helpers mágicos.
- `@DirtiesContext` só quando estritamente necessário — é caro.
- Testcontainers `@Container static` para reuso entre classes (configurar `testcontainers.reuse.enable=true` localmente).

## Gate de qualidade

```
□ Cobertura ≥ 80% no domínio (JaCoCo)
□ Cobertura ≥ 60% geral
□ Zero testes ignorados sem justificativa em comentário
□ Zero @Disabled sem TODO e data
□ Testcontainers roda estável no CI (< 2% flakiness)
□ ArchUnit verde
```
