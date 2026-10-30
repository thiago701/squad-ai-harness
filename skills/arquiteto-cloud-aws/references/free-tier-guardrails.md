# Referência — Guardião do Free Tier (limites centralizados, contadores e kill switch)

> Parte da skill `arquiteto-cloud-aws`. Carregue quando o projeto tiver **"free tier obrigatório"** ou "custo ≤ US$ X/mês" como critério de aceite, quando precisar de **rate limit de uso** (não só de requisições) ou quando Lambda, Step Functions, IaC e AWS Budgets precisarem ler **o mesmo** limite. Hub: `../SKILL.md`. Fatos conferidos em 12/10/2026 nas fontes do fim — reconfirme antes de fixar valores.

## 1. Mapa do free tier que importa para serverless

| Serviço | *Always free* (enquanto for cliente) | Só 12 meses / crédito | Sem free tier |
|---|---|---|---|
| Lambda | 1 M requisições + 400 k GB-s/mês | | |
| DynamoDB | 25 WCU + 25 RCU **provisionadas** + 25 GB (somadas entre tabelas **e GSIs**) | | on-demand não entra |
| Step Functions | **Standard: 4.000 transições/mês** (não expira) | | **Express** (US$ 1/M requisições + GB-s) |
| EventBridge Scheduler / rules / API Destinations | 14 M invocações/mês | | |
| SSM Parameter Store | parâmetros *standard* (4 KB, throughput padrão) | | *advanced* US$ 0,05/parâmetro/mês |
| CloudWatch | 5 GB de logs, 10 alarmes, 10 métricas custom | | |
| SNS | 1.000 e-mails | | |
| S3 | | 5 GB (12 meses) | |
| API Gateway | | 1 M chamadas (12 meses) | HTTP API US$ 1/M depois |
| AWS Budgets | 2 orçamentos **com ação** grátis; alertas grátis | | 3º orçamento com ação: US$ 0,10/dia |
| AppConfig | | | US$ 0,0008 por configuração **recebida** + US$ 0,0000002 por requisição |
| Bedrock | | | por token (Nova Micro 0,035/0,14 · Nova Lite 0,06/0,24 · Claude Haiku 4.5 1/5 — US$ por 1 M tokens entrada/saída, us-east-1) |

Conta criada **depois de 15/07/2025** entra no plano Free com até US$ 200 de créditos por 6 meses; conta anterior segue 12 meses + *always free*. Verifique no console de Billing antes de prometer "zero".

## 2. Um arquivo, muitos consumidores (o padrão)

```
repo/config/limites.yaml  ──(PR revisado)──▶ pipeline/IaC ──▶ SSM Parameter Store  /<projeto>/limites  (JSON)
        │                                                        ▲            ▲            ▲
        │ mesma fonte                                            │            │            │
        ├─▶ IaC: reserved concurrency, throttling, MaxConcurrency, cadência do Scheduler, max_tokens
        ├─▶ Lambdas: leem na init com cache (TTL 5 min)         Step Functions: 1 transição (`ssm:getParameter`)
        ├─▶ AWS Budgets: orçamentos de uso e custo criados a partir dos mesmos números
        └─▶ CLI / GitHub Actions (OIDC): leem o parâmetro — nenhum valor copiado à mão
```

"Centralizado e público" significa **um único lugar lido por todos os recursos da conta via IAM** — nunca exposto à internet.

Esqueleto do arquivo (adapte nomes; versione o schema):
```yaml
versao: 1
free_tier:                      # quotas que não podem ser ultrapassadas
  stepfunctions: {transicoes_mes: 4000}
  lambda:        {invocacoes_mes: 1000000, gb_segundos_mes: 400000}
  dynamodb:      {wcu_total: 25, rcu_total: 25, gb: 25}
  cloudwatch:    {logs_gb_mes: 5, alarmes: 10}
limiares:  {aviso: 0.70, degradacao: 0.85, bloqueio: 0.95}
orcamento_custo_mes_usd: 5
rate_limits:                    # valores que a IaC e o código aplicam
  lambda:  {reserved_concurrency: {assistente: 5, coletador: 2}}
  api:     {rate_por_segundo: 10, burst: 20}
  stepfunctions: {map_max_concurrency: 2, agenda: {incremental: "cron(0 3 * * ? *)", completa: "cron(0 4 ? * SUN *)"}}
  bedrock: {max_tokens_resposta: 800, tokens_mes: 3000000, modelo_rapido: "amazon.nova-lite-v1:0", modelo_raciocinio: "anthropic.claude-haiku-4-5"}
  teams:   {posts_por_5min: 20, menções_por_card: 20, card_kb_max: 28}
```

## 3. Onde guardar o limite: SSM × AppConfig × S3

| Critério | **SSM Parameter Store (standard)** | **AWS AppConfig** | S3 (JSON versionado) |
|---|---|---|---|
| Custo | grátis (≤ 4 KB; 8 KB em *advanced* US$ 0,05/mês) | US$ 0,0008/config recebida (+ requisições); extensão Lambda faz *poll* a cada 45 s mas só "recebe" quando muda | centavos |
| Editar no console | sim (texto) | sim, com **validador** (JSON Schema ou Lambda) | não é UX de edição |
| Rollout/rollback | não | **estratégias de implantação** (gradual, *bake time*, rollback automático por alarme CloudWatch), *feature flags* | versões do objeto |
| Leitura do Step Functions | `aws-sdk:ssm:getParameter` = **1 transição** | `startConfigurationSession` + `getLatestConfiguration` = 2 transições (ou via Lambda) | `aws-sdk:s3:getObject` = 1 transição |
| Leitura da Lambda | SDK + cache em memória | extensão AppConfig (cache local, sem código de polling) | SDK + cache |
| Risco | edição no console gera *drift* com o repo | mais uma peça gerenciada; conceito de *environment/profile* | sem validação |

**Decisão padrão (P1 > P3):** arquivo no repo → **SSM** na POC; regra de ouro "o console é somente leitura, a fonte é o repo". Suba para **AppConfig** quando precisar de *feature flag*, validação de schema no deploy ou rollout gradual com rollback — não antes.

## 4. Fazer cumprir em três camadas

**Estática — a IaC lê o mesmo arquivo.** *Reserved concurrency* por Lambda (teto duro de execuções paralelas), *throttling* por rota na HTTP API (`rate`/`burst`), `MaxConcurrency` em `Map`, cadência no EventBridge Scheduler, `timeout`/memória, `max_tokens` por chamada, capacidade provisionada no DynamoDB. Sem isso, nenhuma guarda dinâmica salva de um laço descontrolado.

**Dinâmica — contador mensal no DynamoDB.** Um item por métrica e mês (`CONTADOR#<aaaa-mm>#<metrica>`, `ADD valor :n`, TTL 13 meses). Cada execução **estima** o que vai consumir (transições = constante da máquina + itens × estados por item; tokens = `usage` da resposta do modelo) e incrementa. A guarda no início da máquina:

```json
"LerLimites": { "Type": "Task", "Resource": "arn:aws:states:::aws-sdk:ssm:getParameter",
  "Arguments": { "Name": "/agente/limites" },
  "Assign": { "limites": "{% $parse($states.result.Parameter.Value) %}" }, "Next": "LerContador" },
"LerContador": { "Type": "Task", "Resource": "arn:aws:states:::dynamodb:getItem",
  "Arguments": { "TableName": "aid-execucoes", "Key": { "pk": {"S": "SQUAD#x"}, "sk": {"S": "{% 'CONTADOR#' & $substring($now(),0,7) & '#transicoes' %}"} } },
  "Assign": { "usadas": "{% $exists($states.result.Item) ? $number($states.result.Item.valor.N) : 0 %}" }, "Next": "Guarda" },
"Guarda": { "Type": "Choice",
  "Choices": [ { "Condition": "{% $usadas >= $limites.free_tier.stepfunctions.transicoes_mes * $limites.limiares.bloqueio %}", "Next": "BloqueadoPorOrcamento" } ],
  "Default": "Trabalho" }
```
A guarda custa **3 transições por execução** — entra no orçamento. Entre *aviso* e *bloqueio*, degrade (reduza cadência, pule a execução completa, troque para o modelo mais barato) em vez de parar.

**Externa — AWS Budgets como rede de segurança.** Um orçamento de **uso** (ex.: `StateTransition` ≥ 3.800, `Lambda-GB-Second`) e um de **custo** (≥ US$ 5) — os dois primeiros com ação são grátis. Ação: **anexar uma política IAM `Deny` às roles de execução** (Lambda/Step Functions) = kill switch sem código, reversível ao desanexar; alertas em 70/85/95 % por SNS/e-mail; os alertas automáticos do Free Tier (85 %) chegam por e-mail sem configuração.

## 5. Step Functions: gastar menos transições por desenho

- **JSONata + Variables** (desde 22/11/2024): `QueryLanguage: JSONata` no topo; `Arguments`/`Output`/`Assign` substituem `Parameters`/`ResultSelector`/`ResultPath`; estados `Pass` só para "carregar dado adiante" **somem** (cada `Pass` é 1 transição). Funções `$hash`, `$uuid`, `$parse`, `$partition`, `$range`; `States.Hash` existe **só** em estados JSONPath. Variables funcionam também em JSONPath, para migração incremental.
- **Integração direta em vez de Lambda:** `dynamodb:getItem/putItem`, `s3:getObject`, `ssm:getParameter`, `bedrock:invokeModel`, `http:invoke` (API de terceiros com EventBridge Connection) — 1 transição, zero cold start, zero código.
- **Lote dentro da Lambda:** `BatchWriteItem` na função, nunca `putItem` por item dentro de `Map`.
- **Incremental antes de completo:** processe só o que mudou (`pushed_at`, versão, ETag); a varredura completa roda numa cadência menor.
- **Fórmula de orçamento:** `transições ≈ Σ execuções × (estados fixos + itens × estados por item)`. Ex.: coletador diário com 5 repos novos × 6 estados + 7 fixos ≈ 37/dia ≈ 1.100/mês.
- **Standard × Express:** abaixo de 4.000 transições/mês Standard é grátis e guarda 90 dias de histórico; Express cobra por requisição + duração e não tem free tier — só compensa em alto volume de execuções curtas.

## 6. Checklist do guardião
- [ ] `config/limites.yaml` versionado; schema validado no CI; console marcado "somente leitura".
- [ ] IaC, Lambdas, Step Functions e Budgets leem **o mesmo** parâmetro — nenhum número copiado à mão.
- [ ] Contador mensal por métrica com `ADD` atômico e TTL; guarda no início de cada máquina; degradação antes do bloqueio.
- [ ] Dois orçamentos com ação (uso + custo) e política `Deny` pronta; alertas em 70/85/95 %.
- [ ] Tags `projeto`/`ambiente` em tudo (Cost Explorer por tag é a prova).
- [ ] Transições por execução calculadas e registradas no plano; revisão mensal com o número real do Cost Explorer.

## Fontes (consultadas em 12/10/2026)
- AWS Step Functions — Pricing (4.000 transições Standard não expiram; Express por requisição + duração): https://aws.amazon.com/step-functions/pricing/
- AWS Systems Manager — Pricing (AppConfig US$ 0,0008/config recebida; Parameter Store standard sem custo): https://aws.amazon.com/systems-manager/pricing/
- AWS Budgets — Pricing (2 orçamentos com ação grátis; US$ 0,10/dia depois): https://aws.amazon.com/aws-cost-management/aws-budgets/pricing/
- AWS Free Tier FAQs e novo plano Free (07/2025): https://aws.amazon.com/free/faqs/ · https://aws.amazon.com/about-aws/whats-new/2025/07/aws-free-tier-credits-month-free-plan/
- Step Functions JSONata e Variables — guia prático (introdução em 22/11/2024; `$hash`, `$uuid`, `Assign`): https://hidekazu-konishi.com/entry/aws_step_functions_jsonata_and_variables_guide.html · doc oficial *Transforming data*: https://docs.aws.amazon.com/step-functions/latest/dg/transforming-data.html
- Preços de modelos (Nova Micro/Lite, Claude Haiku 4.5): https://cloudprice.net/models/aws/nova-micro · https://anotherwrapper.com/tools/llm-pricing/claude-haiku-45/amazon-nova-lite (confirmar em https://aws.amazon.com/bedrock/pricing/)
