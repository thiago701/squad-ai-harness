# Referência — Modo Especialista Enterprise (filosofia + stack Tier 0)

> Parte da skill `arquiteto-cloud-aws`. Carregue este arquivo sob demanda quando a tarefa tocar este eixo. Hub: `../SKILL.md`.
## Modo Especialista Enterprise (P1 = PERFORMANCE inegociável)

> **ATENÇÃO — INVERSÃO DE PRIORIDADES PARA PROJETOS CORPORATIVOS DE ALTA ESCALA.**
>
> Para empresas que **já operam massivamente na AWS** atendendo milhões de usuários simultâneos, o jogo muda. As três prioridades do ecossistema (P1 Simplicidade > P2 Performance > P3 Custo) são **invertidas** quando o sistema precisa entregar **disponibilidade 99,99%+, latência p99 < 100ms global e throughput de centenas de milhares de RPS sustentado**:
>
> ```
> P1 — PERFORMANCE   (inegociável)  → SLAs cumpridos sob carga real de produção
> P2 — RESILIÊNCIA   (multi-AZ + multi-region quando aplicável)
> P3 — SIMPLICIDADE  (mantida onde não conflita com P1/P2)
> P4 — CUSTO         (free tier vira secundário; otimização vem depois de SLO ok)
> ```
>
> **Quando ativar este modo:**
> - Sistema com pico real ≥ 50.000 RPS sustentados
> - SLO de disponibilidade ≥ 99,95% mensal
> - Latência p99 < 200ms exigida pelo negócio
> - Receita direta correlacionada com latência (e-commerce, fintech, streaming)
> - Time tem orçamento AWS provisionado e budget review trimestral
>
> Sem esses gatilhos, **continue no modo padrão** (P1 Simplicidade). Engenharia para escala que não existe é desperdício de tempo e dinheiro.

### Filosofia do Modo Enterprise

Você é um arquiteto sênior atendendo um time corporativo que **já paga AWS Enterprise Support**, tem **TAM dedicado** e roda cargas que justificam **Reserved Instances + Savings Plans + Compute Optimizer**. Aqui:

1. **Benchmarking é obrigatório**: nenhuma decisão arquitetural sem dados reais de carga (k6, Gatling, Locust, AWS Distributed Load Testing).
2. **Multi-AZ é o piso**: 1 AZ é configuration error. Multi-region é a meta para Tier 0.
3. **Capacity Provider Strategies + Predictive Scaling** substituem auto-scaling reativo.
4. **Infraestrutura como código (CDK Java)** com testes automatizados (`assertions` do CDK).
5. **Observability stack premium**: CloudWatch + X-Ray + Prometheus/Grafana managed + DataDog/New Relic se justificável.
6. **Chaos Engineering** com AWS FIS (Fault Injection Simulator) em staging — mensal mínimo.

### Stack de Referência Enterprise (Tier 0)

```
┌──────────────────────────────────────────────────────────────────────┐
│  Route 53 (latency-based + health checks + DNS Failover multi-region) │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│  CloudFront (edge caching + AWS Shield Advanced + WAF + L4-L7)        │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Global Accelerator (anycast IP) — opcional para latência ultra-baixa │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│  ALB (HTTP/2, gRPC, mTLS) ─OR─ NLB (TCP/UDP TLS, > 1M conn/s)         │
│  Cross-zone enabled · WAF associado · TLS 1.3 + ACM                   │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│  ECS Fargate (Graviton ARM) com Capacity Providers                    │
│   FARGATE (base 4) + FARGATE_SPOT (até 70%)                           │
│   Service Connect · ECS Exec · App Mesh (opcional)                    │
└──────────────────────────────────────────────────────────────────────┘
                                  │
            ┌─────────────────────┼─────────────────────┐
            ▼                     ▼                     ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ RDS Aurora       │  │ ElastiCache      │  │ DynamoDB         │
│ Postgres Cluster │  │ Valkey/Redis 7   │  │ Global Tables    │
│ + RDS Proxy      │  │ Cluster Mode     │  │ + DAX            │
│ + Reader Endpoint│  │ + Auto-scaling   │  │ + Streams        │
└──────────────────┘  └──────────────────┘  └──────────────────┘
            │                     │                     │
            └─────────────────────┼─────────────────────┘
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│  SQS (FIFO + Standard) · S3 (Multi-Region Access Points)              │
│  Kinesis Data Streams · MSK (Kafka managed) — para eventos > 100K/s   │
└──────────────────────────────────────────────────────────────────────┘
```

---

