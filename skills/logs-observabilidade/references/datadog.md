# logs-observabilidade · reference — Datadog Logs (escrita, correlação, custo e redação)

> Hub: `../SKILL.md`. Regras: LOG-22, LOG-23, LOG-24, LOG-25. Skills irmãs: `dd-logs` (busca/pipelines via `pup`),
> `dd-apm` (traces), `datadog-lambda-java` (instrumentação Lambda), `dd-monitors`. Esta reference cobre **como
> escrever o log** para que o Datadog o entenda sem parser — não repete a operação da plataforma.

## 1. Escreva JSON com os atributos reservados certos (zero pipeline)

O pré-processamento JSON do Datadog mapeia automaticamente, sem Grok, quando o log usa estes nomes:

| Função | Atributos reconhecidos (defaults) | Use |
|---|---|---|
| data | `@timestamp`, `timestamp`, `date`, `eventTime`… | `timestamp` RFC3339 UTC |
| mensagem | `message`, `msg`, `log` | `message` |
| status | `status`, `severity`, `level`, `syslog.severity` | `level` (ou `status`) |
| serviço | `service`, `dd.service` | `service` |
| host | `host`, `hostname` | automático no agent/extension |
| trace | `dd.trace_id`, `trace_id` | `dd.trace_id` (injeção) |
| span | `dd.span_id`, `span_id` | `dd.span_id` |

Reserved attributes: `host, source, status, service, trace_id, message`. Qualquer outro campo vira atributo
pesquisável (`@pedido_id:p-55010`) sem configuração — por isso JSON + chave=valor estruturado (`doutrina-eventos.md`).

**Standard attributes** (nomeie assim e os painéis prontos funcionam): `http.method`, `http.status_code`, `http.url`,
`http.url_details.path`, `http.request_id`, `http.useragent`, `network.client.ip`, `duration` (**nanossegundos**),
`usr.id` (nunca `usr.email` em prod), `error.kind`, `error.message`, `error.stack`, `logger.name`,
`logger.thread_name`, `db.statement` (sem binds), `evt.name`, `evt.outcome`.

## 2. Unified Service Tagging (LOG-23) — sem isso não há correlação

```yaml
# Lambda (SAM) / ECS task def / Helm values
DD_SERVICE: pedidos
DD_ENV: prod
DD_VERSION: 1.4.2            # git SHA ou SemVer — o que o deploy muda
DD_LOGS_INJECTION: "true"    # default em dd-trace-java ≥ 0.74 para JSON; explícito não custa
DD_TAGS: "team:pagamentos,squad:faturamento"
```

Kubernetes: labels `tags.datadoghq.com/env|service|version`. Com `DD_LOGS_INJECTION` o tracer injeta
`dd.trace_id`, `dd.span_id`, `dd.service`, `dd.env`, `dd.version` no MDC → o encoder JSON os emite.

## 3. Correlação log ↔ trace (LOG-22)

- **JVM + dd-trace-java**: automática (SLF4J/Logback/Log4j2) com JSON; se o path não for `dd.trace_id`, ajuste o
  reserved attribute no pipeline. Manual: `MDC.put("dd.trace_id", CorrelationIdentifier.getTraceId())` (retorna
  `"0"` sem span ativo) ou, via OTel API, `Span.current().getSpanContext().getTraceId()`.
- **128-bit**: `DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED=true` (default) e
  `DD_TRACE_128_BIT_TRACEID_LOGGING_ENABLED=true` → 32 hex no log. Pipelines/parsers custom devem tratar
  `dd.trace_id`/`dd.span_id` como **string** (não numérico).
- **GraalVM native (AOT)**: não há agente; injete pelo OTel SDK (`datadog-lambda-java` modo B) ou
  `OpenTelemetryAppender` (`trace-correlacao.md` §4).
- **Lambda**: `AWS_LAMBDA_EXEC_WRAPPER=/opt/datadog_wrapper`, layer `Datadog-Extension(-ARM)`, `DD_API_KEY_SECRET_ARN`
  (nunca `DD_API_KEY` em texto), `DD_SITE`, `DD_TRACE_ENABLED=true`; Java 8–25 com ≥ 1024 MB.
- Query de correlação: `service:pedidos @dd.trace_id:<id>`; da trace para os logs: aba *Logs* do span.

Logback para Datadog (texto, se JSON for impossível): `%d{yyyy-MM-dd HH:mm:ss} %-5p %C:%L - %X{dd.trace_id}
%X{dd.span_id} - %m%n` + `log_processing_rules` multi_line no agent. JSON é o recomendado (stack trace no mesmo evento).

## 4. Sensitive Data Scanner — rede de segurança na plataforma (LOG-25)

- Roda **no backend antes de indexar**; só afeta dados ingeridos após a regra; *scanning groups* (filtro por query,
  ex.: `service:pedidos env:prod`) + *scanning rules* (biblioteca ou regex própria).
- Ações: `Redact` (texto substituto), `Partially Redact` (n caracteres de uma ponta), `Hash` (FarmHash 64-bit —
  correlacionável sem expor), `Mask` (reversível com permissão *Data Scanner Unmask*).
- Regras de biblioteca relevantes: `Brazilian Cadastro de Pessoas Físicas (CPF) Scanner`, `Brazilian Cadastro
  Nacional da Pessoa Jurídica (CNPJ) Scanner`, `AWS Access Key ID Scanner`, `AWS Secret Access Key Scanner`,
  cartões por bandeira, JWT, chaves privadas.
- Tags recomendadas para auditoria: `sensitive_data:true`, `sensitive_data_category:<tipo>` → monitor
  "PII escapou para o log" (`dd-monitors`).
- Atributos reservados (`host, service, env, status, trace_id, date`) ficam protegidos da redação.
- Alinhe o **formato** com a origem: a regra de CPF deve produzir `***.456.789-**`, igual ao `mascara.py` —
  operador vê um só padrão e sabe que é CPF mascarado.

Regra customizada (Terraform) e padrões prontos: `templates/datadog/sensitive-data-scanner.tf.example`.

## 5. Custo: Logging without Limits (LOG-24)

Ingestão é desacoplada de indexação — tudo passa pelo pipeline (Live Tail, arquivos, métricas), só o que entra no
**índice** custa caro (~US$ 2,55/M eventos indexados vs ~US$ 0,01/M só processados — confirme no contrato).

1. Descubra o ruído: *top service/status* → *patterns*.
2. **Exclusion filters** por índice (query + 0–100 %): `@http.url_details.path:(/health OR /ready)`, `status:debug`,
   `source:lambda @message:*INIT_REPORT*`, `@message:*EXTENSION*`. Só o primeiro filtro ativo que casa se aplica;
   índices são avaliados em ordem.
3. **Log-based metrics** para contadores de alto volume (10 s de granularidade, 15 meses, cobradas como custom
   metrics) — sem group-by de alta cardinalidade (`usr.id` explode séries).
4. Retenção por índice conforme uso (3–15 d quente); *Flex Logs* para 3–15 meses frios (sem monitores/Watchdog).
5. Quota diária por índice com alerta a 50 %.

## 6. Checklist Datadog (review)

- [ ] JSON com `timestamp`, `level`, `message`, `service` e atributos padrão (`http.*`, `usr.id`, `error.*`, `duration` em ns).
- [ ] `DD_SERVICE/DD_ENV/DD_VERSION` em todo deploy (LOG-23); `DD_API_KEY_SECRET_ARN`, nunca a chave em texto.
- [ ] `dd.trace_id`/`dd.span_id` presentes (injeção ou manual no AOT) (LOG-22); 128-bit tratado como string.
- [ ] Sensitive Data Scanner ativo no índice do serviço com regras CPF/CNPJ/cartão/AWS/JWT e tag `sensitive_data` (LOG-25) — e **ainda assim** mascarado na origem.
- [ ] Exclusion filters para health/debug/INIT_REPORT; contadores em log-based metrics; retenção definida (LOG-24).
- [ ] Nenhum `usr.email`, `cpf`, `cartao` indexado — se o `pup logs search "@cpf:*"` devolver algo, é incidente.

## Fontes

- Pipelines e pré-processamento JSON: https://docs.datadoghq.com/logs/log_configuration/pipelines/
- Standard/reserved attributes: https://docs.datadoghq.com/standard-attributes/?product=log+management · https://docs.datadoghq.com/logs/log_configuration/attributes_naming_convention/
- Correlação Java: https://docs.datadoghq.com/tracing/other_telemetry/connect_logs_and_traces/java/ · config do tracer (128-bit, logs injection): https://docs.datadoghq.com/tracing/trace_collection/library_config/java/
- Unified Service Tagging: https://docs.datadoghq.com/getting_started/tagging/unified_service_tagging/
- Lambda Java: https://docs.datadoghq.com/serverless/aws_lambda/installation/java/
- Log collection Java (Logback/Log4j2): https://docs.datadoghq.com/logs/log_collection/java/?tab=logback
- Sensitive Data Scanner: https://docs.datadoghq.com/sensitive_data_scanner/setup/telemetry_data/ · regras de biblioteca: https://docs.datadoghq.com/sensitive_data_scanner/library_rules/
- Logging without Limits: https://docs.datadoghq.com/logs/guide/getting-started-lwl · índices/exclusion filters: https://docs.datadoghq.com/logs/log_configuration/indexes/ · log-based metrics: https://docs.datadoghq.com/logs/log_configuration/logs_to_metrics/ · Flex Logs: https://docs.datadoghq.com/logs/log_configuration/flex_logs/
