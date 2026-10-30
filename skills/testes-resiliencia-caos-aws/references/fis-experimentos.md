# AWS Fault Injection Service (FIS) — experimentos

> Reference de `testes-resiliencia-caos-aws`. Base: guia do usuário do FIS (what-is, referência de ações,
> scenario library, stop conditions), REL12-BP04 e DevOps Guidance QA.NT.6. "FIS carries out real actions
> on real AWS resources" — a AWS recomenda fortemente planejar e rodar antes em pré-produção.

## 1. Conceitos

- **Experiment template**: ações (sequenciais ou paralelas), **alvos** (ARN, tag ou filtro, com
  seleção por quantidade/porcentagem), **stop conditions** (alarmes do CloudWatch), papel IAM, log.
- Experimentos **multi-conta**; **scenario library** com cenários prontos; definível por CloudFormation e CLI.
- Cobrança por minuto de ação e por conta-alvo.
- Experimento parado por stop condition **não pode ser retomado** — inicie outro.
- Não precisa de aprovação da AWS: as ações são em recursos do cliente (red team com C2 e eventos de
  segurança simulados seguem o formulário de Simulated Events; carga volumétrica segue a política de stress test).

## 2. Ações mais usadas (identificadores da referência atual)

| alvo | ações | uso típico |
|---|---|---|
| qualquer API AWS (por role) | `aws:fis:inject-api-internal-error`, `inject-api-throttle-error`, `inject-api-unavailable-error` | dependência AWS falhando ou estrangulando |
| Lambda | `aws:lambda:invocation-add-delay` (`startupDelayMilliseconds` 0–900.000), `invocation-error` (com `preventExecution`), `invocation-http-integration-response` (status falso para ALB/API GW/VPC Lattice) | cold start/timeout simulado, erro da função, resposta HTTP de falha; todas com `invocationPercentage` 1–100 (usam extensão do FIS + S3; recomenda-se `AWS_FIS_POLL_MAX_WAIT_MILLISECONDS`) |
| ECS | `stop-task`, `drain-container-instances`, `task-cpu-stress`, `task-io-stress`, `task-kill-process`, `task-network-latency`, `task-network-packet-loss`, `task-network-blackhole-port` | perda de task, saturação, rede degradada (ações de task exigem SSM) |
| EC2 / ASG | `stop-instances`, `terminate-instances`, `reboot-instances`, `send-spot-instance-interruptions`, falta de capacidade (`api-insufficient-instance-capacity-error`, `asg-…`), stress via SSM | perda de instância, Spot, capacidade |
| EKS | `pod-delete`, `pod-cpu-stress`, `pod-memory-stress`, `pod-network-*`, `terminate-nodegroup-instances` | Kubernetes |
| rede | `aws:network:disrupt-connectivity` (clona a NACL e nega; restaura no fim), cross-region, `disrupt-vpc-endpoint` | isolamento de subnet, endpoint, região |
| dados | `aws:rds:failover-db-cluster`, `reboot-db-instances`, `aws:dynamodb:global-table-pause-replication`, `aws:s3:bucket-pause-replication`, `aws:ebs:volume-io-latency`, `aws:elasticache:replicationgroup-interrupt-az-power`, `aws:dsql:cluster-connection-failure`, `aws:kinesis:stream-*` | failover de banco, replicação, IO |
| controle | `aws:fis:wait`, `aws:cloudwatch:assert-alarm-state` (prova que o alarme disparou), `aws:arc:start-zonal-autoshift` | cadência e verificação do próprio alerta |

## 3. Scenario library

AZ Availability: **Power Interruption** · AZ: Application Slowdown · Cross-AZ: Traffic Slowdown ·
Cross-Region: Connectivity · stress de EC2/EKS · latência de EBS. Use como ponto de partida e ajuste
alvos e duração.

## 4. Guardrails obrigatórios (REL12-BP04 + Squad)

- **Stop conditions**: até 5 alarmes por template, cobrindo o estado estável, o componente afetado e um
  **canário de usuário** (Synthetics).
- **Papel IAM do FIS** só com as ações e alvos do experimento (nada de `*`).
- Alvos por **tag dedicada** (ex.: `caos=permitido`) + porcentagem pequena no início.
- Duração curta e explícita; post-action de rollback quando houver.
- Aviso a operação/suporte; começar fora de pico; produção só com gate humano.
- "Do not run an experiment you know the workload will fail" — corrija antes.

## 5. Template exemplo (Lambda com latência, pré-produção)

```json
{
  "description": "Pagamentos: +3s em 20% das invocações por 10 min",
  "targets": {},
  "actions": {
    "latencia": {
      "actionId": "aws:lambda:invocation-add-delay",
      "parameters": {"duration": "PT10M", "invocationPercentage": "20", "startupDelayMilliseconds": "3000"},
      "targets": {"Functions": "funcoes"}
    }
  },
  "stopConditions": [
    {"source": "aws:cloudwatch:alarm", "value": "arn:aws:cloudwatch:<regiao>:<conta>:alarm:checkout-p99-slo"},
    {"source": "aws:cloudwatch:alarm", "value": "arn:aws:cloudwatch:<regiao>:<conta>:alarm:canary-checkout"}
  ],
  "roleArn": "arn:aws:iam::<conta>:role/fis-experimento-pagamentos",
  "tags": {"ambiente": "pre-prod"}
}
```

(Ajuste o bloco `targets` com `resourceType: aws:lambda:function`, seleção por tag e `selectionMode`;
confira os parâmetros exatos na referência de ações antes de usar.)

## 6. No pipeline

- DevOps Guidance QA.NT.6: caos **embutido no pipeline após o deploy** em Gamma; REL12-BP04: rodar
  **dentro e fora** do CI/CD.
- Hipótese confirmada vira **regressão automática**; DPRA: desvio significativo reprova o pipeline.
- Sem CI novo no banco: o harness local inicia o experimento (`aws fis start-experiment`), espera o fim
  e lê o estado; inconclusivo se faltar permissão ou conta.

## Fontes

- https://docs.aws.amazon.com/fis/latest/userguide/what-is.md
- https://docs.aws.amazon.com/fis/latest/userguide/fis-actions-reference.md
- https://docs.aws.amazon.com/fis/latest/userguide/scenario-library-scenarios.html
- https://docs.aws.amazon.com/fis/latest/userguide/stop-conditions.html
- https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_testing_resiliency_failure_injection_resiliency.html
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/qa.nt.6-experiment-with-failure-using-resilience-testing-to-build-recovery-preparedness.html
- https://aws-samples.github.io/aws-deployment-pipeline-reference-architecture/application-pipeline/index.html
