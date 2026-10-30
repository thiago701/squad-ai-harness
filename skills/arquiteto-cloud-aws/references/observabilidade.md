# Referência — Observabilidade (CloudWatch, X-Ray)

> Parte da skill `arquiteto-cloud-aws`. Carregue este arquivo sob demanda quando a tarefa tocar este eixo. Hub: `../SKILL.md`.
### Observabilidade — CloudWatch + X-Ray

```
Free tier CloudWatch:
  - 10 métricas customizadas gratuitas
  - 5GB de ingestão de logs/mês
  - 3 dashboards gratuitos
  - 10 alarmes gratuitos

Lambda Powertools (Python) e AWS X-Ray automatizam:
  ✓ Structured logging (JSON) → CloudWatch Logs
  ✓ Distributed tracing → X-Ray (rastreia Lambda + RDS + DynamoDB + SQS)
  ✓ Custom metrics → CloudWatch Metrics
  ✓ Correlation IDs automáticos entre serviços
```

```python
# Python — Lambda Powertools: observabilidade com zero boilerplate
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext

logger  = Logger(service="pedido-service")   # JSON automático, correlation ID incluído
tracer  = Tracer(service="pedido-service")   # X-Ray automático
metrics = Metrics(namespace="PedidoApp")

@logger.inject_lambda_context(correlation_id_path="requestContext.requestId")
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: dict, context: LambdaContext) -> dict:
    pedido_id = event["pathParameters"]["id"]

    logger.info("Buscando pedido", pedido_id=pedido_id)
    metrics.add_metric("BuscaPedido", MetricUnit.Count, 1)

    with tracer.provider.in_subsegment("buscar_banco"):
        pedido = pedido_repo.buscar(pedido_id)

    return {"statusCode": 200, "body": pedido.to_json()}
```

#### Java 25 — Observabilidade Distribuída com OpenTelemetry + X-Ray

```java
// Spring Boot 4 — Correlation ID propagado automaticamente via Virtual Threads + Scoped Values
// Dependência: spring-boot-starter-opentelemetry (exporta para X-Ray via OTLP)

// 1. Configuração centralizada
// application.yml
/*
management:
  tracing:
    sampling:
      probability: 1.0        # 100% em dev, 0.1 (10%) em prod
  otlp:
    tracing:
      endpoint: http://otel-collector:4318/v1/traces

logging:
  pattern:
    level: "%5p [${spring.application.name},%X{traceId},%X{spanId}]"
*/

// 2. Scoped Value para Correlation ID customizado (além do traceId do OTEL)
public final class RequestContext {
    public static final ScopedValue<String> CORRELATION_ID = ScopedValue.newInstance();
}

// 3. Filter que captura/gera correlationId e propaga via ScopedValue
@Component
public class CorrelationIdFilter extends OncePerRequestFilter {

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res,
                                     FilterChain chain) throws ServletException, IOException {
        var correlationId = Optional.ofNullable(req.getHeader("X-Correlation-ID"))
            .orElse(UUID.randomUUID().toString());
        res.setHeader("X-Correlation-ID", correlationId);

        ScopedValue.runWhere(RequestContext.CORRELATION_ID, correlationId,
            () -> { chain.doFilter(req, res); });
    }
}

// 4. Propagação para SQS — adicionar correlationId como atributo da mensagem
@Component
public class PedidoSqsPublisher {

    public void publicar(PedidoEvent evento) {
        sqsTemplate.send(to -> to
            .queue("pedidos")
            .payload(evento)
            .header("X-Correlation-ID", RequestContext.CORRELATION_ID.get())
        );
    }
}

// 5. Consumer SQS — restaurar correlationId
@SqsListener("pedidos")
public void processar(@Payload PedidoEvent evento,
                       @Header("X-Correlation-ID") String correlationId) {
    ScopedValue.runWhere(RequestContext.CORRELATION_ID, correlationId,
        () -> pedidoService.processar(evento));
}
```

```
OBSERVABILIDADE CROSS-SERVICE — Checklist:
  □ OpenTelemetry configurado em todos os serviços (spring-boot-starter-opentelemetry)
  □ X-Ray habilitado no API Gateway, Lambda, ECS (via OTEL Collector → X-Ray)
  □ Correlation ID propagado: HTTP header → SQS attribute → Lambda context
  □ Structured logging JSON com traceId e spanId em todo log
  □ Métricas de negócio: pedidos/min, latência de confirmação, taxa de erro
  □ Dashboard CloudWatch com métricas OTEL + métricas customizadas
  □ Alarmes: p99 > SLA threshold, error rate > 1%, DLQ messages > 0
```

#### X-Ray Sampling Strategy — Otimização de Custo sem Perder Observabilidade

**Por que sampling importa em produção:**

```
X-Ray cobra $0.50 por 1M traces armazenados (depois free tier 100k/mês).
Em prod com 1M requisições/dia:
  - 100% sampling     = 30M traces/mês = $15/mês (além do free tier)
  - 1% sampling       = 300k traces/mês = $0.10/mês
  - Sampling inteligente = 300k normal + 100% errors = $0.15/mês

Signal-to-noise ratio: traces de sucesso ocupam storage sem valor.
Erros 5xx e outliers (p99 latência) têm valor diagnosticado.
```

**Estratégia canônica por ambiente:**

```yaml
# Ambiente: DEV (todos os traces — debugging local)
#   sampling-rate: 100% (1.0)
#   custo: negligenciável (tráfego baixo)

# Ambiente: STAGING (amostragem diária)
#   sampling-rate: 10% (0.1)
#   custo: aceitável (validar infra antes de prod)

# Ambiente: PRODUCTION (inteligente + errors)
#   baseline:     1% (0.01) — amostra aleatória de sucesso
#   errors:      100% (1.0) — TODOS os 5xx, exceções
#   outliers:    10% (0.1) — p99 latência, p95 duration
#   debug_mode: 100% (1.0) — forced via header X-Debug: true
```

**Configuração via sampling-rules.json em CDK Java:**

```java
@Component
public class XRayTracingConfig {

    // Sampling rules JSON — define estratégia por serviço
    public static final String SAMPLING_RULES_JSON = """
        {
          "version": 2,
          "default": {
            "fixed_target": 1,        // 1 trace/segundo garantido
            "rate": 0.01              // + 1% de tudo (prod)
          },
          "rules": [
            {
              "description": "Health checks — nunca sampler",
              "service_name": "*",
              "http_method": "GET",
              "url_path": "/actuator/health*",
              "fixed_target": 0,
              "rate": 0
            },
            {
              "description": "Pedidos de alto valor — sempre sampler",
              "service_name": "pedido-api",
              "resource_arn": "*",
              "attributes": {
                "order_value": "^[0-9]{4,}$"  // > 1000
              },
              "fixed_target": 1,
              "rate": 1.0
            },
            {
              "description": "Serviço externo (CEP, pagamento) — 10%",
              "service_name": "external-api",
              "fixed_target": 1,
              "rate": 0.1
            }
          ]
        }
        """;

    @Bean
    public void configureSampling(AWSXRay xray) {
        // Upload sampling rules para X-Ray (via console ou API)
        // xray.putSamplingRule(SAMPLING_RULES_JSON);
    }
}
```

**Integração com OpenTelemetry OTLP + AWS Distro for OpenTelemetry (ADOT):**

```yaml
# application.yml — OpenTelemetry + X-Ray Exporter
management:
  tracing:
    sampling:
      probability: 0.01  # Baseline 1% em prod
  otlp:
    tracing:
      endpoint: http://localhost:4318/v1/traces  # ADOT Collector local
      timeout: 5s

logging:
  pattern:
    level: "%5p [${spring.application.name},%X{traceId},%X{spanId}] %msg%n"
```

**Java 25 — Forced Sampling via Correlation ID header:**

```java
@Component
public class DebugSamplingInterceptor extends OncePerRequestFilter {

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res,
                                    FilterChain chain) throws ServletException, IOException {
        
        // Header X-Debug: true força sampling 100% desta request
        if ("true".equals(req.getHeader("X-Debug"))) {
            // Propagar sampling decision para downstream
            var ctx = AWSXRay.getGlobalRecorder().getCurrentSegment();
            ctx.setSampled(true);  // Force sampler (override rules)
            
            res.setHeader("X-Debug-Sampled", "true");
            logger.info("Força sampling habilitado via X-Debug: true");
        }
        
        chain.doFilter(req, res);
    }
}

// Client HTTP — propagate debug header
@Component
public class DebugHeaderClientInterceptor implements ClientHttpRequestInterceptor {

    @Override
    public ClientHttpResponse intercept(HttpRequest request, byte[] body,
                                        ClientHttpRequestExecution execution)
            throws IOException {
        String debugFlag = RequestContextHolder.currentRequestAttributes()
            .getRequest().getHeader("X-Debug");
        
        if ("true".equals(debugFlag)) {
            request.getHeaders().set("X-Debug", "true");  // Propaga downstream
        }
        
        return execution.execute(request, body);
    }
}
```

**Debugging em produção com sampling forçado:**

```bash
# Teste de ponta a ponta com X-Debug
curl -H "X-Debug: true" https://pedido-api.example.com/pedidos/123

# Console AWS X-Ray:
# - ServiceMap mostra latência real
# - Traces aparecem em segundos (sampling atual)
# - CloudWatch Logs correlacionado com traceId
# 
# Desabilitar X-Debug após debug:
curl -H "X-Debug: false" https://pedido-api.example.com/health
```

**Cloudwatch Alarms baseados em sampling:**

```yaml
# CDK Java — Alarme se p99 latência > 1s (amostrada)
var p99Metric = Metric.builder()
    .namespace("AWS/X-Ray")
    .metricName("TracedRequestCount")
    .statistic(Statistic.AVERAGE)
    .period(Duration.minutes(5))
    .build();

Alarm.Builder.create(this, "P99Latency")
    .metric(p99Metric)
    .threshold(1000)  // milliseconds
    .evaluationPeriods(2)
    .alarmName("Pedidos-API-P99-Latency")
    .alarmDescription("P99 latency > 1s — escalate on-call")
    .treatMissingData(TreatMissingData.NOT_BREACHING)
    .build();
```

**Cost Breakdown — 30 dias produção:**

```
Baseline (1%):          300k traces × $0.50/1M = $0.15
Errors (100%):          30k traces × $0.50/1M = $0.015
Outliers (10%):         300k traces × $0.50/1M = $0.15
Debug sampling:         ~50k traces × $0.50/1M = $0.025
────────────────────────────────────────────────
Total:                                           ~$0.34/mês

vs 100% sampling:       30M traces × $0.50/1M = $15/mês
Economia: 97.7% custo sem perder observabilidade de erros e anomalias
```

---

