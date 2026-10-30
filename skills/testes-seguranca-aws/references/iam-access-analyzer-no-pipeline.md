# IAM Access Analyzer como teste de política no pipeline

> Reference de `testes-seguranca-aws`. Base: doc de custom policy checks do IAM Access Analyzer, blogs
> de lançamento e o blog "Validate IAM policies by using IAM Policy Validator for AWS CloudFormation and
> GitHub Actions". **Restrição da Squad:** não criar nem alterar `.github/workflows` sem pedido — use o
> validador pela CLI no harness local; as GitHub Actions citadas são só referência.

## 1. O que existe

| verificação | pergunta | quando usar |
|---|---|---|
| **validate-policy** | a política tem erro, aviso de segurança ou de boa prática? | toda política nova ou alterada |
| **CheckNoNewAccess** | a nova versão concede mais acesso que a referência? | mudança em política existente |
| **CheckAccessNotGranted** | ações/recursos sensíveis (ex.: `iam:PassRole`, `kms:Decrypt`, `s3:DeleteBucket`) estão fora? | guarda-corpo do time/empresa |
| **CheckNoPublicAccess** | a política de recurso (S3, KMS, SQS, Lambda...) é pública? | toda política de recurso |
| **unused access** (analisador) | há roles, chaves, senhas e permissões sem uso (padrão 90 dias)? | contínuo, pós-deploy |
| **external access** (analisador) | recurso compartilhado fora da conta/organização? | contínuo, pós-deploy |

Os custom checks usam raciocínio automatizado (prova formal sobre a política). Cobrança **por check**.

## 2. No pipeline

- **IAM Policy Validator for AWS CloudFormation** (`cfn-policy-validator`, awslabs): extrai as políticas
  do template, roda validate-policy e os custom checks; achado bloqueante reprova.
- Terraform: o validador equivalente lê o plano em JSON (`terraform show -json`).
- Referência AWS (aws-samples `access-analyzer-automated-policy-analysis-blog`): PR → CodeBuild →
  comentário no PR → deploy só se passar.

```bash
# exemplo pela CLI (harness local ou CodeBuild); credenciais da conta de CI por variável/role
aws accessanalyzer validate-policy --policy-type IDENTITY_POLICY \
  --policy-document file://politica.json
aws accessanalyzer check-access-not-granted --policy-type IDENTITY_POLICY \
  --policy-document file://politica.json \
  --access '[{"actions":["iam:PassRole","kms:Decrypt"]}]'
aws accessanalyzer check-no-public-access --resource-type AWS::S3::Bucket \
  --policy-document file://bucket-policy.json
```

## 3. Regras de gate

- `ERROR` e `SECURITY_WARNING` do validate-policy **bloqueiam**; `SUGGESTION` vira comentário.
- CheckAccessNotGranted e CheckNoPublicAccess `FAIL` **bloqueiam**.
- CheckNoNewAccess `FAIL` exige revisão humana registrada (aumento de acesso pode ser legítimo).
- Exceção só com aceite datado (dono, motivo, prazo).
- Complementos: cfn-guard/cdk-nag para padrões da empresa (`testes-infra-iac-aws`).

## 4. Depois do deploy

- Analisadores de **acesso externo** e **acesso não utilizado** ativos; achados no Security Hub CSPM.
- Revisão periódica: remover permissões sem uso (least privilege contínuo).

## Fontes

- https://docs.aws.amazon.com/IAM/latest/UserGuide/access-analyzer-custom-policy-checks.html
- https://aws.amazon.com/blogs/security/introducing-iam-access-analyzer-custom-policy-checks
- https://aws.amazon.com/blogs/aws/iam-access-analyzer-updates-find-unused-access-check-policies-before-deployment
- https://aws.amazon.com/blogs/security/validate-iam-policies-by-using-iam-policy-validator-for-aws-cloudformation-and-github-actions
