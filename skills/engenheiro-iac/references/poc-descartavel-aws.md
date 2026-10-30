# POC descartável na AWS — subir, testar, apagar tudo e subir de novo

> **Origem:** caso-modelo RadarIAOps (13/10/2026; Terraform 1.16, provider AWS 6.6x, conta pessoal com ambientes
> simulados por região). Lição `LL-0018`. Use quando o dono quer **ciclos de cenário**: aplicar, testar, melhorar,
> destruir sem sobras e reaplicar — e na spec da Onda 0, não depois do primeiro `apply`.

## 1. Duas camadas de estado

| Camada | Vive | Contém | Destroy |
|---|---|---|---|
| **conta-base** (`infra/bootstrap`) | persistente | bucket do tfstate, **singletons por conta**: agregador do Resource Explorer, provider OIDC do GitHub | só com `--tudo` |
| **plataforma** (`infra/terraform`) | descartável | tudo que o produto usa (tabelas, Lambdas, Step Functions, AppConfig, budgets, alarmes) | todo ciclo |

Por que singletons vão para a base:
- **Resource Explorer**: trocar o índice AGGREGATOR tem **cooldown de 24 h** — destruir/recriar a cada ciclo trava.
- **OIDC provider** do GitHub: um por URL por conta; se outra stack já tem, o `apply` falha.
- Bucket do state não pode ser destruído pela stack que ele guarda.

## 2. Tags de rastreamento (via `default_tags` do provider)

| Tag | Valor | Para quê |
|---|---|---|
| `projeto` | `<slug>` | filtro de custo, varredura, budget por tag |
| `ambiente` | `dev`/`hml`/`prod` | separação por região simulada |
| `gerenciado-por` | `terraform` | distingue do que o runtime cria sozinho |
| `stack` | `plataforma` \| `conta-base` | o que o destroy normal pode apagar |
| `repositorio` | nome do repo | descoberta por tag (Resource Explorer `tag:repositorio=<repo>`) quando o nome vem de config |
| `cenario` | rótulo do ciclo de teste (validado por regex) | comparar custos/resultados entre ciclos |

Teste com `terraform test` + `mock_provider` que **toda** tag obrigatória está no provider (run `tags_de_rastreamento`).

## 3. O que quebra o `destroy` (e a correção)

| Sintoma | Causa | Correção no fluxo |
|---|---|---|
| `DeleteApplication` / perfil falha | **deletion protection** do AppConfig (perfil usado recentemente) | antes do destroy: parar deployments, apagar versões hospedadas, `DeletionProtectionCheck="BYPASS"` |
| role não apaga | policy anexada fora do Terraform (ex.: ação de budget) | `force_detach_policies = true` + desanexar no preparo |
| log groups sobram | o runtime da Lambda/Step Functions cria `/aws/...` sozinho | apagar órfãos **por nome exato** da saída do Terraform |
| sobra algo sem tag | recurso criado pelo serviço (budget, alarme, parâmetro) | varredura por **Tag API + nomes** (IAM, budgets, SSM paginado, logs paginado, AppConfig, alarmes, scheduler), deduplicando por (serviço, nome) |
| destroy na conta errada | profile trocado | **conferir a conta** (`sts:GetCallerIdentity`) contra a saída do Terraform e exigir frase digitada (ex.: `destruir <projeto>`) |

Fluxo testado: gerar flags → `init` → `output` → conferir conta → confirmação digitada → preparar → `terraform
destroy` → órfãos → (`--tudo`: destruir a base e o `backend.hcl`) → varredura → relatório do que sobrou.

## 4. Segredos e permissões que não vazam no ciclo

- **Segredo nunca no state**: `aws_ssm_parameter` com `value_wo` + `value_wo_version` (argumentos *write-only*,
  Terraform 1.11+). `sensitive = true` **não** tira o valor do state; `ignore_changes` também não (o refresh lê).
  O valor real entra fora do Terraform (`getpass` → `PutParameter` SecureString).
- `aws_lambda_permission` de serviço → `source_account` (o ARN de origem às vezes não existe ainda).
- Lambda com zip gerado pelo build: `source_code_hash = fileexists(var.zip) ? filebase64sha256(var.zip) : null`
  para `validate`/`test` rodarem sem o artefato.
- Roles de CI que o projeto não usa ainda **não nascem** (menor superfície no primeiro `apply`).

## 5. Runbooks que o dono executa (gated)

`bootstrap` → `apply` → `segredos` → `publicar` (configs, em série: 1 deployment por ambiente de cada vez) →
`verificar` → ciclo de testes → `destroy` (ou `destroy --tudo`) → `varrer`. A Squad entrega o runbook e o
`tarefas.py`; **quem roda o irreversível na conta é o dono**.

## 6. Anti-padrões

- **"Singleton na stack descartável"** — agregador/OIDC dentro da plataforma: o 2º ciclo falha.
- **"Varredura por substring"** — apagar `foo-scheduler` porque casou `foo`; dedupe e nomes exatos.
- **"Destroy de confiança"** — sem conferir conta e sem frase digitada.
- **"Segredo sensível = segredo seguro"** — `sensitive` só esconde do log, o state continua com o valor.
