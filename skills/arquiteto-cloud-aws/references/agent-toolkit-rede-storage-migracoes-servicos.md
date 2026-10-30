# Catálogo de Rede, Storage, Compute, Comunicações e Migrações (Agent Toolkit for AWS)

> **Procedência:** absorvido e reescrito em PT-BR a partir de `aws/agent-toolkit-for-aws` (`skills/core-skills/*`, `networking-and-content-delivery-skills/*`, `ec2-skills/*`, `storage-skills/*`, `customer-communications-skills/*`, `aws-marketplace-skills/*`, `end-user-computing-skills/*`, `quantum-computing-skills/*`, `migration-and-modernization-skills/*`, `web-and-mobile-development/*` e `plugins/aws-startup-advisor/skills/*`, commit `658b852f0612ca629d56d0a4de52738fb6a58714`, Apache-2.0).

---

## 1. Rede, Borda e Conectividade Híbrida (`aws-networking` + 12 Skills Especializadas)

| Domínio / Tarefa | Skill Absorvida | Padrão Arquitetural e Guardrails |
|---|---|---|
| **VPC de Produção Multi-AZ** | `creating-production-vpc-multi-az` | Mínimo 2–3 AZs, sub-redes públicas (apenas ALB/NAT) e privadas (workloads/bancos), Flow Logs ativos. Nunca coloque banco de dados em sub-rede pública |
| **Acesso Privado a Serviços AWS (PrivateLink)** | `configuring-vpc-endpoints-for-private-aws-service-access` | Use **Gateway Endpoints** (custo zero por hora/GB) para **S3 e DynamoDB**; use **Interface Endpoints** (PrivateLink) para SQS, SNS, KMS, Secrets Manager, ECR e Bedrock em sub-redes sem NAT |
| **Saída de Internet para Lambda em VPC** | `enabling-lambda-vpc-internet-access` | Lambdas em VPC privada nunca saem à internet mesmo com Public IP; exigem sub-rede privada com rota `0.0.0.0/0` apontando para um **NAT Gateway** situado em sub-rede pública (com IGW) |
| **VPC Peering vs Transit Gateway** | `connecting-vpcs-with-peering`, `transitgateway` | **VPC Peering** (não-transitivo, sem custo de hora) para 2–3 VPCs com CIDR sem sobreposição; **Transit Gateway** (hub-and-spoke, inspeção centralizada L3/L7 com AWS Network Firewall) para > 3 VPCs ou conectividade híbrida em escala |
| **Conectividade Híbrida (VPN e Direct Connect)** | `sitetositevpn`, `directconnect` | **Site-to-Site VPN** com BGP dinâmico e 2 túneis ativos para entrada rápida/backup; **Direct Connect** (Dedicated ou Hosted) com MACsec/IPsec e VIFs resilientes em múltiplos locais para banda dedicada e latência previsível |
| **DNS e Roteamento Global** | `route53`, `routing-traffic-with-route53-and-cloudfront` | Route 53 Alias records (`A` e `AAAA`) apontando para CloudFront/ALB, Health Checks com failover ativo-passivo, DNSSEC e **Route 53 Resolver DNS Firewall** contra domínios maliciosos |
| **CDN e Proteção de Origem** | `cloudfront` | **Origin Access Control (OAC)** obrigatório para origens S3/Lambda URL/VPC Origins; TLS 1.2/1.3 no ACM (`us-east-1`), políticas de cache separadas de origin request policies e suporte a distribuições multi-tenant |
| **Proteção L7 e DDoS** | `waf`, `shieldadvanced` | **AWS WAF**: implante Managed Rules primeiro em modo `Count`, analise labels, crie exceções cirúrgicas e promova para `Block` + Rate-Based Rules. **Shield Advanced**: agrupe recursos em Protection Groups, configure detecção baseada em Health Checks do Route 53 e mitigação automática L7 |

---

## 2. Compute EC2, Containers e Armazenamento (`aws-compute`, `aws-containers`, `aws-storage`, `ec2-skills`, `storage-skills`)

- **EC2 com Boas Práticas (`aws-compute`, `launching-ec2-instance-with-best-practices`, `setting-up-ec2-instance-profiles`, `amazon-ec2-image-builder`):**
  1. Prefira instâncias **Graviton (Arm64 — `m7g`, `c7g`, `r7g`, `t4g`)** para melhor relação preço/performance.
  2. Exija **IMDSv2 obrigatório** (`HttpTokens: required`, `HttpPutResponseHopLimit: 1` ou `2` para containers).
  3. **Zero chaves SSH estáticas ou Access Keys em disco:** acesse via **SSM Session Manager** e autentique chamadas AWS via **EC2 Instance Profile** com IAM Role de privilégio mínimo.
  4. Para imagens douradas (AMIs ou imagens de container endurecidas CIS/STIG), automatize pipelines recorrentes no **EC2 Image Builder** com testes e scanning Inspector antes da distribuição.
- **Containers (`aws-containers`):**
  - Escolha **ECS Fargate** como padrão operacional (P1); use **EKS** apenas quando houver requisito real de portabilidade Kubernetes multi-cloud ou operadores K8s específicos. Ative scanning no push e políticas de ciclo de vida (lifecycle policies) em todo repositório **ECR**.
- **Armazenamento (`aws-storage`, `securing-s3-buckets`, `troubleshooting-s3-files`, `troubleshooting-efs`):**
  - **Hardening de S3 (`securing-s3-buckets`):** `BlockPublicAccess` (4 flags = `true`), `BucketOwnerEnforced` (ACLs desativadas), criptografia SSE-S3/SSE-KMS padrão, política de bucket negando HTTP (`aws:SecureTransport: false`) e Object Lock / Versioning para dados críticos.
  - **Diagnóstico de S3 e EFS (`troubleshooting-s3-files`, `troubleshooting-efs`):** em erros `403 Access Denied` no S3, verifique a interseção de 5 camadas (IAM Principal Policy + Bucket Policy + KMS Key Policy + VPC Endpoint Policy + SCP/Block Public Access). Em EFS, valide Mount Targets na AZ correta, Security Group liberando TCP **2049 (NFS)** e `efs-utils` com TLS.

---

## 3. FinOps, Well-Architected e SDKs (`aws-billing-and-cost-management`, `aws-well-architected-review`, `aws-sdk-*`)

- **Gestão de Custos (`aws-billing-and-cost-management`):**
  - Sempre consulte a data corrente antes de montar janelas do **Cost Explorer**. Combine **AWS Budgets** (alertas em 50%, 80%, 100% do orçado e do projetado), **Cost Anomaly Detection** e **Cost Optimization Hub** (direcionamento de Compute Optimizer, idle resources, Graviton e Savings Plans).
- **Revisão Well-Architected (`aws-well-architected-review`):**
  - Avalie sistematicamente os 6 pilares (Operational Excellence, Security, Reliability, Performance Efficiency, Cost Optimization, Sustainability) cruzando descoberta de código/IaC com inventário vivo somente leitura.
- **Uso Idiomático dos AWS SDKs (`aws-sdk-js-v3-usage`, `aws-sdk-python-usage`, `aws-sdk-swift-usage`):**
  - Reutilize clientes SDK entre invocações (escopo de módulo/singleton), use clientes modulares (`@aws-sdk/client-*` no JS v3), pagine sempre com *paginators* oficiais e trate exceções tipadas do serviço com backoff e jitter.

---

## 4. Comunicações, Marketplace, WorkSpaces, Quantum, Amplify e Migrações Multi-Cloud

- **Comunicações com o Cliente (`amazon-ses`, `aws-sms-voice`, `aws-social-messaging`):**
  - **Amazon SES:** configure identidade de domínio com **Easy DKIM (2048 bits)**, **SPF** e **DMARC** (`p=quarantine`/`reject`), mais Configuration Set para rastrear bounces e complaints (< 5% bounce e < 0,1% complaint são obrigatórios antes de sair da Sandbox).
  - **SMS/Voice e WhatsApp (`aws-sms-voice`, `aws-social-messaging`):** cumpra o registro regulatório de remetente por país (10DLC, Sender ID, Toll-Free) antes do go-live e gerencie templates aprovados da Meta no AWS End User Messaging Social com destino de eventos em EventBridge/Kinesis.
- **AWS Marketplace Metering (`aws-marketplace-metering`):**
  - Para SaaS PAYG no Marketplace: implemente `ResolveCustomer` no onboarding do token de registro, `BatchMeterUsage` periódico para dimensões de consumo (enviando **a cada hora**, inclusive `Quantity: 0` como heartbeat de atividade quando aplicável) e verificação de entitlement (`GetEntitlements`).
- **WorkSpaces Agent Access & Amazon Braket (`amazon-workspaces-agent-access`, `amazon-braket`):**
  - **WorkSpaces Applications:** conecte agentes a sessões remotas Windows via protocolo estruturado com ciclo de vida de sessão e isolamento de credenciais.
  - **Amazon Braket:** valide disponibilidade do dispositivo (simulador local SV1/DM1 vs QPU real), defina **Spending Limits** antes de submeter tarefas quânticas e use Hybrid Jobs para algoritmos variacionais (QAOA/VQE).
- **AWS Amplify Gen 2 & AWS Blocks (`aws-amplify`, `aws-blocks`, `launch-with-aws`):**
  - Para full-stack code-first TypeScript, estruture `amplify/auth`, `amplify/data` (AppSync + DynamoDB com autorização por modelo/campo) e `amplify/storage` com ambientes sandbox isolados por desenvolvedor.
- **Migrações Multi-Cloud e Modernização (`azure-to-aws`, `gcp-to-aws`, `heroku-to-aws`, `aws-transform`, `architect-for-startups`, `start-building-for-startups`, `operate-on-aws`, `knowledge-base-for-startups`, `prompt-library-for-startups`, `contextual-offers-for-startups`, `signing-in-to-aws`):**
  - **Mapeamento de Migração Cloud:**
    - **Azure → AWS (`azure-to-aws`):** AKS/Container Apps → ECS Fargate/EKS; Azure Functions → Lambda/Step Functions; Cosmos DB → DynamoDB/DocumentDB; Entra ID B2C → Cognito; Service Bus/Event Grid → SQS/SNS/EventBridge.
    - **GCP → AWS (`gcp-to-aws`):** Cloud Run/GKE → ECS Fargate/App Runner/EKS; Firestore/Bigtable → DynamoDB/Keyspaces; Pub/Sub → SNS+SQS/Kinesis/EventBridge; Vertex AI → Amazon Bedrock/SageMaker; BigQuery → Redshift Serverless/Athena+Iceberg.
    - **Heroku → AWS (`heroku-to-aws`):** Dynos Web/Worker → ECS Fargate ou App Runner; Heroku Postgres → Aurora PostgreSQL Serverless v2; Heroku Redis → ElastiCache Valkey; Scheduler → EventBridge Scheduler.
  - **Modernização de Código com AWS Transform (`aws-transform`):** utilize a CLI `atx` para upgrades automatizados de linguagem/framework (ex.: Java legado → Java 21/25, .NET Framework → .NET moderno) com validação de compilação e síntese de resultados por módulo.
