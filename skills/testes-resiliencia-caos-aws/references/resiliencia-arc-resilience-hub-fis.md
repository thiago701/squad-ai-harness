# Ciclo de Resiliência AWS: Resilience Hub, ARC Region Switch e FIS (Agent Toolkit for AWS)

> **Procedência:** absorvido e reescrito em PT-BR a partir de `aws/agent-toolkit-for-aws` (as 8 skills de `skills/specialized-skills/resilience-skills/*`: `aws-resilience-lifecycle`, `resilience-program-design`, `resilience-hub-getting-started`, `resilience-hub-multi-account`, `resilience-hub-failure-mode-assessment`, `recovery-controller-setup`, `arc-region-switch` e `aws-fault-injection-service`, commit `658b852f0612ca629d56d0a4de52738fb6a58714`, Apache-2.0).

---

## 1. Programa e Ciclo de Vida de Resiliência (`resilience-program-design`, `aws-resilience-lifecycle`)

1. **Classificação por Tiers de Criticidade (`resilience-program-design`):**
   - **Tier 0 / Missão Crítica:** RTO ≤ 5–15 min, RPO ≈ 0 (Multi-AZ + Multi-Region ativo-ativo ou warm standby com ARC Region Switch).
   - **Tier 1 / Negócio Essencial:** RTO ≤ 1–4h, RPO ≤ 15 min (Multi-AZ + Pilot Light / Backup Cross-Region).
   - **Tier 2 / Operacional:** RTO ≤ 24h, RPO ≤ 24h (Multi-AZ + snapshots diários).
2. **As 5 Fases do Ciclo de Vida (`aws-resilience-lifecycle`):**
   - **Definir metas (RTO/RPO) por tier** → **Projetar para falhas** → **Avaliar postura (Resilience Hub + FMA)** → **Validar com experimentos controlados (FIS + Game Days)** → **Operar e recuperar (ARC + alarmes + post-mortem)**.
   - **Regra obrigatória:** sempre valide se uma recomendação melhora de fato a postura reexecutando a avaliação antes de marcar o achado como resolvido.

---

## 2. AWS Resilience Hub: Single Account, Multi-Account e FMA (`resilience-hub-getting-started`, `resilience-hub-multi-account`, `resilience-hub-failure-mode-assessment`)

- **Onboarding e Avaliação (`resilience-hub-getting-started`):**
  1. Importe a aplicação a partir de stacks CloudFormation/CDK, state files Terraform, Resource Groups ou EKS.
  2. Associe uma **Resilience Policy** com alvos explícitos de RTO/RPO para quatro categorias de evento: **Application**, **Infrastructure**, **Availability Zone (AZ)** e **Region**.
  3. Publique a versão da aplicação e dispare `start-app-assessment`.
- **Governança Multi-Account (`resilience-hub-multi-account`):**
  - Configure uma conta **Delegated Administrator** no AWS Organizations e provisione roles cross-account (`AwsResilienceHubAdminAccountRole` na conta central e `AwsResilienceHubAssessmentRole` nas contas-membro) para consolidar avaliações sem copiar credenciais.
- **Failure Mode Assessment — FMA (`resilience-hub-failure-mode-assessment`):**
  - Analise os modos de falha descobertos por componente (SPOFs, ausência de Multi-AZ, falta de DLQ/retry/timeout, backup sem teste de restore) e gere recomendações operacionais (alarmes CloudWatch, SOPs de recuperação e templates de experimento FIS).

---

## 3. Application Recovery Controller (ARC): Zonal Shift, Routing Control e Region Switch (`recovery-controller-setup`, `arc-region-switch`)

### 3.1. Regra de Ouro do ARC: Data Plane ≠ Control Plane (`recovery-controller-setup`)
- **NUNCA dependa de APIs de Control Plane (`route53:ChangeResourceRecordSets`, `update-stack`, IAM) durante um desastre ativo.**
- Os **Routing Controls** do ARC rodam em um cluster de **Data Plane** globalmente distribuído em **5 endpoints regionais independentes**. Para chavear tráfego em emergência, chame `update-routing-control-states` diretamente contra os endpoints do cluster (iterando em fallback pelos 5 endpoints se um falhar).
- Configure **Safety Rules** (ex.: `ATLEAST 1` célula ativa) para impedir que uma automação defeituosa desligue 100% das regiões simultaneamente.
- Ative **ARC Zonal Autoshift** em ALBs/NLBs Multi-AZ (com `cross_zone_load_balancing` revisado) para evacuar automaticamente uma AZ degradada.

### 3.2. ARC Region Switch (`arc-region-switch`)
- Permite modelar, testar e executar **planos completos de recuperação multi-região** (*Region Switch Plans*) como workflows coordenados de Data Plane:
  1. Define passos ordenados e paralelos (promover Aurora Global Database / DynamoDB Global Tables, escalar ASG/ECS na região standby, virar Routing Controls do ARC).
  2. Executa avaliação contínua de prontidão do plano (*Plan Evaluation*) alertando sobre drift de capacidade ou permissões IAM antes que um desastre ocorra.

---

## 4. Engenharia de Caos com AWS Fault Injection Service (`aws-fault-injection-service`)

1. **Stop Condition é obrigatória antes de qualquer experimento:** todo Experiment Template do FIS exige pelo menos um alarme CloudWatch configurado como `StopCondition` para abortar e reverter a injeção ao violar o SLO.
2. **Escopo explícito de seleção (`Targets`):** filtre recursos por tags (`env=staging` ou `chaosReady=true`), `SelectionMode` (`COUNT(1)` ou `PERCENT(25)`) — nunca `ALL` em produção na primeira rodada.
3. **Ações canônicas por camada:**
   - **Compute/Rede:** `aws:ec2:stop-instances`, `aws:ecs:stop-task`, `aws:ssm:send-command` (`AWSFIS-Run-CPU-Stress`, `AWSFIS-Run-Network-Latency-Sources`, `AWSFIS-Run-Network-Packet-Loss-Sources`).
   - **Banco/Storage:** `aws:rds:failover-db-cluster`, `aws:dynamodb:global-table-pause-replication`.
   - **Nível de AZ:** `aws:network:disrupt-connectivity` (simula isolamento completo de sub-redes em uma AZ).
