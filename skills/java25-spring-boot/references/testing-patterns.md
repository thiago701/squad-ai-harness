# Testing Patterns — Java 25 + Spring Boot 4

## Stack de Testes Recomendada

| Camada | Ferramenta | Uso |
|--------|-----------|-----|
| Unit | JUnit 5.11+ | Lógica de negócio isolada |
| Integration | Testcontainers 2.0 | Banco, cache, mensageria reais |
| API | RestTestClient | Controllers Spring Boot |
| Contract | Spring Cloud Contract | Contratos entre serviços |
| Performance | JMH | Microbenchmarks |
| Architecture | ArchUnit | Regras de dependência |

## RestTestClient (Novo no Spring Boot 4)

```java
@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT)
class UserControllerIntegrationTest {

    @Autowired
    RestTestClient client;

    @Test
    void shouldCreateUser() {
        client.post().uri("/api/users")
            .contentType(MediaType.APPLICATION_JSON)
            .bodyValue(new CreateUserRequest("João", "joao@email.com"))
            .exchange()
            .expectStatus().isCreated()
            .expectHeader().exists("Location")
            .expectBody(UserResponse.class)
            .value(user -> {
                assertThat(user.name()).isEqualTo("João");
                assertThat(user.id()).isNotNull();
            });
    }

    @Test
    void shouldReturn404ForUnknownUser() {
        client.get().uri("/api/users/999")
            .exchange()
            .expectStatus().isNotFound()
            .expectBody()
            .jsonPath("$.error").isEqualTo("User not found");
    }
}
```

## Testcontainers 2.0 com Spring Boot 4

```java
// application-test.properties via @ServiceConnection
@SpringBootTest
@Testcontainers
class OrderRepositoryTest {

    @Container
    @ServiceConnection  // Spring Boot auto-configura datasource!
    static PostgreSQLContainer<?> postgres =
        new PostgreSQLContainer<>("postgres:17-alpine");

    @Container
    @ServiceConnection
    static GenericContainer<?> redis =
        new GenericContainer<>("redis:7-alpine").withExposedPorts(6379);

    @Autowired
    OrderRepository orderRepository;

    @Test
    void shouldPersistOrder() {
        var order = new Order(null, "PROD-001", 3, BigDecimal.valueOf(29.90));
        var saved = orderRepository.save(order);

        assertThat(saved.id()).isNotNull();
        assertThat(orderRepository.findById(saved.id())).isPresent();
    }
}
```

### Testcontainers Reusáveis (speedup de testes)

```java
// Em src/test/resources/testcontainers.properties
testcontainers.reuse.enable=true

// No container:
@Container
@ServiceConnection
static PostgreSQLContainer<?> postgres =
    new PostgreSQLContainer<>("postgres:17-alpine")
        .withReuse(true);  // Reutiliza entre execuções de teste
```

## Testando Structured Concurrency

```java
@Test
void shouldAggregateFromMultipleServices() throws Exception {
    // Given
    when(userService.findById(1L)).thenReturn(testUser);
    when(orderService.findByUser(1L)).thenReturn(List.of(testOrder));
    when(loyaltyService.getPoints(1L)).thenReturn(1500);

    // When
    UserProfile profile;
    try (var scope = StructuredTaskScope.open(Joiner.allSuccessfulOrThrow())) {
        var userTask = scope.fork(() -> userService.findById(1L));
        var ordersTask = scope.fork(() -> orderService.findByUser(1L));
        var loyaltyTask = scope.fork(() -> loyaltyService.getPoints(1L));
        scope.join();

        profile = new UserProfile(userTask.get(), ordersTask.get(), loyaltyTask.get());
    }

    // Then
    assertThat(profile.user()).isEqualTo(testUser);
    assertThat(profile.orders()).hasSize(1);
    assertThat(profile.loyaltyPoints()).isEqualTo(1500);
}

@Test
void shouldHandlePartialFailure() {
    when(userService.findById(1L)).thenReturn(testUser);
    when(orderService.findByUser(1L)).thenThrow(new ServiceException("timeout"));

    assertThatThrownBy(() -> {
        try (var scope = StructuredTaskScope.open(Joiner.allSuccessfulOrThrow())) {
            scope.fork(() -> userService.findById(1L));
            scope.fork(() -> orderService.findByUser(1L));
            scope.join();
        }
    }).isInstanceOf(FailedException.class);
}
```

## Testando Scoped Values

```java
static final ScopedValue<String> TENANT_ID = ScopedValue.newInstance();

@Test
void shouldPropagateToNestedCalls() {
    ScopedValue.where(TENANT_ID, "tenant-42").run(() -> {
        assertThat(TENANT_ID.get()).isEqualTo("tenant-42");

        // Simula chamada em serviço interno
        String result = innerService.process();
        assertThat(result).contains("tenant-42");
    });
}

@Test
void shouldNotBeAccessibleOutsideScope() {
    assertThat(TENANT_ID.isBound()).isFalse();
    assertThatThrownBy(TENANT_ID::get)
        .isInstanceOf(NoSuchElementException.class);
}
```

## ArchUnit — Regras de Arquitetura

```java
@AnalyzeClasses(packages = "com.myapp")
class ArchitectureTest {

    @ArchTest
    static final ArchRule servicesShouldNotDependOnControllers =
        noClasses().that().resideInAPackage("..service..")
            .should().dependOnClassesThat().resideInAPackage("..controller..");

    @ArchTest
    static final ArchRule repositoriesShouldOnlyBeAccessedByServices =
        noClasses().that().resideOutsideOfPackage("..service..")
            .should().dependOnClassesThat().resideInAPackage("..repository..")
            .as("Repositories devem ser acessados apenas por services");

    @ArchTest
    static final ArchRule noThreadLocalUsage =
        noClasses().should().callMethod(ThreadLocal.class, "set", Object.class)
            .as("Use ScopedValue em vez de ThreadLocal");
}
```

## Testes em Native Image

```java
@SpringBootTest
@EnabledInNativeImage  // Roda apenas em contexto nativo
class NativeSmokeTest {

    @Autowired
    ApplicationContext context;

    @Test
    void contextLoads() {
        assertThat(context).isNotNull();
    }

    @Test
    void allBeansResolve() {
        // Verifica que AOT processing não quebrou nenhum bean
        assertThat(context.getBeanDefinitionNames()).hasSizeGreaterThan(10);
    }
}
```
