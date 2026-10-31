# Simulação de Infraestrutura Local: HashiCorp Vault + LocalStack + Terraform (`tflocal` / `lstk`)

## 1. Arquitetura do Laboratório Integrado (`docker-compose.yml`)

Para simular com fidelidade **VPC + Sub-redes + Security Groups + VPC Endpoints + KMS Auto-Unseal + Vault AWS Dynamic Secrets** em qualquer estação de desenvolvimento (sem custos AWS e 100% offline):

```yaml
services:
  localstack:
    image: localstack/localstack:3.8
    container_name: squad-localstack
    ports:
      - "4566:4566"
    environment:
      - SERVICES=ec2,iam,sts,kms,s3,dynamodb,secretsmanager,ssm,logs
      - AWS_DEFAULT_REGION=us-east-1
      - DEBUG=0
    networks:
      - vpc-sim-net
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4566/_localstack/health"]
      interval: 5s
      timeout: 3s
      retries: 10

  vault:
    image: hashicorp/vault:1.17
    container_name: squad-vault
    ports:
      - "8200:8200"
    environment:
      - VAULT_DEV_ROOT_TOKEN_ID=squad-dev-root-token
      - VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:8200
      - VAULT_ADDR=http://127.0.0.1:8200
      - AWS_ACCESS_KEY_ID=test
      - AWS_SECRET_ACCESS_KEY=test
      - AWS_DEFAULT_REGION=us-east-1
    cap_add:
      - IPC_LOCK
    depends_on:
      localstack:
        condition: service_healthy
    networks:
      - vpc-sim-net

networks:
  vpc-sim-net:
    driver: bridge
```

> **Regra de ouro de DNS entre containers:**
> - Quando o **Vault** (dentro do container `squad-vault`) chama o LocalStack (`iam_endpoint`, `sts_endpoint`, `kms endpoint`), use **`http://localstack:4566`**.
> - Quando o **Terraform** ou seus testes em **Go/Java/Python** rodam no **host Windows/Linux**, use **`http://localhost:4566`** para o LocalStack e **`http://127.0.0.1:8200`** para o Vault.

---

## 2. Configuração Completa em Terraform Multi-Provider (`main.tf`)

O módulo abaixo provisiona simultaneamente:
1. **No LocalStack (`hashicorp/aws`):** VPC `10.20.0.0/16`, Sub-rede Privada de App, Sub-rede Isolada do Vault, Route Tables, Gateway Endpoint de S3, Interface Endpoints de KMS e STS, Security Groups encadeados (`SG-to-SG`), chave KMS de Auto-Unseal e IAM Role para a aplicação.
2. **No HashiCorp Vault (`hashicorp/vault`):** Motor `kv-v2`, Motor `aws` apontando `iam_endpoint` e `sts_endpoint` para o LocalStack, Role de credenciais dinâmicas STS, método `auth/aws` e Policy HCL least-privilege.

```hcl
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    vault = {
      source  = "hashicorp/vault"
      version = "~> 4.0"
    }
  }
}

provider "aws" {
  region                      = "us-east-1"
  access_key                  = "test"
  secret_key                  = "test"
  s3_use_path_style           = true
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  endpoints {
    ec2            = "http://localhost:4566"
    iam            = "http://localhost:4566"
    sts            = "http://localhost:4566"
    kms            = "http://localhost:4566"
    s3             = "http://localhost:4566"
    dynamodb       = "http://localhost:4566"
    secretsmanager = "http://localhost:4566"
  }
}

provider "vault" {
  address = "http://127.0.0.1:8200"
  token   = var.vault_token
}

variable "vault_token" {
  type      = string
  default   = "squad-dev-root-token"
  sensitive = true
}

# ============================================================================
# 1. REDE AWS VPC ZERO-TRUST NO LOCALSTACK
# ============================================================================

resource "aws_vpc" "squad_vpc" {
  cidr_block           = "10.20.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "squad-zero-trust-vpc" }
}

resource "aws_subnet" "private_app_az1" {
  vpc_id                  = aws_vpc.squad_vpc.id
  cidr_block              = "10.20.16.0/24"
  availability_zone       = "us-east-1a"
  map_public_ip_on_launch = false
  tags                    = { Name = "private-app-az1", Tier = "App" }
}

resource "aws_subnet" "isolated_vault_az1" {
  vpc_id                  = aws_vpc.squad_vpc.id
  cidr_block              = "10.20.64.0/24"
  availability_zone       = "us-east-1a"
  map_public_ip_on_launch = false
  tags                    = { Name = "isolated-vault-az1", Tier = "Vault" }
}

resource "aws_route_table" "isolated_rt" {
  vpc_id = aws_vpc.squad_vpc.id
  tags   = { Name = "isolated-vault-rt" }
}

resource "aws_route_table_association" "isolated_assoc" {
  subnet_id      = aws_subnet.isolated_vault_az1.id
  route_table_id = aws_route_table.isolated_rt.id
}

# Security Groups Encadeados (SG-to-SG)
resource "aws_security_group" "app_sg" {
  name        = "squad-app-sg"
  description = "Workloads de aplicacao (Lambda/ECS)"
  vpc_id      = aws_vpc.squad_vpc.id
}

resource "aws_security_group" "vault_sg" {
  name        = "squad-vault-cluster-sg"
  description = "Acesso restrito a porta 8200 exclusivamente a partir de app_sg"
  vpc_id      = aws_vpc.squad_vpc.id

  ingress {
    description     = "HTTPS Vault API from App SG only"
    from_port       = 8200
    to_port         = 8200
    protocol        = "tcp"
    security_groups = [aws_security_group.app_sg.id]
  }

  ingress {
    description = "Vault Raft Cluster internal replication"
    from_port   = 8201
    to_port     = 8201
    protocol    = "tcp"
    self        = true
  }
}

resource "aws_security_group" "vpce_sg" {
  name        = "squad-vpce-interface-sg"
  description = "Interface Endpoints (KMS/STS) acessiveis por App e Vault"
  vpc_id      = aws_vpc.squad_vpc.id

  ingress {
    description     = "HTTPS from App and Vault SGs"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.app_sg.id, aws_security_group.vault_sg.id]
  }
}

# Gateway Endpoint Gratuito para S3
resource "aws_vpc_endpoint" "s3_gateway" {
  vpc_id            = aws_vpc.squad_vpc.id
  service_name      = "com.amazonaws.us-east-1.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.isolated_rt.id]
}

# Interface Endpoints (PrivateLink) para KMS e STS
resource "aws_vpc_endpoint" "kms_interface" {
  vpc_id              = aws_vpc.squad_vpc.id
  service_name        = "com.amazonaws.us-east-1.kms"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.isolated_vault_az1.id]
  security_group_ids  = [aws_security_group.vpce_sg.id]
  private_dns_enabled = true
}

resource "aws_vpc_endpoint" "sts_interface" {
  vpc_id              = aws_vpc.squad_vpc.id
  service_name        = "com.amazonaws.us-east-1.sts"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.isolated_vault_az1.id]
  security_group_ids  = [aws_security_group.vpce_sg.id]
  private_dns_enabled = true
}

# Chave KMS para Auto-Unseal do Vault
resource "aws_kms_key" "vault_unseal" {
  description             = "KMS Key for HashiCorp Vault Auto-Unseal"
  deletion_window_in_days = 7
  enable_key_rotation     = true
}

# ============================================================================
# 2. CONFIGURAÇÃO DO HASHICORP VAULT CONECTADO AO LOCALSTACK
# ============================================================================

resource "vault_mount" "kvv2" {
  path        = "secret-squad"
  type        = "kv"
  options     = { version = "2" }
  description = "KV v2 Secret Engine para microsservicos da Squad"
}

resource "vault_aws_secret_backend" "aws_localstack" {
  path                      = "aws-local"
  access_key                = "test"
  secret_key                = "test"
  region                    = "us-east-1"
  iam_endpoint              = "http://localstack:4566"
  sts_endpoint              = "http://localstack:4566"
  default_lease_ttl_seconds = 900
  max_lease_ttl_seconds     = 3600
}

resource "vault_aws_secret_backend_role" "s3_dynamic_role" {
  backend         = vault_aws_secret_backend.aws_localstack.path
  name            = "order-s3-writer"
  credential_type = "iam_user"
  policy_document = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
      Resource = ["arn:aws:s3:::squad-orders-*", "arn:aws:s3:::squad-orders-*/*"]
    }]
  })
}

resource "vault_policy" "order_service_policy" {
  name = "order-service-least-privilege"
  policy = <<EOT
path "secret-squad/data/orders/*" {
  capabilities = ["read"]
}
path "aws-local/creds/order-s3-writer" {
  capabilities = ["read"]
}
EOT
}
```

---

## 3. Fluxo de Validação via CLI (PowerShell)

```powershell
# 1. Subir LocalStack + Vault
docker compose up -d

# 2. Configurar AWS Secrets Engine no Vault apontando para o LocalStack
$env:VAULT_ADDR = "http://127.0.0.1:8200"
$env:VAULT_TOKEN = "squad-dev-root-token"

vault secrets enable -path=aws aws
vault write aws/config/root `
    access_key="test" `
    secret_key="test" `
    region="us-east-1" `
    iam_endpoint="http://localstack:4566" `
    sts_endpoint="http://localstack:4566"

# 3. Gerar credencial IAM dinâmica no Vault e validar que o usuário/token foi criado no LocalStack
vault read aws/creds/order-s3-writer
aws --endpoint-url=http://localhost:4566 iam list-users
```
