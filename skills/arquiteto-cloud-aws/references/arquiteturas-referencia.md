# Referência — Arquiteturas de Referência (VPC, Multi-Region, Free Tier)

> Parte da skill `arquiteto-cloud-aws`. Carregue este arquivo sob demanda quando a tarefa tocar este eixo. Hub: `../SKILL.md`.
### Arquitetura 2 — Microserviço com Filas (processamento assíncrono)

```
Ideal para: sistema com picos, processamento demorado, desacoplamento

┌─────────┐    ┌────────┐    ┌─────┐    ┌────────────┐
│ API GW  │───►│ Lambda │───►│ SQS │───►│ Lambda     │
│         │    │(sync)  │    │     │    │(async)     │
└─────────┘    └────────┘    └─────┘    └─────┬──────┘
                                               │
                                    ┌──────────▼───────────┐
                                    │  SES (email)          │
                                    │  SNS (push/SMS)       │
                                    │  RDS (persistência)   │
                                    └──────────────────────┘
Custo estimado (500k operações/mês):
  Lambda:      FREE
  SQS:         FREE (1M req/mês gratuito)
  API Gateway: ~$0.18
  Total:       < $1/mês
```

### Arquitetura 3 — Aplicação Containerizada (Java Spring Boot)

```
Ideal para: API Java que precisa de JVM estável, tráfego constante

┌─────────┐    ┌─────┐    ┌──────────────┐    ┌─────┐
│ Route53 │───►│ ALB │───►│  ECS Fargate │───►│ RDS │
└─────────┘    └─────┘    │  (2 tasks)   │    └─────┘
                           └──────┬───────┘
                                  │           ┌───────────┐
                                  └──────────►│ElastiCache│
                                              │  (Redis)  │
                                              └───────────┘
Custo estimado (tráfego médio, 24/7):
  ECS Fargate (0.25 vCPU, 0.5GB × 2): ~$18/mês
  ALB:                                  ~$18/mês
  RDS t3.small:                         ~$28/mês
  ElastiCache t3.micro:                 ~$13/mês
  Total:                                ~$77/mês
```

### 3.1 VPC Reference Architecture — 3-Tier Network

```
┌─────────────────────────────────────────────────────────────────┐
│                         VPC (10.0.0.0/16)                       │
│                                                                  │
│  ┌──────────────── AZ-a ──────────────┐  ┌──── AZ-b ──────────┐│
│  │                                     │  │                     ││
│  │  ┌─────────────────────────────┐   │  │  (espelha AZ-a)    ││
│  │  │ Public Subnet (10.0.1.0/24) │   │  │                     ││
│  │  │ ALB, NAT Gateway, Bastion   │   │  │  Public (10.0.2.0) ││
│  │  └──────────────┬──────────────┘   │  │                     ││
│  │                 │                   │  │                     ││
│  │  ┌──────────────▼──────────────┐   │  │                     ││
│  │  │ Private Subnet (10.0.3.0/24)│   │  │  Private (10.0.4.0)││
│  │  │ ECS Fargate Tasks, Lambda   │   │  │                     ││
│  │  └──────────────┬──────────────┘   │  │                     ││
│  │                 │                   │  │                     ││
│  │  ┌──────────────▼──────────────┐   │  │                     ││
│  │  │ Isolated Subnet (10.0.5.0/24│   │  │  Isolated (10.0.6.0││
│  │  │ RDS, ElastiCache (sem NAT)  │   │  │                     ││
│  │  └─────────────────────────────┘   │  │                     ││
│  └─────────────────────────────────────┘  └─────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

**CDK Java 25 — VPC 3-Tier:**

```java
var vpc = Vpc.Builder.create(this, "AppVpc")
    .maxAzs(2)
    .natGateways(1)               // 1 NAT para custo (2 para HA)
    .subnetConfiguration(List.of(
        SubnetConfiguration.builder()
            .name("Public")
            .subnetType(SubnetType.PUBLIC)
            .cidrMask(24)
            .build(),
        SubnetConfiguration.builder()
            .name("Private")
            .subnetType(SubnetType.PRIVATE_WITH_EGRESS)
            .cidrMask(24)
            .build(),
        SubnetConfiguration.builder()
            .name("Isolated")
            .subnetType(SubnetType.PRIVATE_ISOLATED)
            .cidrMask(24)
            .build()))
    .build();

// Security Groups — princípio do mínimo privilégio
var albSg = SecurityGroup.Builder.create(this, "AlbSg")
    .vpc(vpc).allowAllOutbound(false).build();
albSg.addIngressRule(Peer.anyIpv4(), Port.tcp(443), "HTTPS from internet");

var appSg = SecurityGroup.Builder.create(this, "AppSg")
    .vpc(vpc).allowAllOutbound(false).build();
appSg.addIngressRule(albSg, Port.tcp(8080), "From ALB only");

var dbSg = SecurityGroup.Builder.create(this, "DbSg")
    .vpc(vpc).allowAllOutbound(false).build();
dbSg.addIngressRule(appSg, Port.tcp(5432), "PostgreSQL from app only");
```

**Security Groups vs NACLs:**

| Aspecto | Security Group | NACL |
|---|---|---|
| Nível | ENI (instância/task) | Subnet |
| Estado | Stateful (retorno automático) | Stateless (regra explícita in/out) |
| Regras | Apenas ALLOW | ALLOW e DENY |
| Ordem | Todas avaliadas | Número de prioridade |
| Quando usar | Sempre (primary) | Camada extra para compliance |

**Checklist VPC:**
- ✅ 3 tiers de subnet: Public (ALB/NAT), Private (compute), Isolated (dados)
- ✅ Mínimo 2 AZs para alta disponibilidade
- ✅ NAT Gateway em subnet pública para egress de subnets privadas
- ✅ Security Groups com mínimo privilégio (ALB→App→DB chain)
- ✅ VPC Flow Logs habilitado para auditoria (S3 ou CloudWatch)
- ✅ Sem acesso direto à internet de subnets isoladas
- ✅ Endpoints VPC para S3, DynamoDB, ECR (evita tráfego via NAT)

### 3.2 Multi-Region Patterns — Alta Disponibilidade

```
Ideal para: Aplicações que exigem RPO < 1h e RTO < 5min

                    ┌────────────────────────────────────┐
                    │        Route53 (Failover Policy)    │
                    │  Primary: us-east-1  │  Secondary: us-west-2 │
                    └────────┬─────────────┴──────────┬──┘
                             │                        │
               ┌─────────────▼──────────┐  ┌─────────▼──────────────┐
               │    us-east-1 (PRIMARY) │  │  us-west-2 (STANDBY)   │
               │                        │  │                        │
               │  ALB → ECS Fargate     │  │  ALB → ECS Fargate     │
               │         │              │  │         │              │
               │    RDS Primary ────────┼──┼──► RDS Read Replica   │
               │         │              │  │                        │
               │  ElastiCache (Redis)   │  │  ElastiCache (Redis)   │
               └────────────────────────┘  └────────────────────────┘
```

**Route53 Failover — CDK Java 25:**

```java
// Route53 Health Check + Failover Routing
var healthCheck = CfnHealthCheck.Builder.create(this, "PrimaryHealthCheck")
    .healthCheckConfig(CfnHealthCheck.HealthCheckConfigProperty.builder()
        .type("HTTPS")
        .fullyQualifiedDomainName("api.example.com")
        .port(443)
        .resourcePath("/actuator/health")
        .requestInterval(10)          // check a cada 10s
        .failureThreshold(3)          // 3 falhas → failover
        .build())
    .build();

// Record Set com Failover Policy
RecordSet.Builder.create(this, "PrimaryRecord")
    .zone(hostedZone)
    .recordName("api.example.com")
    .recordType(RecordType.A)
    .target(RecordTarget.fromAlias(new LoadBalancerTarget(primaryAlb)))
    .build();
// Adicionar failover policy via CfnRecordSet para primary/secondary
```

**RDS Read Replica Cross-Region — CDK Java 25:**

```java
// RDS Primary na região primária
var primaryDb = DatabaseInstance.Builder.create(this, "PrimaryDB")
    .engine(DatabaseInstanceEngine.postgres(
        PostgresInstanceEngineProps.builder()
            .version(PostgresEngineVersion.VER_16_4)
            .build()))
    .instanceType(InstanceType.of(InstanceClass.T3, InstanceSize.SMALL))
    .multiAz(true)                    // Alta disponibilidade intra-região
    .storageEncrypted(true)
    .build();

// Read Replica cross-region (deploy no stack da região secundária)
var readReplica = DatabaseInstanceReadReplica.Builder
    .create(secondaryStack, "CrossRegionReplica")
    .sourceDatabaseInstance(primaryDb)
    .instanceType(InstanceType.of(InstanceClass.T3, InstanceSize.SMALL))
    .build();
```

**Padrões de Multi-Region:**

| Padrão | RPO | RTO | Custo | Quando usar |
|---|---|---|---|---|
| **Backup & Restore** | Horas | Horas | $ | Dev, staging |
| **Pilot Light** | Minutos | 15-30min | $$ | Apps não-críticas |
| **Warm Standby** | Segundos | < 5min | $$$ | Apps de negócio |
| **Active-Active** | Zero | Zero | $$$$ | Apps mission-critical |

**Checklist Multi-Region:**
- ✅ Route53 Health Check com failover policy configurado
- ✅ RDS Read Replica cross-region para dados quentes
- ✅ ElastiCache Global Datastore para cache distribuído
- ✅ S3 Cross-Region Replication para assets estáticos
- ✅ Secrets Manager replicado nas duas regiões
- ✅ CloudWatch Cross-Region Dashboard para monitoramento unificado
- ✅ Runbook de failover manual + automático documentado

### Arquitetura 4 — Full Stack com Autenticação (produção real)

```
┌─────────────┐   ┌───────────┐   ┌────────────┐
│  CloudFront │◄──│    S3     │   │  Cognito   │
│  (CDN/SPA)  │   │(frontend) │   │(auth)      │
└──────┬──────┘   └───────────┘   └─────┬──────┘
       │                                │
       ▼                                ▼
┌─────────────┐   ┌────────────────────────────┐
│ API Gateway │──►│     Lambda Functions        │
│ + Cognito   │   │  (business logic por rota)  │
│ Authorizer  │   └─────────────┬──────────────┘
└─────────────┘                 │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
                  ┌─────┐   ┌─────┐   ┌────────┐
                  │ RDS │   │ SQS │   │   S3   │
                  └─────┘   └─────┘   └────────┘
```

---

## Free Tier AWS — Mapa Completo para Desenvolvimento

```
PERMANENTE (não expira nunca):
  Lambda:        1M invocações/mês + 400k GB-segundos
  DynamoDB:      25GB + 25 WCU + 25 RCU
  SQS:           1M requisições/mês
  SNS:           1M publicações/mês
  CloudWatch:    10 métricas + 5GB logs + 3 dashboards
  CodeBuild:     100 min/mês
  ECR:           500MB/mês
  Secrets Manager: NÃO tem free tier ($0.40/secret/mês)
  Parameter Store: SSM Standard Parameters — GRATUITO (use no lugar de Secrets Manager para valores não críticos)

PRIMEIROS 12 MESES:
  EC2:           750h t2.micro/mês
  RDS:           750h db.t3.micro/mês + 20GB storage
  S3:            5GB + 20k GET + 2k PUT
  ElastiCache:   750h cache.t3.micro/mês
  CloudFront:    1TB egress/mês + 10M requisições
  API Gateway:   1M requisições REST ou 1M HTTP/mês
  Cognito:       50k MAU/mês (permanente para User Pools)
  SES:           3k mensagens/mês (permanente ao enviar de EC2/Lambda)
```

---

