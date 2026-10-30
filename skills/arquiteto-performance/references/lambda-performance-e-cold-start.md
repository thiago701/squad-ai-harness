# arquiteto-performance · Lambda — Performance e Cold Start

> Reference da skill `arquiteto-performance` (movida da SKILL.md em 11/10/2026 — hub + references, I3). Carregue só quando a tarefa pedir este tema.

## Lambda — Performance e Cold Start

### Diagnóstico de Cold Start

```
Métricas chave no CloudWatch:
  InitDuration  → tempo de inicialização (cold start real)
  Duration      → tempo de execução pós-init
  BilledDuration → InitDuration + Duration (o que você paga)

Threshold de ação:
  InitDuration > 1000ms  → Habilitar SnapStart (zero config)
  InitDuration > 300ms pós-SnapStart → GraalVM Native Image
  Duration p99 > timeout × 0.8 → aumentar timeout ou otimizar lógica
```

**Como medir com CloudWatch Insights:**

```sql
-- Frequência e magnitude de cold starts por hora
fields @timestamp, @initDuration, @duration, @requestId
| filter @type = "REPORT" and ispresent(@initDuration)
| stats count() as cold_starts, avg(@initDuration) as avg_init_ms,
         max(@initDuration) as max_init_ms by bin(1h)
| sort by bin(1h) desc
```

### Decisão SnapStart vs GraalVM Native

```
SnapStart (escolha padrão — zero esforço):
  ✓ Resultado: 100–300ms cold start (restore do snapshot da JVM)
  ✓ Suporta 100% das features Java (reflection, dynamic proxies, ThreadLocal)
  ✓ Habilitar: SnapStart.ApplyOn = PublishedVersions + invocar pelo alias
  ✗ Não elimina 100% do cold start — há overhead de restore

GraalVM Native Image (latência crítica):
  ✓ Resultado: 10–50ms cold start (binário nativo, sem JVM)
  ✓ 30–50% menos memória Lambda necessária
  ✗ Build: 15–25 min CI (vs 3 min JVM)
  ✗ Reflection requer reflect-config.json manual para libs não suportadas
  ✗ Debugging mais difícil

CRaC / OpenJ9 Checkpoint (alternativa emergente):
  ✓ Resultado: 40–100ms, sem limitações de reflection
  ✓ OpenJ9 26+ com CRIU — checkpoint de JVM aquecida (incluindo JIT compilado)
  ✗ Suporte AWS experimental (custom runtime al2023)
```

### Lambda Power Tuning — Achando a Memória Ótima

**Memória padrão (128MB) raramente é o melhor custo-benefício.** Para Java, frequentemente
512MB–1024MB é mais barato por invocação E mais rápido. Para Python/Node, 256–512MB.

```bash
# Deploy Lambda Power Tuning (uma vez por conta):
aws serverlessrepo create-cloud-formation-change-set \
  --application-id arn:aws:serverlessrepo:us-east-1:451282441545:applications/aws-lambda-power-tuning \
  --semantic-version 4.3.4 \
  --stack-name lambda-power-tuning \
  --capabilities CAPABILITY_IAM

# Executar análise (50 invocações por configuração de memória):
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:us-east-1:$ACCOUNT:stateMachine:powerTuningMachine \
  --input '{
    "lambdaARN": "arn:aws:lambda:us-east-1:$ACCOUNT:function:minha-funcao",
    "powerValues": [128, 256, 512, 1024, 1536, 2048, 3008],
    "num": 50,
    "payload": {"body": "{}"},
    "parallelInvocation": true,
    "strategy": "cost"
  }'
```

**Saída:** URL para visualização de curva custo × velocidade. Escolha o ponto de mínimo custo.

### Heurísticas Lambda Performance

| Sintoma | Causa Provável | Ação |
|---|---|---|
| InitDuration > 2s, Java | Cold start sem SnapStart | `SnapStart.ApplyOn = PublishedVersions` |
| InitDuration 100–300ms pós-SnapStart | Restore overhead (normal) | Aceitável; se crítico → GraalVM |
| Duration constante alta | Memória sub-dimensionada | Lambda Power Tuning |
| p99 >> p95 (spike) | Cold starts esporádicos + GC | Provisioned Concurrency para baseline |
| Throttling (TooManyRequests) | Limite de concorrência da conta/função ou pico além da taxa de escalonamento | Calcular RPS × duração; reservar (proteger) ou limitar (conter) por função; fila na frente — ver `references/lambda-diagnostico-por-sintoma.md` |
| Timeout esporádico | Downstream lento ou loop | Adicionar circuit breaker + timeout SDK |
| Custo inesperado alto | Memória grande desnecessária OU muitas invocações desnecessárias | Power Tuning + SQS batch de eventos |

> **Sintoma fora da tabela?** (iterador de stream atrasando, DLQ enchendo, timeout em VPC, SnapStart sem efeito,
> 502/503 no API Gateway) → `references/lambda-diagnostico-por-sintoma.md` (diagnóstico por sintoma, sob demanda).


### Provisioned Concurrency — Eliminar Cold Start em Produção

Para workloads com SLA rígido (< 100ms p99 absoluto), use Provisioned Concurrency para
manter instâncias pré-aquecidas. **Mais caro** (paga mesmo idle), use com critério.

```yaml
# SAM — Provisioned Concurrency no alias de produção
PedidoFunctionAlias:
  Type: AWS::Lambda::Alias
  Properties:
    FunctionName: !Ref PedidoFunction
    FunctionVersion: !GetAtt PedidoFunction.Version
    Name: prod
    ProvisionedConcurrencyConfig:
      ProvisionedConcurrentExecutions: 10   # 10 instâncias sempre quentes
```

**Auto Scaling de Provisioned Concurrency** (escala com agendamento ou métricas):

```bash
# Target tracking — mantém 70% de utilização das instâncias provisionadas
aws application-autoscaling register-scalable-target \
  --service-namespace lambda \
  --resource-id function:minha-funcao:prod \
  --scalable-dimension lambda:function:ProvisionedConcurrency \
  --min-capacity 2 \
  --max-capacity 50

aws application-autoscaling put-scaling-policy \
  --service-namespace lambda \
  --resource-id function:minha-funcao:prod \
  --scalable-dimension lambda:function:ProvisionedConcurrency \
  --policy-name pc-tracking \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration \
    '{"TargetValue":0.7,"PredefinedMetricSpecification":{"PredefinedMetricType":"LambdaProvisionedConcurrencyUtilization"}}'
```

---
