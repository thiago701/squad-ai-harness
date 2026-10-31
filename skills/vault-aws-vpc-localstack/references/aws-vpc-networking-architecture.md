# Arquitetura de Rede AWS VPC — PrivateLink, Transit Gateway, VPC Lattice e Security Groups

## 1. Topologia de Referência Multi-AZ em 3 Camadas

Toda VPC de produção da Squad deve ser planejada via **AWS IPAM** (evitando colisão de blocos RFC 1918) e dividida em no mínimo **3 zonas de disponibilidade (AZs)** com 3 camadas de sub-redes por AZ:

```
VPC (10.20.0.0/16) — DNS Support = true | DNS Hostnames = true
├── Camada 1: Sub-redes Públicas (10.20.0.0/22 → /24 por AZ)
│   ├── Recursos: ALB Público, NLB, NAT Gateway (com Elastic IP)
│   └── Route Table: 0.0.0.0/0 -> Internet Gateway (igw-xxx)
│
├── Camada 2: Sub-redes Privadas de Aplicação (10.20.16.0/20 → /22 por AZ)
│   ├── Recursos: ECS Fargate, EKS Workers, AWS Lambda (VPC-attached)
│   └── Route Table:
│       ├── 10.20.0.0/16 -> local
│       ├── pl-s3 / pl-dynamodb -> Gateway VPC Endpoints (US$ 0)
│       ├── 10.0.0.0/8 -> Transit Gateway (tgw-xxx) [se multi-VPC]
│       └── 0.0.0.0/0 -> NAT Gateway da mesma AZ (apenas egress externo necessário)
│
└── Camada 3: Sub-redes Isoladas de Dados & Vault (10.20.64.0/20 → /22 por AZ)
    ├── Recursos: Cluster HashiCorp Vault (Raft), Aurora/RDS, ElastiCache, Interface Endpoints (KMS/STS)
    └── Route Table:
        ├── 10.20.0.0/16 -> local
        ├── pl-s3 / pl-dynamodb -> Gateway VPC Endpoints
        └── SEM ROTA 0.0.0.0/0 (Zero acesso direto à Internet)
```

---

## 2. Matriz de Decisão: Conectividade entre VPCs e Serviços

| Necessidade Arquitetural | Solução AWS Recomendada | Camada OSI | Vantagem Principal & FinOps |
|---|---|---|---|
| **Acessar S3 e DynamoDB a partir de sub-rede privada** | **Gateway VPC Endpoint** | L3 (Route Table) | **Custo US$ 0,00/h e US$ 0,00/GB.** Evita pagar US$ 0,045/GB no NAT Gateway. |
| **Acessar KMS, STS, Secrets Manager, SSM ou expor o HashiCorp Vault para outras VPCs** | **Interface VPC Endpoint (`AWS PrivateLink`)** | L4 (TCP Unidirecional) | Tráfego unidirecional por ENI privada; **funciona mesmo com CIDRs sobrepostos**; não expõe a rede inteira da VPC produtora. |
| **Interconectar 5+ VPCs (Prod, Dev, Shared Services) + Direct Connect On-Premises** | **AWS Transit Gateway (TGW)** | L3 (Roteamento IP) | Topologia Hub-and-Spoke escalável com **TGW Route Tables isoladas** e Inspection VPC centralizada (AWS Network Firewall). |
| **Comunicação HTTP/HTTPS/gRPC entre microsserviços em múltiplas VPCs/Contas (ECS + Lambda + EKS)** | **Amazon VPC Lattice** | L7 (Service Mesh Nativa) | Autenticação e autorização **IAM SigV4 por rota/método**, descoberta de serviço automática e independência total de CIDR/IP. |
| **Conectar apenas 2 VPCs da mesma região sem transitividade** | **VPC Peering** | L3 | Sem custo fixo por hora (apenas tráfego cross-AZ), baixa latência. |

---

## 3. Padrão de Exposição do HashiCorp Vault via AWS PrivateLink + Split-Horizon DNS

Quando o cluster **HashiCorp Vault** roda em uma **Shared Services / Security VPC** (ou HCP Vault Dedicated), nunca abra roteamento IP irrestrito de todas as Spoke VPCs:

1. **Na VPC do Vault (Provedora):**
   - Coloque um **Network Load Balancer (NLB)** interno na frente dos nós do Vault (porta TCP `8200`, health check HTTP em `/v1/sys/health?standbyok=true`).
   - Crie um **VPC Endpoint Service (`aws_vpc_endpoint_service`)** apontando para o NLB, exigindo aceitação explícita (`acceptance_required = true`) e restringindo `allowed_principals` às contas da organização.
2. **Nas Spoke VPCs (Consumidoras):**
   - Crie um **Interface VPC Endpoint (`aws_vpc_endpoint`)** conectado ao serviço do Vault.
   - Associe uma **Route 53 Private Hosted Zone (`vault.internal.squad.local`)** com registro Alias apontando para o DNS do Interface Endpoint local daquela VPC (*Split-Horizon DNS*).
   - Resultado: toda aplicação chama `https://vault.internal.squad.local:8200` com o mesmo certificado TLS, trafegando 100% dentro da malha privada AWS via PrivateLink.

---

## 4. Microssegmentação Zero-Trust com Security Groups Encadeados (`SG-to-SG`)

Regras obrigatórias de Security Group para proteger a VPC e o Vault:

1. **`sg-alb-public`:**
   - Inbound: `443/tcp` de origens autorizadas (CloudFront Managed Prefix List ou CIDR corporativo).
   - Outbound: `8080/tcp` exclusivamente para `sg-app-workloads`.
2. **`sg-app-workloads` (ECS / Lambda / EKS):**
   - Inbound: `8080/tcp` exclusivamente de `sg-alb-public`.
   - Outbound:
     - `8200/tcp` para `sg-vault-cluster` (ou `sg-vpce-vault`).
     - `5432/tcp` para `sg-aurora-db`.
     - `443/tcp` para `sg-aws-interface-endpoints` e prefix list do S3/DynamoDB.
3. **`sg-vault-cluster`:**
   - Inbound:
     - `8200/tcp` **somente** de `sg-app-workloads` (ou do NLB PrivateLink).
     - `8201/tcp` **somente** de `self` (`sg-vault-cluster`, replicação Raft entre nós do cluster).
   - Outbound:
     - `8201/tcp` para `self`.
     - `443/tcp` para `sg-aws-interface-endpoints` (comunicação com KMS Auto-Unseal, STS e IAM).
     - `5432/tcp` para `sg-aurora-db` (necessário para o Vault criar/revogar credenciais dinâmicas no banco!).
4. **Auditoria de Rede Contínua:**
   - **VPC Flow Logs v5** habilitados em nível de VPC (enviados ao S3 com partição por hora/Athena) capturando `REJECT` e `ACCEPT`.
   - **AWS Network Access Analyzer & Reachability Analyzer** para provar matematicamente que não existe caminho entre o `igw` e as sub-redes isoladas (`Isolated Data/Vault`).
