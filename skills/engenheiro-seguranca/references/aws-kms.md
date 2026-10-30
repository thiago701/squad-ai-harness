# AWS KMS — chaves, políticas, rotação, auditoria e maturidade de criptografia

> **Quando ler:** desenhar ou revisar criptografia em repouso na AWS; escrever/auditar política de chave e permissões
> `kms:*`; decidir chave gerenciada pela AWS × chave do cliente (CMK); rotação; custo e quotas; auditoria/ciclo de
> vida; avaliar a **maturidade de criptografia** de uma squad; criptografia pós-quântica. Fatos verificados em
> **15/10/2026** (fontes no fim). Para o HCL e os checks de IaC, ver `engenheiro-iac/references/kms-terraform.md`;
> para custo/decisão por serviço, `arquiteto-cloud-aws/references/kms-custo-e-decisao.md`.

## 1. Modelo mental (30 segundos)

- **KMS key** = metadados (id, ARN, política, alias, tags, estado) + **material criptográfico** que **nunca sai** dos
  HSMs do serviço (FIPS 140-3). Tudo o que a AWS ou você cifra "com a chave" é **envelope encryption**: a KMS key cifra
  *data keys*; a data key (em memória, no serviço) cifra os dados. Por isso o custo é por **requisição** à KMS, não
  por byte.
- Três perguntas decidem quase tudo: **quem pode usar** (política de chave + IAM + grants), **em que contexto**
  (`kms:ViaService`, `kms:EncryptionContext:*`, `aws:SourceArn`) e **o que acontece se a chave sumir** (desabilitar /
  agendar exclusão derruba o serviço que a usa — DynamoDB fica *Inaccessible*, Step Functions falha execuções).
- Criptografia em repouso **sempre existe** na AWS (chaves *AWS owned*). O que a CMK acrescenta é **controle e
  auditoria**: política própria, rotação sob seu comando, CloudTrail com contexto, separação de funções, exclusão.

## 2. Tipos de chave

| Tipo | Onde vive | Política / auditoria | Rotação | Custo |
|---|---|---|---|---|
| **AWS owned** (padrão de DynamoDB, Step Functions, S3 SSE-S3…) | conta da AWS, invisível | nenhuma visibilidade; não aparece no CloudTrail da sua conta | ~anual, pela AWS | zero |
| **AWS managed** (`alias/aws/ssm`, `aws/sns`, `aws/lambda`, `aws/dynamodb`…) | sua conta, criada no 1º uso | visível e auditável no CloudTrail; **política não editável** | anual, fixa | armazenamento grátis; **requisições cobradas** |
| **Customer managed (CMK)** | sua conta | política sua, aliases, grants, tags, exclusão, `GetKeyLastUsage` | opcional: automática (90–2560 d) ou sob demanda | **US$ 1/mês por chave** (rateado por hora) + requisições |
| CMK **multi-Region** | primária + réplicas | idem; mesmo id em cada Região | na primária | US$ 1/mês **por réplica** |
| CMK **importada** (`EXTERNAL`, BYOK) | material seu, importado | idem; pode expirar | só **sob demanda** (desde 06/2025) ou manual | US$ 1/mês |
| CMK em **custom key store** (CloudHSM ou **XKS** externo) | material fora do KMS | idem | só manual | US$ 1/mês + CloudHSM (~US$ 1,60/HSM/h) ou o seu HSM externo |

**Key specs:** `SYMMETRIC_DEFAULT` (AES-256-GCM — o caso de 95 %), `RSA_2048/3072/4096`, `ECC_NIST_P256/P384/P521`,
`ECC_SECG_P256K1`, `ECC_NIST_EDWARDS25519`, `HMAC_224..512`, **`ML_DSA_44/65/87`** (FIPS 204, pós-quântico, GA em
13/06/2025) e `SM2` (China). **Key usage:** `ENCRYPT_DECRYPT`, `SIGN_VERIFY`, `GENERATE_VERIFY_MAC`, `KEY_AGREEMENT`.
Só a simétrica aceita *encryption context* e rotação automática.

## 3. Política de chave — a regra do jogo

A política de chave é **a** política de recurso: sem um `Allow` explícito nela, o acesso é negado — **inclusive para
IAM**. A declaração `"Principal": {"AWS": "arn:aws:iam::<conta>:root"}, "Action": "kms:*"` não dá acesso a ninguém
em si; ela **delega à conta** o direito de usar políticas IAM para conceder permissões sobre a chave. Sem ela, nenhuma
policy IAM funciona (só *deny*). Chave cuja política só cita um usuário que foi apagado vira **inadministrável**
(só o Suporte recupera) — por isso a declaração do *root* existe.

Estrutura recomendada (console e docs da AWS), em **quatro papéis separados**:

```json
{ "Version": "2012-10-17", "Statement": [
  { "Sid": "EnableIAMUserPermissions", "Effect": "Allow",
    "Principal": { "AWS": "arn:aws:iam::111122223333:root" }, "Action": "kms:*", "Resource": "*" },
  { "Sid": "Administradores (gerem, NAO usam)", "Effect": "Allow",
    "Principal": { "AWS": "arn:aws:iam::111122223333:role/seg-kms-admin" },
    "Action": ["kms:Create*","kms:Describe*","kms:Enable*","kms:List*","kms:Put*","kms:Update*","kms:Revoke*",
               "kms:Disable*","kms:Get*","kms:Delete*","kms:TagResource","kms:UntagResource",
               "kms:ScheduleKeyDeletion","kms:CancelKeyDeletion","kms:RotateKeyOnDemand"],
    "Resource": "*" },
  { "Sid": "Usuarios (usam, NAO gerem)", "Effect": "Allow",
    "Principal": { "AWS": ["arn:aws:iam::111122223333:role/app-faturamento"] },
    "Action": ["kms:Encrypt","kms:Decrypt","kms:ReEncrypt*","kms:GenerateDataKey*","kms:DescribeKey"],
    "Resource": "*",
    "Condition": { "StringEquals": { "kms:ViaService": "dynamodb.us-east-1.amazonaws.com" } } },
  { "Sid": "Grants so por servico da AWS", "Effect": "Allow",
    "Principal": { "AWS": ["arn:aws:iam::111122223333:role/app-faturamento"] },
    "Action": ["kms:CreateGrant","kms:ListGrants","kms:RevokeGrant"], "Resource": "*",
    "Condition": { "Bool": { "kms:GrantIsForAWSResource": "true" } } },
  { "Sid": "Servico da AWS sem confused deputy", "Effect": "Allow",
    "Principal": { "Service": "logs.us-east-1.amazonaws.com" },
    "Action": ["kms:Encrypt*","kms:Decrypt*","kms:ReEncrypt*","kms:GenerateDataKey*","kms:Describe*"],
    "Resource": "*",
    "Condition": { "ArnLike": { "kms:EncryptionContext:aws:logs:arn": "arn:aws:logs:us-east-1:111122223333:log-group:/app/*" } } }
] }
```

Regras que não se negociam:
1. **Nunca `"Principal": "*"`** (nem `"AWS": "*"`) num `Allow` sem condição que feche o universo — é chave **pública**
   (Security Hub **KMS.5**, crítico). `kms:CallerAccount` ou `aws:PrincipalOrgID` são as condições mínimas.
2. **`kms:*` só para o root e para administradores nomeados**; e administrador **não** recebe `Decrypt`/`Encrypt`
   (separação de funções). `kms:Put*` inclui `PutKeyPolicy`: administrador pode se dar tudo — monitore `PutKeyPolicy`.
3. **`kms:Decrypt` em `Resource: "*"` numa policy IAM é achado** (Security Hub **KMS.1/KMS.2**): cite o ARN da chave
   **e** uma condição de contexto/serviço.
4. **`BypassPolicyLockoutSafetyCheck` fica `false`**: a checagem impede você de gravar uma política que te expulse.
5. **Serviço como principal → `aws:SourceArn`** (ou `aws:SourceAccount`) **+ `kms:EncryptionContext:*`** contra
   *confused deputy*.
6. **Entre contas** precisa dos dois lados: `Allow` na política da chave **e** policy IAM na conta chamadora; a conta
   chamadora **paga** as requisições; Regiões *opt-in* precisam estar habilitadas nas duas.
7. **Grants** são para serviços integrados (EBS, RDS, Lambda, DynamoDB criam grants em seu nome). Pessoas não
   chamam `CreateGrant` — daí `kms:GrantIsForAWSResource`.

## 4. Condition keys que valem a revisão

| Chave | Serve para | Nota de uso |
|---|---|---|
| `kms:ViaService` | só via um serviço (`ssm.us-east-1.amazonaws.com`) | **não** use na role de execução do Step Functions (bloqueia execuções); use na policy de quem chama |
| `kms:EncryptionContext:<chave>` | amarra a permissão ao contexto da cifra | só em operações com contexto (`Decrypt`, `GenerateDataKey`, `CreateGrant`); em `DescribeKey` nega. Valores: `StringEquals` é *case-sensitive* |
| `kms:EncryptionContextKeys` | exige/limita as chaves do contexto | `"Null": {"kms:EncryptionContextKeys": false}` = "tem que haver contexto"; **nunca** `ForAllValues` com `kms:EncryptionContext:<chave>` (KMS rejeita como *OverlyPermissiveCondition*) |
| `kms:CallerAccount` | conta chamadora | fecha o universo quando o principal é um serviço ou `*` |
| `kms:GrantIsForAWSResource` | grant só criado por serviço integrado | padrão do console |
| `kms:GrantOperations`, `kms:GranteePrincipal`, `kms:GrantConstraintType` | limita o que um grant pode conceder | `ForAllValues` casa conjunto vazio — exija `Operations` |
| `kms:RequestAlias` / `kms:ResourceAliases` | ABAC por alias | `RequestAlias` só casa se a chamada usou alias; `ResourceAliases` vale pelo recurso |
| `kms:KeySpec`, `kms:KeyUsage`, `kms:KeyOrigin`, `kms:MultiRegion` | guardrails em `CreateKey` (SCP) | ex.: proibir `EXTERNAL`/`MultiRegion` fora da conta de segurança |
| `kms:RotationPeriodInDays` | limita o período que alguém pode definir | ex.: `NumericLessThanEquals: 365` |
| `kms:ScheduleKeyDeletionPendingWindowInDays` | força janela mínima | ex.: `NumericGreaterThanEquals: 30` |
| **`kms:TrailingDaysWithoutKeyUsage`** (abr/2026) | nega `ScheduleKeyDeletion`/`DisableKey` de chave usada há menos de N dias | combina com `GetKeyLastUsage` (§7) |
| `kms:BypassPolicyLockoutSafetyCheck` | nega `CreateKey`/`PutKeyPolicy` que pulem a trava | SCP: `Bool: true` → Deny |
| `kms:SigningAlgorithm`, `kms:MessageType`, `kms:MacAlgorithm`, `kms:EncryptionAlgorithm` | fixa algoritmos | pós-quântico: só `ML_DSA_*` para assinar documentos de longa vida |

## 5. *Encryption context* por serviço (verificados hoje)

| Serviço | Chave de contexto | Valor | Como aparece na permissão |
|---|---|---|---|
| SSM Parameter Store | `PARAMETER_ARN` | ARN do parâmetro (com o caminho) | `"kms:EncryptionContext:PARAMETER_ARN": "arn:aws:ssm:…:parameter/app/x"` |
| Step Functions | `aws:states:stateMachineArn` / `aws:states:activityArn` | ARN da máquina/atividade | na role de execução: `Decrypt` + `GenerateDataKey` com esse contexto |
| S3 (SSE-KMS) | `aws:s3:arn` | ARN do **objeto**; com **Bucket Key** vira o ARN do **bucket** | policies com ARN de objeto **quebram** ao ligar Bucket Key |
| CloudWatch Logs | `aws:logs:arn` | ARN do log group | principal `logs.<região>.amazonaws.com` |
| CloudTrail | `aws:cloudtrail:arn` | ARN da trilha | + `aws:SourceArn` |
| Demais (DynamoDB, SQS, SNS, Lambda, Secrets Manager, EBS, RDS…) | documentado na página "How *serviço* uses AWS KMS" do guia KMS | — | **confira antes de escrever** — nomes de contexto não são padronizados |

Padrão de permissão mínima para um *consumidor* (ex.: Lambda que lê um SecureString padrão):

```json
{ "Effect": "Allow", "Action": "kms:Decrypt", "Resource": "arn:aws:kms:us-east-1:111122223333:key/<id>",
  "Condition": { "StringEquals": {
      "kms:ViaService": "ssm.us-east-1.amazonaws.com",
      "kms:EncryptionContext:PARAMETER_ARN": "arn:aws:ssm:us-east-1:111122223333:parameter/app/github/token" } } }
```
Com a chave **gerenciada pela AWS** (`aws/ssm`) o `Resource` fica `"*"` (o ARN é da conta, descoberto no apply) — e
é exatamente aí que a condição de contexto impede que a mesma permissão leia **outro** parâmetro.

## 6. Rotação

| Modo | Para quem | Como | Efeito |
|---|---|---|---|
| **Automática** | CMK simétrica de origem `AWS_KMS` (inclusive multi-Region, pela primária) | `EnableKeyRotation` + `RotationPeriodInDays` **90–2560** (padrão **365**); **desligada por padrão** | id/ARN/alias/política não mudam; material antigo fica para decifrar; nada no app muda |
| **Sob demanda** | CMK simétrica (inclusive **importada**, desde 06/2025); não asimétrica/HMAC/custom key store | `RotateKeyOnDemand` (**≤ 25 por chave**), `ListKeyRotations`, `GetKeyRotationStatus` | não altera a agenda automática; consistência eventual |
| **Manual** | assimétrica, HMAC, custom key store | nova chave + mover o **alias** (`UpdateAlias`); manter a antiga habilitada | `Decrypt` simétrico dispensa `KeyId`; assimétrica/HMAC exigem |
| AWS managed | — | anual, fixa, sem controle | — |

**Custo da rotação:** a 1ª e a 2ª rotação adicionam US$ 1/mês cada (rateado); da 3ª em diante não há cobrança —
teto de **US$ 3/mês por chave** com rotação (política de preços de 2024). Chave agendada para exclusão não é cobrada.

## 7. Auditoria e ciclo de vida

- **CloudTrail** registra toda chamada à KMS com o *encryption context* em claro (`requestParameters`) e, para
  serviços, `invokedBy` (ex.: `states.amazonaws.com`). O contexto é, portanto, **dado não sensível por definição**.
- **`GetKeyLastUsage`** (API e console, **abr/2026**): `Timestamp`, `Operation`, `CloudTrailEventId`, `KmsRequestId`
  e `TrackingStartDate`. Se `KeyLastUsage` vem vazio e `KeyCreationDate ≥ TrackingStartDate`, a chave nunca foi
  usada. Não é cross-account. **Não decida excluir só por isso**: desabilite primeiro e observe `DisabledException`
  no CloudTrail (fluxos sazonais).
- **Exclusão:** `ScheduleKeyDeletion` com janela **7–30 dias** (padrão 30). Dados cifrados viram **irrecuperáveis**.
  Guardrails: SCP negando `ScheduleKeyDeletion` sem MFA, `kms:ScheduleKeyDeletionPendingWindowInDays ≥ 30` e
  `kms:TrailingDaysWithoutKeyUsage`; Security Hub **KMS.3** (chave agendada para exclusão = crítico).
- **Efeito em cascata ao desabilitar/excluir:** DynamoDB marca a tabela **Inaccessible** na hora e a **arquiva após
  7 dias**; Step Functions falha execuções em andamento e recusa novas; S3 devolve `KMS.DisabledException`.
- **Estados:** `Enabled`, `Disabled`, `PendingDeletion`, `PendingImport`, `PendingReplicaDeletion`, `Unavailable`
  (custom key store desconectado).

## 8. Custo e quotas (o que muda o desenho)

- **Free tier:** 20.000 requisições/mês somadas em todas as Regiões; **fora** do free tier: operações com chaves
  assimétricas (`Sign/Verify/Encrypt/Decrypt/GetPublicKey`) e `GenerateDataKeyPair*`.
- **Requisições:** ~US$ 0,03/10 k (simétricas, HMAC) e ~US$ 0,15/10 k (assimétricas). **Chaves AWS managed cobram
  requisições também** — só o armazenamento é grátis.
- **Quem chama paga** (cross-account); cada Região de uma multi-Region cobra separado.
- **Quotas compartilhadas por conta/Região** (simétricas): 100.000 rps em `us-east-1`/`us-west-2`/`eu-west-1`;
  20.000 em `us-east-2`, `ap-southeast-1/2`, `ap-northeast-1`, `eu-central-1`, `eu-west-2`, `eu-south-2`;
  10.000 nas demais. Assimétricas (RSA, ECC, **ML-DSA**): 1.000 rps cada. Custom key store: 1.800 rps.
  Ajustáveis via Service Quotas (exceto CloudHSM key store). Throttling = `ThrottlingException` (retry com backoff).
- **Reduzir chamadas** (= custo + risco de throttling): S3 **Bucket Keys** (−99 %), Step Functions
  `KmsDataKeyReusePeriodSeconds` (60–900 s, padrão 300), SQS `KmsDataKeyReusePeriodSeconds`, DynamoDB já faz cache
  (refresh a cada 5 min por chamador com tráfego — mantenha *keep-alive* no SDK), **data key caching** do AWS
  Encryption SDK em aplicações.

## 9. Integração por serviço — o que verificar

| Serviço | Padrão | Opção CMK | Permissão que esquece | Observação |
|---|---|---|---|---|
| S3 | SSE-S3 (AES-256, grátis) | SSE-KMS (+ Bucket Key) · DSSE-KMS (duas camadas, sem Bucket Key) | `kms:GenerateDataKey` para quem grava; `Decrypt` para quem lê | contexto muda com Bucket Key (§5) |
| DynamoDB | AWS owned (grátis) | AWS managed `aws/dynamodb` ou CMK (`SSESpecification`) | nenhuma no app (DynamoDB usa grant) | tabela/índices/streams usam a mesma chave; backup fica com a chave da época |
| SSM Parameter Store | `aws/ssm` | CMK no parâmetro (`key_id`) | `kms:Decrypt` (padrão) / `GenerateDataKey` (Advanced grava) | Standard = `Encrypt` direto; Advanced = envelope (Encryption SDK) |
| Secrets Manager | `aws/secretsmanager` | CMK | `Decrypt` no leitor; `GenerateDataKey` em quem grava | US$ 0,40/segredo/mês + rotação por Lambda |
| Lambda (variáveis de ambiente) | `aws/lambda` (grátis) | CMK (`kms_key_arn`) | *deployer*: `kms:CreateGrant` + `kms:Encrypt`; role: `kms:Decrypt` | sem `Decrypt`, o console não mostra as variáveis (bom para segredos operacionais) |
| Step Functions | AWS owned | CMK (`encryptionConfiguration`, 2024) | role: `Decrypt`+`GenerateDataKey` (Express síncrona: só `Decrypt`); log delivery: `delivery.logs.amazonaws.com` `Decrypt` | eventos do EventBridge omitem `Input/Output/Error/Cause` quando há CMK |
| SNS / SQS | **sem SSE** por padrão (SQS tem SSE-SQS grátis) | `KmsMasterKeyId` (`aws/sns`, `aws/sqs` ou CMK) | **publicadores que são serviços** (EventBridge, S3, CloudWatch, Budgets) precisam de `GenerateDataKey*` + `Decrypt` na política da chave | só o corpo é cifrado; HTTPS + SigV4 obrigatórios |
| CloudWatch Logs | AWS owned | `associate-kms-key` | principal `logs.<região>` com `aws:logs:arn` | log group novo no console; existente via CLI |
| AWS Backup | AWS owned/CMK | **CMK em cofres air-gapped** (nov/2025) | — | — |

## 10. Pós-quântico (PQC) — o que já é real

- **ML-DSA** (FIPS 204) no KMS: `CreateKey` com `ML_DSA_44/65/87`, `Sign`/`Verify` (`MessageType` `RAW`,
  `DIGEST` ou `EXTERNAL_MU`), **GA em 13/06/2025**; quota 1.000 rps; preço de operação assimétrica. Use para
  assinaturas que precisam valer por décadas (firmware, documentos, carimbo).
- **ML-KEM híbrido no TLS** dos endpoints do KMS, ACM e Secrets Manager (**abr/2025**, não-FIPS, partição `aws`):
  o cliente precisa suportar (AWS-LC, s2n-tls; SDKs via AWS CRT) — o endpoint prefere PQ quando o cliente oferece.
- Em repouso, AES-256 (o que o KMS usa) já é considerado resistente a computador quântico; o risco real é
  **"harvest now, decrypt later"** em trânsito e assinaturas de longa vida.

## 11. Anti-padrões que a revisão bloqueia

| Achado | Sev. | Correção |
|---|---|---|
| `Principal: "*"` sem condição na política de chave (KMS.5) | 🔴 | nomear principais; `kms:CallerAccount`/`aws:PrincipalOrgID` |
| `kms:Decrypt`/`kms:ReEncryptFrom` em `Resource: "*"` em policy IAM (KMS.1/KMS.2) | 🔴 | ARN da chave + `kms:ViaService`/`EncryptionContext` |
| `aws_kms_key` **sem `policy`** (fica só o root → qualquer admin IAM usa) | 🟡 | política explícita admins × users × serviços |
| `bypass_policy_lockout_safety_check = true` | 🔴 | remover; corrigir a política |
| CMK de produção sem rotação (KMS.4 / CIS 3.6 / PCI 3.7.4) | 🟡 | `enable_key_rotation = true` (365 d ou menos) |
| `deletion_window_in_days = 7` em produção | 🟡 | 30 + SCP com `ScheduleKeyDeletionPendingWindowInDays` |
| Chave agendada para exclusão com uso recente (KMS.3) | 🔴 | `CancelKeyDeletion`; adotar `kms:TrailingDaysWithoutKeyUsage` |
| Serviço como principal sem `aws:SourceArn` | 🟡 | adicionar `aws:SourceArn` + contexto |
| `kms:ViaService` na role de execução do Step Functions | 🟡 | mover para a policy do chamador |
| Policy com contexto de **objeto** S3 + Bucket Key ligada | 🟡 | contexto = ARN do bucket |
| Segredo em variável de ambiente sem CMK e com `Decrypt` amplo | 🟡 | Secrets Manager/SSM + CMK + contexto |
| Mesma chave para tudo (sem separação por domínio/dado) | 🔵 | 1 chave por domínio de dado/ambiente; alias por domínio |

## 12. Modelo de maturidade de criptografia (0–4)

Use para **medir** uma squad/conta e para dizer "o próximo passo". Cada nível pressupõe o anterior. Indicadores em
porcentagem são calculáveis a partir do IaC + `DescribeKey`/`GetKeyRotationStatus`/`GetKeyLastUsage`/`GetKeyPolicy`.

| Nível | Nome | O que se vê | Indicadores |
|---|---|---|---|
| **0** | Opaco | só chaves *AWS owned*/padrão; ninguém sabe o que está cifrado com o quê; sem inventário | inventário de chaves = ∅ |
| **1** | Visível | 100 % dos dados em repouso cifrados (SSE-S3, AWS owned/managed); inventário de recursos × tipo de chave; CloudTrail ligado; SNS/SQS com SSE | `cobertura_repouso` = 100 %; `recursos_sem_sse` = 0 |
| **2** | Governado | CMK onde há dado sensível/regulado; política admins × users × serviços (`aws:SourceArn`); **zero** `kms:*`/`Decrypt *` fora de admin; rotação automática ligada; janela de exclusão 30; alias e tags por domínio | `cmk_em_dados_sensiveis` = 100 %; `chaves_sem_rotacao` = 0; `politicas_abertas` = 0 |
| **3** | Mínimo privilégio por contexto | toda permissão de uso tem `kms:ViaService` **e** `kms:EncryptionContext:*`; grants só `GrantIsForAWSResource`; Bucket Keys/reuso de data key; SCP/RCP contra exclusão (MFA, janela, `TrailingDaysWithoutKeyUsage`); chaves sem uso identificadas e desabilitadas antes de excluir | `permissoes_sem_contexto` = 0; `chaves_sem_uso_90d` tratadas |
| **4** | Soberano e cripto-ágil | multi-Region com runbook de DR; BYOK/XKS/CloudHSM onde o regulador exige; ML-DSA em assinaturas de longa vida; PQ-TLS nos clientes; rotação sob demanda em incidente; **KPIs contínuos** com remediação por PR revisado | painel vivo; tempo de remediação medido |

**Contexto bancário (Brasil).** A Res. CMN 4.893/2021 (política de segurança cibernética e nuvem), alterada pela
**Res. CMN 5.274 de 18/12/2025** (adequação até 01/03/2026), lista **criptografia** entre os controles mínimos,
exige controle de acesso físico e lógico às **chaves privadas** sob responsabilidade da instituição, procedimentos
contra compartilhamento indevido e veda acesso de terceiros às chaves que assinam mensagens (Pix/STR em instância
dedicada). Tradução prática: nível **≥ 3** para dados do banco, chaves de assinatura em CMK/HSM com política que
exclui prestadores, e auditoria por CloudTrail. (Síntese informativa, não jurídica — confira o texto no DOU.)

### 12.1 Operacionalizar a régua (o que funcionou no OpsNauta, 16/10/2026)

Sem isto o modelo fica em slide. A régua vira **dado** e o motor fica estúpido de propósito (nenhum modelo de IA
decide o que é seguro):

```yaml
- id: chave_sem_rotacao                     # uma regra = um item do perfil declarativo
  escopo: { tipo_recurso: kms_key, atributos: { uso: ENCRYPT_DECRYPT, origem_material: AWS_KMS, replica: false } }
  verificacao: { tipo: atributo_inventario, atributo: rotacao, operador: falso }   # operador de um conjunto fechado
  mensagem: "A chave {{nome}} ({{ambiente}}) não tem rotação automática (KMS.4 / CIS 3.6)."
  correcao: "enable_key_rotation = true (e rotation_period_in_days entre 90 e 2560; padrão 365)."
  remediacao: { tarefa: habilitar-rotacao-kms }   # tarefa de um catálogo FECHADO — ou revisao_humana: true
  maturidade: { indicador: chaves_sem_rotacao, nivel: 2 }   # o nível que este indicador TRAVA
```

- **Nível N** = todo indicador de nível ≤ N zerado; para N ≥ 2 exige **algo governável** (CMK, permissão `kms:*`,
  recurso com CMK) — não se afirma governança do que não existe. Nível 4 fica reservado (depende da conta e de processo).
- **Validador antes de implantar** (ameaça "recomendação que piora"): recusa `correcao` com `enable_key_rotation = false`,
  `sqs_managed_sse_enabled = false`, `storage_encrypted = false`, janela < 30, chave vazia, `Principal *`, "desligue/
  remova … criptografia"; recusa `remediacao.tarefa` fora do catálogo; operador fora do conjunto; nível fora de 1–4.
- **Achados** com dedupe por hash (regra | repo | alvo | ambiente) que **fecham sozinhos** quando a avaliação não os
  reencontra — só entre as regras avaliadas (regra removida do perfil não resolve nada).
- **Um próximo passo** por repositório e pela squad (o indicador do nível mais baixo, com a correção e a tarefa em
  lote), mais o relatório executivo com fórmulas (Resumo · Recursos · Chaves · Permissões · Recomendações).
- **O mesmo motor roda sem nuvem** sobre checkouts (parser do IaC → regras → maturidade): é o teste de aceite e a
  ferramenta do dev. E **mede a própria plataforma**: no OpsNauta isso expôs o tópico SNS de avisos sem SSE (nível 0).
- Inventário guarda **só o trecho `kms:`** de cada policy (ações, `Resource *` sem condição, `ViaService`,
  `EncryptionContext`, chaves nomeadas) — nunca a policy inteira; chave sem alias ganha ARN **provisório**
  (`key/<rótulo>`) e uma regra cobrando o alias; valor de chave que vem de `local.`/função fica `indefinida` (revisão).

### 12.2 Sondar o parser antes de confiar nele (revisão independente, 17/10/2026)

Gabarito escrito pela mesma mão que escreveu o parser só confirma o que o autor já pensou. Antes de dar um nível a
alguém, rode estes cenários sintéticos contra o parser — cada um foi um erro real no OpsNauta:

| Sondagem | Resposta certa |
|---|---|
| `Effect = Deny` com `kms:Decrypt` em `Resource = "*"` (piso de segurança) | **não** é permissão ampla; `Deny Principal *` **não** é política aberta |
| statement com `Principal`/`principals` (política de **recurso**: chave, tópico, bucket) com `Resource = "*"` | não é permissão de identidade — `*` ali é o próprio recurso; avaliar como política da chave |
| `policy = data.aws_iam_policy_document.x.json` e `policy = file("x.json")` | seguir a referência: o documento/arquivo é a política |
| `Principal = { AWS = ["*"] }`, `identifiers = ["*"]`, `"Principal": "*"` em heredoc | todas são "aberta" (sem `Condition`) |
| `data "aws_kms_key" { key_id = "alias/aws/sns" }` usado por um recurso | chave **gerenciada pela AWS**, não CMK — sem isso o repo "ganha" governança que não tem |
| `aws_s3_bucket { server_side_encryption_configuration { … } }` inline (provider 3.x) | ler como o recurso à parte do provider ≥ 4 |
| `aws_kms_key.x[0].key_id`, `alias/${var.nome}` sem valor | referência com índice resolve; alias declarado conta mesmo sem nome |
| `customer_master_key_spec = "RSA_2048"` com `ENCRYPT_DECRYPT` | rotação **não se aplica** — regra e receita de rotação têm de pular (o `apply` falharia) |
| `kms_master_key_id = ""`, `"aws/sqs"` sem `alias/`, `enabled = var.x` sem valor | ausente / gerenciada pela AWS / `indefinida` |
| squad com um repo nível 3 e outro nível 1 | squad = **1** (elo mais fraco), com o repo apontado no próximo passo |
| 200 recomendações com textos de 1 000 caracteres | item de banco tem teto por **bytes** (DynamoDB: 400 KB), não só por contagem |
| validador T17: `= "false"` entre aspas, `server_side_encryption { enabled = false }`, `Principal = { AWS = "*" }`, "tire/retire/desabilite a cifra", `kms_key_arn = " "`, texto na `mensagem` | todos recusados; "remova o Principal curinga" passa |

## 13. Checklist de revisão (11 perguntas)

1. Que **dado** está em repouso aqui e qual o tipo de chave (owned / managed / CMK)? O tipo bate com a sensibilidade?
2. A política de chave tem **root + admins + users + serviços** separados? Algum `Principal: "*"`?
3. Alguma policy IAM com `kms:*` ou `Decrypt` em `*`? Toda permissão de uso tem **`ViaService` + contexto**?
4. Serviços como principal têm `aws:SourceArn`/`SourceAccount`?
5. Rotação automática ligada (período ≤ 365)? Quem pode `RotateKeyOnDemand`?
6. Janela de exclusão 30? SCP/RCP bloqueando `ScheduleKeyDeletion` sem MFA / com uso recente?
7. Chaves **sem uso** (`GetKeyLastUsage`) e chaves **agendadas para exclusão**?
8. Custo: há Bucket Key / reuso de data key / cache? Quantas chamadas KMS por minuto o desenho gera?
9. Quotas por Região suportam o pico (ex.: `us-east-2` = 20 k rps)?
10. Assinaturas de longa vida já em ML-DSA? Clientes com PQ-TLS?
11. A régua é **dado** (regra com indicador + nível + remediação; validador recusa correção que reduz segurança) e
    roda sem nuvem sobre o IaC? A própria plataforma está medida por ela?

## Fontes (consultadas em 15/10/2026)

- [KMS pricing](https://aws.amazon.com/kms/pricing/) · [Enable automatic rotation](https://docs.aws.amazon.com/kms/latest/developerguide/rotating-keys-enable.html) · [On-demand rotation](https://docs.aws.amazon.com/kms/latest/developerguide/rotating-keys-on-demand.html) · [Manual rotation](https://docs.aws.amazon.com/kms/latest/developerguide/rotate-keys-manually.html)
- [Least-privilege permissions](https://docs.aws.amazon.com/kms/latest/developerguide/least-privilege.html) · [Condition keys](https://docs.aws.amazon.com/kms/latest/developerguide/conditions-kms.html) · [Key policies](https://docs.aws.amazon.com/kms/latest/developerguide/key-policy-overview.html) · [Default key policy](https://docs.aws.amazon.com/kms/latest/developerguide/key-policy-default.html)
- [Request quotas](https://docs.aws.amazon.com/kms/latest/developerguide/requests-per-second.html) · [GetKeyLastUsage](https://docs.aws.amazon.com/kms/latest/APIReference/API_GetKeyLastUsage.html) · [KMS tracks last usage (27/04/2026)](https://aws.amazon.com/about-aws/whats-new/2026/04/aws-kms-tracks-last-usage-kms-keys/) · [ICYMI June 2026 security](https://aws.amazon.com/blogs/security/icymi-june-2026-aws-security/)
- [Parameter Store + KMS](https://docs.aws.amazon.com/kms/latest/developerguide/services-parameter-store.html) · [Step Functions encryption at rest](https://docs.aws.amazon.com/step-functions/latest/dg/encryption-at-rest.html) · [DynamoDB encryption at rest](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/EncryptionAtRest.html) · [DynamoDB: how it works](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/encryption.howitworks.html) · [S3 Bucket Keys](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-key.html) · [Lambda env vars encryption](https://docs.aws.amazon.com/lambda/latest/dg/configuration-envvars-encryption.html) · [SNS SSE](https://docs.aws.amazon.com/sns/latest/dg/sns-server-side-encryption.html)
- [Security Hub KMS controls](https://docs.aws.amazon.com/securityhub/latest/userguide/kms-controls.html) · [AWS Post-Quantum Cryptography](https://aws.amazon.com/security/post-quantum-cryptography/) · [On-demand rotation for imported keys (06/2025)](https://aws.amazon.com/about-aws/whats-new/2025/06/aws-kms-on-demand-key-rotation-imported-keys/) · [Backup air-gapped vaults + CMK (11/2025)](https://aws.amazon.com/about-aws/whats-new/2025/11/aws-backup-kms-customer-managed-keys/)
- [Res. CMN 5.274/2025 (altera a 4.893/2021)](https://www.legisweb.com.br/legislacao/?id=488277) · [cloudburn — KMS pricing breakdown (mar/2026)](https://cloudburn.io/blog/aws-kms-pricing) · [Infracost — KMS rotation policy](https://www.infracost.io/resources/finops-policies/kms-consider-enabling-automatic-key-rotation)
