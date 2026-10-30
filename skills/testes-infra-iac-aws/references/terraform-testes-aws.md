# Terraform na AWS — testes (o que a AWS publica)

> Reference de `testes-infra-iac-aws`. Terraform é da HashiCorp **(terceiro)**; tflint, tfsec e Checkov
> também são **(terceiros)**. Base: blog AWS DevOps sobre o `terraform test`, Prescriptive Guidance
> "Create a CI/CD pipeline to validate Terraform configurations", PG de LocalStack + Terraform Tests e PG
> de boas práticas do provider AWS. Autoria, state e módulos: `engenheiro-iac`.

## 1. `terraform test` (Terraform 1.6+)

- Arquivos `*.tftest.hcl` com blocos `provider`, `variables` e **`run`** (executados em ordem).
- **`command = plan`**: rápido e sem custo — testes unitários e de contrato.
- **`command = apply`**: cria infraestrutura real para integração e **destrói ao final**, passando ou
  falhando.
- `assert { condition, error_message }`; **`expect_failures`** para testes negativos (validação de
  variáveis); módulos auxiliares (`run.<nome>.<output>`).
- Camadas da AWS: `terraform test` (unit e integração) → **validation e pre/postconditions** (contrato) →
  **check blocks** (verificação pós-criação) → política como código.

```hcl
# tests/fila.tftest.hcl
run "fila_tem_dlq" {
  command = plan
  assert {
    condition     = jsondecode(aws_sqs_queue.pedidos.redrive_policy).maxReceiveCount == 5
    error_message = "Fila de pedidos precisa de DLQ com maxReceiveCount = 5."
  }
}

run "nome_invalido_reprova" {
  command = plan
  variables { nome_servico = "Pedidos_X" }
  expect_failures = [var.nome_servico]
}
```

## 2. Pipeline de validação (Prescriptive Guidance)

Estágios: checkout → **validate** (`terraform fmt -check`, `terraform validate`, tfsec, TFLint, Checkov) →
**plan** (`-out=tfplan`) → **apply em ambiente de teste** → **destroy**.

- **Atenção:** no padrão publicado, `SKIPVALIDATIONFAILURE` vem como "Y" — a validação **não bloqueia**.
  Mude para "N".
- Fixe versões, backend remoto (S3) cifrado, role do pipeline com menor privilégio, artefatos com KMS.
- No blog do `terraform test`: um CodeBuild roda Checkov (falha reprova), outro roda init/validate/test.

## 3. Políticas IAM e segurança

- Políticas IAM do plano validadas pelo IAM Access Analyzer (validador para Terraform lê o plano em JSON) —
  ver `testes-seguranca-aws` (`iam-access-analyzer-no-pipeline.md`).
- Amazon Inspector code security varre Terraform no repositório.
- cfn-guard também valida o plano em JSON (`terraform show -json`).

## 4. LocalStack (terceiro) com Terraform Tests

- PG da AWS mostra `terraform test` contra LocalStack: sem custo AWS e feedback rápido.
- Limitações: emulação parcial, recursos só na versão paga, não rodar o contêiner privilegiado no CI.
- Regra da Squad: emulador acelera; **a integração crítica roda em conta AWS de teste**.

## 5. Matriz mínima

| camada | comando | bloqueia? |
|---|---|---|
| formato e sintaxe | `terraform fmt -check`, `terraform validate`, tflint | sim |
| segurança/política | Checkov ou equivalente; Guard/OPA; Access Analyzer | sim (alto/crítico) |
| unitário | `terraform test` com `command = plan` | sim |
| integração | `terraform test` com `apply` em conta de teste | sim |
| mudança | `terraform plan` revisado por humano | gate de produção |
| pós-deploy | plan periódico para drift; AWS Config | alerta + correção no código |

## Fontes

- https://aws.amazon.com/blogs/devops/terraform-ci-cd-and-testing-on-aws-with-the-new-terraform-test-framework/
- https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/create-a-ci-cd-pipeline-to-validate-terraform-configurations-by-using-aws-codepipeline.html
- https://docs.aws.amazon.com/en_us/prescriptive-guidance/latest/patterns/test-aws-infra-localstack-terraform.html
- https://docs.aws.amazon.com/prescriptive-guidance/latest/terraform-aws-provider-best-practices/resources.html
- https://docs.aws.amazon.com/cfn-guard/latest/ug/what-is-guard.html
