# X-Ray Sampling 3-Tiers — Estratégia Canônica

> Custo de X-Ray cresce linearmente com o volume de traces. Em produção real, tracear 100% das requisições é inviável. Uma estratégia **3-tiers** equilibra observabilidade crítica com custo previsível.

## Regra Geral

| Tier | Tipo de Request | Taxa | Fixed Rate | Reservoir |
|------|-----------------|-----:|-----------:|----------:|
| **Tier 1** | Health checks, liveness/readiness probes | **1%** | 0.01 | 0 req/s |
| **Tier 2** | Tráfego normal (`/api/*`) | **10%** | 0.10 | 1 req/s |
| **Tier 3** | **Erros 5xx** + requisições lentas (> p95) | **100%** | 1.00 | 5 req/s |

**Justificativa**:
- Tier 1: health checks são ruído — 1% é suficiente para detectar falha do endpoint em si.
- Tier 2: 10% cobre distribuição estatisticamente representativa sem explodir custo.
- Tier 3: **erros sempre vão para o X-Ray** — o debugging requer 100% de visibilidade em cenários de falha.

## Configuração — Sampling Rules (JSON)

Subir via CDK Java, Terraform ou Console AWS. Regras são avaliadas em ordem de `priority` (menor = antes).

```json
{
  "version": 2,
  "rules": [
    {
      "description": "Tier 3 — Erros 5xx (máxima prioridade)",
      "priority": 100,
      "http_method": "*",
      "url_path": "*",
      "service_type": "*",
      "service_name": "*",
      "host": "*",
      "resource_arn": "*",
      "fixed_target": 5,
      "rate": 1.0,
      "attributes": {
        "http.status_code": "5*"
      }
    },
    {
      "description": "Tier 1 — Health checks",
      "priority": 200,
      "http_method": "GET",
      "url_path": "/actuator/*",
      "service_type": "*",
      "service_name": "*",
      "host": "*",
      "resource_arn": "*",
      "fixed_target": 0,
      "rate": 0.01
    },
    {
      "description": "Tier 1 — Kubernetes probes",
      "priority": 210,
      "http_method": "GET",
      "url_path": "/healthz*",
      "service_type": "*",
      "service_name": "*",
      "host": "*",
      "resource_arn": "*",
      "fixed_target": 0,
      "rate": 0.01
    },
    {
      "description": "Tier 2 — Tráfego normal (default)",
      "priority": 9000,
      "http_method": "*",
      "url_path": "*",
      "service_type": "*",
      "service_name": "*",
      "host": "*",
      "resource_arn": "*",
      "fixed_target": 1,
      "rate": 0.10
    }
  ],
  "default": {
    "fixed_target": 1,
    "rate": 0.05
  }
}
```

## Configuração — CDK Java

```java
import software.amazon.awscdk.services.xray.CfnSamplingRule;

CfnSamplingRule.Builder.create(this, "Tier3Errors")
    .samplingRule(CfnSamplingRule.SamplingRuleProperty.builder()
        .ruleName("tier3-errors")
        .priority(100)
        .fixedRate(1.0)
        .reservoirSize(5)
        .httpMethod("*")
        .urlPath("*")
        .host("*")
        .serviceName("*")
        .serviceType("*")
        .resourceArn("*")
        .attributes(Map.of("http.status_code", "5*"))
        .version(1)
        .build())
    .build();

CfnSamplingRule.Builder.create(this, "Tier1HealthChecks")
    .samplingRule(CfnSamplingRule.SamplingRuleProperty.builder()
        .ruleName("tier1-health-checks")
        .priority(200)
        .fixedRate(0.01)
        .reservoirSize(0)
        .httpMethod("GET")
        .urlPath("/actuator/*")
        .host("*")
        .serviceName("*")
        .serviceType("*")
        .resourceArn("*")
        .version(1)
        .build())
    .build();

CfnSamplingRule.Builder.create(this, "Tier2Default")
    .samplingRule(CfnSamplingRule.SamplingRuleProperty.builder()
        .ruleName("tier2-default")
        .priority(9000)
        .fixedRate(0.10)
        .reservoirSize(1)
        .httpMethod("*")
        .urlPath("*")
        .host("*")
        .serviceName("*")
        .serviceType("*")
        .resourceArn("*")
        .version(1)
        .build())
    .build();
```

## OpenTelemetry Equivalente

Quando usando o OpenTelemetry Collector + AWS X-Ray exporter, a sampling é feita **antes** do export:

```yaml
# otel-collector-config.yaml
processors:
  tail_sampling:
    decision_wait: 10s
    num_traces: 100
    policies:
      - name: tier3-errors
        type: status_code
        status_code: { status_codes: [ERROR] }
      - name: tier3-slow
        type: latency
        latency: { threshold_ms: 1000 }
      - name: tier1-health
        type: string_attribute
        string_attribute:
          key: http.target
          values: [/actuator/.*, /healthz.*]
          enabled_regex_matching: true
          invert_match: false
        probabilistic: { sampling_percentage: 1 }
      - name: tier2-default
        type: probabilistic
        probabilistic: { sampling_percentage: 10 }

exporters:
  awsxray:
    region: us-east-1
```

## Observações Operacionais

1. **Reservoir** é o número mínimo garantido por segundo — útil para Tier 3 garantir que erros raros não sejam perdidos mesmo com `rate` pequeno.
2. **Custo esperado**: ~90% de redução vs 100% sampling em tráfego médio (10% tier 2 + 1% tier 1 dominando volume).
3. **Service Maps** continuam corretos — X-Ray usa **todos** os traces para construir o mapa; sampling afeta apenas o armazenamento detalhado.
4. **Correlação logs ↔ traces**: mesmo em traces não-sampled, o `Trace-Id` continua propagado — permita busca em logs estruturados (Loki, CloudWatch Insights).
5. **Alterações de rule são dinâmicas** — X-Ray daemon refaz refresh a cada ~10s sem restart.

## Anti-padrões

- ❌ **Rate=1.0 em produção** em todas rotas — bomba de custo.
- ❌ **Rate=0.01 em tudo** — perde-se visibilidade em debugging.
- ❌ **Regras sem priority explícita** — ordem indeterminada.
- ❌ **Exceções a regex de URL** — manter regras simples e revisáveis.

## Conexões

- Aplicado em `arquiteto-cloud-aws/SKILL.md` (seção Observabilidade distribuída)
- Complementa CloudWatch Application Signals (métricas) + Logs estruturados
- Cross-reference: `engenheiro-devops` (OpenTelemetry pipeline)
