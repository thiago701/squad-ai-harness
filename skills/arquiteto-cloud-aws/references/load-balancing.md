# Referência — Load Balancing (ALB, NLB, WAF, mTLS)

> Parte da skill `arquiteto-cloud-aws`. Carregue este arquivo sob demanda quando a tarefa tocar este eixo. Hub: `../SKILL.md`.
## Application Load Balancer (ALB) — Especialista Enterprise

> ALB é o ponto único de entrada HTTP/HTTPS da maioria dos sistemas. Erros de configuração aqui geram outage total, não degradação parcial. Trate como infraestrutura crítica.

### ALB vs NLB vs GWLB — Matriz de Decisão

| Característica | **ALB** | **NLB** | **GWLB** |
|----------------|---------|---------|----------|
| Camada OSI | L7 (HTTP/HTTPS/gRPC) | L4 (TCP/UDP/TLS) | L3 (IP packets) |
| Latência p99 | 5-15 ms | < 1 ms (sub-millisecond) | < 1 ms |
| Conexões/segundo | ~25K | **> 1M** | > 1M |
| TLS termination | Sim (SNI, mTLS opcional) | Sim (passthrough ou termination) | Não (passthrough) |
| WebSocket | Sim | Sim | N/A |
| HTTP/2 | Sim | N/A | N/A |
| HTTP/3 (QUIC) | **Sim (2024)** | N/A | N/A |
| gRPC | Sim | Sim (TCP) | N/A |
| Routing rules | Path, host, header, method, query | Não (só porta) | N/A |
| Sticky sessions | Sim (cookie) | Sim (source IP) | N/A |
| Static IPs | Não (DNS only) | **Sim (Elastic IPs)** | Sim |
| WAF integration | **Sim (nativo)** | Não (use CloudFront na frente) | Não |
| Use case | APIs REST, SPAs, microservices | Trading, gaming, IoT, mTLS extremo, > 100K RPS | Firewall appliances inline (Palo Alto, Check Point) |

**Regra:** comece com **ALB** (90% dos casos). Migre para **NLB** quando precisar de IP estático, mTLS sem terminação, ou > 100K RPS sustentado.

### Target Group — Configuração Crítica

```java
ApplicationTargetGroup tg = ApplicationTargetGroup.Builder.create(this, "OrdersTg")
    .vpc(vpc)
    .port(8080)
    .protocol(ApplicationProtocol.HTTP)
    .protocolVersion(ApplicationProtocolVersion.HTTP2)   // HTTP/2 para gRPC e multiplexing
    .targetType(TargetType.IP)                           // IP target para ECS Fargate awsvpc

    // Health checks finos (NÃO usar defaults!)
    .healthCheck(HealthCheck.builder()
        .path("/actuator/health/readiness")              // readiness, NÃO liveness
        .protocol(Protocol.HTTP)
        .port("traffic-port")
        .healthyThresholdCount(2)                        // 2 sucessos = healthy
        .unhealthyThresholdCount(3)                      // 3 falhas = unhealthy
        .interval(Duration.seconds(10))                  // checa a cada 10s
        .timeout(Duration.seconds(5))                    // 5s timeout
        .healthyHttpCodes("200")
        .build())

    // Stickiness — cuidado!
    .stickinessCookieDuration(null)                      // desabilitado por padrão
    // .stickinessCookieDuration(Duration.hours(1))      // só se sessão server-side existir

    // Slow start — task nova não recebe carga total imediatamente
    .slowStart(Duration.seconds(60))                     // ramp linear 60s

    // Deregistration delay — espera conexões em voo terminarem
    .deregistrationDelay(Duration.seconds(30))           // casa com graceful shutdown

    // Connection draining
    .targetGroupName("orders-tg")
    .build();
```

**Erros fatais comuns:**
- ❌ `path: /actuator/health` (genérico) → liveness reinicia pod a cada blip de banco
- ❌ `interval: 30, healthyThresholdCount: 5` → 150s para detectar falha
- ❌ `slowStart: 0` → task nova recebe pico imediato, JIT ainda quente, p99 explode
- ❌ `deregistrationDelay: 300` (default) → deploy lento, conexões longas penduradas
- ❌ `stickiness habilitado sem necessidade` → uneven load distribution, hot tasks

### Listener Rules — Roteamento Avançado

```java
ApplicationListener listener = alb.addListener("HttpsListener",
    BaseApplicationListenerProps.builder()
        .port(443)
        .protocol(ApplicationProtocol.HTTPS)
        .certificates(List.of(ListenerCertificate.fromCertificateManager(cert)))
        .sslPolicy(SslPolicy.TLS13_RES)            // TLS 1.3 only, FS ciphers
        .defaultAction(ListenerAction.fixedResponse(404,
            FixedResponseOptions.builder()
                .contentType("application/json")
                .messageBody("{\"error\":\"not found\"}")
                .build()))
        .build());

// Roteamento por path
listener.addAction("OrdersRoute",
    AddApplicationActionProps.builder()
        .priority(10)
        .conditions(List.of(
            ListenerCondition.pathPatterns(List.of("/api/v1/orders/*"))
        ))
        .action(ListenerAction.forward(List.of(ordersTg)))
        .build());

// Canary release por header
listener.addAction("OrdersCanary",
    AddApplicationActionProps.builder()
        .priority(5)                             // prioridade maior = avaliada antes
        .conditions(List.of(
            ListenerCondition.pathPatterns(List.of("/api/v1/orders/*")),
            ListenerCondition.httpHeader("X-Canary", List.of("true"))
        ))
        .action(ListenerAction.forward(List.of(ordersCanaryTg)))
        .build());

// Weighted forward — split de tráfego
listener.addAction("PaymentsAB",
    AddApplicationActionProps.builder()
        .priority(20)
        .conditions(List.of(
            ListenerCondition.pathPatterns(List.of("/api/v1/payments/*"))
        ))
        .action(ListenerAction.weightedForward(List.of(
            WeightedTargetGroup.builder().targetGroup(paymentsV1Tg).weight(80).build(),
            WeightedTargetGroup.builder().targetGroup(paymentsV2Tg).weight(20).build()
        )))
        .build());
```

### Cross-Zone Load Balancing

**Default ALB:** habilitado (no extra cost dentro da região).
**Default NLB:** **DESABILITADO** (cobra data transfer cross-AZ).

Para sistemas Tier 0, **sempre habilitar cross-zone no NLB**, mesmo pagando data transfer:

```java
NetworkLoadBalancer nlb = NetworkLoadBalancer.Builder.create(this, "Nlb")
    .vpc(vpc)
    .crossZoneEnabled(true)        // CRÍTICO para distribuição equitativa
    .internetFacing(true)
    .build();
```

Sem cross-zone, se um AZ tiver 1 task e outro tiver 10, os 50% de tráfego do AZ menor sobrecarregam a única task.

### mTLS no ALB (Mutual TLS — 2024)

ALB suporta mTLS nativamente desde nov/2023. Substitui solução custom em 90% dos casos.

```java
listener.setMutualAuthentication(MutualAuthentication.builder()
    .mode(MutualAuthenticationMode.VERIFY)              // VERIFY ou PASS_THROUGH
    .trustStore(trustStore)                             // CA bundle no ACM Trust Store
    .ignoreClientCertificateExpiry(false)
    .build());
```

**TrustStore** é gerenciado pelo ACM PCA. Use para integrações B2B com certificados X.509, IoT devices, ou zero-trust internal services.

### WAF Web ACL — Obrigatório em produção

```java
CfnWebACL webAcl = CfnWebACL.Builder.create(this, "WebAcl")
    .name("orders-prod")
    .scope("REGIONAL")                          // CLOUDFRONT para distribuição global
    .defaultAction(CfnWebACL.DefaultActionProperty.builder().allow(Map.of()).build())
    .visibilityConfig(CfnWebACL.VisibilityConfigProperty.builder()
        .sampledRequestsEnabled(true)
        .cloudWatchMetricsEnabled(true)
        .metricName("orders-waf")
        .build())
    .rules(List.of(
        // AWS Managed Rules — Core Rule Set
        rule("AWSManagedRulesCommonRuleSet", 1, "AWS"),
        rule("AWSManagedRulesKnownBadInputsRuleSet", 2, "AWS"),
        rule("AWSManagedRulesAmazonIpReputationList", 3, "AWS"),
        rule("AWSManagedRulesAnonymousIpList", 4, "AWS"),
        rule("AWSManagedRulesSQLiRuleSet", 5, "AWS"),
        rule("AWSManagedRulesLinuxRuleSet", 6, "AWS"),

        // Rate limit — 2000 req/5min por IP
        rateBasedRule("RateLimitPerIp", 10, 2000)
    ))
    .build();

// Associar ao ALB
CfnWebACLAssociation.Builder.create(this, "WafAssoc")
    .resourceArn(alb.getLoadBalancerArn())
    .webAclArn(webAcl.getAttrArn())
    .build();
```

### Métricas Críticas para Alarmar

| Métrica | Threshold (Tier 0) | Ação |
|---------|--------------------|------|
| `HTTPCode_Target_5XX_Count` | > 10 em 5 min | PagerDuty |
| `TargetResponseTime` (p99) | > 2s em 5 min | PagerDuty |
| `RejectedConnectionCount` | > 0 | Investigar (LCU saturada) |
| `UnHealthyHostCount` | ≥ 1 por 5 min | Investigar |
| `ActiveConnectionCount` | > 80% capacity LCU | Scale ALB |
| `ConsumedLCUs` | > 80% provisioned | Cost review (LCU = $0.008/h) |

---

