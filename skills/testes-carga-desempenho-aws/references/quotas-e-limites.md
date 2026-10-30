# Quotas e limites — checar antes de gerar carga

> Reference de `testes-carga-desempenho-aws`. Base: REL01-BP04, docs de quotas do Lambda e do API
> Gateway. Valores de 17/10/2026: **confira sempre no Service Quotas da conta de teste**, porque contas
> novas e regiões novas têm valores menores e quotas mudam.

## 1. Valores de referência

| serviço | quota | padrão | ajustável? |
|---|---|---|---|
| Lambda | execuções concorrentes por região | 1.000 (contas novas podem ter menos) | sim |
| Lambda | taxa de escalonamento por função | +1.000 ambientes a cada 10 s | não |
| Lambda | payload síncrono | 6 MB | não |
| Lambda | timeout | 900 s | não |
| API Gateway | throttle por conta e região | 10.000 RPS (várias regiões novas: 2.500) | sim |
| API Gateway | burst | 5.000 (regiões novas: 1.250) | não |

Outros a verificar conforme a arquitetura: capacidade e partição do DynamoDB, conexões do RDS/Aurora,
limites do ALB e do Fargate (tasks por serviço/região), throughput do SQS FIFO, shards do Kinesis, IPs da
subnet (Lambda/Fargate em VPC), quotas de chamadas de API de controle (que o próprio teste pode estourar).

## 2. REL01-BP04 — gestão de quotas

- Monitore quotas (Service Quotas, Trusted Advisor, alarmes do CloudWatch) e também os **hard limits**.
- **Aumento de quota não é imediato** — peça com antecedência.
- Compare quotas entre contas e regiões (pré-prod × produção; região de DR).
- **Antes de um teste grande, valide e aumente as quotas da conta de teste.**

## 3. Interpretar throttling no resultado

| sinal | significado | ação |
|---|---|---|
| 429 do API Gateway | throttle do Gateway (conta, estágio ou método) | ajustar throttling/usage plan ou pedir quota |
| `Throttles` da Lambda + `ConcurrentExecutions` no teto | concorrência da conta ou reservada | quota, reservada, ou rever o desenho |
| erros crescendo em degraus de 10 s | taxa de escalonamento da Lambda | rampa realista; provisioned concurrency |
| `ThrottledRequests` no DynamoDB | capacidade/partição quente | chave de partição, on-demand, retries com backoff |

Se o teste parou no throttling antes da meta, o resultado é **inconclusivo para a capacidade do
sistema** — registre o limite atingido, não "o sistema aguenta X".

## 4. Checklist pré-teste

- [ ] Quotas da conta de teste listadas e comparadas com a meta (com margem).
- [ ] Pedidos de aumento feitos e confirmados.
- [ ] Concorrência reservada das funções conhecida (não estrangula o teste nem a conta vizinha).
- [ ] Throttling do Gateway por estágio/método conhecido.
- [ ] Capacidade dos bancos e filas conhecida.
- [ ] Alarme de orçamento e de throttling ligado durante o teste.

## Fontes

- https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_manage_service_limits_monitor_manage_limits.html
- https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html
- https://docs.aws.amazon.com/lambda/latest/dg/burst-concurrency.html
- https://docs.aws.amazon.com/us_en/apigateway/latest/developerguide/limits.html
