# API Gateway na frente de Lambda Java — decisão, autorização e armadilhas

A skill gera `Events: HttpApi` por padrão (ver `sam-template.md`). Este guia diz **quando
essa escolha é certa, quando migrar para REST API** e quais armadilhas de gateway aparecem
como "bug do handler". Os números abaixo são cotas **padrão e ajustáveis** segundo a fonte;
confirme na página oficial de cotas antes de usá-los em dimensionamento.

## Índice

1. [HTTP API ou REST API?](#http-api-ou-rest-api)
2. [Autorização: árvore de decisão](#autorização-árvore-de-decisão)
3. [Authorizer em Lambda Java](#authorizer-em-lambda-java)
4. [Timeouts e operações longas](#timeouts-e-operações-longas)
5. [Throttling e cache](#throttling-e-cache)
6. [Observabilidade e custo de log](#observabilidade-e-custo-de-log)
7. [Armadilhas que parecem bug do handler](#armadilhas-que-parecem-bug-do-handler)
8. [Checklist de revisão](#checklist-de-revisão)

## HTTP API ou REST API?

HTTP API é um proxy barato e rápido (fonte: ~70% mais barato). REST API é a plataforma de
gestão de API completa. Escolha pelo que o contrato exige, não por hábito.

| Preciso de… | HTTP API | REST API |
|---|---|---|
| Menor custo e latência para CRUD → Lambda | sim | não necessário |
| Plano de uso / chave de API / cota por consumidor | não | sim |
| Validação de request pelo gateway (JSON Schema) | não | sim |
| Cache de resposta no gateway | não | sim |
| WAF direto no gateway, resource policy, endpoint privado | não (WAF via CloudFront) | sim |
| Canary de deployment, X-Ray no gateway, execution log | não | sim |
| JWT/OIDC nativo | sim (JWT authorizer) | não (use Cognito authorizer ou Lambda authorizer) |
| Timeout de integração além de 30 s | não (limite fixo) | sim, até 300 s em Regional/Privado, mediante cota |

Regra prática: **comece em HTTP API** (default da skill). Migre para REST API quando surgir
**um** requisito da coluna da direita que não dê para cobrir fora do gateway. Para WAF, cache
de borda ou edge compute com HTTP API, ponha um CloudFront próprio na frente (use endpoint
Regional; o "edge-optimized" só otimiza TCP e **não** faz cache na borda).

WebSocket é outro produto: mensagem de até 128 KB, autorização só no `$connect`, sem
mTLS nativo. Não entra neste guia.

## Autorização: árvore de decisão

1. Consumidor é serviço/recurso AWS → **IAM (SigV4)**. A assinatura é por região: em
   multirregião com failover, o cliente assinado para uma região falha na outra (SigV4a
   não é suportado). Nesse caso prefira JWT ou Lambda authorizer.
2. App de navegador/mobile com IdP OIDC (Cognito, Auth0, Okta…) → **HTTP API: JWT
   authorizer**. Em REST API: Cognito authorizer, ou Lambda authorizer validando o JWT.
3. Máquina-a-máquina → OAuth2 *client credentials* com JWT authorizer; se exigir certificado
   de cliente, **mTLS** (só domínio customizado Regional; truststore PEM em S3 da mesma região).
4. Lógica própria (token opaco, ES256, regras por tenant) → **Lambda authorizer**.

Detalhes do **JWT authorizer** (HTTP API) que mordem em produção:

- Valida `iss`, `aud`/`client_id`, `exp`, `nbf`, `iat` e escopos da rota; só **RSA**
  (RS256/384/512). Token assinado com ECDSA ou token **opaco** não funciona → Lambda authorizer.
- O resultado da validação **não é cacheado**; só as chaves públicas (JWKS) ficam em cache por
  ~2 h. Planeje a **rotação de chaves** com essa janela.
- Prefira *access token* com escopos; ID token só serve quando a rota não declara escopos.
- Revogação **não é consultada**: token revogado no IdP vale até o `exp`. Para logout forte,
  use TTL curto ou checagem no backend.
- Com mTLS, **desligue o endpoint padrão** (`DisableExecuteApiEndpoint`); senão o cliente
  contorna o certificado chamando a URL `execute-api` direta. O gateway também não consulta CRL.

Resource policy (REST): na mesma conta com IAM/Lambda authorizer a avaliação é OR; com
Cognito é AND; entre contas é AND (política silenciosa = negado). `Deny` explícito sempre
vence. **Reimplante** a API depois de mudar a política.

## Authorizer em Lambda Java

Se o authorizer for uma Lambda da própria stack (nativa ou SnapStart), valem regras extras:

- **HTTP API**: aceita resposta *simples* (`isAuthorized` + `context`), bem mais enxuta que
  um documento IAM. Cache vem **desligado** (TTL 0); ao ligar, inclua a rota
  (`$context.routeKey`) nas fontes de identidade para não reutilizar a decisão entre rotas.
  Timeout máximo do authorizer: 10 s.
- **REST API**: cache padrão de 300 s (máx. 3600 s). Se a política devolvida cobre só o
  recurso da primeira chamada, as chamadas seguintes a **outros caminhos** serão negadas pelo
  cache — gere a política para o conjunto da API (curinga) quando ligar o cache.
- REST: sem `principalId` na resposta, ou política acima de ~8 KB, ou resposta malformada
  resulta em **500**, não em 401/403 — sintoma clássico de confusão no debug.
- REST tipo TOKEN: sem o cabeçalho de identidade o gateway devolve 401 **sem invocar** a
  Lambda; ela nunca chega a tratar token ausente.
- Cold start do authorizer soma na latência de **toda** requisição não cacheada. Trate-o como
  caminho crítico: mesmo runtime nativo/SnapStart da API, memória generosa, sem I/O na inicialização.
- O authorizer pode propagar identidade ao handler pelo `context` (ex.: tenant, subject);
  leia-o no handler em vez de reparsear o token.

## Timeouts e operações longas

- REST: 29 s por padrão (50 ms–29 s); aumentável até 300 s só em Regional/Privado.
- HTTP API: **30 s fixos**; estouro volta como 504 com corpo `Service Unavailable`.
- Em ambos, o **cliente recebe 504 mas a Lambda continua executando**. Resultado: trabalho
  duplicado se o cliente repetir. Torne a operação **idempotente** (ver Powertools
  idempotency em `lambda-powertools-java.md`).
- Para trabalho acima de poucos segundos, não estique timeout: responda `202 Accepted`,
  enfileire (SQS/EventBridge) e entregue o resultado por polling ou callback. Para
  fluxos longos com estado, considere Step Functions ou Durable Functions (ver
  `arquiteto-cloud-aws`).
- Defina o `Timeout` da Lambda **menor** que o do gateway para o erro vir do seu código
  (com log), e não do gateway.

## Throttling e cache

- Limite de conta padrão: 10.000 req/s com *burst* de 5.000 (balde de fichas); é *best effort*,
  picos breves acima podem passar. Acima do limite o cliente recebe **429**: exija *retry*
  com backoff exponencial e *jitter* nos clientes.
- REST: limites por estágio/método e por consumidor via plano de uso (a taxa do plano vale
  **por chave**: 100 req/s com 10 chaves = 100 por chave). Não associe a mesma chave a dois
  planos do mesmo estágio (a escolha é não determinística).
- HTTP API: só limite por rota; **sem limite por consumidor**. Se precisar, implemente no
  authorizer ou no backend.
- Cache (só REST): TTL padrão 300 s, máx. 3600 s, resposta de até 1 MB, só GET por padrão.
  É cobrado por hora mesmo vazio — ligue só com caso de uso claro e **inclua a identidade do
  cliente na chave** para não vazar dados entre usuários.
- O gateway escala sozinho; o gargalo vira a **concorrência da Lambda** e a capacidade do
  DynamoDB. Dimensione a pilha inteira, não só o gateway.

## Observabilidade e custo de log

- Sempre habilite **access log** (JSON) no estágio, com `requestId`, rota, status, latência
  de integração e erro do authorizer.
- HTTP API **não tem execution log**; REST e WebSocket têm. Em produção use nível `ERROR`:
  o nível `INFO` gera dezenas de eventos por requisição e o custo de CloudWatch Logs pode
  superar o de Lambda + gateway somados. Evento de execution log é truncado em 1.024 bytes.
- Correlacione com o handler: grave o `requestId` do gateway no log estruturado da Lambda
  (campo do contexto do evento v2) para cruzar nos Logs Insights.
- X-Ray no gateway só em REST; em HTTP API o rastreio começa na Lambda.
- Alarmes mínimos: 5xx, 4xx anômalo (401/403 em alta = autenticação quebrada), `Latency`
  versus `IntegrationLatency` (a diferença é overhead do gateway/authorizer) e `Count`.

## Armadilhas que parecem bug do handler

| Sintoma | Causa mais comum | Ação |
|---|---|---|
| 502 Bad Gateway | Resposta da Lambda fora do formato de proxy (sem `statusCode`/`body`), ou corpo binário sem *base64* | Devolver o formato do evento da versão do payload; marcar `isBase64Encoded` |
| 500 com stage variables | Falta permissão de invocação (política baseada em recurso) na Lambda | Conceder `lambda:InvokeFunction` ao gateway |
| 403 "Missing Authentication Token" | Nome do estágio na URL com domínio customizado, ou rota inexistente | Remover o estágio do caminho; conferir a rota |
| 401 | Tipo de token errado (ID vs access) ou fonte de identidade ausente | Alinhar token, escopos e `identitySource` |
| 504 | Backend passou do timeout do gateway | Seção de timeouts acima |
| Erro de CORS | Faltam cabeçalhos CORS nas respostas de erro (4XX/5XX) do gateway, não só no handler | Configurar CORS no gateway (HTTP API nativo) ou nas Gateway Responses (REST); 413 é a única resposta que não se customiza |
| 403 vindo da VPC | DNS privado do endpoint de VPC intercepta **todas** as chamadas `execute-api` | Usar domínio customizado para APIs públicas |
| Mudança não surte efeito (REST) | Falta **novo deployment** | Reimplantar o estágio |
| `Authorization` some no backend | O gateway remove/remapeia alguns cabeçalhos (`Authorization` quando assinado/IAM, `Host`, `Content-MD5`) | Não depender deles; repassar por outro cabeçalho |
| Query string cortada | `;` em HTTP API, `\|` e `{}` em REST precisam de URL-encoding | Codificar no cliente |
| Rota `/ping` ou `/sping` não responde | Caminhos reservados | Escolher outro nome |
| `security` ignorado no OpenAPI | Só vale por operação; o nível raiz é ignorado | Declarar em cada operação |
| Automação de deploy tomando 429 | API de gerenciamento limitada (~10 req/s, burst 40) | Serializar/recuar nos pipelines |

Também: proxy `HTTP_PROXY` para fora da VPC cria um **caminho de saída para a internet** que
não aparece nos *flow logs*; restrinja a domínios fixos, nunca monte a URL com entrada do
chamador, e aplique resource policy + access log.

## Checklist de revisão

- [ ] Tipo de API justificado (HTTP por padrão; REST só com requisito da tabela).
- [ ] Autorização escolhida pela árvore; rotas sem authorizer são intencionalmente públicas.
- [ ] Com authorizer cacheado: política cobre a API toda (REST) ou a rota está na chave (HTTP).
- [ ] mTLS ⇒ endpoint `execute-api` padrão desabilitado.
- [ ] `Timeout` da Lambda < timeout do gateway; operações longas viraram assíncronas.
- [ ] Handler idempotente para retry do cliente após 504.
- [ ] Access log ligado; execution log em `ERROR` (REST); retenção de log definida.
- [ ] Clientes tratam 429 com backoff + jitter; concorrência da Lambda e do DynamoDB dimensionada.
- [ ] CORS cobre respostas de erro; corpo binário com `isBase64Encoded`.
- [ ] Cotas citadas aqui foram conferidas na página oficial vigente.

## Procedência

Reescrito em português a partir de `awslabs/agent-plugins`
(`plugins/aws-serverless/skills/api-gateway`, Apache-2.0). Nenhum trecho, código ou
modelo da fonte foi copiado; instruções operacionais embutidas na fonte (framework de IaC
padrão, fluxo de MCP) **não** foram absorvidas. Registro completo em `docs/ATTRIBUTIONS.md`.
