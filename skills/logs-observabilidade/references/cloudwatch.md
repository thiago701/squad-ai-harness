# logs-observabilidade · reference — CloudWatch Logs (Lambda Java 25 / Python · Spring Boot 4)

> Hub: `../SKILL.md`. Regras: LOG-20, LOG-22, LOG-24, LOG-25 (+ LOG-16 amostragem). Skills irmãs:
> `aws-lambda-java25-aot` (Powertools no AOT), `analise-producao-aws` (Insights somente-leitura em incidente),
> `arquiteto-cloud-aws` (IaC). Fontes oficiais no fim — versões de API mudam; confirme na doc antes de fixar.

## 1. Decisão de stack

| Contexto | Saída de log | Como |
|---|---|---|
| Lambda Java (JVM/SnapStart) | JSON Powertools | `powertools-logging` + `powertools-logging-logback` (`LambdaJsonEncoder`) ou `-log4j` (`JsonTemplateLayout` `LambdaJsonLayout.json`) |
| Lambda Java GraalVM native | JSON Powertools (v2 suporta native) ou `LambdaLogger` JSON nativo | ver `aws-lambda-java25-aot`; sem agente Java |
| Lambda sem Powertools | JSON nativo do runtime | `LoggingConfig: {LogFormat: JSON, ApplicationLogLevel: INFO, SystemLogLevel: WARN}`; `context.getLogger().log(msg, LogLevel.INFO)` |
| Lambda Python | Powertools `Logger` | `Logger(service=...)` + `@logger.inject_lambda_context(correlation_id_path=..., clear_state=True)` |
| ECS/EKS Spring Boot 4 | JSON ECS/logstash nativo | `logging.structured.format.console=ecs` (ou `logstash`/`gelf`) → awslogs/Fluent Bit |

Texto livre (`PatternLayout` puro) em produção = LOG-20: não é pesquisável por campo, não correlaciona e permite
log forging (`filtro-segredos.md` §3).

## 2. Powertools for AWS Lambda (Java v2) — Logging

```java
@Logging(correlationIdPath = CorrelationIdPaths.API_GATEWAY_REST, clearState = true, samplingRate = 0.05)
public APIGatewayProxyResponseEvent handleRequest(APIGatewayProxyRequestEvent in, Context ctx) {
    MDC.put("cliente_id", clienteId);                       // persiste até clearState limpar
    log.info("pedido.criado", entry("pedido_id", id), entries(Map.of("valor_centavos", v)));
    ...
}
```

- `@Logging` atributos: `logEvent` (**default off** — "disabled by default to prevent sensitive info being logged";
  ligar só em dev), `logResponse`, `logError`, `correlationIdPath` (JMESPath ou `CorrelationIdPaths.*`:
  `API_GATEWAY_REST`/`API_GATEWAY_HTTP` = `requestContext.requestId`, `APPLICATION_LOAD_BALANCER` =
  `headers."x-amzn-trace-id"`, `EVENT_BRIDGE` = `id`), `samplingRate` (amostra DEBUG), `clearState`
  (`MDC.clear()` ao fim — obrigatório se você faz `MDC.put` no handler: invocação warm reaproveita a JVM),
  `flushBufferOnUncaughtError`.
- Chaves emitidas: `timestamp`, `level`, `service`, `sampling_rate`, `message`, `xray_trace_id`, `error`,
  `cold_start`, `function_name|version|memory_size|arn|request_id`, `correlation_id`.
- Env: `POWERTOOLS_SERVICE_NAME` (≠ `service_undefined` — LOG-23), `POWERTOOLS_LOG_LEVEL`,
  `POWERTOOLS_LOGGER_SAMPLE_RATE`, `POWERTOOLS_LOGGER_LOG_EVENT`. Prioridade de nível:
  `AWS_LAMBDA_LOG_LEVEL` (ALC) > `POWERTOOLS_LOG_LEVEL` > XML.
- Adicionar chaves: `MDC.put` (sem validação de reservadas) ou `StructuredArguments.entry/entries/json/array`
  (ignora reservadas com warning) ou SLF4J fluent `addKeyValue`. `LoggingUtils.appendKey` é **v1** (legado).
- Logback: `<encoder class="software.amazon.lambda.powertools.logging.logback.LambdaJsonEncoder">` com
  `throwableConverter` (`ShortenedThrowableConverter`, `rootCauseFirst`, `maxDepthPerThrowable`), `LambdaEcsEncoder`
  para ECS. Sob ALC o timestamp deve ser RFC3339 `yyyy-MM-dd'T'HH:mm:ss.SSS'Z'`.
- Buffering: `BufferingAppender` (`maxBytes=20480`, `bufferAtVerbosity=DEBUG`, `flushOnErrorLog=true`) —
  DEBUG fica em memória e só vai ao CloudWatch quando um ERROR acontece. Não bufferiza no cold start.
- Métricas EMF: `@FlushMetrics(namespace, service, captureColdStart=true)` + `metrics.addMetric("PedidoCriado", 1,
  MetricUnit.COUNT)`; dimensões de **baixa cardinalidade** (nunca `cliente_id`); ≤ 100 métricas por flush;
  EMF **não funciona** na classe Infrequent Access.

Python (paridade): `logger.append_keys(cliente_id=...)` (`thread_safe_append_keys` em threads),
`logger.set_correlation_id`, `logger.exception` adiciona `exception_name`/`exception`,
`LoggerBufferConfig(max_bytes=20480, buffer_at_verbosity="WARNING", flush_on_error_log=True)`.

## 3. Advanced Logging Controls (JSON nativo + nível por função)

```yaml
# SAM / CloudFormation
LoggingConfig:
  LogFormat: JSON
  ApplicationLogLevel: INFO     # TRACE|DEBUG|INFO|WARN|ERROR|FATAL — filtra ANTES de ingerir ($)
  SystemLogLevel: WARN          # DEBUG|INFO|WARN — INIT_REPORT/REPORT viram JSON filtrável
  LogGroup: !Ref LogGroupDaFuncao
```

- Filtragem por nível exige `LogFormat=JSON`; log sem `level`/timestamp válido vira INFO.
- Env expostas ao runtime: `AWS_LAMBDA_LOG_FORMAT`, `AWS_LAMBDA_LOG_LEVEL`.
- Log4j2 sem Powertools: `aws-lambda-java-log4j2:[1.6.0,)` + `log4j-layout-template-json` + appender
  `<Lambda format="${env:AWS_LAMBDA_LOG_FORMAT:-TEXT}">` com `<LambdaJSONFormat><JsonTemplateLayout
  eventTemplateUri="classpath:LambdaLayout.json"/></LambdaJSONFormat>`; chaves MDC viram campos JSON.
  Nunca `aws-lambda-java-log4j` 1.0.x.
- O Lambda **não apaga** o log group ao remover a função: crie o log group na IaC com retenção.

## 4. Log groups: retenção, classe e custo (LOG-24)

```yaml
LogGroupDaFuncao:
  Type: AWS::Logs::LogGroup
  Properties:
    LogGroupName: !Sub /aws/lambda/${Funcao}
    RetentionInDays: 90            # prod 90–400; dev 7–14 — nunca "Never expire"
    LogGroupClass: STANDARD        # INFREQUENT_ACCESS = metade do preço de ingestão, mas sem metric filter,
                                   # subscription filter, Live Tail, EMF, field index, anomaly detection
    DataProtectionPolicy: !Ref PoliticaMascaramento   # §5
```

- Preço escalonado para logs Lambda (us-east-1, desde 05/2025): Standard $0.50/GB até 10 TB → $0.25 → $0.10 →
  $0.05; IA $0.25 → $0.15 → $0.075 → $0.05; armazenamento ~$0.03/GB-mês; Insights cobra por GB varrido —
  **janela e log group explícitos em toda query** (`analise-producao-aws`).
- Classe é definida na criação e **imutável**; IA serve para logs que só se leem em auditoria/incidente.
- Classe Delivery (Lambda → S3/Firehose): 2 dias, sem Insights.

## 5. Data protection policy — rede de segurança gerenciada (LOG-25)

Política por log group **ou** por conta (ambas se aplicam). Só mascara eventos ingeridos **depois** de ativa;
mascarado em todas as saídas (Insights, metric/subscription filters); só IAM `logs:Unmask` vê o original
(`fields @timestamp, unmask(@message)`). Identificadores gerenciados úteis no Brasil:

| Categoria | Identificadores (`arn:aws:dataprotection::aws:data-identifier/<Nome>`) |
|---|---|
| Brasil | `CpfCode-BR`, `Cnpj-BR`, `RgNumber-BR`, `CepCode-BR`, `PhoneNumber-BR` |
| Credenciais | `AwsSecretKey`, `OpenSshPrivateKey`, `PgpPrivateKey`, `PkcsPrivateKey`, `PuttyPrivateKey` |
| Financeiro | `CreditCardNumber`, `CreditCardExpiration`, `CreditCardSecurityCode` |
| PII geral | `EmailAddress`, `Address`, `Name`, `IpAddress`, `LatLong` |

Template pronto: `templates/cloudwatch/data-protection-policy.json` (operações `Audit` → métrica
`LogEventsWithFindings` + `Deidentify` → `MaskConfig`). Custo: ~$0.12/GB varrido. **Não substitui** mascarar na
origem (`mascaramento.md`): a política só vê o que já foi escrito e cobra por isso.

## 6. CloudWatch Logs Insights — queries de bolso (JSON estruturado)

```sql
-- erros de uma função com contexto
fields @timestamp, level, message, correlation_id, error.message
| filter level = "ERROR" | sort @timestamp desc | limit 50

-- seguir uma requisição ponta a ponta (Powertools correlation_id / trace)
fields @timestamp, function_name, message | filter correlation_id = "c0ffee-0001" | sort @timestamp asc

-- taxa de erro por 5 min
stats count(*) as total, sum(level = "ERROR") as erros by bin(5m)

-- top eventos de negócio (catálogo em uso)
parse message /^(?<evento>[a-z][a-z0-9_]*(\.[a-z0-9_]+)+)/ | stats count(*) by evento | sort count desc

-- cold starts e duração
filter cold_start = 1 | stats count(*), avg(duration_ms), pct(duration_ms, 99) by function_name

-- auditoria: conteúdo mascarado por política (requer logs:Unmask)
fields @timestamp, unmask(@message) | filter @message like /\*\*\*/
```

Comandos: `fields, filter/where, stats, sort, limit (limit any), display, dedup, parse, pattern, diff, unmask,
unnest, filterIndex`. Alarme direto de query: `aws cloudwatch put-log-alarm --scheduled-query-configuration`;
métrica de filtro: `aws logs put-metric-filter`.

## 7. Spring Boot 4 em ECS/EKS (sem Powertools)

```yaml
logging:
  structured:
    format.console: ecs                   # ou logstash | gelf | FQCN de StructuredLogFormatter
    ecs.service: {name: pedidos, version: "${APP_VERSION}", environment: "${APP_ENV}"}
    json:
      exclude: [process.thread.name]
      add: {regiao: sa-east-1}
      stacktrace: {root: first, max-length: 4000, include-common-frames: false}
  pattern.correlation: "[${spring.application.name:},%X{traceId:-},%X{spanId:-}] "
```

Todo MDC e `addKeyValue` entram no JSON. Alternativa madura: `logstash-logback-encoder` 9.x com
`MaskingJsonGeneratorDecorator` (`mascaramento.md` §3) — escolha **uma**.

## 8. Checklist CloudWatch (review)

- [ ] JSON (Powertools/ALC/structured) — sem `PatternLayout` como único layout em prod (LOG-20).
- [ ] `POWERTOOLS_SERVICE_NAME`/`service.name` definido (LOG-23); `correlationIdPath` ou `correlation_id` manual (LOG-22).
- [ ] `clearState=true` quando há `MDC.put` no handler; `logEvent=false` em prod.
- [ ] `ApplicationLogLevel`/`AWS_LAMBDA_LOG_LEVEL` definem o mínimo; `DEBUG` só amostrado/bufferizado.
- [ ] Log group na IaC com `RetentionInDays` e classe consciente (LOG-24); data protection policy ativa (LOG-25).
- [ ] Métricas via EMF (`@FlushMetrics`) com dimensões de baixa cardinalidade; contadores não viram log.
- [ ] Toda query Insights em runbook tem log group + janela (custo por GB varrido).

## Fontes

- Powertools Java v2 Logging: https://docs.powertools.aws.dev/lambda/java/core/logging/ · Metrics: https://docs.powertools.aws.dev/lambda/java/core/metrics/ · anúncio v2: https://aws.amazon.com/blogs/compute/introducing-v2-of-powertools-for-aws-lambda-java
- Powertools Python Logger: https://docs.aws.amazon.com/powertools/python/latest/core/logger/
- Lambda Advanced Logging Controls: https://docs.aws.amazon.com/lambda/latest/dg/monitoring-cloudwatchlogs-log-level.html · Java logging: https://docs.aws.amazon.com/lambda/latest/dg/java-logging.html
- Logs Insights query syntax: https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_QuerySyntax.html
- Data protection policies: https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/cloudwatch-logs-data-protection-policies.html · identificadores gerenciados: https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL-managed-data-identifiers.html
- Classes de log group: https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CloudWatch_Logs_Log_Classes.html · preço escalonado Lambda: https://aws.amazon.com/blogs/compute/aws-lambda-introduces-tiered-pricing-for-amazon-cloudwatch-logs-and-additional-logging-destinations · pricing: https://aws.amazon.com/cloudwatch/pricing/
- Spring Boot structured logging: https://docs.spring.io/spring-boot/reference/features/logging.html · https://spring.io/blog/2024/08/23/structured-logging-in-spring-boot-3-4
- Skill comunitária absorvida: itsmostafa/aws-agent-skills `cloudwatch` (MIT) — queries, metric filters, retenção
