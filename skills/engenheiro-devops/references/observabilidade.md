# Referência — Observabilidade (logs, métricas, health probes, DORA, dependency auditing)

> Parte da skill `engenheiro-devops`. Carregue sob demanda. Hub: `../SKILL.md`.
## Observabilidade — Stack Mínima

### Correlation ID Propagation — End-to-End (GLOSSARIO §3)

**Referência canônica:** GLOSSARIO.md §3 — Correlation ID. A seguir, implementação completa em Java 25 + Spring Boot 4 com propagação por HTTP, SQS, SNS e OpenTelemetry.

**Fluxo fim a fim:**

```
HTTP Request → Filter (extrai/cria UUID)
    ↓
ScopedValue + MDC bind
    ↓
Logs JSON (correlationId incluído automaticamente)
    ↓
Egress HTTP (RestClient + @HttpExchange propaga header)
Egress SQS (messageAttribute contém correlationId)
Egress SNS (messageAttribute contém correlationId)
    ↓
Downstream services recebem e rebind ScopedValue
    ↓
OpenTelemetry Span com atributo correlation.id
```

#### Implementação: CorrelationIdFilter (Servlet Filter)

```java
// com.example.core.correlation.CorrelationIdContext
package com.example.core.correlation;

import java.util.UUID;

public final class CorrelationIdContext {

    public static final ScopedValue<String> CORRELATION_ID = ScopedValue.newInstance();

    private CorrelationIdContext() {}

    public static String currentOrNew() {
        return CORRELATION_ID.isBound()
                ? CORRELATION_ID.get()
                : UUID.randomUUID().toString();
    }

    public static String get() {
        return CORRELATION_ID.isBound()
                ? CORRELATION_ID.get()
                : throw new IllegalStateException("correlationId not bound");
    }
}
```

```java
// com.example.adapter.in.http.CorrelationIdFilter
package com.example.adapter.in.http;

import com.example.core.correlation.CorrelationIdContext;
import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.MDC;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.Optional;
import java.util.UUID;

@Component
public class CorrelationIdFilter implements Filter {

    public static final String HEADER = "X-Correlation-Id";

    @Override
    public void doFilter(ServletRequest req, ServletResponse res, FilterChain chain)
            throws IOException, ServletException {

        HttpServletRequest http = (HttpServletRequest) req;
        HttpServletResponse httpRes = (HttpServletResponse) res;

        // 1. Extrair correlationId do header ou gerar novo UUID
        String correlationId = Optional.ofNullable(http.getHeader(HEADER))
                .orElseGet(() -> UUID.randomUUID().toString());

        // 2. Propagar no response header
        httpRes.setHeader(HEADER, correlationId);

        // 3. Bind em ScopedValue + MDC para toda a request
        try (var mdc = MDC.putCloseable("correlationId", correlationId)) {
            ScopedValue.where(CorrelationIdContext.CORRELATION_ID, correlationId)
                    .run(() -> {
                        try {
                            chain.doFilter(req, res);
                        } catch (Exception e) {
                            throw new RuntimeException(e);
                        }
                    });
        }
    }

    @Override
    public void init(FilterConfig config) {
        // noop
    }

    @Override
    public void destroy() {
        // noop
    }
}
```

#### Implementação: RestClient Interceptor (HTTP Egress)

```java
// com.example.adapter.out.client.CorrelationIdClientInterceptor
package com.example.adapter.out.client;

import com.example.core.correlation.CorrelationIdContext;
import org.springframework.http.HttpRequest;
import org.springframework.http.client.ClientHttpRequestExecution;
import org.springframework.http.client.ClientHttpRequestInterceptor;
import org.springframework.http.client.ClientHttpResponse;

import java.io.IOException;

public class CorrelationIdClientInterceptor implements ClientHttpRequestInterceptor {

    private static final String HEADER = "X-Correlation-Id";

    @Override
    public ClientHttpResponse intercept(HttpRequest request, byte[] body,
            ClientHttpRequestExecution execution) throws IOException {

        // Propagar correlationId em chamadas outbound
        String correlationId = CorrelationIdContext.currentOrNew();
        request.getHeaders().set(HEADER, correlationId);

        return execution.execute(request, body);
    }
}
```

```java
// Registrar interceptor no RestClient (Spring Boot 4 convention)
@Configuration
public class HttpClientConfig {

    @Bean
    public RestClient restClient() {
        return RestClient.builder()
                .requestInterceptor(new CorrelationIdClientInterceptor())
                .build();
    }
}
```

#### Implementação: SQS Send (AWS SDK v2)

```java
// com.example.adapter.out.messaging.SqsPublisher
package com.example.adapter.out.messaging;

import com.example.core.correlation.CorrelationIdContext;
import software.amazon.awssdk.services.sqs.SqsAsyncClient;
import software.amazon.awssdk.services.sqs.model.MessageAttributeValue;
import software.amazon.awssdk.services.sqs.model.SendMessageRequest;
import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.Map;

@Component
public class SqsPublisher {

    private final SqsAsyncClient sqsClient;

    public SqsPublisher(SqsAsyncClient sqsClient) {
        this.sqsClient = sqsClient;
    }

    public void publish(String queueUrl, String messageBody) {
        String correlationId = CorrelationIdContext.currentOrNew();

        Map<String, MessageAttributeValue> attributes = new HashMap<>();
        attributes.put("correlationId", MessageAttributeValue.builder()
                .dataType("String")
                .stringValue(correlationId)
                .build());

        SendMessageRequest request = SendMessageRequest.builder()
                .queueUrl(queueUrl)
                .messageBody(messageBody)
                .messageAttributes(attributes)
                .build();

        sqsClient.sendMessage(request);
    }
}
```

#### Implementação: SQS Consumer (@SqsListener)

```java
// com.example.adapter.in.messaging.SqsConsumer
package com.example.adapter.in.messaging;

import com.example.core.correlation.CorrelationIdContext;
import io.awspring.cloud.sqs.annotation.SqsListener;
import org.slf4j.MDC;
import org.springframework.messaging.Message;
import org.springframework.stereotype.Component;

@Component
public class SqsConsumer {

    private final ProcessarPedidoUseCase processarPedidoUseCase;

    public SqsConsumer(ProcessarPedidoUseCase processarPedidoUseCase) {
        this.processarPedidoUseCase = processarPedidoUseCase;
    }

    @SqsListener("pedidos-queue")
    public void listen(Message<String> message) {
        // 1. Extrair correlationId do message attribute
        String correlationId = message.getHeaders()
                .get("correlationId", String.class);

        if (correlationId == null) {
            correlationId = java.util.UUID.randomUUID().toString();
        }

        // 2. Rebind em ScopedValue + MDC para processing
        final String finalCorrelationId = correlationId;
        try (var mdc = MDC.putCloseable("correlationId", finalCorrelationId)) {
            ScopedValue.where(CorrelationIdContext.CORRELATION_ID, finalCorrelationId)
                    .run(() -> {
                        String payload = message.getPayload();
                        processarPedidoUseCase.processar(payload);
                    });
        }
    }
}
```

#### Configuração Logback — JSON Structured Logging

```xml
<!-- resources/logback-spring.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <property name="LOG_FILE" value="${LOG_FILE:-${LOG_PATH:-${LOG_TEMP:-${java.io.tmpdir:-/tmp}}/spring.log}}"/>

  <!-- Console Appender com LogstashEncoder -->
  <appender name="CONSOLE" class="ch.qos.logback.core.ConsoleAppender">
    <encoder class="net.logstash.logback.encoder.LogstashEncoder">
      <includeContext>true</includeContext>
      <includeMdcData>true</includeMdcData>
      <includeCallerData>false</includeCallerData>
      <customFields>
        {
          "service": "pedidos-api",
          "environment": "${SPRING_PROFILES_ACTIVE:dev}",
          "version": "${project.version:dev}"
        }
      </customFields>
    </encoder>
  </appender>

  <!-- File Appender (rotação automática) -->
  <appender name="FILE" class="ch.qos.logback.core.rolling.RollingFileAppender">
    <file>${LOG_FILE}</file>
    <encoder class="net.logstash.logback.encoder.LogstashEncoder">
      <includeContext>true</includeContext>
      <includeMdcData>true</includeMdcData>
      <customFields>{"service": "pedidos-api"}</customFields>
    </encoder>
    <rollingPolicy class="ch.qos.logback.core.rolling.SizeAndTimeBasedRollingPolicy">
      <fileNamePattern>${LOG_PATH}/spring-%d{yyyy-MM-dd}.%i.log</fileNamePattern>
      <maxFileSize>10MB</maxFileSize>
      <maxHistory>7</maxHistory>
    </rollingPolicy>
  </appender>

  <!-- Root logger -->
  <root level="INFO">
    <appender-ref ref="CONSOLE"/>
    <appender-ref ref="FILE"/>
  </root>

  <!-- Framework loggers (verbosity control) -->
  <logger name="org.springframework" level="INFO"/>
  <logger name="org.springframework.web" level="DEBUG"/>
  <logger name="org.hibernate" level="WARN"/>
</configuration>
```

```xml
<!-- pom.xml — dependências para Correlation ID + Logging -->
<dependency>
    <groupId>net.logstash.logback</groupId>
    <artifactId>logstash-logback-encoder</artifactId>
    <version>8.0</version>
</dependency>

<!-- OpenTelemetry Java Instrumentation (opcional) -->
<dependency>
    <groupId>io.opentelemetry.instrumentation</groupId>
    <artifactId>opentelemetry-instrumentation-bom</artifactId>
    <version>2.0.0</version>
    <type>pom</type>
    <scope>import</scope>
</dependency>
```

#### Prometheus Alert: Falha de Propagação de Correlation ID

```yaml
# prometheus/rules.yml — detectar requests sem correlationId
groups:
- name: observability
  rules:
  - alert: CorrelationIdMissing
    expr: |
      (increase(http_requests_without_correlation_id_total[5m]) / 
       increase(http_server_requests_total[5m])) > 0.001
    for: 5m
    annotations:
      summary: "Mais de 0.1% de requests sem correlationId"
      description: "{{ $value | humanizePercentage }} de requests não têm X-Correlation-Id"
      severity: "warning"
```

```java
// Métrica customizada no controller base
@RestController
public class BaseController {

    private final MeterRegistry meterRegistry;

    @PostConstruct
    void registerMetrics() {
        Counter.builder("http.requests.without_correlation_id.total")
                .description("Requests recebidas sem X-Correlation-Id header")
                .register(meterRegistry);
    }

    protected void validateCorrelationId(HttpServletRequest request) {
        String correlationId = request.getHeader("X-Correlation-Id");
        if (correlationId == null || correlationId.isBlank()) {
            meterRegistry.counter("http.requests.without_correlation_id.total").increment();
        }
    }
}
```

#### Checklist: Correlation ID End-to-End

- ✅ `CorrelationIdFilter` extrai/cria UUID no ingress HTTP
- ✅ UUID propagado em response header `X-Correlation-Id`
- ✅ ScopedValue + MDC bind em toda a request
- ✅ RestClient interceptor injeta header em egress HTTP
- ✅ SQS send inclui `messageAttribute` com `correlationId`
- ✅ SQS consumer rebind ScopedValue antes de processar
- ✅ Logback LogstashEncoder inclui `%X{correlationId}` em JSON
- ✅ OpenTelemetry span incluido `correlation.id` como atributo
- ✅ Prometheus metric para falha de propagação (> 0.1%)
- ✅ Testes: validar propagação em cadeia HTTP → SQS → Downstream

---

### Logs Estruturados

```java
// Java — Spring Boot com Logback JSON
// logback-spring.xml com LogstashEncoder
// Todos os logs incluem correlationId automaticamente via MDC
log.info("Pedido confirmado", Map.of(
    "pedido_id", pedidoId,
    "operador", operadorId,
    "latencia_ms", elapsed
));

// Output (JSON):
// {
//   "timestamp": "2026-04-10T15:30:45.123Z",
//   "level": "INFO",
//   "message": "Pedido confirmado",
//   "correlationId": "550e8400-e29b-41d4-a716-446655440000",
//   "pedido_id": 12345,
//   "operador": "user@example.com",
//   "latencia_ms": 234,
//   "service": "pedidos-api"
// }
```

```python
# Python — structlog (propagação de correlation ID via contextvars)
import structlog
from contextvars import ContextVar

correlation_id_var = ContextVar('correlation_id', default=None)

logger = structlog.get_logger()

def log_with_correlation():
    logger.info("pedido_confirmado",
        pedido_id=pedido_id,
        operador=operador_id,
        latencia_ms=elapsed,
        correlation_id=correlation_id_var.get()
    )
```

### Health Check Endpoint

Todo serviço deve expor `/health` ou `/actuator/health` com:
- Status do banco de dados
- Status de serviços externos críticos
- Versão do build (commit SHA)

### Métricas (Micrometer / Prometheus)

```
# Métricas obrigatórias:
http_server_requests_seconds (p50, p95, p99)
jvm_memory_used_bytes (Java)
process_resident_memory_bytes (Python)
db_pool_active_connections
custom_pedidos_confirmados_total (métricas de negócio)
```

### Dependency Auditing Pipeline — Ferramenta Integrada

> Conteúdo integral movido verbatim para `dependency-auditing.md` (mesma pasta): OWASP Dependency-Check
> Maven plugin + suppressions, SLA de patch por severidade CVSS, governo de bypasses com ADR expirável,
> workflow GitHub Actions (Dependency-Check + Trivy + SARIF + alerta Slack), dependabot.yml e checklist.
> Carregue aquele arquivo quando o problema for vulnerabilidade/atualização de dependências.

---

### DORA Metrics — Coleta Automatizada com GitHub Actions

As 4 métricas DORA medem a efetividade do time de engenharia. **Definições, armadilhas de medição e a
consulta oficial commit → deploy estão em `references/dora-metrics.md`** (I17, 11/10/2026) — esta seção
guarda só a coleta de eventos. Os limiares das faixas Elite/High/Medium/Low **mudam entre edições do
Accelerate State of DevOps Report (DORA/Google Cloud)** e não ficam aqui: leia-os na edição citada e
registre (relatório, editor, ano, página) em `docs/dora-baseline.md`.

| Métrica | O que mede | Faixa |
|---|---|---|
| **Deployment Frequency** | deploys bem-sucedidos em produção, por serviço, por período | <ler na edição citada> |
| **Lead Time for Changes** | commit → esse commit servindo tráfego em produção | <ler na edição citada> |
| **Change Failure Rate** | deploys que exigiram rollback/hotfix/incidente ÷ deploys que serviram tráfego | <ler na edição citada> |
| **Time to Restore / Failed Deployment Recovery Time** | detecção → serviço restaurado | <ler na edição citada> |

> O workflow abaixo coleta **eventos** (execuções de deploy e rollbacks). O "lead time" que ele imprime é a
> idade da execução de deploy (`now − created_at`), **não** commit → deploy — serve de sinal, não de número
> oficial. O número oficial sai da consulta de `references/dora-metrics.md § Consulta de exemplo`.

```yaml
# .github/workflows/dora-metrics.yml
name: DORA Metrics Collection
on:
  workflow_run:
    workflows: ["Deploy to Production"]
    types: [completed]
  schedule:
    - cron: '0 8 * * 1'    # Relatório semanal às segundas 8h

jobs:
  collect-metrics:
    runs-on: ubuntu-latest
    steps:
      - name: Deployment Frequency
        run: |
          DEPLOYS=$(gh run list --workflow deploy.yml --status success \
            --created ">=$(date -d '7 days ago' +%Y-%m-%d)" --json conclusion -q length)
          echo "DEPLOY_FREQUENCY=$DEPLOYS" >> $GITHUB_ENV

      - name: Lead Time for Changes
        run: |
          # Tempo médio entre merge na main e deploy em produção
          LEAD_TIME=$(gh api repos/${{ github.repository }}/actions/runs \
            --jq '[.workflow_runs[] | select(.name=="Deploy to Production" and .conclusion=="success")
            | .created_at] | map(now - fromdate) | add / length / 3600')
          echo "LEAD_TIME_HOURS=$LEAD_TIME" >> $GITHUB_ENV

      - name: Change Failure Rate
        run: |
          TOTAL=$(gh run list --workflow deploy.yml --created ">=$(date -d '30 days ago' +%Y-%m-%d)" --json conclusion -q length)
          FAILURES=$(gh run list --workflow rollback.yml --created ">=$(date -d '30 days ago' +%Y-%m-%d)" --json conclusion -q length)
          RATE=$(echo "scale=1; $FAILURES * 100 / $TOTAL" | bc 2>/dev/null || echo "0")
          echo "CHANGE_FAILURE_RATE=$RATE%" >> $GITHUB_ENV

      - name: Publish metrics
        run: |
          echo "## DORA Metrics ($(date +%Y-%m-%d))" >> $GITHUB_STEP_SUMMARY
          echo "| Metric | Value | Target |" >> $GITHUB_STEP_SUMMARY
          echo "|--------|-------|--------|" >> $GITHUB_STEP_SUMMARY
          echo "| Deploy Frequency (7d) | $DEPLOY_FREQUENCY | ≥5/semana |" >> $GITHUB_STEP_SUMMARY
          echo "| Idade da execução de deploy (sinal, não lead time) | ${LEAD_TIME_HOURS}h | ver dora-metrics.md |" >> $GITHUB_STEP_SUMMARY
          echo "| Change Failure Rate (30d) | $CHANGE_FAILURE_RATE | meta = baseline próprio |" >> $GITHUB_STEP_SUMMARY
```

**Checklist DORA:**
- ✅ Deployment Frequency coletado via `gh run list`
- ✅ Lead Time calculado commit → deploy pela consulta de `references/dora-metrics.md` (o workflow acima só dá a idade da execução)
- ✅ Change Failure Rate = rollbacks / total deploys (30 dias)
- ✅ MTTR coletado via integração com PagerDuty/Opsgenie (quando aplicável)
- ✅ Relatório semanal publicado no GitHub Step Summary
- ✅ Alertar quando a métrica cai abaixo do baseline próprio (≥ 4 semanas medidas), nunca de um limiar de memória

---

### Health Probes e Graceful Shutdown — Obrigatórios para Cloud Native

> Conteúdo integral movido verbatim para `health-probes-graceful-shutdown.md` (mesma pasta): config
> mínima Spring Boot 4, liveness vs readiness vs startup (semântica GLOSSARIO §4), health check
> ECS/K8s, fórmula de `initialDelaySeconds`, troubleshooting CrashLoopBackOff 137, Deployment completo
> com 3 probes, graceful shutdown em 3 fases (GLOSSARIO §5) com K8s/ECS e checklists. Carregue aquele
> arquivo quando o problema for probe/zero-downtime/shutdown.

---

