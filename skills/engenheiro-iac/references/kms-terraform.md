# KMS no Terraform — recursos, política de chave, criptografia por serviço, testes e scanners

> **Quando ler:** criar ou revisar `aws_kms_key`/`aws_kms_alias`/política de chave; ligar SSE-KMS em S3, DynamoDB,
> SNS/SQS, Lambda, Step Functions, Logs, SSM; escrever asserções de `terraform test` para criptografia; interpretar
> achados do Checkov/Trivy/Security Hub. Doutrina e condition keys em
> `engenheiro-seguranca/references/aws-kms.md`; custo/decisão em `arquiteto-cloud-aws/references/kms-custo-e-decisao.md`.
> Provider AWS v6 (argumentos conferidos no registry em 15/10/2026).

## 1. `aws_kms_key` — argumentos e padrões que importam

| Argumento | Padrão | O que vigiar |
|---|---|---|
| `description` | — | nomeie o **domínio de dado** ("faturamento — dados em repouso"), não o serviço |
| `key_usage` | `ENCRYPT_DECRYPT` | `SIGN_VERIFY`, `GENERATE_VERIFY_MAC` |
| `customer_master_key_spec` | `SYMMETRIC_DEFAULT` | `RSA_*`, `ECC_*`, `HMAC_*`, **`ML_DSA_44/65/87`** (pós-quântico) |
| `policy` | **ausente = política padrão (só o root da conta)** | escreva sempre (admins × users × serviços) — `CKV2_AWS_64` |
| `bypass_policy_lockout_safety_check` | `false` | mantenha `false` |
| `deletion_window_in_days` | **30** (7–30) | produção: 30 |
| `enable_key_rotation` | **`false`** | CMK simétrica: `true` (KMS.4 / `CKV_AWS_7`) |
| `rotation_period_in_days` | — (90–2560; exige `enable_key_rotation`) | 365 ou menor; limite por SCP `kms:RotationPeriodInDays` |
| `multi_region` | `false` | US$ 1/mês por réplica; DR real exige runbook |
| `is_enabled` | `true` | — |
| `custom_key_store_id`, `xks_key_id` | — | CloudHSM / XKS — só com regulador exigindo |

Exportados: `arn`, `key_id`, `tags_all`. Relacionados: `aws_kms_alias` (`name = "alias/<dominio>"`,
`target_key_id`), `aws_kms_key_policy` (política separada do recurso — útil quando a política referencia roles
criadas depois), `aws_kms_replica_key` (`primary_key_arn`), `aws_kms_grant` (`grantee_principal`, `operations`,
`constraints { encryption_context_equals }`), `data "aws_kms_alias"` (ex.: `alias/aws/ssm` para citar a chave
gerenciada pela AWS), `aws_kms_ciphertext` (cifra em plan — o ciphertext vai para o state; evite para segredos).

## 2. Política de chave idiomática (`aws_iam_policy_document`)

```hcl
data "aws_caller_identity" "eu" {}
data "aws_region" "atual" {}

data "aws_iam_policy_document" "chave_faturamento" {
  statement { # delega à conta o uso de IAM (sem isto, nenhuma policy IAM funciona)
    sid       = "EnableIAMUserPermissions"
    principals { type = "AWS" identifiers = ["arn:aws:iam::${data.aws_caller_identity.eu.account_id}:root"] }
    actions   = ["kms:*"]
    resources = ["*"]
  }
  statement { # administra, não usa
    sid       = "Administradores"
    principals { type = "AWS" identifiers = [var.role_admin_kms] }
    actions   = ["kms:Create*", "kms:Describe*", "kms:Enable*", "kms:List*", "kms:Put*", "kms:Update*",
                 "kms:Revoke*", "kms:Disable*", "kms:Get*", "kms:Delete*", "kms:TagResource",
                 "kms:UntagResource", "kms:ScheduleKeyDeletion", "kms:CancelKeyDeletion", "kms:RotateKeyOnDemand"]
    resources = ["*"]
  }
  statement { # usa, não administra — e só através do serviço esperado
    sid       = "UsoPelaAplicacao"
    principals { type = "AWS" identifiers = [aws_iam_role.app.arn] }
    actions   = ["kms:Encrypt", "kms:Decrypt", "kms:ReEncrypt*", "kms:GenerateDataKey*", "kms:DescribeKey"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["dynamodb.${data.aws_region.atual.region}.amazonaws.com", "s3.${data.aws_region.atual.region}.amazonaws.com"]
    }
  }
  statement { # serviço da AWS como principal: sempre com aws:SourceArn (confused deputy)
    sid       = "CloudWatchLogs"
    principals { type = "Service" identifiers = ["logs.${data.aws_region.atual.region}.amazonaws.com"] }
    actions   = ["kms:Encrypt*", "kms:Decrypt*", "kms:ReEncrypt*", "kms:GenerateDataKey*", "kms:Describe*"]
    resources = ["*"]
    condition {
      test     = "ArnLike"
      variable = "kms:EncryptionContext:aws:logs:arn"
      values   = ["arn:aws:logs:${data.aws_region.atual.region}:${data.aws_caller_identity.eu.account_id}:log-group:/faturamento/*"]
    }
  }
}

resource "aws_kms_key" "faturamento" {
  description             = "faturamento — dados em repouso (DynamoDB, S3, Logs)"
  enable_key_rotation     = true
  rotation_period_in_days = 365
  deletion_window_in_days = 30
  policy                  = data.aws_iam_policy_document.chave_faturamento.json
  tags                    = { dominio = "faturamento" }
}
resource "aws_kms_alias" "faturamento" {
  name          = "alias/faturamento"
  target_key_id = aws_kms_key.faturamento.key_id
}
```

**Ciclo de dependência** (política cita a role; a role cita a chave): separe com `aws_kms_key_policy`, ou dê
permissões de uso pela policy IAM da role (mantendo na chave só root/admins/serviços).

## 3. Ligar criptografia por serviço (nomes exatos)

```hcl
# S3 — SSE-KMS com Bucket Key (−99 % de chamadas KMS)
resource "aws_s3_bucket_server_side_encryption_configuration" "b" {
  bucket = aws_s3_bucket.b.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "aws:kms", kms_master_key_id = aws_kms_key.k.arn }
    bucket_key_enabled = true
  }
}
# DynamoDB — CMK (sem bloco = chave AWS owned; enabled=true sem kms_key_arn = AWS managed aws/dynamodb)
resource "aws_dynamodb_table" "t" {
  # ...
  server_side_encryption { enabled = true, kms_key_arn = aws_kms_key.k.arn }
}
# SNS / SQS — sem isto NÃO há SSE no SNS (SQS tem SSE-SQS grátis: sqs_managed_sse_enabled = true)
resource "aws_sns_topic" "t" { name = "avisos", kms_master_key_id = aws_kms_key.k.arn }
resource "aws_sqs_queue" "q" {
  name                              = "pedidos"
  kms_master_key_id                 = aws_kms_key.k.arn
  kms_data_key_reuse_period_seconds = 300 # 60–86400; maior = menos chamadas
}
# Lambda — variáveis de ambiente (padrão aws/lambda, grátis). CMK exige CreateGrant+Encrypt em quem aplica e Decrypt na role
resource "aws_lambda_function" "f" { # ...
  kms_key_arn = aws_kms_key.k.arn
}
# Step Functions — CMK (padrão AWS owned). Role: Decrypt + GenerateDataKey com kms:EncryptionContext:aws:states:stateMachineArn
resource "aws_sfn_state_machine" "m" { # ...
  encryption_configuration {
    type                              = "CUSTOMER_MANAGED_KMS_KEY"
    kms_key_id                        = aws_kms_key.k.arn
    kms_data_key_reuse_period_seconds = 300 # 60–900
  }
}
# CloudWatch Logs
resource "aws_cloudwatch_log_group" "g" { name = "/faturamento/api", kms_key_id = aws_kms_key.k.arn }
# SSM Parameter Store (padrão alias/aws/ssm)
resource "aws_ssm_parameter" "p" { name = "/app/token", type = "SecureString", key_id = aws_kms_key.k.arn, value_wo = "…", value_wo_version = 1 }
```

**Permissão mínima de quem lê um SecureString** (chave AWS managed ⇒ `Resource "*"`, por isso o contexto é o que
fecha a porta):

```hcl
{ Effect = "Allow", Action = ["kms:Decrypt"], Resource = "*",
  Condition = { StringEquals = {
    "kms:ViaService"                      = "ssm.${local.regiao}.amazonaws.com"
    "kms:EncryptionContext:PARAMETER_ARN" = aws_ssm_parameter.p.arn } } }
```

**Armadilhas:** (1) ligar Bucket Key muda o contexto de objeto para **bucket** — policies com
`kms:EncryptionContext:aws:s3:arn` de objeto param de funcionar; (2) `kms:ViaService` na **role de execução** do
Step Functions impede execuções — só na policy de quem chama; (3) publicadores que são serviços (EventBridge → SNS
cifrado, S3 → SQS cifrada, Budgets → SNS) precisam de `GenerateDataKey*` + `Decrypt` na **política da chave**;
(4) `aws_kms_ciphertext` grava ciphertext no state; (5) trocar a chave de um DynamoDB/S3 não re-cifra backups/objetos
antigos; (6) ADR de POC com "nenhum serviço com mínimo mensal": **CMK = US$ 1/mês** — decisão explícita.

### 3.1 O que NÃO automatizar em lote (vai quebrar produção)

- **SNS sem SSE + serviço da AWS publicando** (`aws_cloudwatch_metric_alarm`, `aws_cloudwatch_event_target`,
  `aws_budgets_budget`, `aws_s3_bucket_notification`, `aws_sns_topic_policy` com `Service`…): `alias/aws/sns` não
  aceita política → o serviço perde a publicação. Precisa de **CMK** com `kms:GenerateDataKey*`/`Decrypt` para
  `cloudwatch`/`events`/`budgets` (+ `aws:SourceAccount`). A remediação automática deve **só relatar** este caso.
- **Bucket Key em bucket cujo repositório condiciona policy por `kms:EncryptionContext:aws:s3:arn`** (contexto do
  objeto): com Bucket Key o contexto vira o **ARN do bucket** e a condição deixa de casar. Idem: só relatar.
- Rotação automática **não existe** para chave assimétrica, HMAC, importada (`EXTERNAL`) ou de custom key store —
  seletor exclui; `aws_kms_replica_key` herda a rotação da primária.

## 4. `terraform test` — asserções que pegam regressão

```hcl
run "chaves_governadas" {
  command = plan
  assert {
    condition     = alltrue([for k in values(aws_kms_key.dominio) : k.enable_key_rotation && k.deletion_window_in_days == 30])
    error_message = "KMS.4: toda CMK com rotação automática e janela de exclusão de 30 dias."
  }
  assert {
    condition     = alltrue([for k in values(aws_kms_key.dominio) : !strcontains(k.policy, "\"AWS\":\"*\"") && !strcontains(k.policy, "\"Principal\":\"*\"")])
    error_message = "KMS.5: política de chave nunca com Principal *."
  }
  assert { # quem pode decifrar o segredo X só consegue com o contexto do parâmetro X
    condition     = alltrue([for st in local.politicas["app"] : try(st.Condition.StringEquals["kms:EncryptionContext:PARAMETER_ARN"], "") != "" if try(contains(st.Action, "kms:Decrypt"), false)])
    error_message = "kms:Decrypt sem kms:EncryptionContext:PARAMETER_ARN."
  }
  assert {
    condition     = aws_s3_bucket_server_side_encryption_configuration.b.rule[0].bucket_key_enabled == true
    error_message = "SSE-KMS no S3 sem Bucket Key = custo e throttling desnecessários."
  }
}
```

Para políticas que o módulo monta em `locals` (padrão "uma fonte para a policy e para o teste"), teste o **local**
com `toset(...)`/`contains(...)` — o ARN mockado não importa, a **forma** importa.

### 4.1 Recurso opcional com custo (CMK opt-in) — o que o plan exige

```hcl
variable "cmk" { type = bool  default = false }            # decisão explícita do dono (US$ 1/mês)
module "cmk"    { source = "./modulos/cmk"  ativa = var.cmk  … }   # count = var.ativa ? 1 : 0
module "bucket" { cmk_ativa = var.cmk  kms_key_arn = module.cmk.arn }  # bool CONHECIDO + ARN desconhecido, separados
# no módulo: sse_algorithm = var.cmk_ativa ? "aws:kms" : "AES256"; kms_master_key_id = var.cmk_ativa ? var.kms_key_arn : null
# dynamic "server_side_encryption" { for_each = var.cmk_ativa ? [1] : [] … }   # NUNCA `var.kms_key_arn != null`
```

- `for_each`/`count`/`dynamic` sobre `arn != null` falham no `plan` ("value not known until apply") — a condição tem
  de ser um **bool conhecido** (`var.cmk`), o ARN só entra como valor.
- No `terraform test` com `mock_provider`, DynamoDB/S3 validam o **formato** do ARN da chave já no plan: declare
  `mock_resource "aws_kms_key" { defaults = { arn = "arn:aws:kms:us-east-1:<conta>:key/<uuid>", key_id = "<uuid>" } }`.
  Não troque o `run` para `command = apply` por causa disso — o provider simulado gera ARNs inválidos para IAM/Lambda.
- Asserções úteis: `var.cmk == false` por padrão e `module.cmk.arn == null`; com `cmk = true`, rotação/janela/alias
  pelos **outputs** do módulo (`forma = { rotacao, janela_dias, alias, statements }` — recursos internos de módulo não
  são acessíveis no teste) e "nenhum statement com `Principal` AWS `*`".
- `kms:Decrypt` das roles: `Resource = var.cmk ? [module.cmk.arn] : ["*"]` (mesmo tipo nos dois ramos) **sempre**
  com `kms:ViaService` + `kms:EncryptionContext:*`; uso via S3/SNS entra só com a chave ligada (`cmk_via` em `locals`).
- `terraform destroy` **agenda** a exclusão (janela 30 d): a varredura de "conta limpa" deve tratar `KeyState =
  PendingDeletion` como esperado, não como remanescente.

## 5. Scanners e controles — o que cada um pega

| Ferramenta | Regra | Achado |
|---|---|---|
| Checkov | `CKV_AWS_7` | CMK sem rotação automática |
| Checkov | `CKV2_AWS_64` | `aws_kms_key` sem `policy` definida |
| Checkov | `CKV_AWS_33` | política de chave com `Principal: *` |
| Checkov | `CKV_AWS_145` / `CKV_AWS_19` | S3 sem SSE-KMS / sem SSE |
| Checkov | `CKV_AWS_119` | DynamoDB sem CMK |
| Checkov | `CKV_AWS_26` / `CKV_AWS_27` | SNS / SQS sem SSE |
| Checkov | `CKV_AWS_158` | log group sem KMS |
| Security Hub | `KMS.1`/`KMS.2` (médio) | `Decrypt`/`ReEncryptFrom` em `*` em policy IAM (gerenciada/inline) |
| Security Hub | `KMS.3` (crítico) | chave agendada para exclusão |
| Security Hub | `KMS.4` (médio; CIS 3.6, PCI 3.7.4) | rotação desligada |
| Security Hub | `KMS.5` (crítico) | chave pública/acesso externo |

IDs do Checkov mudam entre versões — confira com `checkov -l | grep -i kms` antes de citar num gate. Trivy cobre o
mesmo conjunto (`AVD-AWS-*`). Rode no CI sobre o `plan` em JSON e bloqueie 🔴 no GATE 2.

## 6. Receita de revisão (5 minutos)

1. `grep -n "aws_kms_key" -A8` → `enable_key_rotation`, `deletion_window_in_days`, `policy` presentes?
2. `grep -n "kms:\*\|\"kms:Decrypt\"" -B2 -A6` nas policies IAM → `Resource "*"` sem `Condition`?
3. `grep -n "kms_key\|kms_master_key_id\|sse_algorithm\|server_side_encryption\|encryption_configuration"` → todo
   recurso com dado em repouso tem a linha? Qual tipo de chave?
4. Serviço como principal → `aws:SourceArn`?
5. `terraform test` tem pelo menos as 4 asserções da §4?
