# Referência — FinOps (TCO, otimização e governança de custo)

> Parte da skill `arquiteto-cloud-aws`. Carregue este arquivo sob demanda quando a tarefa tocar este eixo. Hub: `../SKILL.md`.
## FinOps — Custo de Desenvolvimento: Construir vs Usar Serviço AWS

A decisão mais importante de FinOps não é escolher entre EC2 e Fargate — é decidir se vale a pena **construir algo do zero** quando a AWS já oferece aquele serviço. O custo de engenharia é sistematicamente subestimado porque não aparece na fatura AWS, mas é real e recorrente.

### TCO Real: Código Próprio vs Serviço Gerenciado

```
FÓRMULA DO TCO DE CÓDIGO PRÓPRIO:
  TCO = (dias de desenvolvimento × custo/dia do engenheiro)
      + (horas/mês de manutenção × custo/hora × 12 meses)
      + (custo de infraestrutura própria × 12 meses)
      + (custo de incidentes/bugs em produção)
      + (custo de onboarding de novos devs no módulo)

EXEMPLO REAL — Módulo de Autenticação:

  CONSTRUIR DO ZERO:
    Desenvolvimento inicial:  15 dias × R$500/dia = R$7.500
    Manutenção mensal:        4h × R$62,50/h × 12 = R$3.000/ano
    Infraestrutura (Redis +   ~R$50/mês × 12 = R$600/ano
      sessão + banco):
    Incidentes de segurança:  histórico médio: 2/ano × R$2.000 = R$4.000/ano
    TCO ANO 1:                R$7.500 + R$3.000 + R$600 + R$4.000 = R$15.100
    TCO ANO 2+:               R$7.600/ano (manutenção + infra + incidentes)

  COGNITO:
    Desenvolvimento:          2 dias × R$500/dia = R$1.000
    Manutenção:               ~0 (AWS mantém)
    Custo AWS (50k MAU):      R$0 (free tier permanente)
    TCO ANO 1:                R$1.000
    TCO ANO 2+:               ~R$0 até 50k usuários

  ECONOMIA COGNITO vs PRÓPRIO:  R$14.100 no primeiro ano
                                 R$7.600/ano recorrente a partir do segundo
```

### Tabela de TCO por Módulo Comum

| Módulo | Construir Próprio (TCO Ano 1) | Serviço AWS | Custo AWS/mês | Economia Estimada |
|---|---|---|---|---|
| Autenticação completa | R$15.000–25.000 | Cognito | R$0–50 | R$14.000–24.000 |
| Sistema de filas | R$8.000–15.000 | SQS | R$0–5 | R$8.000–15.000 |
| Email transacional | R$5.000–10.000 | SES | R$1–20 | R$5.000–10.000 |
| Agendador de jobs (cron) | R$3.000–8.000 | EventBridge Scheduler | R$0–2 | R$3.000–8.000 |
| Upload/storage de arquivos | R$5.000–12.000 | S3 | R$2–30 | R$5.000–12.000 |
| Gerenciamento de secrets | R$4.000–8.000 | Parameter Store | R$0 | R$4.000–8.000 |
| Logging centralizado | R$6.000–12.000 | CloudWatch Logs | R$5–50 | R$6.000–12.000 |
| Cache distribuído | R$8.000–15.000 | ElastiCache | R$13–80 | R$8.000–15.000 |

### Como Apresentar TCO para o Time e para o Negócio

```
TEMPLATE DE DECISÃO BUILD vs BUY:

CONTEXTO: [módulo que está sendo considerado implementar do zero]

OPÇÃO A — CONSTRUIR PRÓPRIO:
  Esforço de desenvolvimento: X dias de engenharia
  Custo de desenvolvimento:   R$ X.000 (X dias × custo/dia)
  Manutenção recorrente:      X h/mês × custo → R$ X.000/ano
  Infraestrutura própria:     R$ X/mês
  Risco de segurança/bugs:    estimado R$ X.000/ano
  TCO ANO 1:                  R$ X.000
  TCO ANO 2:                  R$ X.000/ano

OPÇÃO B — SERVIÇO AWS [nome]:
  Esforço de integração:      X dias de engenharia
  Custo de integração:        R$ X.000
  Custo AWS mensal:           R$ X (ou R$0 no free tier)
  Manutenção:                 ~0 (SLA gerenciado pela AWS)
  TCO ANO 1:                  R$ X.000
  TCO ANO 2:                  R$ X.000/ano

RECOMENDAÇÃO: Opção B economiza R$ X.000 no primeiro ano e libera
              X dias de engenharia para features de negócio.
```

---

## FinOps — Otimização de Custos AWS

### Estratégia de Compra: On-Demand → Savings Plans → Reserved → Spot

```
HIERARQUIA DE COMPRA (aplique nesta ordem):

1. ON-DEMAND (padrão inicial):
   Use para: novos workloads sem baseline de uso estabelecido
   Quando migrar: após 2-4 semanas com padrão de uso estável e previsível

2. SAVINGS PLANS (primeira otimização — mais flexível):
   Economiza: 20-66% vs On-Demand
   Compromisso: valor em $/hora por 1 ou 3 anos (não unidade específica)
   Tipos:
     Compute Savings Plans:  aplica a Lambda + Fargate + EC2 (mais flexível)
     EC2 Instance Savings:   aplica apenas a família EC2 específica (mais barato)
   Quando usar: workload tem baseline estável de pelo menos 30% do tempo
   Regra prática: compre Savings Plans para cobrir 70% do uso base — deixe 30% On-Demand para picos

3. RESERVED INSTANCES (segunda otimização — mais economia):
   Economiza: 30-72% vs On-Demand
   Compromisso: instância específica (tipo, região, AZ) por 1 ou 3 anos
   Quando usar: RDS, ElastiCache, Redshift com uso > 80% do tempo
   Não use para EC2 variável — Savings Plans são mais flexíveis

4. SPOT INSTANCES (máxima economia para workloads tolerantes a interrupção):
   Economiza: 60-90% vs On-Demand
   Risco: AWS pode interromper com 2 minutos de aviso
   Casos de uso ideais:
     ✓ Batch processing (ML training, ETL, renderização)
     ✓ CI/CD runners (GitHub Actions, Jenkins workers)
     ✓ Dev/staging environments (tolerantes a reinicialização)
     ✓ Workers de fila SQS com retry configurado
   NÃO use Spot para:
     ✗ Banco de dados primário
     ✗ APIs síncronas sem fallback
     ✗ Qualquer workload stateful sem persistência externa
```

### Rightsizing — Metodologia com Dados Reais

```
PROCESSO DE RIGHTSIZING (execute mensalmente):

PASSO 1 — COLETE MÉTRICAS (mínimo 2 semanas de dados):
  Ferramenta: AWS Cost Explorer → Rightsizing Recommendations
  Métricas relevantes:
    CPU:    média < 10% = muito oversized | média > 70% = candidato a upsize
    Memória: média < 20% = oversized | média > 80% = upsize
    Network: avaliar se instância tem throughput suficiente

PASSO 2 — CLASSIFIQUE POR TIPO:
  UNDERSIZED: CPU/memória consistentemente > 80% → upsize (evita degradação)
  OVERSIZED:  CPU < 10% E memória < 20% → downsize (economiza dinheiro)
  CORRETO:    dentro das faixas → apenas monitore

PASSO 3 — PRIORIZE POR IMPACTO:
  Alto impacto:  instâncias > $100/mês oversized → ação imediata
  Médio impacto: instâncias $20-100/mês → ação no próximo ciclo
  Baixo impacto: instâncias < $20/mês → avaliar no trimestre

REGRAS PRÁTICAS DE RIGHTSIZING:
  Lambda:
    Memória padrão 128MB → aumente até reduzir duração (custo = memória × duração)
    Ferramenta: AWS Lambda Power Tuning (open source) — testa automaticamente
    Regra: 512MB muitas vezes é mais barato que 128MB se reduzir 60% da duração

  ECS Fargate:
    CPU 0.25 vCPU → suficiente para APIs com < 100 RPS
    CPU 0.5 vCPU → APIs com 100-500 RPS
    Monitore: CloudWatch Container Insights → CPU/Memory Utilization

  RDS:
    db.t3.micro: dev/test + produção < 50 conexões simultâneas
    db.t3.small: produção com até 150 conexões
    db.t3.medium: produção com até 400 conexões
    Multi-AZ: apenas quando SLA de disponibilidade > 99,5% é contratual

  ElastiCache:
    cache.t3.micro: sessões + dados com hit rate > 90% e payload < 1KB
    cache.t3.small: cache de queries com objetos > 10KB
    Monitore: CacheHitRate — se < 80%, o problema é arquitetura, não tamanho
```

### Otimização de Storage — S3 Lifecycle Policies

```
REGRA DE OURO: dados frios em storage quente são o desperdício mais fácil de eliminar.

TIERS DE ARMAZENAMENTO S3 (custo crescente → decrescente de acesso):
  S3 Standard:           $0.023/GB    → dados acessados frequentemente (< 30 dias)
  S3 Standard-IA:        $0.0125/GB   → dados acessados mensalmente
  S3 One Zone-IA:        $0.01/GB     → dados reconstrutíveis, acesso raro
  S3 Glacier Instant:    $0.004/GB    → backups acessados < 1x/trimestre
  S3 Glacier Flexible:   $0.0036/GB   → arquivos acessados 1x/ano (retrieval em horas)
  S3 Glacier Deep Archive: $0.00099/GB → arquivos históricos (retrieval em 12h)

LIFECYCLE POLICY PADRÃO (adicione a todo bucket com dados históricos):
```

```python
# CDK Python — Lifecycle Policy automática para qualquer bucket
from aws_cdk import aws_s3 as s3, Duration

bucket = s3.Bucket(self, "DadosBucket",
    lifecycle_rules=[
        s3.LifecycleRule(
            id="mover-dados-frios",
            enabled=True,
            transitions=[
                s3.Transition(
                    storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                    transition_after=Duration.days(30),   # Standard → IA após 30 dias
                ),
                s3.Transition(
                    storage_class=s3.StorageClass.GLACIER,
                    transition_after=Duration.days(90),   # IA → Glacier após 90 dias
                ),
                s3.Transition(
                    storage_class=s3.StorageClass.DEEP_ARCHIVE,
                    transition_after=Duration.days(365),  # Glacier → Deep Archive após 1 ano
                ),
            ],
            expiration=Duration.days(2555),  # exclui após 7 anos (compliance comum)
        ),
        s3.LifecycleRule(
            id="limpar-uploads-incompletos",
            enabled=True,
            abort_incomplete_multipart_upload_after=Duration.days(7),
        ),
    ]
)
```

### Otimização de CloudWatch Logs

```
CloudWatch Logs é o maior "custo fantasma" da AWS — cresce silenciosamente.

CONFIGURAÇÃO OBRIGATÓRIA PARA TODO LOG GROUP:

Retenção padrão por tipo:
  Lambda/ECS produção:      30 dias (debugging + auditoria básica)
  Lambda/ECS desenvolvimento: 7 dias
  API Gateway access logs:  90 dias (compliance mínimo)
  Logs de auditoria/negócio: 1 ano
  Logs de segurança (CloudTrail): 7 anos (compliance)
```

```python
# CDK Python — retenção automática para todos os log groups
from aws_cdk import aws_logs as logs, aws_lambda as lambda_

# Lambda com retenção configurada na criação
funcao = lambda_.Function(self, "MinhaFuncao",
    runtime=lambda_.Runtime.PYTHON_3_12,
    handler="handler.main",
    code=lambda_.Code.from_asset("src"),
    log_retention=logs.RetentionDays.ONE_MONTH,  # nunca deixe como INFINITE
)

# Para log groups existentes (remediação):
# aws logs put-retention-policy --log-group-name /aws/lambda/minha-funcao
#   --retention-in-days 30
```

### Lambda Power Tuning — Otimização Automatizada

```
AWS Lambda Power Tuning é uma State Machine gratuita que testa automaticamente
múltiplas configurações de memória e retorna a configuração ótima para:
  - Menor custo
  - Menor latência
  - Melhor equilíbrio custo/latência

Deploy via SAR (Serverless Application Repository):
  sam deploy \
    --template-url https://serverlessrepo.aws.amazon.com/applications/arn:aws:serverlessrepo:us-east-1:451282441545:applications~aws-lambda-power-tuning

Resultado típico (exemplo real de API Python):
  128MB:  duração 850ms → custo $0.0000017/invocação
  256MB:  duração 320ms → custo $0.0000013/invocação  ← mais barato E mais rápido
  512MB:  duração 180ms → custo $0.0000019/invocação
  1024MB: duração 160ms → custo $0.0000034/invocação

Conclusão: 256MB é o ponto ótimo — execute este teste antes de fixar memória de qualquer Lambda
```

---

## FinOps — Governança e Controle de Custo

### AWS Budgets — Alertas Obrigatórios

```
TODO ambiente AWS deve ter no mínimo 3 budgets configurados:

BUDGET 1 — Custo total da conta (alerta de anomalia):
  Tipo: Cost Budget
  Valor: 110% do gasto médio dos últimos 3 meses
  Alerta: 80% previsto → email ao time de engenharia
  Alerta: 100% real   → email + SNS → Slack do time

BUDGET 2 — Por serviço (EC2, RDS, Lambda separados):
  Tipo: Cost Budget por serviço
  Valor: baseline definido na primeira semana
  Alerta: qualquer serviço ultrapassar 150% do baseline

BUDGET 3 — Ambiente de desenvolvimento:
  Tipo: Cost Budget por tag (Environment=dev)
  Valor: limite fixo (ex: $50/mês)
  Alerta: 80% → aviso | 100% → notificação urgente
  Ação: desligar instâncias dev fora do horário comercial (EventBridge)
```

```python
# CDK Python — Budgets com alertas automáticos
from aws_cdk import aws_budgets as budgets

# Budget principal com alerta por email e SNS
budgets.CfnBudget(self, "BudgetPrincipal",
    budget=budgets.CfnBudget.BudgetDataProperty(
        budget_name="custo-total-mensal",
        budget_type="COST",
        time_unit="MONTHLY",
        budget_limit=budgets.CfnBudget.SpendProperty(
            amount=500, unit="USD"
        ),
    ),
    notifications_with_subscribers=[
        budgets.CfnBudget.NotificationWithSubscribersProperty(
            notification=budgets.CfnBudget.NotificationProperty(
                notification_type="FORECASTED",     # alerta preditivo
                comparison_operator="GREATER_THAN",
                threshold=80,                        # alerta com 80% previsto
                threshold_type="PERCENTAGE",
            ),
            subscribers=[
                budgets.CfnBudget.SubscriberProperty(
                    subscription_type="EMAIL",
                    address="finops@example.com",  # endereço do time de FinOps/Engenharia
                ),
                budgets.CfnBudget.SubscriberProperty(
                    subscription_type="SNS",
                    address=alerta_sns_topic.topic_arn,  # → Slack via Lambda
                ),
            ],
        ),
        budgets.CfnBudget.NotificationWithSubscribersProperty(
            notification=budgets.CfnBudget.NotificationProperty(
                notification_type="ACTUAL",          # alerta real
                comparison_operator="GREATER_THAN",
                threshold=100,
                threshold_type="PERCENTAGE",
            ),
            subscribers=[
                budgets.CfnBudget.SubscriberProperty(
                    subscription_type="EMAIL",
                    address="finops@example.com",  # endereço do time de FinOps/Engenharia
                ),
            ],
        ),
    ],
)
```

### Cost Allocation Tags — Visibilidade por Serviço/Feature

```
TAGGING OBRIGATÓRIO para rastreabilidade de custo:

Tags mínimas em todos os recursos:
  Project:     nome-do-projeto
  Environment: dev | staging | prod
  Team:        nome-do-time
  Feature:     nome-da-feature (opcional mas recomendado)
  ManagedBy:   cdk | sam | terraform (qual IaC criou)

Por que tagging importa:
  → Sem tags: "AWS custou R$3.000 este mês" — impossível agir
  → Com tags: "Feature X custou R$800 em prod e R$400 em dev" — decisão precisa
```

```python
# CDK Python — tags automáticas em toda a stack
from aws_cdk import App, Stack, Tags

app = App()
stack = PedidoStack(app, "PedidoStack")

# Tags aplicadas a TODOS os recursos da stack automaticamente
Tags.of(stack).add("Project",     "sistema-pedidos")
Tags.of(stack).add("Environment", "prod")
Tags.of(stack).add("Team",        "backend")
Tags.of(stack).add("ManagedBy",   "cdk")
```

### Painel de Custo Semanal — Ritual FinOps

```
RITUAL SEMANAL (15 minutos, toda segunda-feira):

1. ABRA o AWS Cost Explorer → Last 7 days → Group by Service
   Pergunta: algum serviço subiu > 20% sem justificativa?

2. VERIFIQUE os top 3 serviços por custo
   Pergunta: o crescimento é proporcional ao crescimento de uso?

3. REVISE recursos ociosos
   Trusted Advisor → Cost Optimization → Idle Resources
   Itens comuns: Elastic IPs não usados ($3,60/mês cada),
                 snapshots antigos, volumes EBS desanexados

4. CONFIRA Compute Optimizer
   AWS Compute Optimizer → instâncias com recomendação de rightsizing pendente

5. REGISTRE no Runbook:
   Custo semana anterior: $X
   Custo semana atual:    $Y
   Variação:              +/-Z%
   Justificativa (se > 15%): [texto]
   Ação se anomalia:      [card criado no backlog]
```

### Desligar Recursos Dev Fora do Horário

```
Ambientes de desenvolvimento rodando 24/7 desperdiçam 65% do custo.
Solução: EventBridge Scheduler desliga automaticamente fora do horário comercial.

ECONOMIA TÍPICA:
  RDS db.t3.small dev: $28/mês → $10/mês (apenas 8h/dia úteis)
  ECS dev (2 tasks):   $20/mês → $7/mês
  EC2 t3.small dev:    $15/mês → $5/mês
  Total por ambiente:  economia de ~65% = R$85/mês por ambiente de dev
```

```python
# CDK Python — liga/desliga RDS dev automaticamente
from aws_cdk import aws_scheduler as scheduler
import json

# Para às 20h (horário Brasília = 23h UTC) — segunda a sexta
scheduler.CfnSchedule(self, "DesligarRDSDev",
    schedule_expression="cron(0 23 ? * MON-FRI *)",
    flexible_time_window=scheduler.CfnSchedule.FlexibleTimeWindowProperty(
        mode="OFF"
    ),
    target=scheduler.CfnSchedule.TargetProperty(
        arn=f"arn:aws:scheduler:::aws-sdk:rds:stopDBInstance",
        role_arn=scheduler_role.role_arn,
        input=json.dumps({"DbInstanceIdentifier": "pedido-dev"}),
    ),
)

# Liga às 7h (10h UTC) — segunda a sexta
scheduler.CfnSchedule(self, "LigarRDSDev",
    schedule_expression="cron(0 10 ? * MON-FRI *)",
    flexible_time_window=scheduler.CfnSchedule.FlexibleTimeWindowProperty(
        mode="OFF"
    ),
    target=scheduler.CfnSchedule.TargetProperty(
        arn=f"arn:aws:scheduler:::aws-sdk:rds:startDBInstance",
        role_arn=scheduler_role.role_arn,
        input=json.dumps({"DbInstanceIdentifier": "pedido-dev"}),
    ),
)
```

### Referências de Custo por Arquitetura

```
ARQUITETURA SERVERLESS (Lambda + API Gateway + DynamoDB):
  100k req/mês:    ~$0     (dentro do free tier)
  1M req/mês:      ~$4/mês
  10M req/mês:     ~$35/mês
  100M req/mês:    ~$320/mês

ARQUITETURA ECS FARGATE (2 tasks 0.25 vCPU / 0.5GB):
  Base 24/7:       ~$18/mês
  + RDS t3.micro:  +$15/mês
  Total mínimo:    ~$33/mês → independente do tráfego

PONTO DE CRUZAMENTO Lambda vs ECS:
  Abaixo de ~5M req/mês:  Lambda é mais barato
  Acima de ~5M req/mês:   ECS Fargate pode ser mais barato (depende da duração)
  Use a calculadora AWS para seu caso específico antes de decidir

RDS — COMPARATIVO DE INSTÂNCIAS:
  db.t3.micro  (2 vCPU, 1GB):   $15/mês  → dev + prod < 20 conexões
  db.t3.small  (2 vCPU, 2GB):   $28/mês  → prod até 100 conexões
  db.t3.medium (2 vCPU, 4GB):   $55/mês  → prod até 300 conexões
  db.t3.large  (2 vCPU, 8GB):   $110/mês → prod alta carga
  Multi-AZ: dobra o custo em todas as instâncias acima
  RDS Proxy: +$0.015/hora por vCPU (necessário com Lambda escalando)
```

---

