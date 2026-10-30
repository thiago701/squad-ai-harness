# Project Generator — scripts/generate_project.py

## Para que serve

Materializar o esqueleto de um projeto Java 25 + Spring Boot 4 seguindo os padrões da squad: Maven 4 multi-module, Clean Architecture, CQRS + Outbox, DDD forte, Aurora PostgreSQL, Testcontainers.

## Uso

```bash
python .agent/skills/squad-ai/scripts/generate_project.py \
    --name pedidos-api \
    --group-id com.example \
    --base-package com.example.pedidos \
    --contexts "pedidos,pagamentos" \
    --java-version 25 \
    --output ./
```

### Parâmetros

| Flag | Obrigatório | Descrição |
|---|---|---|
| `--name` | sim | artifactId Maven e nome do diretório raiz |
| `--group-id` | sim | groupId Maven (ex: `com.example`) |
| `--base-package` | sim | pacote raiz Java (ex: `com.example.pedidos`) |
| `--contexts` | sim | bounded contexts separados por vírgula |
| `--java-version` | não (default `25`) | versão do JDK (25 recomendado) |
| `--output` | não (default `.`) | onde criar o diretório do projeto |
| `--with-example-aggregate` | não (default `true`) | se `true`, gera um Aggregate Root exemplo em cada contexto |
| `--db` | não (default `postgres-16`) | imagem Postgres para docker-compose e Testcontainers |

## O que é gerado

```
<name>/
├── pom.xml                             ← agregador Maven 4 (model 4.1.0)
├── .mvn/maven.config                   ← -T 1C, --no-transfer-progress
├── .gitignore
├── README.md                           ← runbook, comandos, estrutura
├── Dockerfile                          ← multi-stage JDK 25 → JRE slim
├── docker-compose.yml                  ← app + postgres:16
├── .env.example
├── .github/workflows/ci.yml            ← build + tests + ArchUnit + jacoco
│
├── domain/
│   ├── pom.xml                         ← sem Spring, sem Hibernate
│   └── src/
│       ├── main/java/<base-package>/domain/
│       │   ├── common/
│       │   │   ├── DomainException.java
│       │   │   ├── DomainEvent.java
│       │   │   └── vo/Money.java
│       │   └── <ctx>/                  ← um por bounded context
│       │       ├── model/<Aggregate>.java  (se with-example-aggregate)
│       │       ├── vo/                     (VOs exemplo: <Aggregate>Id)
│       │       └── event/<Aggregate>Event.java
│       └── test/java/<base-package>/domain/
│           ├── common/vo/MoneyTest.java
│           └── <ctx>/model/<Aggregate>Test.java
│
├── application/
│   ├── pom.xml                         ← depende de domain
│   └── src/
│       ├── main/java/<base-package>/application/
│       │   └── <ctx>/
│       │       ├── command/             ← Command record + Handler POJO
│       │       ├── query/               ← Query record + Handler POJO
│       │       └── port/                ← Repository/Outbox ports
│       └── test/java/<base-package>/application/
│           └── <ctx>/ *HandlerTest.java  ← Mockito em ports
│
├── infrastructure/
│   ├── pom.xml                         ← Spring Data, JPA, Jackson, Postgres driver
│   └── src/
│       ├── main/java/<base-package>/infrastructure/
│       │   ├── persistence/
│       │   │   ├── <ctx>/<Aggregate>JpaEntity.java
│       │   │   ├── <ctx>/<Aggregate>JpaRepository.java
│       │   │   ├── <ctx>/<Aggregate>RepositoryAdapter.java
│       │   │   └── <ctx>/<Aggregate>Mapper.java
│       │   ├── outbox/
│       │   │   ├── OutboxEventEntity.java
│       │   │   ├── OutboxEventJpaRepository.java
│       │   │   ├── OutboxJpaAdapter.java
│       │   │   └── OutboxPollerRelay.java
│       │   ├── rest/
│       │   │   ├── GlobalExceptionHandler.java    ← ProblemDetail RFC 9457
│       │   │   ├── CorrelationFilter.java         ← ScopedValue
│       │   │   └── <ctx>/<Aggregate>Controller.java
│       │   └── config/
│       │       ├── ApplicationWiring.java         ← @Configuration
│       │       └── VirtualThreadsConfig.java
│       ├── main/resources/db/migration/
│       │   ├── V1__init_schema.sql                ← gerado do DBML se fornecido
│       │   └── V2__outbox.sql
│       └── test/java/<base-package>/infrastructure/
│           ├── persistence/ *IntegrationTest.java  ← Testcontainers
│           ├── outbox/OutboxIntegrationTest.java   ← Testcontainers
│           └── arch/CleanArchitectureTest.java     ← ArchUnit
│
└── bootstrap/
    ├── pom.xml                         ← depende de infrastructure
    └── src/
        ├── main/java/<base-package>/
        │   ├── Application.java
        │   └── config/                 ← beans globais se precisar
        ├── main/resources/
        │   ├── application.yml         ← profile default
        │   ├── application-dev.yml     ← docker-compose local
        │   ├── application-prod.yml    ← Aurora via env
        │   └── logback-spring.xml      ← JSON com correlationId
        └── test/java/<base-package>/
            └── ApplicationTest.java     ← contextLoads smoke test
```

## Padrões aplicados automaticamente

- **Java 25** com `--enable-preview` desligado por default (só features finais).
- **Spring Boot 4 BOM** importado no parent; versões gerenciadas.
- **Spring 7** via Spring Boot 4.
- **Virtual Threads** habilitado em `application.yml` (`spring.threads.virtual.enabled=true`).
- **ZGC Generational** no Dockerfile.
- **Bean Validation** habilitado em controllers.
- **ProblemDetail (RFC 9457)** no GlobalExceptionHandler.
- **Correlation-id via ScopedValue** (filter + MDC).
- **Outbox** com tabela + poller + idempotência.
- **Flyway** com `ddl-auto: validate` e migrations versionadas.
- **ArchUnit** com 4+ regras ligadas ao CI.
- **Testcontainers** configurado com `@ServiceConnection`.

## Pré-condições

- Python 3.10+
- Sem dependência de pasta de template versionada: o scaffold `java25-cqrs-clean` é **gerado** por este procedimento (materializado em tempo de geração, conforme `SKILL.md`).

## Extensões futuras (backlog)

- `--outbox-relay=debezium` — gera conector Debezium em vez de poller.
- `--auth=oidc` — adiciona Spring Security + Resource Server OIDC.
- `--graalvm` — adiciona profile `native` com hints.
- `--modulith` — adiciona Spring Modulith e `@ApplicationModuleTest`.
