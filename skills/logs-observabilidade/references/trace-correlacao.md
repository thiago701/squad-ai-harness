# logs-observabilidade · reference — Trace, correlação e propagação de contexto

> Hub: `../SKILL.md`. Regras: LOG-22, LOG-26. Skills irmãs: `dd-apm`, `datadog-lambda-java`, `trace2local`
> (observabilidade local), `java25-spring-boot` (Virtual Threads/ScopedValue). Objetivo: **todo log de uma
> requisição carrega os mesmos identificadores** — sem isso a busca vira arqueologia.

## 1. Identificadores: o que cada um é

| Identificador | Formato | Quem gera | Onde vive no log |
|---|---|---|---|
| `trace_id` (W3C) | 32 hex (16 bytes), em `traceparent: 00-<trace>-<span>-01` | tracer (OTel/Micrometer/dd-trace) | `trace_id` / `dd.trace_id` (128-bit: 32 hex) |
| `span_id` | 16 hex | tracer | `span_id` / `dd.span_id` |
| `X-Amzn-Trace-Id` | `Root=1-5759e988-bd862e3f…;Parent=…;Sampled=1` | API Gateway/ALB/X-Ray | Powertools `xray_trace_id` (env `_X_AMZN_TRACE_ID`) |
| `correlation_id` / `X-Request-ID` | opaco (UUID) — **sem padrão W3C** | borda (API Gateway `requestContext.requestId`, filtro) | `correlation_id`; Datadog `http.request_id` |
| ids de negócio | `pedido_id`, `cliente_id` | domínio | campos próprios |

Regras: (1) **aceite** `traceparent` de entrada só de chamadores confiáveis — `X-Amzn-Trace-Id` de requisição externa
não autenticada deve ser **descartado** (recomendação de segurança da AWS); (2) gere `correlation_id` na borda
se não vier (`UUID.randomUUID()`), devolva-o no header de resposta e **propague** em toda chamada de saída
(HTTP, SQS `MessageAttributes`, EventBridge `detail`); (3) logs **não** são amostrados pelo tracer — mantenha
`trace_id` no log mesmo em trace não amostrado (`management.tracing.sampling.probability=0.1` amostra spans,
não logs); (4) nunca gere trace_id novo no meio do fluxo.

## 2. Spring Boot 4 + Micrometer Tracing (ECS/EKS)

```xml
<dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-opentelemetry</artifactId></dependency>
```
```yaml
management:
  tracing:
    sampling.probability: 0.1              # spans; logs continuam 100 %
    propagation: {produce: W3C, consume: [W3C, B3, B3_MULTI]}
    baggage:
      correlation.enabled: true
      correlation.fields: [correlation_id, tenant_id]   # baggage → MDC automaticamente
      remote-fields: [correlation_id, tenant_id]        # propaga em headers de saída
logging:
  pattern.correlation: "[${spring.application.name:},%X{traceId:-},%X{spanId:-},%X{correlation_id:-}] "
  include-application-name: false
```

- O MDC recebe `traceId`/`spanId` via `Slf4JEventListener` e os campos de baggage via `Slf4JBaggageEventListener`;
  com `logging.structured.format.console=ecs|logstash` eles saem como campos JSON.
- Sem span em escopo não há baggage: em workers/listeners crie o span (`@Observed`/`Tracer.nextSpan()`).
- OTel→Zipkin está deprecated (removido em 4.2); OTLP é o caminho.

## 3. MDC × Virtual Threads × async (LOG-26) — o buraco clássico

O MDC do Logback é **ThreadLocal**: "a child thread does not automatically inherit a copy of the mapped diagnostic
context of its parent". Com `spring.threads.virtual.enabled=true`, `CompletableFuture`, `@Async`, executors e
`StructuredTaskScope`, o log da tarefa filha sai **sem** `trace_id`/`correlation_id` — e ninguém percebe até o incidente.

```java
// ERRADO: contexto perdido
CompletableFuture.supplyAsync(() -> { log.info("pedido.enriquecido"); return x; });

// CERTO 1 — copiar MDC explicitamente
var ctx = MDC.getCopyOfContextMap();
CompletableFuture.supplyAsync(() -> { MDC.setContextMap(ctx); try { log.info("pedido.enriquecido"); return x; } finally { MDC.clear(); } }, executor);

// CERTO 2 — Micrometer context-propagation (cobre MDC + tracing + baggage)
ContextSnapshot snapshot = ContextSnapshotFactory.builder().build().captureAll();
executor.submit(snapshot.wrap(() -> log.info("pedido.enriquecido")));
// Spring: TaskDecorator que faz o mesmo em todo @Async/TaskExecutor

// CERTO 3 — Java 25 (JEP 506): ScopedValue para o contexto de negócio, MDC só na borda
static final ScopedValue<Contexto> CTX = ScopedValue.newInstance();
ScopedValue.where(CTX, new Contexto(correlationId, tenantId)).run(() -> {
    try (var scope = StructuredTaskScope.open()) {        // subtasks HERDAM ScopedValue (não ForkJoinPool)
        scope.fork(() -> enriquecer());
        scope.join();
    }
});
```

Regras: `MDC.put` sempre com `MDC.remove`/`MDC.clear` em `finally` (ou `MDC.putCloseable`); no Lambda
`@Logging(clearState=true)`; `ScopedValue` é **imutável e com escopo** — resolve a herança cara do ThreadLocal com
milhares de virtual threads, mas **não alimenta o MDC** sozinho: o logger precisa ler `CTX.get()` (converter custom
ou `addKeyValue` na borda). Evite `synchronized` em volta de I/O com VT (pinning) — `java25-spring-boot`.

## 4. OpenTelemetry Logs (appender) e Lambda AOT

```xml
<appender name="OTEL" class="io.opentelemetry.instrumentation.logback.appender.v1_0.OpenTelemetryAppender">
  <captureCodeAttributes>false</captureCodeAttributes>      <!-- overhead; ligue só em debug -->
  <captureMdcAttributes>*</captureMdcAttributes>
  <captureKeyValuePairAttributes>true</captureKeyValuePairAttributes>
</appender>
```
`OpenTelemetryAppender.install(openTelemetrySdk)` no startup; KV pairs SLF4J 2.x e `StructuredArguments` viram
atributos; `exception.type/message/stacktrace` seguem as semantic conventions. No GraalVM native sem agente, é
assim (ou `datadog-lambda-java` modo B) que `trace_id` chega ao log.

## 5. Python

```python
import contextvars, logging
correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="-")

class ContextoFilter(logging.Filter):
    def filter(self, record):              # threads e asyncio preservam contextvars
        record.correlation_id = correlation_id.get()
        return True
```
Lambda: Powertools `correlation_id_path=correlation_paths.API_GATEWAY_REST` e `logger.set_correlation_id(...)`;
OTel Python: `opentelemetry-instrumentation-logging` injeta `otelTraceID`/`otelSpanID` no `LogRecord`.

## 6. Checklist de correlação (review)

- [ ] Todo log da requisição tem `trace_id`+`span_id` **e** `correlation_id` (LOG-22) — teste: grep do id no log de
  cada serviço do fluxo.
- [ ] `correlation_id` gerado na borda, devolvido na resposta, propagado em HTTP/SQS/EventBridge.
- [ ] Tarefas assíncronas/VT/`@Async`/`StructuredTaskScope` carregam o contexto (LOG-26) — teste unitário que loga
  dentro do fork e assere o MDC.
- [ ] `MDC.remove`/`clear` em `finally`; Lambda com `clearState=true`.
- [ ] Headers de trace de entrada não confiáveis descartados na borda pública.
- [ ] Sampling de spans não reduz logs; DEBUG amostrado por `samplingRate`, não por sampler de trace.

## Fontes

- W3C Trace Context: https://www.w3.org/TR/trace-context/ · X-Ray tracing header: https://docs.aws.amazon.com/xray/latest/devguide/xray-concepts.html#xray-concepts-tracingheader
- Spring Boot 4 tracing: https://docs.spring.io/spring-boot/4.0/reference/actuator/tracing.html · Micrometer Tracing API: https://docs.micrometer.io/tracing/reference/api · context-propagation: https://docs.micrometer.io/context-propagation/reference/1.2/usage.html
- Logback MDC: https://logback.qos.ch/manual/mdc.html · JEP 506 Scoped Values: https://openjdk.org/jeps/506
- OTel Logback appender: https://github.com/open-telemetry/opentelemetry-java-instrumentation/blob/main/instrumentation/logback/logback-appender-1.0/library/README.md · Sampling: https://opentelemetry.io/docs/concepts/sampling/
- Python logging cookbook (contextvars/filters): https://docs.python.org/3/howto/logging-cookbook.html
