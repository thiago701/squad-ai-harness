# Fatos verificados na documentação oficial AWS

> **Consulta:** 2026-10-08 · **Método:** leitura das páginas oficiais (docs, What's New, pricing).
> **Regra:** fonte única dos números e compatibilidades usados pelas skills AWS da Squad
> (`governance/politica-evidencias-sigilo-qualidade.md` §4). Revalide o que tiver mais de 90 dias
> antes de transformar em decisão. Itens marcados `[DIV]` ou `[GAP]` não estão resolvidos pela AWS.

Prefixos: `SFN` = `https://docs.aws.amazon.com/step-functions/latest/dg/` ·
`SFNAPI` = `https://docs.aws.amazon.com/step-functions/latest/apireference/` ·
`APIGW` = `https://docs.aws.amazon.com/apigateway/latest/developerguide/` ·
`EB` = `https://docs.aws.amazon.com/eventbridge/latest/userguide/` ·
`IOT` = `https://docs.aws.amazon.com/iot/latest/developerguide/` ·
`DDB` = `https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/` ·
`LBD` = `https://docs.aws.amazon.com/lambda/latest/dg/` ·
`ECS` = `https://docs.aws.amazon.com/AmazonECS/latest/developerguide/`

## 1. Step Functions

| Fato | Fonte |
|---|---|
| Duração máxima: Standard 1 ano; Express 5 min | `SFN/choosing-workflow-type.html` |
| Semântica: Standard exactly-once por estado **exceto quando há `Retry`**; Express assíncrono at-least-once; Express síncrono at-most-once (não reinicia em exceção) | idem |
| Express não guarda histórico no serviço — só com CloudWatch Logs habilitado; Standard: histórico via API por 90 dias | idem |
| Express suporta **apenas Request Response** — sem `.sync` e sem `.waitForTaskToken` | `SFN/connect-to-resource.html` |
| Matriz: Lambda, API Gateway, SQS, SNS, EventBridge = RR (Standard e Express) + callback (Standard), sem `.sync`; DynamoDB = só RR; ECS/Fargate = RR, `.sync` e callback; Step Functions aninhado = RR, `.sync`/`.sync:2` e callback | `SFN/integrate-optimized.html` |
| DynamoDB otimizado: só `GetItem`, `PutItem`, `UpdateItem`, `DeleteItem`; prefixo de erro `DynamoDB` (otimizada) e `DynamoDb` (SDK) | `SFN/connect-ddb.html` |
| ECS: `arn:aws:states:::ecs:runTask.sync` e `...runTask.waitForTaskToken`; falha em `Failures` vira `AmazonECS.Unknown`; `.sync` exige `ecs:StopTask`, `ecs:DescribeTasks` e `events:PutTargets/PutRule/DescribeRule`; `iam:PassRole` para as roles da task | `SFN/connect-ecs.html` |
| Token: `$$.Task.Token` (JSONPath) / `$states.context.Task.Token` (JSONata); deve voltar de principal **da mesma conta** | `SFN/connect-to-resource.html` |
| Timeout de Task de callback gera **novo token aleatório** | idem |
| `SendTaskSuccess`: token 1–2048 chars; output ≤ 262144 bytes; erros (HTTP 400): `InvalidOutput`, `InvalidToken`, `TaskDoesNotExist`, `TaskTimedOut`, `Kms*` | `SFNAPI/API_SendTaskSuccess.html` |
| Callback após timeout ou tarefa já fechada → `TaskTimedOut` | idem |
| `SendTaskHeartbeat` reinicia só o relógio de `HeartbeatSeconds`; **não** estende `TimeoutSeconds` | `SFNAPI/API_SendTaskHeartbeat.html` |
| `HeartbeatSeconds` < `TimeoutSeconds`; padrão 99.999.999; espera máxima de task = 1 ano | `SFN/state-task.html`, `SFN/limits-overview.html` |
| `StartSyncExecution` só para Express; responde **200 mesmo se a execução falhar** (ler `status`); 5 min via SDK, 60 s pelo console | `SFNAPI/API_StartSyncExecution.html` |
| `StartExecution` idempotente **só no Standard**: mesmo nome + mesmo input com execução aberta = mesma resposta; fechada ou input diferente = `400 ExecutionAlreadyExists`; nome reutilizável 90 dias após fechar; `name` 1–80 chars (para logs: `0-9A-Za-z-_`) | `SFNAPI/API_StartExecution.html` |
| Payload entre estados: 256 KiB; histórico Standard: 25.000 eventos (falha ao atingir) | `SFN/limits-overview.html` |
| Retry recomendado para Lambda transitório: `Lambda.ClientExecutionTimeoutException`, `Lambda.ServiceException`, `Lambda.AWSLambdaException`, `Lambda.SdkClientException` (throttling = `Lambda.TooManyRequestsException`; timeout/OOM da função = `Lambda.Unknown`) | `SFN/bp-lambda-serviceexception.html` |
| `events:putEvents`: `FailedEntryCount > 0` falha o estado com `EventBridge.FailedEntry`; o retry reenvia **todas** as entradas | `SFN/connect-eventbridge.html` |
| Retry: `IntervalSeconds` (1), `MaxAttempts` (3; 0 = nunca), `BackoffRate` (2.0), `MaxDelaySeconds`, `JitterStrategy` `FULL`/`NONE`; cada retry é cobrado como transição | `SFN/concepts-error-handling.html`, pricing |
| `States.ALL` **não** captura `States.DataLimitExceeded` nem `States.Runtime`; `States.TaskFailed` captura tudo **menos** `States.Timeout` | `SFN/concepts-error-handling.html` |
| `QueryLanguage` `JSONPath` (padrão) ou `JSONata` (recomendada pelo console para novos workflows); `Assign` funciona nas duas | `SFN/transforming-data.html`, `SFN/workflow-variables.html` |
| Free tier: 4.000 transições/mês (Standard), sem expiração; Express cobra requisição + duração (a página não cita free tier para Express) | `https://aws.amazon.com/step-functions/pricing/` |
| Step Functions Local: **sem suporte** e sem paridade; alternativa oficial = API `TestState` (requer conta AWS) | `SFN/sfn-local.html`, `SFN/test-state-isolation.html` |
| `ValidateStateMachineDefinition` valida sem criar recurso (requer credenciais/IAM `states:ValidateStateMachineDefinition`) | `SFNAPI/API_ValidateStateMachineDefinition.html` |
| `[DIV]` Heartbeat estourado: uma página cita `States.HeartbeatTimeout`, outras `States.Timeout` → capture **os dois** | `SFN/concepts-error-handling.html` × `SFN/state-task.html` |
| `[GAP]` Segundo `SendTaskSuccess` com o mesmo token: não documentado; inferência = `TaskTimedOut` | — |

## 2. API Gateway

| Fato | Fonte |
|---|---|
| REST: API keys, throttling por cliente, request validation (JSON Schema draft 4 → 400), WAF, endpoint privado, transformação de body (VTL). HTTP API: nada disso; só parameter mapping | `APIGW/http-api-vs-rest.html` |
| Autorizadores: REST = IAM, Cognito user pool, Lambda; HTTP = IAM, Lambda, JWT; WebSocket = só IAM ou Lambda REQUEST, **somente no `$connect`** | idem; `APIGW/apigateway-websocket-api-lambda-auth.html` |
| HTTP API — integrações AWS de primeira classe (10): EventBridge-PutEvents, SQS-Send/Receive/Delete/PurgeQueue, AppConfig-GetConfiguration, Kinesis-PutRecord, StepFunctions-StartExecution/StartSyncExecution/StopExecution. **Nenhuma DynamoDB** | `APIGW/http-api-develop-integrations-aws-services-reference.html` |
| Timeout de integração: REST 50 ms–29 s, ampliável acima de 29 s só em Regional/privada (pode reduzir throttle); HTTP API máx. **30 s**, não ampliável; WebSocket 29 s, não ampliável | `APIGW/api-gateway-execution-service-limits-table.html`, `APIGW/http-api-quotas.html` |
| `$util`: só `escapeJavaScript`, `parseJson`, `urlEncode`, `urlDecode`, `base64Encode`, `base64Decode` (não existe `toJson`) | `APIGW/api-gateway-mapping-template-reference.html` |
| `escapeJavaScript` escapa `'` como `\'`, inválido em JSON → use `.replaceAll("\\'","'")` | idem |
| `$context.requestId` pode ser sobrescrito pelo cliente; use `$context.extendedRequestId` | idem |
| Passthrough: `WHEN_NO_MATCH`, `WHEN_NO_TEMPLATES` (recomendado), `NEVER` (415 sem template) | `APIGW/integration-passthrough-behaviors.html` |
| `selectionPattern`: com backend AWS/HTTP casa o **status HTTP**; só com Lambda casa a mensagem de erro | `https://docs.aws.amazon.com/apigateway/latest/api/API_IntegrationResponse.html` |
| `$context.responseOverride.status` sobrescreve o status no template de resposta | `APIGW/apigateway-override-request-response-parameters.html` |
| Mapping template ≤ 300 KB; `#foreach` ≤ 1000 iterações | limits-table |
| Tutorial oficial de DynamoDB via integração AWS (`action/PutItem`, role com só `dynamodb:PutItem` na tabela) | `APIGW/set-up-data-transformations-in-api-gateway.html` |
| WebSocket: `$connect`, `$disconnect`, `$default` + rotas custom; **`$disconnect` é best-effort** | `APIGW/apigateway-websocket-api-route-keys-connect-disconnect.html` |
| `@connections` POST/GET/DELETE com SigV4 e `execute-api:ManageConnections`; `GoneException` após desconexão | `APIGW/apigateway-how-to-call-websocket-api-connections.html` |
| WebSocket: conexão máx. 2 h, idle 10 min, frame 32 KB, mensagem 128 KB, 500 novas conexões/s (ajustável) | `APIGW/apigateway-execution-service-websocket-limits-table.html` |
| Throttle de conta 10.000 RPS / burst 5.000 (2.500/1.250 em 13 regiões); inclui WebSocket e `@connections`; best-effort | `APIGW/limits.html` |
| `[GAP]` Versão do Velocity não documentada; `GoneException` = 410 só no modelo do SDK | — |
| `[GAP]` REST → `StartSyncExecution` não tem guia oficial (só HTTP API tem subtipo) | — |

## 3. EventBridge

| Fato | Fonte |
|---|---|
| Retry padrão de target: 24 h / até 185 tentativas; depois o evento é **descartado** sem DLQ | `EB/eb-rule-retry-policy.html` |
| DLQ de target: só SQS **standard**; permissão ausente, recurso inexistente e DNS vão direto à DLQ, sem retry | `EB/eb-rule-dlq.html` |
| Duplicidade possível ("the same rule can run more than once"); barramento Classic sem ordenação | `EB/eb-troubleshooting.html`, `EB/eb-custom-bus-what-is.html` |
| Novo Custom event bus (24/09/2026): FIFO por event group, retenção 1–365 dias, dedupe de 5 min; o antigo virou "Classic" | `https://aws.amazon.com/about-aws/whats-new/2026/09/eventbridge-relaunches-custom-event-buses/` |
| Evento até **1 MB** nos buses desde 29/01/2026 (exceto 5 regiões); cobrança por blocos de 64 KB | What's New 2026/01 · `[DIV]` a página `eb-putevent-size.html` ainda diz 256 KB |
| `PutEvents` falha parcial: o produtor deve reenviar as entradas com erro; bus inexistente responde 200 e descarta | `EB/eb-putevents.html` |
| Archive/Replay: replay sem garantia de ordem; esperar ~10 min antes de reproduzir | `EB/eb-archive.html` |
| Pipes: ponto a ponto, source → filtro → enrichment → target; fontes DynamoDB Streams, Kinesis, SQS, MQ, MSK, Kafka; ordem da fonte preservada | `EB/eb-pipes.html`, `EB/eb-pipes-event-source.html` |
| Pipes + DynamoDB Streams: at-least-once; ordem por chave; batch parcial via `batchItemFailures`; use `TRIM_HORIZON` | `EB/eb-pipes-dynamodb.html` |
| Input transformer do Pipes **não escapa** valores extraídos; caminho ausente vira string vazia | `EB/eb-pipes-input-transformation.html` |
| Enrichment do Pipes: Lambda, API GW, API destination ou Step Functions **Express** (síncrono, ≤ 6 MB) | `EB/pipes-enrichment.html` |
| Scheduled rules são legado → EventBridge Scheduler (at/rate/cron, fuso IANA, at-least-once, retry 0–185, DLQ SQS standard) | `EB/eb-create-rule-schedule.html`, `https://docs.aws.amazon.com/scheduler/latest/UserGuide/` |
| Preço: management events grátis no Classic; custom US$ 1,00/milhão; **14 milhões grátis/mês são do Scheduler** (invocações) | `https://aws.amazon.com/eventbridge/pricing/` |

## 4. AWS IoT Core

| Fato | Fonte |
|---|---|
| MQTT 3.1.1 e 5; MQTT sobre WebSocket (SigV4 ou custom auth); HTTPS só publish | `IOT/mqtt.html`, `IOT/protocols.html` |
| QoS 0 e 1 (QoS 2 **não**); broker **não** garante ordem | `IOT/mqtt.html` |
| Sessão persistente: MQTT 5 até 7 dias (padrão 1 h) | idem; `https://docs.aws.amazon.com/general/latest/gr/iot-core.html` |
| Payload 128 KB; client ID ≤ 128 bytes; 1 CONNECT/s por client ID; client ID duplicado derruba a conexão anterior | quotas; `IOT/mqtt.html` |
| `${iot:Connection.Thing.ThingName}` resolvida pelo certificado (MQTT/MQTT-WSS) | `IOT/thing-policy-variables.html` |
| Provisionamento: fleet provisioning por claim/trusted user (claim expira em 5 min), JITP | `IOT/provision-wo-cert.html`, `IOT/jit-provisioning.html` |
| Rules Engine: lambda, dynamoDB(v2), sqs, kinesis, firehose, stepFunctions, s3, sns, republish, http… — **sem ação direta para EventBridge**; error action; ≤ 10 ações por regra | `IOT/iot-rule-actions.html`, `IOT/rule-error-handling.html` |
| Device Shadow: 1 classic + named; desired/reported/delta; versão por update; deltas podem chegar **fora de ordem**; documento ≤ 8 KB | `IOT/iot-device-shadows.html`, `IOT/device-shadow-document.html` |
| Lifecycle events podem vir fora de ordem e duplicados | `IOT/life-cycle-events.html` |
| Tópicos: `dt/<app>/<contexto>/<thing>/<tipo>` e `cmd/...`; sem `/` inicial; minúsculas; thing name no tópico; `#` só em regras | `https://docs.aws.amazon.com/whitepapers/latest/designing-mqtt-topics-aws-iot-core/mqtt-design-best-practices.html` (whitepaper histórico) |

## 5. DynamoDB

| Fato | Fonte |
|---|---|
| TTL apaga "typically within a few days"; itens expirados **ainda aparecem** em leituras até a exclusão | `DDB/howitworks-ttl.html`, `DDB/ttl-expired-items.html` |
| Item ≤ 400 KB; `ConditionalCheckFailedException` (400); `ReturnValuesOnConditionCheckFailure` `ALL_OLD`/`NONE` | `DDB/Constraints.html`, API PutItem |
| Query ≤ 1 MB por chamada; `Limit` = itens **avaliados**; `LastEvaluatedKey` presente não garante mais itens | `DDB/Query.Pagination.html` |
| Streams: retenção 24 h; ordem por item; registro aparece uma vez | `DDB/Streams.html` |
| Transação: ≤ 100 itens / 4 MB; `ClientRequestToken` vale 10 min | `DDB/transaction-apis.html` |
| `dynamodb:LeadingKeys` exige `ForAllValues`; exemplo oficial com identity pool (`${cognito-identity.amazonaws.com:sub}`) | `DDB/specifying-conditions.html` |

## 6. Lambda e ECS

| Fato | Fonte |
|---|---|
| Lambda: timeout ≤ 900 s; memória 128–10.240 MB; payload 6 MB síncrono, **1 MB assíncrono** (desde 24/10/2025); `/tmp` 512–10.240 MB; concorrência padrão 1.000/região | `LBD/gettingstarted-limits.html` |
| Assíncrono: 2 retries por padrão (0–2), idade máx. 60–21.600 s; duplicatas possíveis; destinos SQS/SNS standard, Lambda, EventBridge, S3 (só falha) | `LBD/invocation-async-error-handling.html`, `LBD/invocation-async-retain-records.html` |
| `ReportBatchItemFailures` para SQS, Kinesis e DynamoDB Streams | `LBD/services-sqs-errorhandling.html` |
| Runtimes Java: `java25` e `java21` (AL2023); SnapStart: Java 11+, sem provisioned concurrency/EFS/ephemeral > 512 MB | `LBD/lambda-runtimes.html`, `LBD/snapstart.html` |
| Fargate: `stopTimeout` máx. 120 s (padrão 30 s); SIGTERM → SIGKILL | `https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_ContainerDefinition.html` |
| Task role = permissões da aplicação; execution role = agente (ECR, logs, secrets) | `ECS/task-iam-roles.html`, `ECS/task_execution_IAM_role.html` |
| `secrets` (Secrets Manager/SSM) injetados **só no start** — rotação exige nova task | `ECS/secrets-envvar-secrets-manager.html` |
| Circuit breaker de deployment com rollback; limiar padrão 50% (3–200) | `ECS/deployment-circuit-breaker.html` |
| Health check do container: interval 5–300 s (30), timeout 2–60 s (5), retries 1–10 (3), startPeriod 0–300 s | API HealthCheck |
| ECS Exec abre shell/comando no container ("break-glass") — **não é leitura** | `ECS/ecs-exec.html` |
| Fargate até 16 vCPU/120 GB e, desde 05/06/2026, 32 vCPU com 60/120/244 GiB | `ECS/fargate-tasks-services.html`, What's New 2026/06 |

## 7. Correções a afirmações que circulavam nas skills

| Afirmação antiga | Correção | Onde estava |
|---|---|---|
| "Free tier Step Functions: 100.000 (Express)" | A página de preço só cita 4.000 transições (Standard); Express cobra requisição + duração | `references/mensageria.md` (corrigido) |
| "Free tier EventBridge: 14 milhões de eventos/mês" | Os 14 milhões são invocações do **Scheduler**; no bus, só management events são grátis | `references/mensageria.md` (corrigido) |
| "Outbox garante exactly-once effective" | Outbox/CDC garantem publicação **at-least-once**; efeito único depende de consumidor idempotente | `references/mensageria.md` (corrigido) |
| "Cold start GraalVM Native (< 100 ms)" como promessa genérica | Metas por cenário, medidas ponta a ponta (p50/p95/p99) — `references/java-ecs-lambda.md` | `SKILL.md` (corrigido) |
| "EventBridge até 256 KB", "Lambda assíncrona 256 KB", "Fargate máx. 16 vCPU" | 1 MB, 1 MB e 32 vCPU (anúncios 2025–2026) | conhecimento comum |
