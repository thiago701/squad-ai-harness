# KMS — decisão de chave por serviço, custo, quotas e FinOps

> **Quando ler:** escolher entre chave *AWS owned*, *AWS managed* e **CMK** por serviço; estimar o custo de KMS de um
> desenho (requisições, chaves, rotação, multi-Region); evitar throttling; achar chaves sem uso. Segurança, política
> e condition keys em `engenheiro-seguranca/references/aws-kms.md`; HCL em `engenheiro-iac/references/kms-terraform.md`.
> Números conferidos em 15/10/2026 (fontes no fim).

## 1. Matriz de decisão (P1 > P2 > P3)

| Pergunta | Resposta | Chave |
|---|---|---|
| O dado é público ou descartável e nenhuma norma exige controle de chave? | sim | **AWS owned** (grátis, zero operação) |
| Preciso **ver no CloudTrail** quem decifrou, mas não preciso de política própria nem rotação sob meu comando? | sim | **AWS managed** `aws/<serviço>` (armazenamento grátis; requisições cobradas) |
| Preciso de política própria (quem usa, via qual serviço, com qual contexto), rotação sob meu comando, exclusão, separação de funções, auditoria por domínio, ou um regulador/cliente exige "chave do cliente"? | sim | **CMK** (US$ 1/mês + requisições) |
| Preciso que o material **nunca** esteja na AWS (soberania) ou de HSM dedicado? | sim | CMK importada (BYOK), **XKS** ou CloudHSM — custo e operação altos; só com exigência explícita |
| Preciso que a mesma chave decifre em outra Região sem re-cifrar (DR ativo-ativo, réplica global)? | sim | CMK **multi-Region** (US$ 1/réplica) |

**Regra de bolso:** uma CMK **por domínio de dado × ambiente** (não por recurso): a política diz quem é dono do
dado; o alias (`alias/faturamento-prod`) é o nome que os times usam. Muitas chaves = muitas políticas para errar e
US$ 1 cada; uma chave para tudo = raio de impacto total ao desabilitar.

## 2. Modelo de custo

| Item | Preço | Observação |
|---|---|---|
| CMK (qualquer tipo, inclusive importada e em custom key store) | **US$ 1/mês**, rateado por hora | agendada para exclusão: não cobra |
| Rotação (automática ou sob demanda) | +US$ 1/mês na 1ª e na 2ª rotação; **nada da 3ª em diante** | teto efetivo **US$ 3/mês** por chave |
| Réplica multi-Region | US$ 1/mês cada | requisições cobradas em cada Região |
| Requisições simétricas / HMAC | ~US$ 0,03 por 10 k | `Encrypt`, `Decrypt`, `GenerateDataKey*`, `ReEncrypt`, `GenerateRandom`, `GenerateMac/VerifyMac` |
| Requisições assimétricas (RSA, ECC, **ML-DSA**) | ~US$ 0,15 por 10 k | `Sign`, `Verify`, `Encrypt/Decrypt` RSA, `GetPublicKey` |
| `GenerateDataKeyPair*` | tabela própria (RSA/ECC) | fora do free tier |
| **Free tier** | **20.000 requisições/mês**, somadas em todas as Regiões | exclui assimétricas e `GenerateDataKeyPair*` |
| Chaves AWS managed / AWS owned | armazenamento grátis | AWS managed **cobra requisições**; AWS owned não |
| Custom key store CloudHSM | + ~US$ 1,60/HSM/hora (mín. 2 HSMs) | ≈ US$ 2.300+/mês |
| Cross-account | **quem chama paga** | — |

**Exemplos (US$/mês):**
- POC pessoal com SSM `aws/ssm`, S3 SSE-S3, DynamoDB AWS owned, SNS sem SSE: **0** (requisições dentro do free
  tier). *Atenção:* uma ADR do tipo "nenhum serviço com mínimo mensal" **proíbe CMK** sem exceção explícita.
- Plataforma pequena com **1 CMK** para SSM + S3 + DynamoDB + SNS + Logs, rotação anual: **1–3**.
- Produto com 4 domínios × 3 ambientes, rotação ligada: 12 chaves × 3 = **≤ 36** + requisições.
- 1 bilhão de `GET` em S3 SSE-KMS **sem** Bucket Key ≈ **US$ 3.000**; **com** Bucket Key ≈ dezenas de dólares.

## 3. Quantas chamadas KMS o desenho gera? (o que custa e o que estrangula)

| Serviço | Chamadas | Como reduzir |
|---|---|---|
| S3 SSE-KMS | 1 por objeto gravado/lido | **Bucket Key** (−99 %): `bucket_key_enabled = true` |
| DynamoDB (CMK/managed) | refresh da chave de tabela a cada **5 min por chamador** com tráfego | *keep-alive* no SDK (reaproveita a conexão → reaproveita o cache) |
| Step Functions (CMK) | 1 `GenerateDataKey` por `KmsDataKeyReusePeriodSeconds` (60–900, padrão 300) + `Decrypt` ao ler histórico | subir para 900 s onde a latência de rotação de data key não importa |
| SQS (CMK) | 1 por `KmsDataKeyReusePeriodSeconds` (60–86.400) por produtor/consumidor | 3.600+ s em filas internas |
| SSM SecureString | 1 `Decrypt` por `GetParameter` com decifra | cache em memória na Lambda (TTL de minutos) — padrão *config loader* |
| Secrets Manager | 1 `Decrypt` por `GetSecretValue` | cache (AWS Secrets Manager caching libs) |
| Aplicação com Encryption SDK | 1 `GenerateDataKey` por mensagem | **data key caching** (limite por tempo/quantidade/bytes) |
| Lambda env vars | 1 `Decrypt` por **cold start** | nada a fazer (já é mínimo) |

**Quotas por conta/Região** (simétricas, compartilhadas): 100 k rps em `us-east-1`/`us-west-2`/`eu-west-1`;
20 k em `us-east-2`, `ap-southeast-1/2`, `ap-northeast-1`, `eu-central-1`, `eu-west-2`, `eu-south-2`; 10 k nas
demais. Assimétricas: 1 k rps por família. Custom key store: 1.800 rps. Ajustáveis via Service Quotas, exceto
CloudHSM key store. Uma Região "barata" (`us-east-2`, 20 k) **estrangula 5× antes** que `us-east-1` — pese isso
num desenho com ambientes por Região.

## 4. FinOps de chaves

- **Chaves sem uso:** `GetKeyLastUsage` (abr/2026) devolve a última operação, `CloudTrailEventId` e
  `TrackingStartDate`. Rotina mensal: listar CMKs, marcar as sem uso há > 90 dias, **desabilitar** (não excluir) e
  observar `DisabledException` no CloudTrail por 30 dias; só então agendar exclusão com janela de 30.
- **Chaves com rotação "cara":** rotação custa no máximo +US$ 2/mês — não é motivo para desligar; é motivo para
  não ter chaves demais.
- **Multi-Region "por via das dúvidas":** cada réplica é US$ 1/mês e dobra a superfície de política; replique só
  onde há dado replicado.
- **Tag `dominio`/`projeto` na chave** para o Cost Explorer agrupar; alias por domínio para as pessoas acharem.
- **Métrica de maturidade** (ver `engenheiro-seguranca/references/aws-kms.md` §12): `% recursos com SSE`,
  `% dados sensíveis em CMK`, `chaves sem rotação`, `políticas abertas`, `permissões de uso sem contexto`,
  `chaves sem uso 90 d` — vale um painel por squad.

## 5. Padrões de referência

- **Serverless pequeno (POC/free tier):** AWS owned/managed em tudo; IAM com `kms:ViaService` +
  `kms:EncryptionContext` mesmo com chave gerenciada; SNS/SQS com SSE ligada (`aws/sns`, SSE-SQS); zero CMK.
- **Produto/banco:** 1 CMK por domínio × ambiente na **conta de segurança** (política cross-account por serviço com
  `aws:SourceArn`), rotação anual, janela 30, SCP contra exclusão (MFA + `kms:TrailingDaysWithoutKeyUsage`),
  Bucket Key, reuso de data key, CloudTrail em trilha organizacional; chaves de **assinatura** (Pix/STR, documentos)
  em CMK dedicada — ML-DSA quando a validade passa de 10 anos — com política que **exclui prestadores**.
- **DR multi-Região:** multi-Region keys só para os dados replicados; runbook testado de promoção de réplica.

## Fontes (15/10/2026)

[KMS pricing](https://aws.amazon.com/kms/pricing/) · [Request quotas](https://docs.aws.amazon.com/kms/latest/developerguide/requests-per-second.html) · [S3 Bucket Keys](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-key.html) · [DynamoDB: how encryption works](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/encryption.howitworks.html) · [Step Functions encryption at rest](https://docs.aws.amazon.com/step-functions/latest/dg/encryption-at-rest.html) · [GetKeyLastUsage](https://docs.aws.amazon.com/kms/latest/APIReference/API_GetKeyLastUsage.html) · [cloudburn — KMS pricing (mar/2026)](https://cloudburn.io/blog/aws-kms-pricing)
