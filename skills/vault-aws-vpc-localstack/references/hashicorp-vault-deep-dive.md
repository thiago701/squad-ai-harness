# HashiCorp Vault Deep Dive — Arquitetura, Motores Dinâmicos, Auth IAM e Políticas HCL

## 1. Arquitetura de Segurança do Vault (Barrier, Storage Raft e Auto-Unseal)

O HashiCorp Vault opera sob o conceito de **Barreira Criptográfica (*Cryptographic Barrier*)**: nenhum dado persiste no backend de armazenamento em texto claro. A chave mestra (*Root Key*) protege a *Encryption Key* do keyring interno.

### 1.1. Integrated Storage (Raft) + AWS KMS Auto-Unseal (`vault.hcl`)

Em produção na AWS (ou em simulação com LocalStack), evite o unseal manual via chaves Shamir para permitir auto-healing de nós EC2/EKS:

```hcl
ui = true
disable_mlock = true # Recomendado quando usando Integrated Storage (Raft) em Linux moderno

storage "raft" {
  path    = "/opt/vault/data"
  node_id = "vault-node-az1"

  retry_join {
    auto_join = "provider=aws region=us-east-1 tag_key=VaultCluster tag_value=prod-vault"
  }
}

listener "tcp" {
  address         = "0.0.0.0:8200"
  cluster_address = "0.0.0.0:8201"
  tls_cert_file   = "/opt/vault/tls/vault.crt"
  tls_key_file    = "/opt/vault/tls/vault.key"
  tls_min_version = "tls13"
}

seal "awskms" {
  region     = "us-east-1"
  kms_key_id = "alias/squad-vault-auto-unseal"
  # Em simulação LocalStack, descomente:
  # endpoint = "http://localstack:4566"
}

api_addr     = "https://vault.internal.squad.local:8200"
cluster_addr = "https://vault-az1.internal.squad.local:8201"
```

---

## 2. Motores de Segredos (*Secret Engines*)

### 2.1. KV v2 (`secret/`) — Segredos Versionados com Check-And-Set (CAS)
- Obriga `cas_required = true` em ambientes críticos para impedir sobrescrita concorrente acidental (*lost updates*).
- Mantém histórico auditável (`max_versions = 10`) e expiração opcional de versões antigas (`delete_version_after = "90d"`).

### 2.2. AWS Secrets Engine (`aws/`) — Credenciais IAM/STS sob Demanda
Em vez de criar usuários IAM de longa duração (`iam_user`), priorize `assumed_role` via AWS STS (`sts:AssumeRole`), pois não consome a quota de 5.000 IAM Users da conta AWS e nasce com expiração nativa na AWS:

```bash
# 1. Habilitar motor AWS
vault secrets enable -path=aws aws

# 2. Configurar TTL de lease padrão e máximo
vault write aws/config/lease lease=15m lease_max=1h

# 3. Criar role vinculada ao ARN de uma IAM Role com STS AssumeRole
vault write aws/roles/order-service-s3 \
    credential_type=assumed_role \
    role_arns="arn:aws:iam::123456789012:role/OrderServiceS3AccessRole" \
    default_sts_ttl=15m \
    max_sts_ttl=1h

# 4. Obter credenciais STS efêmeras (AccessKeyId, SecretAccessKey, SessionToken)
vault read aws/creds/order-service-s3
```

### 2.3. Database Secrets Engine (`database/`) — Credenciais Efêmeras para PostgreSQL/Aurora
Cria um usuário SQL exclusivo por instância da aplicação e executa `DROP ROLE` automaticamente quando o *lease* expira:

```bash
vault secrets enable database

vault write database/config/orders-aurora \
    plugin_name=postgresql-database-plugin \
    allowed_roles="orders-readwrite,orders-readonly" \
    connection_url="postgresql://{{username}}:{{password}}@orders-aurora.internal:5432/orders?sslmode=verify-full" \
    username="vault_admin" \
    password="$INITIAL_ROOT_PASSWORD"

# Rotacionar imediatamente a senha do vault_admin para que nenhum humano a conheça
vault write -force database/rotate-root/orders-aurora

vault write database/roles/orders-readwrite \
    db_name=orders-aurora \
    creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO \"{{name}}\";" \
    revocation_statements="REASSIGN OWNED BY \"{{name}}\" TO postgres; DROP OWNED BY \"{{name}}\"; DROP ROLE IF EXISTS \"{{name}}\";" \
    default_ttl="1h" \
    max_ttl="24h"
```

### 2.4. Transit Secrets Engine (`transit/`) — Encryption-as-a-Service (EaaS)
Permite criptografar PII/CPF/cartões na aplicação Go/Java/Python sem gerenciar chaves na memória do serviço:
- `POST /v1/transit/encrypt/pii-key` recebe `{"plaintext": "<base64>"}` e devolve `vault:v1:ciphertext...`.
- Suporta rotação de chave (`vault write -f transit/keys/pii-key/rotate`) e `rewrap` de dados antigos sem expor o texto claro.

---

## 3. Autenticação Zero-Trust (`auth/aws` IAM SigV4) e Políticas HCL

### 3.1. Autenticação `auth/aws` (Método `iam`) — Fim do *Secret Zero*
A Lambda ou task ECS assina uma requisição `sts:GetCallerIdentity` usando sua própria Execution Role e inclui o cabeçalho `X-Vault-AWS-IAM-Server-ID: vault.internal.squad.local` (proteção contra replay/MITM):

```bash
vault auth enable aws

# Exigir header X-Vault-AWS-IAM-Server-ID em todo login IAM
vault write auth/aws/config/client \
    iam_server_id_header_value="vault.internal.squad.local"

# Mapear a IAM Role da Lambda para a policy HCL do Vault
vault write auth/aws/role/lambda-order-processor \
    auth_type=iam \
    bound_iam_principal_arn="arn:aws:iam::123456789012:role/lambda-order-processor-role" \
    token_policies="order-processor-policy" \
    token_ttl=15m \
    token_max_ttl=1h
```

### 3.2. Modelo de Política HCL Least-Privilege (`order-processor-policy.hcl`)

```hcl
# Leitura de configurações KV v2 específicas do serviço
path "secret/data/prod/order-processor/*" {
  capabilities = ["read"]
}

# Geração de credenciais dinâmicas de banco
path "database/creds/orders-readwrite" {
  capabilities = ["read"]
}

# Criptografia de PII via Transit (sem permissão de exportar ou apagar chave)
path "transit/encrypt/pii-key" {
  capabilities = ["update"]
}

path "transit/decrypt/pii-key" {
  capabilities = ["update"]
}

# Negação explícita a caminhos administrativos
path "sys/*" {
  capabilities = ["deny"]
}
```
