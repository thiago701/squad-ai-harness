# IaC e CI/CD na AWS: CDK, CloudFormation, CodePipeline e Boas Práticas Terraform (Agent Toolkit for AWS)

> **Procedência:** absorvido e reescrito em PT-BR a partir de `aws/agent-toolkit-for-aws` (`skills/core-skills/aws-cdk`, `aws-cloudformation`, `aws-deployment` e `plugins/aws-startup-advisor/skills/tf-best-practices`, commit `658b852f0612ca629d56d0a4de52738fb6a58714`, Apache-2.0).

---

## 1. Postura de Autoria e Portão de Políticas em Terraform (`tf-best-practices`)

### 1.1. Parte 1 — Postura Preventiva Antes de Escrever `terraform/`
1. **Estrutura Modular e State Seguro:**
   - Backend S3 com criptografia KMS, versionamento ativo e lock nativo (`use_lockfile = true` no Terraform ≥ 1.10 ou tabela DynamoDB de lock).
   - Pinagem estrita de `required_version` do Terraform e de versões dos providers (`~> 5.0`), com `.terraform.lock.hcl` versionado.
2. **Defaults Seguros de Recursos AWS em HCL:**
   - **S3:** `aws_s3_bucket_public_access_block` (4 flags = `true`), `aws_s3_bucket_server_side_encryption_configuration` e `aws_s3_bucket_versioning`.
   - **VPC / Security Groups:** descrições obrigatórias em todas as regras; proibido `0.0.0.0/0` em portas de administração (22, 3389) ou de bancos de dados (5432, 3306, 6379, 27017); prefira recursos `aws_vpc_security_group_ingress_rule` / `egress_rule` avulsos em vez de blocos inline.
   - **IAM:** documentos gerados via `data "aws_iam_policy_document"` (evita erros de sintaxe JSON e interpolação insegura), sem curingas `*` em ações de escrita/administração.
   - **KMS e Logs:** `enable_key_rotation = true` em toda `aws_kms_key` e `retention_in_days` explícito em todo `aws_cloudwatch_log_group`.

### 1.2. Parte 2 — Portão de Validação Pós-Escrita (Antes do `apply`)
Execute em sequência obrigatória:
1. `terraform fmt -check -recursive`
2. `terraform init -backend=false && terraform validate`
3. `terraform test` (testes de unidade/contrato de módulos `.tftest.hcl`)
4. Scanner estático de segurança e policy-as-code (**Checkov / Trivy / tfsec**) — zero achados `CRITICAL`/`HIGH`.
5. `terraform plan -out=tfplan` revisado por humano no **GATE** antes de qualquer `apply`.

---

## 2. AWS CDK: Padrões de Constructs, Conformidade e Deploy Rápido (`aws-cdk`)

1. **Hierarquia de Constructs:**
   - Prefira Constructs **L2** (defaults seguros e métodos `grant*` de privilégio mínimo) ou **L3** (padrões arquiteturais); evite **L1 (`Cfn*`)** a menos que a propriedade ainda não exista no L2 (nesse caso, use *escape hatches* `node.defaultChild`).
2. **Separação de Stacks Stateful vs Stateless:**
   - Mantenha bancos de dados (Aurora, DynamoDB), buckets S3 e chaves KMS em stacks **Stateful** com `RemovalPolicy.RETAIN` e `terminationProtection: true`.
   - Mantenha Lambdas, API Gateway, ECS Services e Step Functions em stacks **Stateless**.
3. **Preservação de Logical IDs:**
   - Renomear ou mover um construct altera seu Logical ID no CloudFormation e **recria (destrói)** o recurso com estado. Sempre rode `cdk diff` e revise qualquer linha `[-] / [+]` ou `replace` antes de implantar.
4. **Conformidade e Velocidade em Dev:**
   - Incorpore **`cdk-nag`** (`AwsSolutionsChecks`) na árvore do App para barrar violações no `cdk synth`.
   - Use `cdk deploy --hotswap` **exclusivamente em ambientes efêmeros de desenvolvimento** para iterar código Lambda/Step Functions/ECS; em staging/produção, use sempre deploy completo via CloudFormation Change Set.

---

## 3. AWS CloudFormation: Autoria, Lint, Guard e Drift (`aws-cloudformation`)

- **Ciclo de validação local obrigatório antes do deploy:**
  1. **`cfn-lint`** para validar sintaxe, tipos de recursos, propriedades válidas por região e referências `!Ref` / `!GetAtt`.
  2. **`cfn-guard`** para validar políticas de segurança e governança (criptografia, IAM, rede).
  3. **Change Sets + Drift Detection:** antes de atualizar uma stack existente, execute `detect-stack-drift` para garantir que alterações manuais no console não serão sobrescritas silenciosamente, e inspecione o Change Set antes de executá-lo.

---

## 4. Pipelines de Entrega na AWS (`aws-deployment`)

- **Composição segura (`CodeConnections` → `CodeBuild` → `CodeDeploy` / `CloudFormation` orquestrados por `CodePipeline` e `CodeArtifact`):**
  1. Use **AWS CodeConnections** (substituto moderno do CodeStar Connections, nunca OAuth tokens pessoais ou chaves SSH estáticas) para integrar repositórios Git.
  2. No **CodeBuild**, utilize role IAM de privilégio mínimo por estágio (role de build/test separada da role de deploy), cache de dependências no S3/CodeArtifact e imagens gerenciadas atualizadas.
  3. No **CodeDeploy**, aplique implantações progressivas (**Canary** ou **Linear** para Lambda/ECS, e **Blue/Green** com validação de tráfego e *auto-rollback* acionado por alarmes CloudWatch).
