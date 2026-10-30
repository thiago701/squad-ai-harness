# Referência — Princípios + Estratégias de Deploy (Feature Flags, Canary, Rollback, Saga, GitOps)

> Parte da skill `engenheiro-devops`. Carregue sob demanda. Hub: `../SKILL.md`.
## Princípios Inegociáveis

### 1. Pipeline como Código, não como Ritual
- Todo pipeline é versionado no repositório junto com o código.
- Se não está no Git, não existe. Zero configuração manual em UI de CI/CD.
- Pipeline deve rodar localmente (ou simulável) para debug rápido.

### 2. Build Rápido é Build que o Time Respeita
- Meta: pipeline completo em < 10 minutos. Se passar de 15, otimize.
- Paralelize jobs independentes (lint, testes unitários, build podem rodar juntos).
- Cache agressivo de dependências (Maven local repo, pip cache, Docker layers).

### 3. Fail Fast, Fail Loud
- Testes mais rápidos rodam primeiro. Se unit test falha, nem roda integração.
- Mensagem de erro do pipeline deve ser acionável: "O que quebrou + onde olhar".
- Zero flaky tests tolerados no pipeline principal. Flaky → quarentena ou delete.

### 4. Deploy é Evento Chato (e isso é Bom)
- Deploy deve ser tão rotineiro que ninguém sente ansiedade ao fazê-lo.
- Rollback em < 5 minutos é obrigatório. Se não tem rollback, não vai para produção.
- Feature flags para separar deploy de release.

### 5. Observabilidade é Arquitetura, não Afterthought
- Logs estruturados (JSON) com correlation_id desde o dia 1.
- Métricas de negócio (pedidos/min, latência de confirmação) junto com métricas de infra.
- Alertas baseados em SLAs (p99 > threshold), não em métricas brutas.

### 6. Feature Flags — Separar Deploy de Release
- Feature flags permitem deploy contínuo sem expor funcionalidades inacabadas.
- Trunk-based development: todos commitam na main, features protegidas por flags.
- Canary release: nova feature ativada para 5% → 25% → 100% gradualmente.

### 6.1 Canary Deployment com ALB Weighted Target Groups + CodeDeploy

```yaml
# appspec.yml — CodeDeploy para ECS Fargate (Canary 10/90 → 100%)
version: 0.0
Resources:
  - TargetService:
      Type: AWS::ECS::Service
      Properties:
        TaskDefinition: <TASK_DEFINITION>
        LoadBalancerInfo:
          ContainerName: "app"
          ContainerPort: 8080
Hooks:
  - BeforeAllowTraffic: "LambdaBeforeAllowTraffic"   # health check customizado
  - AfterAllowTraffic: "LambdaAfterAllowTraffic"     # validação pós-deploy
```

```yaml
# SAM/CloudFormation — CodeDeploy com Canary Strategy
DeploymentGroup:
  Type: AWS::CodeDeploy::DeploymentGroup
  Properties:
    DeploymentConfigName: CodeDeployDefault.ECSCanary10Percent5Minutes
    # Outras opções: ECSLinear10PercentEvery1Minute, ECSAllAtOnce
    AutoRollbackConfiguration:
      Enabled: true
      Events:
        - DEPLOYMENT_FAILURE
        - DEPLOYMENT_STOP_ON_ALARM
    AlarmConfiguration:
      Enabled: true
      Alarms:
        - Name: !Ref HighErrorRateAlarm
        - Name: !Ref HighLatencyAlarm
```

**Estratégias de tráfego disponíveis:**

| Estratégia | Comportamento | Quando usar |
|---|---|---|
| `ECSCanary10Percent5Minutes` | 10% por 5min, depois 100% | Produção padrão |
| `ECSCanary10Percent15Minutes` | 10% por 15min, depois 100% | Produção crítica |
| `ECSLinear10PercentEvery1Minute` | +10% a cada 1min | Migração gradual |
| `ECSAllAtOnce` | 100% imediato | Staging/dev |

### 6.2 Automated Rollback com CloudWatch Alarms

```yaml
# CloudWatch Alarm → Trigger automático de rollback via CodeDeploy
HighErrorRateAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: !Sub "${ServiceName}-high-error-rate"
    MetricName: 5XXError
    Namespace: AWS/ApplicationELB
    Statistic: Sum
    Period: 60
    EvaluationPeriods: 2
    Threshold: 10
    ComparisonOperator: GreaterThanThreshold
    Dimensions:
      - Name: LoadBalancer
        Value: !Ref ALBArn

HighLatencyAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: !Sub "${ServiceName}-high-latency"
    MetricName: TargetResponseTime
    Namespace: AWS/ApplicationELB
    Statistic: p99
    Period: 60
    EvaluationPeriods: 3
    Threshold: 2.0      # 2 segundos p99
    ComparisonOperator: GreaterThanThreshold
```

**Fluxo de rollback automático:**
```
Deploy Canary (10%) → CloudWatch monitora métricas
  ├─ Métricas OK por 5min → Shift para 100% (sucesso)
  └─ Alarm dispara (5XX > 10 ou p99 > 2s) → CodeDeploy rollback automático
      → Task definition anterior restaurada
      → Notificação SNS para equipe
```

**Checklist de Canary + Rollback:**
- ✅ CodeDeploy deployment group com canary strategy configurado
- ✅ CloudWatch Alarms para error rate (5XX) e latência (p99)
- ✅ AutoRollbackConfiguration habilitado com DEPLOYMENT_STOP_ON_ALARM
- ✅ Hook BeforeAllowTraffic com Lambda de health check
- ✅ Hook AfterAllowTraffic com Lambda de smoke test
- ✅ SNS Topic para notificações de deploy/rollback
- ✅ Métricas custom de negócio (pedidos/min) como alarm adicional
- ✅ Runbook documentado para rollback manual de emergência

```java
// Java 25 — Feature Flags com Unleash (open-source) ou Flagsmith
// Dependência: io.getunleash:unleash-client-java

@Configuration
public class FeatureFlagConfig {

    @Bean
    public Unleash unleash() {
        return new DefaultUnleash(UnleashConfig.builder()
            .appName("pedidos-api")
            .unleashAPI("http://unleash:4242/api")
            .apiKey(System.getenv("UNLEASH_API_KEY"))
            .build());
    }
}

// Uso no Use Case — proteção por feature flag
@Service
public class ProcessarPedidoUseCase {

    private final Unleash unleash;

    public Pedido processar(PedidoCommand cmd) {
        var pedido = criarPedido(cmd);

        // Nova feature: notificação push (protegida por flag)
        if (unleash.isEnabled("notificacao-push-pedido")) {
            pushNotificationService.enviar(pedido);
        }

        // Canary: novo algoritmo de cálculo de frete (gradual rollout)
        if (unleash.isEnabled("novo-calculo-frete", unleashContext(cmd.clienteId()))) {
            pedido = calcularFreteV2(pedido);  // novo algoritmo
        } else {
            pedido = calcularFreteV1(pedido);  // algoritmo atual
        }

        return pedidoRepository.salvar(pedido);
    }

    private UnleashContext unleashContext(Long clienteId) {
        return UnleashContext.builder()
            .userId(clienteId.toString())
            .build();
    }
}
```

#### Feature Flag Lifecycle — 4 Estados Nomeados

Cada feature flag passa por **4 estados bem-definidos** com ações e métricas específicas:

```
┌─────────────────────────────────────────────────────────────────┐
│ FEATURE FLAG LIFECYCLE — 4 Estados (duração típica: 2-4 semanas)│
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1️⃣  CREATED (created_at: <hoje>)                              │
│    ├─ PR cria flag em Unleash/AppConfig + code usa if-check    │
│    ├─ Flag inicia com rollout 0% (ninguém afetado)            │
│    ├─ Métrica: nenhum eval ainda                              │
│    └─ Duração: 1 dia (deploy + PR merge)                      │
│                                                                  │
│  ↓                                                                │
│                                                                  │
│  2️⃣  EVALUATED (rollout%: 0 → 100, metrics: eval_count)        │
│    ├─ Canary: 5% → 25% → 50% → 100% gradualmente             │
│    ├─ Metrics coletadas: qual % de usuários evaluam flag      │
│    ├─ Variantes: A/B test tracking (conversion rate, latency)  │
│    ├─ Health: error rate deve estar estável vs baseline       │
│    └─ Duração: 1-2 semanas (monitoração contínua)             │
│                                                                  │
│  ↓                                                                │
│                                                                  │
│  3️⃣  DECIDED (rollout: 100% OU remoção definida)               │
│    ├─ Opção A: Feature estável → rollout 100% permanente      │
│    ├─ Opção B: Feature deprecada → remover (código + flag)    │
│    ├─ Conversão: se A/B test venceu → winner fica 100%        │
│    └─ Duração: 1 dia (change approval)                        │
│                                                                  │
│  ↓                                                                │
│                                                                  │
│  4️⃣  ARCHIVED (archived_at: <hoje>, sunset_deadline: <data>)   │
│    ├─ Opção A: Se rollout 100% → código reference removido    │
│    ├─ Opção B: Se deprecada → remoção + limpeza              │
│    ├─ Flag marcada como archived em Unleash (não mais em UI)  │
│    ├─ OBRIGATÓRIO: código removendo if-check referenciando flag │
│    └─ Duração: 1 PR (cleanup)                                 │
│                                                                  │
│  VALIDAÇÃO: Se flag.created_at > 30 dias E flag.archived=false │
│    → Alerta automático: "Feature flag zombie — retire ou use"  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Exemplo Completo: Feature Flag "novo-calculo-frete"**

```
DAY 0:
  - Engineer: cria branch feature/novo-calculo-frete
  - Code: adiciona if (unleash.isEnabled("novo-calculo-frete"))
  - Unleash: cria flag "novo-calculo-frete" com rollout 0%
  - PR merge na main → deploy automático

DAY 1-2:
  - Monitor: erro rate OK, latency OK
  - Canary 5%: 1000 users tentam novo algoritmo
  - Métrica: latência ~+2%, conversão OK
  - → Escalona para 25%

DAY 3-4:
  - 5000 users com novo algorithm
  - Monitor: latência estável, sem regressão
  - → Escalona para 50%

DAY 5-6:
  - 10000 users, tudo em verde
  - → Rollout 100%

DAY 7-14:
  - Todos rodam novo algoritmo por 1 semana
  - Validação: sem bugs, sem rollback
  - DECIDED: flag é candidata a permanent OU removal

DAY 15:
  - Flag marcada como "decided"
  - Engineer: remove if-check de código, merge PR
  - Unleash: marca flag como archived
  - Code cleanup: nenhuma referência para "novo-calculo-frete"

VALIDATION:
  - Métricas registradas: quando feature foi ativada, latência, conversão
  - Logs: todos com correlationId
  - Alertas: nenhum erro durante rollout
```

#### Trunk-Based Development — Integração com Feature Flags

Feature flags **permitem trunk-based development** (commits diários na main) sem ficar em feature branches.

```
REGRA: Branch protection em main
  ✓ Require pull request review before merge (1 approver)
  ✓ Require status checks to pass before merge (CI green)
  ✓ Require branches to be up to date before merge
  ✓ Dismiss stale pull request approvals
  ✓ Require code reviews from code owners

ANTI-PADRÃO: Long-lived feature branches
  ✗ feature/novo-modulo rodando por 3 semanas
  ✗ Merge conflict ao voltar para main
  ✗ Impede que outro dev acesse código
```

```yaml
# .github/branch-protection-rules.yml (GitHub Actions validation)
name: Branch Protection Validation
on:
  pull_request:
    branches: [main]

jobs:
  branch-protection:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      # Validar que PR é pequeno (< 400 linhas changed)
      - name: Check PR size
        uses: dorny/paths-filter@v2
        id: filter
        with:
          filters: |
            src:
              - 'src/**'
            docs:
              - 'docs/**'
      
      - name: Enforce small PRs
        if: ${{ github.event.pull_request.additions + github.event.pull_request.deletions > 400 }}
        run: |
          echo "::error::PR too large (>400 lines). Split into smaller PRs for trunk-based dev."
          exit 1

      # Validar que branch é recente (< 1 dia sem rebase)
      - name: Ensure fresh branch
        run: |
          DAYS_SINCE_LAST_COMMIT=$(git log -1 --format=%ai HEAD | awk '{print int((systime()-mktime($1" "$2))/86400)}')
          if [ $DAYS_SINCE_LAST_COMMIT -gt 1 ]; then
            echo "::warning::Branch is stale (>1 day). Rebase on main and push force."
          fi
```

#### Cleanup Automático de Zombie Flags

```yaml
# .github/workflows/feature-flag-cleanup.yml
name: Feature Flag Cleanup
on:
  schedule:
    # Verificar flags zombies 2x por semana
    - cron: '0 9 * * 1,4'  # Segunda e quinta

jobs:
  check-zombie-flags:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Check for zombie flags
        run: |
          # Conectar em Unleash API
          UNLEASH_API="https://unleash.example.com/api"
          UNLEASH_TOKEN="${{ secrets.UNLEASH_API_TOKEN }}"

          # Listar todas as flags
          RESPONSE=$(curl -s "$UNLEASH_API/client/features" \
            -H "Authorization: $UNLEASH_TOKEN")

          # Encontrar flags criadas há > 30 dias que não são archived
          echo "$RESPONSE" | jq '.features[] | 
            select(.createdAt < now - (30 * 86400) and .archived == false) |
            {name: .name, createdAt: .createdAt, age_days: ((now - .createdAt) / 86400)}' \
            > zombie-flags.json

          # Se houver zombie flags, criar issue
          ZOMBIE_COUNT=$(jq 'length' zombie-flags.json)
          if [ "$ZOMBIE_COUNT" -gt 0 ]; then
            echo "Found $ZOMBIE_COUNT zombie flags:"
            jq . zombie-flags.json
            
            # Criar GitHub issue automática
            gh issue create \
              --title "🧟 Zombie Feature Flags Detected" \
              --body "$(jq -r '.[] | "- \(.name) (created: \(.createdAt), age: \(.age_days) days)"' zombie-flags.json)" \
              --labels "technical-debt,feature-flags"
          fi
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

#### Métrica: Age da Flag Mais Velha

```yaml
# prometheus/rules.yml — alerta para flags muito antigas
groups:
- name: feature-flags
  rules:
  - alert: OldestFeatureFlagTooOld
    expr: |
      max(feature_flag_age_days{archived="false"}) > 30
    for: 1h
    annotations:
      summary: "Oldest feature flag é > 30 dias"
      description: "{{ $value | printf '%.0f' }} dias. Revisar e remover."
      severity: "warning"

  - alert: ZombieFlagsInCode
    expr: |
      feature_flags_archived_but_in_code > 0
    for: 1h
    annotations:
      summary: "Found {{ $value }} archived flags still referenced in code"
      description: "Rodar 'grep -r \"flag-name\" src/' para encontrar e remover."
      severity: "warning"
```

```java
// Métricas customizadas: idade da flag mais velha
@Component
public class FeatureFlagMetrics {

    private final UnleashClient unleash;
    private final MeterRegistry meterRegistry;

    @PostConstruct
    void registerMetrics() {
        Gauge.builder("feature_flag_age_days", this, this::oldestFlagAgeDays)
                .description("Age in days of oldest non-archived feature flag")
                .register(meterRegistry);

        Gauge.builder("feature_flags_total", this, this::totalFlagCount)
                .description("Total number of feature flags")
                .tag("archived", "false")
                .register(meterRegistry);
    }

    private double oldestFlagAgeDays() {
        return unleash.getAllFeatures().stream()
                .filter(f -> !f.isArchived())
                .mapToLong(f -> ChronoUnit.DAYS.between(f.getCreatedAt(), LocalDateTime.now()))
                .max()
                .orElse(0);
    }

    private double totalFlagCount() {
        return unleash.getAllFeatures().stream()
                .filter(f -> !f.isArchived())
                .count();
    }
}
```

```
FEATURE FLAGS — BOAS PRÁTICAS:
  □ Flags de curta duração (feature toggle): remover após 100% rollout (máx 30 dias)
  □ Flags de longa duração (ops toggle): circuit breaker manual, modo manutenção (sem expiração)
  □ Naming convention: kebab-case descritivo (novo-calculo-frete, notificacao-push-pedido)
  □ Cleanup: flag ativa há > 30 dias sem ser archived → alerta automático GitHub issue
  □ Testes: testar ambos os caminhos (flag on + flag off) — antes, durante, depois
  □ Trunk-based development: PRs pequenos (<400 linhas), merge na main diariamente
  □ Canary rollout: 5% → 25% → 50% → 100% com métricas entre cada etapa
  □ Métricas: eval_count, error_rate, latency (baseline vs flag enabled)
  □ Correlationid: todos os evals incluem X-Correlation-Id em logs estruturados
  □ Garbage collection: archive flags não mais avaliadas, remover código

FERRAMENTAS RECOMENDADAS:
  ✓ Unleash (open-source, self-hosted) — recomendado para P3 (custo baixo)
  ✓ Flagsmith (open-source, SaaS disponível) — alternativa com UI melhor
  ✓ AWS AppConfig Feature Flags — se já usa AWS e quer zero infra adicional
  ✗ LaunchDarkly — excelente mas caro, só se volume justificar

ANTI-PADRÕES: ZOMBIE FLAGS
  ✗ "Feature flag que fica para sempre" → dobra complexidade de testes e código
  ✗ if (unleash.isEnabled("v1-customer-api")) executado há 1 ano → refactor, remover
  ✗ "Vou deixar archived mas nunca vou remover o código" → dívida técnica silenciosa
  
  Impacto: cada flag adiciona branch ao código → permutações exponenciais de testes
    5 flags → 2^5 = 32 combinações (testável)
    10 flags → 2^10 = 1024 combinações (não testável)
    15 flags → 2^15 = 32768 combinações (impossible)
```

### 6.2.1 Saga Pattern — Distributed Transactions em Microserviços

> Conteúdo integral movido verbatim para `saga-pattern.md` (mesma pasta): estilos orquestrada (AWS Step
> Functions, ASL completo com compensações) vs coreografada (SQS/SNS), invocação Java com idempotency
> key, testes de compensação/idempotência e checklist. Carregue aquele arquivo quando o problema for
> transação distribuída/compensação.

---

### 6.3 GitOps — Alternativa Avançada (ArgoCD / Flux)

GitOps é uma abordagem declarativa onde o **repositório Git é a fonte de verdade** para o estado desejado da infraestrutura e aplicações. Ferramentas como ArgoCD ou Flux monitoram o repositório e reconciliam automaticamente o cluster com o estado declarado.

```
FLUXO GITOPS:
  1. Dev faz commit no repo de manifests (Kubernetes YAML / Helm charts)
  2. ArgoCD/Flux detecta mudança no repo
  3. Reconcilia o cluster com o estado desejado
  4. Se divergir → auto-sync restaura o estado declarado

  Git Repo (manifests) ──► ArgoCD/Flux ──► Kubernetes Cluster
       │                        │               │
       └── PR Review ───────────┘               │
                                                 └── Self-healing
```

**Quando considerar GitOps:**

| Cenário | Recomendação |
|---|---|
| Time < 5 devs, 1-3 serviços | Pipeline CI/CD tradicional (mais simples — P1) |
| Time > 10 devs, Kubernetes, multi-ambiente | GitOps com ArgoCD + ApplicationSets |
| ECS Fargate sem Kubernetes | CI/CD com CodeDeploy (GitOps não se aplica diretamente) |
| Compliance/auditoria forte | GitOps (toda mudança tem PR + approval) |

**Nota:** Para a maioria dos projetos seguindo P1 (Simplicidade), **CI/CD com GitHub Actions + CodeDeploy é suficiente**. GitOps adiciona valor significativo apenas em cenários com Kubernetes e múltiplos ambientes/times.

---

