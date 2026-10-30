# Segurança de borda no Amazon API Gateway

> Origem: técnicas reescritas a partir de `awslabs/agent-plugins` (Apache-2.0) — ver `docs/ATTRIBUTIONS.md`.
> Complementa `rate-limiting.md` (CORS/limites) e `api-security-e-supply-chain.md`. Serve de checklist
> de auditoria para APIs REST, HTTP e WebSocket publicadas na AWS.

## 1. Escolha o tipo de API pela superfície de segurança

| Controle | REST | HTTP | WebSocket |
|---|---|---|---|
| Resource policy (IP, VPC endpoint, conta) | sim | **não** | não |
| WAF associado direto ao stage | sim | **não** (usar CloudFront na frente) | não |
| mTLS nativo | sim (domínio custom) | não | não |
| API privada | sim | não | não |

Consequência: exigência de WAF, allowlist por IP ou mTLS em API HTTP/WebSocket obriga uma camada na frente
(CloudFront) ou um Lambda authorizer. Registre isso como decisão arquitetural, não como detalhe de implantação.

## 2. TLS e endpoint padrão

- Piso: TLS 1.2. Prefira as políticas "enhanced" (prefixo `SecurityPolicy_`), que habilitam TLS 1.3 e
  criptografia pós-quântica; o endpoint edge-optimized e o regional/privado usam famílias de política diferentes.
- Migração segura: aplique a política nova no modo de acesso básico, confira nos access logs
  (`$context.tlsVersion`, `$context.cipherSuite`) quem ainda negocia versão antiga e só então passe ao modo
  estrito (que exige SNI coerente com o Host). A propagação do modo estrito leva alguns minutos.
- Com domínio customizado, **desligue o endpoint `execute-api` padrão** (`disableExecuteApiEndpoint`) — senão
  WAF, mTLS e roteamento do domínio podem ser contornados chamando o endereço default. Exige novo deploy
  do stage para valer.

## 3. mTLS

1. Monte a hierarquia de CAs (ACM Private CA ou própria), exporte as raízes/intermediárias num truststore PEM
   e suba para um bucket S3 **versionado** na mesma região.
2. Aponte o domínio customizado para o truststore; o certificado do domínio em si é um certificado público do ACM.
3. Desligue o endpoint padrão.

Pontos de auditoria:
- **O API Gateway não consulta CRL.** Revogação exige Lambda authorizer que compare o serial do certificado do
  cliente com uma lista (ex.: tabela DynamoDB alimentada por evento S3 que valida a assinatura da CRL).
  Se a revogação precisa ser quase imediata, desligue o cache do authorizer; se tolera atraso, use TTL curto
  alinhado a esse atraso.
- Propague a identidade ao backend por mapeamento de header a partir do contexto do authorizer; o backend
  recebe o sujeito do certificado sem repetir a validação.
- API HTTP, WebSocket ou necessidade de modo "opcional" (clientes com e sem certificado) → mTLS no CloudFront
  (trust store + modo required/optional). Ele repassa metadados do certificado em headers (serial, emissor,
  sujeito, validade, impressão SHA-256) e permite checar revogação na própria negociação TLS com funções de
  conexão + KeyValueStore, barrando no edge antes de chegar à origem. Profundidade máxima da cadeia: 4.
- API privada não tem mTLS nativo: coloque um ALB com verificação por trust store (que aceita CRL) à frente
  do VPC endpoint.

## 4. Resource policy (somente REST)

- Padrão de allowlist por IP: um `Allow` amplo seguido de um `Deny` com condição `NotIpAddress` sobre
  `aws:SourceIp`. Tráfego que chega por VPC endpoint usa `aws:VpcSourceIp`, não `aws:SourceIp`.
- Restrição a um VPC endpoint específico: condição `StringEquals` em `aws:SourceVpce`.
- O atalho `execute-api:/*` só vale dentro de resource policy do API Gateway; nunca em política IAM de identidade.
- API HTTP não tem resource policy: o equivalente é Lambda authorizer comparando o IP de origem da requisição
  com a lista (aceite IPs e CIDRs).

## 5. WAF

- REST: associe o Web ACL ao stage. HTTP: WAF só via CloudFront (padrão comum de produção).
- Valor de segurança extra: sem WAF, tráfego de ataque dispara o Lambda authorizer a cada requisição
  ("denial of wallet"); com WAF, o lixo é barrado antes do authorizer.
- Limites de inspeção: corpo ~16 KB por padrão no regional (ajustável até 64 KB, com custo); cabeçalhos até 8 KB
  ou 200 itens. Payloads maiores passam sem inspeção do trecho excedente — considere na análise de risco.
- Conjunto base sugerido (sempre): regras comuns (XSS, LFI/RFI, SSRF, traversal), entradas sabidamente más
  (Log4j, desserialização Java), SQLi e reputação de IP. A regra comum bloqueia corpo acima de ~8 KB:
  se a API aceita payload maior, coloque essa regra específica em Count em vez de desativar o grupo.
- Conjunto situacional: lista de IPs anônimos (Tor/VPN/hosting), Bot Control (comum x direcionado, custos
  por milhão de requisições diferentes; a categoria de bots de IA bloqueia verificados e não verificados —
  use rótulos para distinguir), proteção de rotas administrativas, prevenção de account takeover em login.
- Operação: comece em **Count**, analise métricas/logs, só então Block; sobrescreva a regra que gera falso
  positivo, não o grupo inteiro; use rótulos para lógica customizada; aplique grupos caros só em URIs
  específicas (scope-down). A capacidade padrão de 1.500 WCU por ACL é facilmente estourada pelo conjunto base
  mais extras — planeje o orçamento.
- Rate-based do WAF (na borda, por IP) e throttling do API Gateway (no serviço) se complementam.
- Atrás de CloudFront, o Host reescrito quebra tokens de challenge/CAPTCHA: inclua o domínio do CloudFront na
  lista de domínios de token do Web ACL da origem e encaminhe o cookie do token.
- Resposta de bloqueio aparece como gateway response `WAF_FILTERED` (403); variáveis `$context.waf.*` entram
  no access log para correlação.

## 6. CORS: o erro clássico é esquecer as respostas de erro

- REST: preflight por método OPTIONS com integração mock; a Lambda (proxy) também precisa devolver os headers
  CORS. Adicione-os às gateway responses `DEFAULT_4XX` e `DEFAULT_5XX`, ou o navegador esconde 403/5xx.
  A propriedade `Cors` do SAM não cobre gateway responses. Retire o authorizer do preflight.
- A integração mock aceita uma única origem. Para várias, devolva dinamicamente a partir de uma **allowlist
  explícita**; refletir o header `Origin` sem validar equivale a `*` e ainda funciona com credenciais — 🔴 em auditoria.
- HTTP API: configuração nativa de CORS; `*` em origens é incompatível com credenciais.
- API privada: evite o header customizado de id da API (dispara preflight que falha); use o Host.

## 7. Autenticação por cookie HttpOnly

Contra roubo de token por XSS: callback OAuth2 troca o código e devolve o token em `Set-Cookie` com
`HttpOnly`, `Secure` e `SameSite=Lax`; um Lambda authorizer lê o cookie (identity source de header `cookie`),
valida o JWT e autoriza. Crie o verificador de JWT fora do handler para reaproveitar o cache de JWKS em
execuções quentes. Combine com proteção CSRF, já que o cookie viaja sozinho.

## 8. Higiene do plano de dados e do plano de controle

- Segurança vale também para quem **altera** a API (deploy, stage, authorizer), não só para quem a chama:
  restrinja IAM de gerenciamento e audite mudanças.
- Cache (REST): **não vem criptografado por padrão** e a criptografia só se define na criação do cache.
  O cache **não isola por cliente**: sem um parâmetro identificador (ex.: header de chave de API) na chave de
  cache, um cliente pode receber resposta gerada para outro. Para dados sensíveis, criptografe e inclua o
  identificador na chave.
- Logs: o execution log redige headers de autorização e chaves; já o *data tracing* grava corpos completos,
  com PII e credenciais — não habilite em produção. Trate os log groups como dados sensíveis (IAM, retenção,
  data protection policies do CloudWatch Logs).
- Tipos binários: registre tipos explícitos; evite `*/*`. Uploads grandes vão por URL pré-assinada do S3
  (o limite de payload do API Gateway é 10 MB).
- Entenda o modelo: o serviço é multi-tenant fora da sua VPC; VPC Link é a ponte para recursos privados.

## Checklist de auditoria (severidade sugerida)

- 🔴 Endpoint `execute-api` padrão ativo em API que depende de WAF/mTLS/domínio custom.
- 🔴 CORS refletindo `Origin` sem allowlist, ou `*` com credenciais.
- 🔴 Data tracing ligado em produção em API com PII/credenciais.
- 🟡 Revogação de certificado cliente sem mecanismo (mTLS sem CRL via authorizer/CloudFront).
- 🟡 Cache de REST sem criptografia ou sem identificador de cliente na chave.
- 🟡 API HTTP "protegida por WAF" sem CloudFront na frente (WAF inexistente na prática).
- 🟡 Política TLS abaixo de 1.2; Web ACL direto em Block sem fase de Count.
- 🔵 Headers CORS ausentes nas gateway responses 4XX/5XX.
