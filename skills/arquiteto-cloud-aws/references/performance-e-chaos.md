# Referência — Performance Engineering e Chaos (FIS, Game Days)

> Parte da skill `arquiteto-cloud-aws`. Carregue este arquivo sob demanda quando a tarefa tocar este eixo. Hub: `../SKILL.md`.
## Performance Engineering — Carga de Milhões de Usuários

### Benchmarking Obrigatório (Pré-produção)

```yaml
# k6 script — alvo: 100K RPS, 30 minutos sustentado
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '5m',  target: 10000 },     // ramp up
    { duration: '10m', target: 100000 },    // sustained 100K vUsers
    { duration: '30m', target: 100000 },    // soak
    { duration: '5m',  target: 0 }          // ramp down
  ],
  thresholds: {
    'http_req_duration': ['p(99)<200'],     // p99 < 200ms
    'http_req_failed':   ['rate<0.001']     // < 0.1% errors
  }
};

export default function () {
  const res = http.get('https://api.example.com/v1/products/123');
  check(res, { 'status 200': r => r.status === 200 });
  sleep(0.1);
}
```

**Execute via AWS Distributed Load Testing** (CDK template) — gera carga real distribuída em 3+ regiões. Resultado vai para CloudWatch, comparável a métricas de produção.

### Connection Reuse + HTTP/2

- **HTTP/2 nativo no ALB** — multiplexa centenas de requests por conexão
- **Keep-alive entre app e RDS** via HikariCP (default ok)
- **Apache HttpClient 5 com connection pool** para chamadas downstream
- **gRPC para comunicação inter-microservice** (40% menos latency vs REST + JSON)

### Caching Stack

```
Request
  ↓
CloudFront (5min default TTL para GETs)
  ↓
ALB
  ↓
ECS Task → Caffeine in-memory cache (1ms latency, 95% hit rate)
            ↓ miss
            ElastiCache Redis Cluster Mode (5ms latency)
                  ↓ miss
                  RDS Aurora (50ms+ latency)
```

**Layers:**
- **Caffeine (in-memory L1)**: 1ms, dados super hot, TTL curto, capacity bounded
- **Redis Cluster (L2)**: 5ms, dados quentes shared entre tasks, TTL médio
- **DynamoDB DAX**: 1ms para leituras DynamoDB, transparent
- **CloudFront (edge)**: 0ms para clientes na mesma POP

### Database Sizing para 100K+ TPS

- **Aurora Postgres Cluster** com `db.r6g.16xlarge` writer + 3-5 readers
- **RDS Proxy** entre app e Aurora — pool server-side, failover < 1s
- **Read replicas** para queries pesadas, **reader endpoint** com round-robin
- **Aurora Serverless v2** quando carga é variável (10K - 200K ACUs auto-scale)
- **DynamoDB On-Demand** para tabelas com tráfego imprevisível
- **DynamoDB DAX** para leituras quentes (reduz latency de 9ms → 0.4ms)

### Capacity Planning Rule of Thumb

```
Worst case throughput = picoEsperado × 2 (safety factor)
ECS tasks needed     = worstCase ÷ rps_por_task_validado_em_load_test
Min always-on        = ceiling(picoMédio × 0.8)
Aurora connections   = (max_conn_RDS × 0.8) ÷ num_tasks
Redis nodes          = ceiling(cacheSize / 25GB) × 2  (replication)
SQS workers          = ceiling(picoRPS × p99Latency) ÷ batchSize
```

### Pré-Aquecimento (Pre-warming)

Para deploys e Black Friday:

1. **Spring Boot CDS warm-up**: gerar `app-cds.jsa` no build, copiar para imagem
2. **JIT warm-up**: rodar 10K requests sintéticos no startup health check (`/actuator/warmup`)
3. **Connection pool warm-up**: HikariCP `initialization-fail-timeout` + `minimum-idle = max`
4. **Cache warm-up**: pre-load top 1000 keys do Redis no startup
5. **ALB warm-up**: `aws elbv2 modify-load-balancer-attributes` solicitar via Support para eventos pico
6. **Lambda concurrent execution**: provisioned concurrency para funções críticas

---

## Chaos Engineering com AWS FIS

```java
CfnExperimentTemplate fisTemplate = CfnExperimentTemplate.Builder.create(this, "TerminateTaskExp")
    .description("Terminate 30% of orders ECS tasks")
    .roleArn(fisRole.getRoleArn())
    .stopConditions(List.of(
        CfnExperimentTemplate.ExperimentTemplateStopConditionProperty.builder()
            .source("aws:cloudwatch:alarm")
            .value(error5xxAlarm.getAlarmArn())
            .build()
    ))
    .targets(Map.of("EcsTasks",
        CfnExperimentTemplate.ExperimentTemplateTargetProperty.builder()
            .resourceType("aws:ecs:task")
            .resourceTags(Map.of("Service", "orders"))
            .selectionMode("PERCENT(30)")
            .build()))
    .actions(Map.of("TerminateTasks",
        CfnExperimentTemplate.ExperimentTemplateActionProperty.builder()
            .actionId("aws:ecs:stop-task")
            .targets(Map.of("Tasks", "EcsTasks"))
            .build()))
    .tags(Map.of("Environment", "staging"))
    .build();
```

**Execução mensal mínima em staging.** Se algo quebra, é bug a ser corrigido — não desculpa para parar de testar.

### Game Days — Trimestral

Simular falhas em produção controlada:
- AZ inteira down (network partition)
- RDS failover forçado
- ElastiCache primary down
- ALB target group esgotado
- DynamoDB throttling

Documentar runbooks. Treinar on-call. **MTTR cai pela metade após 2 game days bem feitos.**

---



```
Ideal para: MVP, produto novo, tráfego imprevisível

┌─────────┐    ┌─────────────┐    ┌────────┐    ┌─────┐
│ Cliente │───►│ API Gateway │───►│ Lambda │───►│ RDS │
└─────────┘    └─────────────┘    └────────┘    └─────┘
                                       │
                              ┌────────▼────────┐
                              │    DynamoDB      │  ← sessões, cache
                              │    (free tier)   │
                              └─────────────────┘

Custo estimado (100k req/mês):
  Lambda:      FREE (dentro do free tier)
  API Gateway: $0.035 (100k requests HTTP API)
  RDS t3.micro: FREE (12 meses) → $15/mês depois
  DynamoDB:    FREE (permanente)
  Total:       ~$0 nos primeiros 12 meses
```

