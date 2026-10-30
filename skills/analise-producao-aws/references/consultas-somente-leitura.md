# Consultas somente leitura — plano de exemplo, bloqueios e perfil IAM

> Parte da skill `analise-producao-aws`. Hub: `../SKILL.md`. Todo plano passa por
> `scripts/aws/guarda_somente_leitura.py` antes de rodar. Os limites de janela (24 h para logs,
> 14 dias para métricas) e de volume (10.000 linhas) são **da política da Squad**, para conter custo —
> não são quotas da AWS.

## 1. Fatos que orientam o custo (consulta 2026-10-08)

| Fato | Fonte |
|---|---|
| Logs Insights cobra pelo volume de log **não comprimido varrido**; consulta expira em 60 min; 100 consultas concorrentes por conta | https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/AnalyzingLogData.html |
| `GetExecutionHistory` devolve input/output dos eventos por padrão (`includeExecutionData` = true); `maxResults` ≤ 1000 | https://docs.aws.amazon.com/step-functions/latest/apireference/API_GetExecutionHistory.html |
| ECS Exec abre comando/shell no contêiner — é execução | https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs-exec.html |

## 2. Plano de exemplo aprovado (Lambda com p99 alto e throttling após deploy)

Janela sintética: 2026-01-05 10:00–14:00 UTC (epoch 1767607200–1767621600).

```text
aws cloudwatch get-metric-data --start-time 1767607200 --end-time 1767621600 --metric-data-queries file://consultas-lambda.json
aws lambda list-versions-by-function --function-name ordens-aprovacao
aws lambda get-function-configuration --function-name ordens-aprovacao --query "{memoria:MemorySize,timeout:Timeout,versao:Version,arq:Architectures}"
aws cloudtrail lookup-events --start-time 1767607200 --end-time 1767621600 --lookup-attributes AttributeKey=EventSource,AttributeValue=lambda.amazonaws.com
aws logs start-query --log-group-name /aws/lambda/ordens-aprovacao --start-time 1767607200 --end-time 1767621600 --query-string "filter @type = 'REPORT' | stats pct(@duration, 99) as p99, count(*) as n by bin(5m) | limit 500"
aws stepfunctions get-execution-history --execution-arn arn:aws:states:us-east-1:111122223333:execution:OrdemManutencao:exemplo --no-include-execution-data --max-items 200
aws sqs get-queue-attributes --queue-url https://sqs.us-east-1.amazonaws.com/111122223333/fila-projecao --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible
```

## 3. Variantes que a guarda BLOQUEIA (e por quê)

| Comando | Motivo |
|---|---|
| `aws lambda get-function-configuration --function-name f` | devolve `Environment` (pode conter segredo) sem `--query` |
| `aws stepfunctions get-execution-history --execution-arn …` | sem `--no-include-execution-data`: input/output podem ter token/PII |
| `aws logs start-query … --query-string "fields @message"` sem janela/limite | custo ilimitado |
| `aws sqs receive-message …` | oculta mensagens da fila (efeito colateral) |
| `aws ecs execute-command …` | execução remota no contêiner |
| `aws secretsmanager get-secret-value …` | leitura de segredo |
| `aws lambda update-function-configuration …` | escrita — correção é outra ação, autorizada à parte |

## 4. Consultas Logs Insights úteis (sempre com janela e `limit`)

```text
# Lambda: p50/p95/p99 e cold start por janela de 5 min
filter @type = "REPORT"
| stats pct(@duration, 50) as p50, pct(@duration, 95) as p95, pct(@duration, 99) as p99,
        sum(strcontains(@message, "Init Duration")) as frios, count(*) as n by bin(5m)
| limit 500

# Erros estruturados (log JSON) por tipo, sem projetar o corpo
filter nivel = "ERROR" | stats count(*) as n by evento, tipo | sort n desc | limit 50

# API Gateway (access log JSON da casa): 5xx e latência por rota
filter status like /5\d\d/ | stats count(*) as n, pct(latenciaMs, 99) as p99 by rota | limit 50
```

## 5. Perfil IAM de leitura (esboço)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {"Sid": "LeituraOperacional", "Effect": "Allow",
     "Action": ["cloudwatch:GetMetricData", "cloudwatch:ListMetrics", "logs:StartQuery", "logs:GetQueryResults",
                "logs:StopQuery", "logs:FilterLogEvents", "logs:DescribeLogGroups", "xray:GetTraceSummaries",
                "xray:BatchGetTraces", "states:ListExecutions", "states:GetExecutionHistory",
                "states:DescribeStateMachine", "ecs:DescribeServices", "ecs:ListTasks", "ecs:DescribeClusters",
                "lambda:ListVersionsByFunction", "lambda:GetFunctionConfiguration", "sqs:GetQueueAttributes",
                "cloudtrail:LookupEvents"],
     "Resource": "*"},
    {"Sid": "NegarSegredoExecucaoEDados", "Effect": "Deny",
     "Action": ["secretsmanager:GetSecretValue", "ssm:GetParameter*", "kms:Decrypt", "ecs:ExecuteCommand",
                "ssm:StartSession", "lambda:GetFunction", "lambda:InvokeFunction", "s3:GetObject",
                "dynamodb:GetItem", "dynamodb:Query", "dynamodb:Scan", "sqs:ReceiveMessage", "states:StartExecution",
                "states:SendTask*"],
     "Resource": "*"}
  ]
}
```

`[AN]` `lambda:GetFunctionConfiguration` continua permitido no IAM porque o bloqueio do campo
`Environment` é feito pela guarda (`--query`); se o time não usar a guarda, remova essa ação.
`[AN]` Avalie as políticas gerenciadas de função de trabalho (ex.: visualização) antes de criar uma
própria — confira o escopo atual na página oficial; não use `ReadOnlyAccess` sem revisar, porque ler
**conteúdo** (objetos, itens) não é o mesmo que ler **metadados**.
