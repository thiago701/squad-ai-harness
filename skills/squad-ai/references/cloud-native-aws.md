# Cloud Native + AWS (Aurora PostgreSQL default)

## Princípios 12-factor aplicados

| Factor | Como aplicar em Spring Boot 4 |
|---|---|
| I. Codebase | Um repositório, muitos deploys via tag/imagem |
| II. Dependencies | `pom.xml` explícito, Maven 4 com consumer POM |
| III. Config | `application.yml` sem valores sensíveis; tudo via env / SSM / Secrets Manager |
| IV. Backing services | Aurora, SQS, S3 como recursos anexos (URLs via env) |
| V. Build, release, run | CI produz imagem imutável; release tagueada; run lê config em runtime |
| VI. Processes | Stateless. Sessão zero; cache distribuído se necessário |
| VII. Port binding | Tomcat embutido; sem servidor externo |
| VIII. Concurrency | Virtual Threads para I/O; scale horizontal |
| IX. Disposability | Startup rápido, graceful shutdown |
| X. Dev/prod parity | docker-compose em dev reproduz prod (Aurora → Postgres 16 local) |
| XI. Logs | stdout JSON estruturado; agregador faz o resto |
| XII. Admin processes | Migration via Flyway no boot |

## Aurora PostgreSQL como default

### application.yml (perfil prod)

```yaml
spring:
  datasource:
    url: jdbc:postgresql://${DB_HOST}:${DB_PORT:5432}/${DB_NAME}
    username: ${DB_USER}
    password: ${DB_PASSWORD}
    hikari:
      maximum-pool-size: ${DB_POOL_MAX:20}
      minimum-idle: ${DB_POOL_MIN:5}
      connection-timeout: 5000
      max-lifetime: 1800000  # < Aurora's max idle
  jpa:
    hibernate:
      ddl-auto: validate   # Flyway controla schema
    properties:
      hibernate.jdbc.batch_size: 50
      hibernate.order_inserts: true
      hibernate.order_updates: true
  flyway:
    enabled: true
    baseline-on-migrate: false
  threads:
    virtual:
      enabled: true
  lifecycle:
    timeout-per-shutdown-phase: 30s
```

### Aurora-specific recomendações

- **Aurora Serverless v2** para workloads irregulares — escala ACUs automaticamente.
- **IAM authentication** quando possível (sem senha em env).
- **Read replicas** para queries pesadas — rote via segundo `DataSource` anotado com `@Qualifier("readOnly")` e use em `@Transactional(readOnly = true)`.
- **RDS Proxy** em cenários com muitas instâncias curtas (Lambda, Fargate spot) — evita thundering herd de conexões.
- **Pool HikariCP**: `max-lifetime` < timeout do Aurora; monitore `hikaricp.connections.acquire` via Micrometer.

## Dockerfile multi-stage

```dockerfile
# syntax=docker/dockerfile:1.7
FROM eclipse-temurin:25-jdk AS build
WORKDIR /src
COPY . .
RUN --mount=type=cache,target=/root/.m2 ./mvnw -T 1C -q -DskipTests package

FROM eclipse-temurin:25-jre AS runtime
RUN groupadd -r app && useradd -r -g app app
WORKDIR /app
COPY --from=build /src/bootstrap/target/bootstrap-*.jar app.jar
USER app
EXPOSE 8080
ENV JAVA_TOOL_OPTIONS="-XX:+UseZGC -XX:+ZGenerational \
    -Xms512m -Xmx1024m \
    -Dspring.profiles.active=prod"
ENTRYPOINT ["java","-jar","/app/app.jar"]
```

**ZGC Generational** (Java 25 padrão) — pausas sub-milissegundo até heaps multi-GB; ideal para containers.

### Para GraalVM Native Image (startup < 100ms)

```dockerfile
FROM ghcr.io/graalvm/native-image-community:25 AS build
WORKDIR /src
COPY . .
RUN ./mvnw -T 1C -q -Pnative -DskipTests native:compile

FROM gcr.io/distroless/base-debian12
COPY --from=build /src/bootstrap/target/pedidos-api /pedidos-api
EXPOSE 8080
ENTRYPOINT ["/pedidos-api"]
```

Use native quando: funções Lambda, cold start crítico, footprint < 100 MB. Evite quando usa reflection dinâmica não configurada (prefira AOT hints do Spring AOT).

## Observabilidade

### OpenTelemetry auto-configurado

`application.yml`:

```yaml
management:
  endpoints:
    web:
      exposure:
        include: health,info,prometheus,metrics,flyway
  endpoint:
    health:
      probes:
        enabled: true
      group:
        liveness:
          include: livenessState
        readiness:
          include: readinessState,db,outbox
  tracing:
    sampling:
      probability: 1.0   # ajuste em produção
otel:
  service:
    name: pedidos-api
  exporter:
    otlp:
      endpoint: ${OTLP_ENDPOINT:http://otel-collector:4317}
```

Dependências:
```xml
<dependency>
  <groupId>io.opentelemetry.instrumentation</groupId>
  <artifactId>opentelemetry-spring-boot-starter</artifactId>
</dependency>
<dependency>
  <groupId>io.micrometer</groupId>
  <artifactId>micrometer-registry-prometheus</artifactId>
</dependency>
```

### Health indicators customizados

Readiness verifica Aurora **e** lag do outbox:

```java
@Component
class OutboxLagHealthIndicator implements HealthIndicator {
    private final OutboxEventJpaRepository repo;
    @Override public Health health() {
        long pending = repo.countUnprocessed();
        long oldest = repo.oldestPendingSeconds();
        if (oldest > 60) return Health.down().withDetail("oldestPendingSeconds", oldest).build();
        return Health.up().withDetail("pending", pending).build();
    }
}
```

### Logs estruturados JSON

`logback-spring.xml`:

```xml
<configuration>
    <appender name="JSON" class="ch.qos.logback.core.ConsoleAppender">
        <encoder class="net.logstash.logback.encoder.LogstashEncoder">
            <customFields>{"service":"pedidos-api"}</customFields>
            <includeMdcKeyName>correlationId</includeMdcKeyName>
            <includeMdcKeyName>traceId</includeMdcKeyName>
        </encoder>
    </appender>
    <root level="INFO">
        <appender-ref ref="JSON"/>
    </root>
</configuration>
```

Propague `correlationId` via MDC no filter junto com o `ScopedValue`.

## Stateless + horizontal scale

- Sessão zero (JWT ou token em cookie assinado).
- Cache: Redis/ElastiCache quando precisa compartilhar entre instâncias; `Caffeine` local OK se idempotente com TTL curto.
- Jobs agendados: use shedlock (com Aurora) ou EventBridge Scheduler — evita duplicação em múltiplas instâncias.

## Graceful shutdown

```yaml
server:
  shutdown: graceful
spring:
  lifecycle:
    timeout-per-shutdown-phase: 30s
```

Deregister do LB → drain conexões ativas → stop. Combine com readiness response falsa durante shutdown.

## Compute target (neutro no scaffold)

O scaffold entrega **Dockerfile** e **docker-compose** para dev. IaC em produção fica a critério do time:

- **ECS Fargate** — container gerenciado, boa integração com Aurora e SQS
- **App Runner** — PaaS mais simples, ideal para MVP
- **Lambda + SnapStart / GraalVM** — serverless pay-per-use, requer AOT
- **EKS** — se o time já mantém cluster

Decisão via ADR quando sair do dev.

## FinOps essencial

- Aurora Serverless v2 só se tráfego é irregular. Instâncias reservadas para carga estável.
- Métricas de custo por requisição (`cost_per_request = bill / requests`) no dashboard.
- Alertas de gasto anormal (Cost Anomaly Detection).
- Scripts para identificar queries caras (`pg_stat_statements`).

## Checklist Cloud Native (review)

```
□ Stateless (sem estado local persistente)
□ 12-factor respeitado em toda config
□ Logs JSON em stdout
□ Health liveness + readiness separados
□ OpenTelemetry configurado
□ Graceful shutdown ativo
□ Migrations versionadas via Flyway
□ Secrets fora do repositório (env / SSM / Secrets Manager)
□ TLS obrigatório (LB termina)
□ Dockerfile multi-stage; imagem ≤ 300 MB
□ User não-root no container
□ CPU/memória limites definidos (task def / deployment)
□ Observability: traces propagados entre serviços
```
