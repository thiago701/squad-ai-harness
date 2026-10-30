# Catálogo de falhas por arquitetura na AWS

> Reference de `testes-resiliencia-caos-aws`. Como escolher o que quebrar: REL12-BP04 manda partir do
> design, das dependências, dos incidentes passados e de FMEA, e priorizar por frequência × impacto.
> As ações citadas são do AWS FIS (`fis-experimentos.md`).

## 1. Formato da hipótese (REL12-BP04)

"**Se** X ocorrer, o workload Y **vai** Z **para manter** W." Exemplos da AWS: queda de 20% dos nós com
p99 < 100 ms e recuperação em minutos; falha de uma instância com aumento de 5xx < 0,01%; failover do
RDS com erros por menos de 1 min. Estado estável de exemplo: 300 TPS, 99% de sucesso, 500 ms.

## 2. Serverless (API Gateway + Lambda + DynamoDB/SQS)

| falha | ação FIS | o que observar | defesa esperada |
|---|---|---|---|
| Lambda lenta (cold start, dependência) | `aws:lambda:invocation-add-delay` | p99 do Gateway, timeouts, retries | timeout < timeout do chamador; backoff com jitter; circuit breaker |
| Lambda com erro | `aws:lambda:invocation-error` | 5xx, DLQ, reprocessamento | retry idempotente, DLQ com alarme |
| resposta HTTP de falha da integração | `aws:lambda:invocation-http-integration-response` | tratamento do cliente | mensagem e status corretos, sem vazamento |
| DynamoDB estrangulando | `aws:fis:inject-api-throttle-error` (role da função) | erros, latência, fila | retry com backoff do SDK, degradação graciosa |
| dependência AWS indisponível | `aws:fis:inject-api-unavailable-error` | fallback | cache, fila, resposta degradada |
| replicação de global table parada | `aws:dynamodb:global-table-pause-replication` | consistência entre regiões | leitura/escrita na região certa, reconciliação |

## 3. Contêiner (ECS/Fargate + ALB)

| falha | ação FIS | defesa esperada |
|---|---|---|
| task morre | `aws:ecs:stop-task` | ALB tira do alvo, serviço repõe, sem erro visível |
| CPU/IO saturados | `task-cpu-stress`, `task-io-stress` | autoscaling no tempo esperado; latência dentro do SLO |
| rede degradada | `task-network-latency`, `task-network-packet-loss`, `blackhole-port` | timeouts e retries corretos; sem tempestade de retry |
| processo morto | `task-kill-process` | health check e reinício |

## 4. Infra de rede, AZ e região

| falha | ação/cenário | defesa esperada |
|---|---|---|
| perda de AZ | cenário **AZ Availability: Power Interruption**; `aws:arc:start-zonal-autoshift` | capacidade pré-escalada nas outras AZs; zonal shift |
| lentidão numa AZ | cenário AZ: Application Slowdown | detecção por AZ e desvio |
| subnet isolada | `aws:network:disrupt-connectivity` | rotas alternativas; dependências multi-AZ |
| conectividade entre regiões | cenário Cross-Region: Connectivity | operação regional independente; fila de replicação |
| endpoint de VPC fora | `aws:network:disrupt-vpc-endpoint` | erro claro, sem travar threads |

## 5. Dados

| falha | ação | defesa esperada |
|---|---|---|
| failover de Aurora/RDS | `aws:rds:failover-db-cluster` | reconexão automática; erros por < meta |
| reboot de instância de banco | `aws:rds:reboot-db-instances` | pool resiliente |
| latência de disco | `aws:ebs:volume-io-latency` | timeouts adequados |
| replicação de S3 parada | `aws:s3:bucket-pause-replication` | alarme de replicação; RPO conhecido |
| Aurora DSQL sem conexão | `aws:dsql:cluster-connection-failure` | retry/reconexão (ver `arquiteto-cloud-aws`, reference de failover DSQL) |

## 6. Falhas não técnicas (game day)

Credencial expirada, certificado vencido, quota atingida, deploy ruim (rollback funciona?), alarme que não
dispara (`aws:cloudwatch:assert-alarm-state`), runbook desatualizado, pessoa-chave ausente.

## 7. Priorização

| prioridade | critério |
|---|---|
| alta | já causou incidente, ou afeta jornada crítica e é provável |
| média | provável com impacto moderado, ou rara com impacto alto |
| baixa | rara e de baixo impacto |

## Fontes

- https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_testing_resiliency_failure_injection_resiliency.html
- https://docs.aws.amazon.com/fis/latest/userguide/fis-actions-reference.md
- https://docs.aws.amazon.com/fis/latest/userguide/scenario-library-scenarios.html
- https://docs.aws.amazon.com/r53recovery/latest/dg/arc-zonal-autoshift.how-it-works.html
