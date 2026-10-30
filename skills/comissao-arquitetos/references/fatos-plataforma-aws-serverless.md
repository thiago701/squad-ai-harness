# Fatos de plataforma verificados — AWS serverless low-code + JEV (out/2026)

> Conhecimento absorvido no caso *Consolidador de Treinamentos*. Verificado pelo especialista B na
> documentação oficial e na AWS Price List Bulk API (preços de **ap-northeast-1**, publicações
> set–out/2026) e corrigido pelo revisor independente. Preços mudam: reconfirmar antes de prometer.
> Coluna "Errado na 1ª versão" = o que a comissão ou o motor assumiram errado e foi corrigido.

## Step Functions
| Fato | Fonte | Errado na 1ª versão? |
|---|---|---|
| **Standard**: 4.000 transições/mês grátis "indefinitely"; depois US$0,000025/transição | aws.amazon.com/step-functions/pricing | — |
| **Express não tem free tier**: US$1,00/M req + US$0,00001667/GB-s; máx. 5 min; sync = at-most-once | idem + concepts-standard-vs-express | — |
| `StartSyncExecution` só em Express; devolve `executionArn, status, output (string JSON), error, cause, input, billingDetails`; **HTTP 200 mesmo com `status: FAILED`**; ecoa o `input` (cuidado com segredo) | API_StartSyncExecution | parcial (eco do input só visto na R2) |
| JSONata (`QueryLanguage`) e **variáveis** valem para Standard e Express; 256 KiB por variável | transforming-data, workflow-variables | — |
| Funções JSONata próprias do SFN: **`$hash(src, alg)`** (MD5/SHA-1/SHA-256/384/512), `$partition`, `$range`, `$random`, `$uuid`, `$parse` (substitui `$eval`) | transforming-data | **sim** — B afirmou "JSONata não tem hash"; corrigido na R3 |
| Integrações SDK incluem `dynamodb`, `secretsmanager`, `ssm`, `s3` (IAM não é gerado automaticamente) | supported-services-awssdk | — |
| **`TestState`** testa Task/Pass/Choice/Wait/Succeed/Fail com integração real (`roleArn`, `variables`); **não executa `Map`/`Parallel`** | API_TestState | **sim** — invariante "todo estado testável" precisou de exceção |
| Entrada/saída por estado ≤ 256 KiB → saída de `Map` inline com muitos itens estoura: limite o `Output` por iteração | service-quotas | **sim** — lote de 500 → 300 → 100 |
| HTTP Task: EventBridge Connection + `states:InvokeHTTPEndpoint`, `events:RetrieveConnectionCredentials`, `secretsmanager:GetSecretValue/DescribeSecret`; timeout 60 s; segredo `events!connection/*` gerido pelo serviço | connect-third-party-apis | — |

## API Gateway
| Fato | Fonte | Errado? |
|---|---|---|
| **HTTP API** tem subtipo nativo `StepFunctions-StartSyncExecution` (`StateMachineArn`, `Input`…); **não** tem subtipo DynamoDB; não transforma body (devolve o envelope) | http-api-develop-integrations-aws-services-reference | — |
| **Timeout de integração do HTTP API = 30 s fixo** (REST 29 s, ampliável). Workflow síncrono atrás dele precisa de `TimeoutSeconds ≤ 28` | http-api-quotas | **sim — 🔴 só o revisor independente pegou** (SF admin estava com 290 s) |
| Tóquio: HTTP US$1,29/M; REST US$4,25/M; free 1M/mês só 12 meses em conta legada | Price List | — |
| API keys/usage plans/VTL/request validator/cache/WAF são **só REST**; HTTP tem JWT authorizer | http-api-vs-rest | — |
| Integração direta **API GW → DynamoDB só existe no REST com VTL** | idem | (pergunta do usuário — virou ADR "Rejeitado") |
| Mapear `${request.header.x}` + `${request.querystring.y}` compostos num JSON de `Input`: **não documentado** para o subtipo SFN → spike; fallback documentado: CloudFront Function monta `q=<JSON>` e `Input: $request.querystring.q` | http-api-parameter-mapping | — |

## DynamoDB
| Fato | Fonte |
|---|---|
| Always free = **25 RCU + 25 WCU provisionadas + 25 GB, por conta (todas as tabelas/regiões)**; **on-demand é cobrado desde a 1ª unidade** | dynamodb/pricing + Price List |
| `Scan` com filtro consome RCU pelo total **varrido**; 1 MB por página (`LastEvaluatedKey`); burst capacity é best-effort (300 s) | Scan, burst-adaptive |
| TTL é preguiçoso (até ~48 h): filtrar `expiraEm > now` na leitura | TTL docs |

## CloudFront
| Fato | Fonte | Errado? |
|---|---|---|
| Pay-as-you-go: **1 TB + 10M req + 2M CloudFront Functions + 2M leituras de KVS, always free**; plano flat-rate "Free" é pior (100 GB/1M) | cloudfront/pricing | — |
| API GW como origem: `AllViewerExceptHostHeader` (Host quebra) + `CachingDisabled`; `Authorization` é removido em GET/HEAD | managed policies, re:Post | — |
| **`CachingDisabled` não repassa query string sem origin request policy** → com cache, o dashboard de A seria servido a B | idem | **sim** — 🔴 de privacidade levantado por Segurança na R2 |
| Response headers policy **gerenciada não inclui CSP** → policy custom | managed response headers | **sim** |
| CloudFront Functions suportam KVS e `crypto` (SHA-256/HMAC) e podem responder 401/403/200 → Auth individual por usuário + sessão HMAC `__Host-` gratuito | CF Functions runtime | — |
| **Limite rígido de código da CloudFront Function = 10.240 bytes** (CRLF no Windows estoura o limite; exigir LF e `len(bytes) + 64 < 10240`) | CF quotas (`LL-0027`) | **sim** — descoberto no deploy de Sandbox |
| **Default Cache Behavior (`GET/HEAD/OPTIONS`) bloqueia `POST` com `403`** antes da CloudFront Function rodar → rotas virtuais `/auth/*` na borda precisam usar `GET` + guarda CSRF (`Sec-Fetch-Site` + `X-Requested-With`) | CF cache behavior (`LL-0027`) | **sim** — descoberto no fluxo de troca de senha |
| **JSONata `$now()` no Step Functions retorna UTC (`Z`)** → às 21h BRT avança 1 dia; usar `$now('[Y0001]-[M01]-[D01]', '-0300')` e `$fromMillis(..., '-0300')` | SFN JSONata (`LL-0025`) | **sim** — descoberto em produção após 21h BRT |

## Secrets Manager, Budgets, Free Tier
| Fato | Fonte | Errado? |
|---|---|---|
| US$0,40/segredo/mês + US$0,05/10k chamadas; **30 dias grátis por segredo novo** (revisor) — B não achou o trial na página em out/2026: confirmar na fatura | secrets-manager/pricing | conflito de fontes |
| Budgets sem ação grátis; **2 primeiros budgets com ação grátis** → kill switch "anexar Deny" sem Lambda | aws-budgets/pricing | — |
| Free tier 2025: conta criada **antes de 15/07/2025** = legado (12 meses + always free); conta nova = Free plan (**fecha em 6 meses/US$200**) ou Paid plan; checar em Billing → Free Tier | blog AWS 15/07/2025, FAQs | — |
| Latência sa-east-1 ↔ ap-northeast-1 ≈ 260 ms RTT (não oficial) → consulta p50 ≈ 0,5 s / p95 ≈ 1,2 s via CloudFront | economize.cloud | — |

## JEV (TypeSafe "System One")
| Fato | Fonte |
|---|---|
| Decisão tipada (`choice` ≤ 255 opções, `score` ≤ 10, `noul`); **não gera texto; só texto (não lê PDF/imagem)**; pesos fechados (**não treinável pelo usuário**) | squad-ai-harness `docs/propostas/jev-quality-delivery/02-modelos-jev.md` |
| ≈ US$0,07/1.000 decisões; p50 ~250 ms; **ECE 0,246 (calibração ruim)**, 13 % de flips com permutação de opções | idem |
| Uso correto: triagem gated por confiança no **resíduo** que o determinístico não resolve, com gold set e gate anti-regressão; **nunca juiz final**; empate com difflib → difflib | idem + ADR-08 do caso |
| "Classificar se há treinamento em aberto" é **fato determinístico** (exigidos − evidências): não usar modelo probabilístico | ADR-08 do caso |

## Padrão "low-code" serverless que funcionou
`CloudFront Function + KVS (auth individual + sessão HMAC + RBAC) → HTTP API → Step Functions Express (integrações SDK + JSONata com timezone -0300) → DynamoDB + Read Models S3 (0 RCU)`, com **0 Lambda**, invariantes estáticos (`Inv.1..12`), baterias comportamentais (`Q1..Q5` incluindo execução local de CF Function em `node vm`), fragments JSONata via `templatefile`, `TestState` como teste unitário e `StartSyncExecution` real como e2e. Detalhamento completo em `../arquiteto-cloud-aws/references/serverless-lowcode-sfn-cloudfront-kvs.md`.
