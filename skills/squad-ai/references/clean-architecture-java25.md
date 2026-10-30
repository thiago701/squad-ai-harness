# Clean Architecture em Java 25 + Spring Boot 4

## Princípio central

**Dependências apontam para dentro.** O domínio não conhece nada além dele mesmo. A aplicação conhece o domínio. A infraestrutura conhece aplicação e domínio. O bootstrap conhece todos (para fazer o wiring).

```
  ┌───────────────────────────────────────────────────┐
  │                   BOOTSTRAP                       │  ← Spring Boot main, @Configuration
  │  ┌─────────────────────────────────────────────┐  │
  │  │             INFRASTRUCTURE                  │  │  ← JPA, REST, AWS adapters, Outbox relay
  │  │  ┌───────────────────────────────────────┐  │  │
  │  │  │            APPLICATION                │  │  │  ← Use Cases, Commands, Queries, Ports
  │  │  │  ┌─────────────────────────────────┐  │  │  │
  │  │  │  │            DOMAIN               │  │  │  │  ← Aggregates, VOs, Events
  │  │  │  │   (zero deps externas)          │  │  │  │
  │  │  │  └─────────────────────────────────┘  │  │  │
  │  │  └───────────────────────────────────────┘  │  │
  │  └─────────────────────────────────────────────┘  │
  └───────────────────────────────────────────────────┘
```

## Estrutura Maven multi-module

```
<projeto>/
├── pom.xml                          ← agregador (packaging=pom)
├── domain/
│   ├── pom.xml                      ← zero deps de Spring/Jakarta/Hibernate
│   └── src/{main,test}/java/...
├── application/
│   ├── pom.xml                      ← depende de domain
│   └── src/{main,test}/java/...
├── infrastructure/
│   ├── pom.xml                      ← depende de application
│   └── src/{main,test}/java/...
└── bootstrap/
    ├── pom.xml                      ← depende de infrastructure (transitivamente tudo)
    └── src/{main,test}/java/...
```

### pom.xml do módulo domain (ilustrativo)

```xml
<project>
    <modelVersion>4.1.0</modelVersion>
    <parent>
        <groupId>com.example</groupId>
        <artifactId>pedidos</artifactId>
        <version>0.1.0-SNAPSHOT</version>
    </parent>
    <artifactId>pedidos-domain</artifactId>

    <dependencies>
        <!-- APENAS testes, zero framework runtime -->
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.assertj</groupId>
            <artifactId>assertj-core</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
```

Se o domínio pegar dependência Spring, **o build do módulo falha** — o melhor tipo de guard rail.

## Ports e Adapters

O domínio define **ports** (interfaces). A infraestrutura implementa.

```java
// application/.../port/PedidoRepositoryPort.java
public interface PedidoRepositoryPort {
    Optional<Pedido> findById(PedidoId id);
    void save(Pedido pedido);
}
```

```java
// infrastructure/.../persistence/PedidoRepositoryJpaAdapter.java
@Repository
class PedidoRepositoryJpaAdapter implements PedidoRepositoryPort {
    private final PedidoJpaRepository jpa;
    private final PedidoJpaMapper mapper;

    @Override public Optional<Pedido> findById(PedidoId id) {
        return jpa.findById(id.value()).map(mapper::toDomain);
    }

    @Override public void save(Pedido pedido) {
        jpa.save(mapper.toEntity(pedido));
    }
}
```

Regras:
- **Um adapter por tecnologia.** JPA e S3 não misturam no mesmo adapter.
- **Mapper explícito** entre Domain Entity e JPA Entity. Não use `@Entity` em `domain/`.
- **ArchUnit** valida que `domain/` não importa `application/` e que `application/` não importa `infrastructure/`.

## Use Cases (application)

Um caso de uso = um Command Handler ou um Query Handler.

```java
// application/.../pedidos/command/ConfirmarPedidoCommand.java
public record ConfirmarPedidoCommand(PedidoId pedidoId) {}

// application/.../pedidos/command/ConfirmarPedidoHandler.java
public class ConfirmarPedidoHandler {
    private final PedidoRepositoryPort repo;
    private final OutboxPort outbox;

    public ConfirmarPedidoHandler(PedidoRepositoryPort repo, OutboxPort outbox) {
        this.repo = repo; this.outbox = outbox;
    }

    public void handle(ConfirmarPedidoCommand cmd) {
        Pedido pedido = repo.findById(cmd.pedidoId())
            .orElseThrow(() -> new DomainException("pedido não encontrado: " + cmd.pedidoId()));
        pedido.confirmar();
        repo.save(pedido);
        outbox.enqueue(pedido.pullEvents());
    }
}
```

**Sem anotações Spring** na classe de handler (o bean é registrado no bootstrap/infrastructure via `@Configuration`). Isso mantém `application/` puro — testa-se sem carregar contexto Spring.

## Recursos modernos Java 25 / Spring 7 alinhados com Clean Architecture

| Objetivo | Recurso moderno | Por quê |
|---|---|---|
| Testabilidade | `record` para Commands/Queries | Imutáveis, sem boilerplate, seguros entre threads |
| Exaustividade de estados | `sealed` + pattern matching | Compilador garante tratamento de todos os casos |
| I/O de adapters paralelo | `StructuredTaskScope` | Fan-out com cancelamento propagado — substitui CompletableFuture chains |
| Contexto de execução | `ScopedValue` | Correlation-id / tenant / user sem ThreadLocal leak |
| Cliente HTTP declarativo | `@HttpExchange` | Adapter de outbound sem Feign/Retrofit; parte do Spring 7 |
| Config externa | `@ConfigurationProperties` com records | Validação em construtor, imutável |
| REST error handling | `ProblemDetail` (RFC 9457) | Adapter REST produz erros padronizados |
| Testes de módulos | Spring Modulith `@ApplicationModuleTest` | Valida boundary sem subir toda a aplicação |
| Health granular | `@Health`/`HealthContributor` | Readiness checa dependências (Aurora, Outbox) |

## Injeção via construtor, sempre

Zero `@Autowired` em campo. Zero setter injection. Apenas construtor — torna dependências explícitas e força design testável.

```java
@Configuration
class ApplicationConfig {

    @Bean ConfirmarPedidoHandler confirmarPedidoHandler(
        PedidoRepositoryPort repo, OutboxPort outbox
    ) {
        return new ConfirmarPedidoHandler(repo, outbox);
    }
}
```

Handler em `application/` não sabe nada de Spring. `@Configuration` em `bootstrap/` ou `infrastructure/config/` faz o wiring.

## ArchUnit — regras vivas

Salvar em `domain/src/test/java/.../CleanArchitectureTest.java` ou módulo dedicado:

```java
@AnalyzeClasses(packages = "com.example.pedidos", importOptions = ImportOption.DoNotIncludeTests.class)
class CleanArchitectureTest {

    @ArchTest
    static final ArchRule dominioNaoDependeDeFramework =
        noClasses().that().resideInAPackage("..domain..")
            .should().dependOnClassesThat().resideInAnyPackage(
                "jakarta..", "org.springframework..", "org.hibernate..",
                "com.fasterxml.jackson..", "software.amazon..", "org.apache.http.."
            );

    @ArchTest
    static final ArchRule applicationNaoConheceInfraestrutura =
        noClasses().that().resideInAPackage("..application..")
            .should().dependOnClassesThat().resideInAPackage("..infrastructure..");

    @ArchTest
    static final ArchRule arquiteturaEmCamadas =
        layeredArchitecture().consideringAllDependencies()
            .layer("Domain").definedBy("..domain..")
            .layer("Application").definedBy("..application..")
            .layer("Infrastructure").definedBy("..infrastructure..")
            .layer("Bootstrap").definedBy("..bootstrap..")
            .whereLayer("Domain").mayOnlyBeAccessedByLayers("Application", "Infrastructure", "Bootstrap")
            .whereLayer("Application").mayOnlyBeAccessedByLayers("Infrastructure", "Bootstrap")
            .whereLayer("Infrastructure").mayOnlyBeAccessedByLayers("Bootstrap");

    @ArchTest
    static final ArchRule naoUsarThreadLocal =
        noClasses().should().dependOnClassesThat()
            .haveFullyQualifiedName("java.lang.ThreadLocal");
}
```

## Benefícios práticos

- **Testabilidade**: unit test de domínio roda em < 50ms total; não carrega Spring.
- **Portabilidade**: trocar Aurora por outro Postgres é apenas um adapter.
- **Onboarding**: novo dev entende o domínio em < 10 min abrindo `domain/`.
- **Refactor seguro**: ArchUnit falha o CI se alguém quebrar o boundary.
