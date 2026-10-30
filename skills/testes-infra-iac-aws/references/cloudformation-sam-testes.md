# CloudFormation e SAM — testes de template, política e mudança segura

> Reference de `testes-infra-iac-aws`. Base: docs do cfn-lint, CloudFormation Guard, CloudFormation
> Hooks, change sets, drift detection, TaskCat (aws-ia) e DevOps Guidance QA.NT.1.

## 1. cfn-lint (estático)

- Valida contra os **resource provider schemas**: propriedade inválida, valor não suportado, referência
  quebrada, boas práticas; aplica o transform do **SAM**.
- `--regions` (padrão us-east-1), `--parameters`/`--parameter-files`; saída `json`, `junit` ou **`sarif`**;
  exit code ≠ 0 reprova (`--non-zero-exit-code`).
- Configuração em `.cfnlintrc` ou `Metadata.cfn-lint`; regras próprias em uma linha
  (`AWS::EC2::Instance InstanceType NOT_EQUALS "m4.16xlarge" WARN`) ou em Python (`--append-rules`).
- Language Server no IDE, **pre-commit**, API Python.

```bash
cfn-lint template.yaml --format sarif --output-file cfn-lint.sarif
```

## 2. CloudFormation Guard (política como código)

- DSL declarativa com **framework de teste unitário das próprias regras** (cada regra com caso que passa e
  caso que falha).
- Valida qualquer JSON/YAML: templates **e change sets**, Terraform em JSON (plano), Kubernetes,
  configuration items do AWS Config.
- **Não substitui o cfn-lint** (não valida sintaxe) e **não faz enforcement no servidor** (isso é Hook).
- Usos: preventivo (PR), detectivo (Config), **segurança de deploy** (bloquear change set que causa
  *replacement*, ex.: renomear tabela DynamoDB) e Hooks.

```
# regras/s3.guard
let buckets = Resources.*[ Type == 'AWS::S3::Bucket' ]
rule s3_bloqueia_publico when %buckets !empty {
  %buckets.Properties.PublicAccessBlockConfiguration.BlockPublicAcls == true
  %buckets.Properties.PublicAccessBlockConfiguration.RestrictPublicBuckets == true
}
```
```bash
cfn-guard validate --data template.yaml --rules regras/
cfn-guard test --rules-file regras/s3.guard --test-data regras/s3-testes.yaml
```

## 3. CloudFormation Hooks (enforcement no provisionamento)

- Inspecionam recurso, stack, change set e Cloud Control API **antes** do provisionamento; em não
  conformidade **falham** a operação ou só avisam.
- Implementação: controles proativos do Control Tower, **regras Guard**, funções Lambda ou Hook próprio.
- Exemplos: regras de security group, instâncias menores em dev, backup obrigatório no RDS.

## 4. Change sets (mudança segura)

- Revise mudanças e **property-level changes** antes de executar; atenção a `Replacement: True`.
- A criação gera avisos (quotas, conflitos) sem bloquear; exige reconhecer capabilities de IAM.
- Use como gate humano antes de produção e como entrada do Guard.

## 5. Drift detection (conformidade pós-deploy)

- Stack `DRIFTED`/`IN_SYNC`/`NOT_CHECKED`; recurso `MODIFIED`/`DELETED`.
- Limitações: só recursos suportados; não varre stacks aninhadas automaticamente; compara só propriedades
  explícitas; não compara algumas (ex.: código da Lambda); falsos positivos de unidade (1024 MB × 1 GB).
- Agende e trate drift como defeito: corrigir no código, não no console.

## 6. TaskCat (implantação real multirregião)

- Faz o **deploy real** do template em várias regiões, com parâmetros e número de AZs configuráveis, e
  gera relatório **pass/fail por região**. Rodar em conta de teste; limpar no fim.

## 7. SAM

- `sam validate --lint` usa o cfn-lint sobre o template SAM.
- Teste da aplicação sobre a stack: ver `estrategia-testes-aws` (`serverless-testes-na-nuvem.md`).
- Contrato da API no Gateway configurado: `contrato-reverso` (lê SAM, CloudFormation/CDK e Terraform).

## Fontes

- https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cfn-lint.md
- https://docs.aws.amazon.com/cfn-guard/latest/ug/what-is-guard.html
- https://docs.aws.amazon.com/cloudformation-cli/latest/hooks-userguide/what-is-cloudformation-hooks.html
- https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-changesets-create.html
- https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-stack-drift.html
- https://github.com/aws-ia/taskcat
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/qa.nt.1-evaluate-code-quality-through-static-testing.html
