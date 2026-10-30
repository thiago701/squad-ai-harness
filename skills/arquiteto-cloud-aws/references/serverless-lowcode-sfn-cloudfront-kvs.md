# Arquitetura Serverless Low-Code (`0 Lambda`): Step Functions Express + JSONata + CloudFront Functions + KVS + Read Model S3

> **Origem:** validado em produção/sandbox no projeto *Consolidador de Treinamentos* (out/2026, `ap-northeast-1`, custo mensal real ≤ US$ 0,60/conta).
> **Vínculos:** `LL-0023`, `LL-0025`, `LL-0027`, `LL-0030`, `LL-0036..0043` · `instinto-0013`, `instinto-0015`, `instinto-0019`.

---

## 1. Quando adotar o padrão Serverless Low-Code (`0 Lambda`)

Para dashboards corporativos internos, portais de consulta/consolidação e APIs de escrita moderada (< 100k req/mês), **não é necessário provisionar funções Lambda, containers nem Cognito**:

```
Browser → CloudFront (Edge Auth: CloudFront Function + KVS)
           ├─ /*                     → S3 (SPA estática + Read Models JSON via OAC)
           ├─ /auth/* (GET virtual)  → CloudFront Function (login, sessão HMAC, troca de senha)
           ├─ /api/consulta          → API Gateway HTTP API → Step Functions Express (leitura: 2 Queries DynamoDB)
           ├─ /api/admin/*           → API Gateway HTTP API → Step Functions Express (escrita: Secrets Manager + DynamoDB + S3)
           └─ /integracao/auditoria-360 → API Gateway HTTP API → Step Functions Express (Secrets Manager + DynamoDB + S3 < 256 KB)
```

| Componente | Custo Mensal (Free Tier Permanente / Pay-as-you-go) | Papel |
|---|---|---|
| **CloudFront + CloudFront Functions + KVS** | **US$ 0,00** (1 TB egress + 10M req + 2M CF Functions + 2M leituras KVS grátis/mês) | CDN, Auth individual por colaborador, RBAC na borda, headers de segurança (CSP A+) |
| **DynamoDB Provisioned (10 RCU / 10 WCU)** | **US$ 0,00** (Always Free até 25 RCU / 25 WCU por conta) | Single-table design (`COLAB#<id>`, `CICLO#<ano>`, `CATALOGO`) + tabela de auditoria 360° |
| **Step Functions Express + JSONata** | **~US$ 0,05** (US$ 1,00/M execuções + duração em GB-s) | Orquestração síncrona via `StartSyncExecution` e transformação JSONata sem Lambda |
| **API Gateway HTTP API** | **~US$ 0,02** (US$ 1,29/M em Tóquio) | Integração nativa `StepFunctions-StartSyncExecution` |
| **S3 Standard (< 50 MB)** | **~US$ 0,01** (US$ 0,025/GB-mês após 12 meses) | Assets da SPA, Read Models JSON (`0 RCU`), Cache Espelho filtrado e Datasets 360° |
| **Secrets Manager (1–2 segredos)** | **US$ 0,40** | `apiKey` administrativa e chaves por sistema consumidor |

**Gatilho objetivo para introduzir a 1ª Lambda:** somente quando um estado exigir `> 60 linhas` de JSONata ou algoritmo não suportado nativamente (ex.: distância de edição/fuzzy matching em tempo de execução, parsing binário de PDF no backend).

---

## 2. Armadilhas Reais do Step Functions Express + JSONata (e como blindar)

### 2.1. Fuso horário UTC em `$now()` e `$fromMillis()` (`LL-0025`)
- **O problema:** no Step Functions, `$now()` retorna ISO-8601 em **UTC** (`Z`). Às 21h05 BRT (`00:05Z` do dia seguinte), `$substring($now(), 0, 10)` avança 1 dia e classifica certificados emitidos hoje no Brasil como *"data futura"*.
- **A regra:** sempre especificar picture e timezone explícito na expressão JSONata:
  ```jsonata
  $now('[Y0001]-[M01]-[D01]', '-0300')
  $fromMillis($toMillis($states.input.dataConclusao), '[Y0001]-[M01]-[D01]', '-0300')
  ```

### 2.2. Timeout fixo de 30 s do HTTP API vs `TimeoutSeconds` da State Machine (`LL-0023`)
- O API Gateway HTTP API corta qualquer integração em **30 segundos fixos**.
- Toda State Machine Express acionada sincronamente via HTTP API DEVE declarar `"TimeoutSeconds": 28` (ou menor) e limitar o tamanho de lotes (`maxItems: 100`).

### 2.3. Limite de 256 KiB no `Output` de `Map` Inline (`LL-0025`)
- Um estado `Map` inline acumula um array com o `Output` de cada iteração. Se cada iteração devolver o objeto completo, lotes de 100 itens estouram 256 KiB (`States.DataLimitExceeded`).
- **A regra:** o `Output` final de cada iteração do `Map` deve projetar apenas `{ "status": ..., "sk": ..., "metodo": ... }`.

### 2.4. `StartSyncExecution` devolve HTTP 200 em falha e ecoa `input` (`LL-0025`)
- A chamada `StepFunctions-StartSyncExecution` retorna HTTP `200 OK` mesmo quando a execução falha (`status: "FAILED"`), e o envelope bruto inclui o campo `"input"` enviado.
- **As regras:**
  1. Nunca passar segredos brutos se o envelope sem filtro for exposto, ou sanitizar na borda;
  2. O cliente (`app.js` / scripts) deve inspecionar `envelope.status === "SUCCEEDED"` antes de fazer `JSON.parse(envelope.output)`.

### 2.5. Itens gêmeos (`EVID#` vs `REVISAO#`) na mesma partição single-table (`LL-0025`)
- Quando itens definitivos (`SK = EVID#<curso>#<hash>`) e pendentes de revisão (`SK = REVISAO#<hash>`, `tipo = "REVISAO"`) compartilham `PK = CICLO#<ano>`, uma query por `PK` traz ambos.
- **A regra:** a query de leitura consolidada deve filtrar `FilterExpression: "tipo <> :tipoRev"` (ou usar prefixo de `SK` quando aplicável).

### 2.6. Exceção do `TestState` para `Map` e `Parallel`
- A API `states:TestState` valida estados individuais (`Task`, `Pass`, `Choice`, `Succeed`, `Fail`), mas **não executa estados `Map` ou `Parallel`**. Teste o interior do `Map` por estado e valide o fluxo completo com `StartSyncExecution` (`test-e2e`).

### 2.7. Gramática JSONata no AWS Step Functions: Proibido Operador Unário `!` (`LL-0043` / `LL-31`)
- **O problema:** diferente do JavaScript, o motor JSONata embarcado no AWS Step Functions **rejeita o operador unário `!`** (ex.: `!$exists($x)` ou `!($a = $b)`) com erro em tempo de execução `QueryEvaluationError: Unexpected operator '!'`.
- **A regra:** use **exclusivamente a função nativa `$not(...)`** para qualquer negação booleana em fragmentos `.jsonata` ou expressões inline `{% ... %}`:
  ```jsonata
  $not($exists($cfg)) or $cfg.ativo != true
  ```
- **Guarda estática (`Inv.3`):** proibir via regex `(?<![=!<>])!\s*(?:\$[A-Za-z_]|exists\b|\()` em `statemachines/fragments/*.jsonata`.

---

## 3. Autenticação Individual e RBAC na Borda com CloudFront Functions + KVS (`LL-0027`)

Quando Cognito é pesado demais para o caso de uso (ex.: login por matrícula/funcional corporativa com senha inicial = funcional e troca de senha no próprio portal), use **CloudFront Functions (`cloudfront-js-2.0`) + KeyValueStore (KVS)**:

### 3.1. Esquema de Chaves no KVS e Sessão Stateless
- **`u:<funcional>`** → `"<sha256_hex(funcional + ':' + senha)>|<colabId>"`
- **`session_secret`** → segredo aleatório de 256 bits para assinar o cookie HMAC-SHA256
- **`auth_verifier`** → fallback legado opcional
- **Cookie de sessão:** `__Host-ntt_session=<colabId>.<expEpoch>.<funcional>.<hmacBase64Url>; Path=/; Secure; HttpOnly; SameSite=Strict`
- A CloudFront Function valida o cookie, injeta `request.headers['x-colab-id'] = { value: colabId }` para a origem e expõe a identidade em `/auth/ntt-whoami`.

### 3.2. Três Restrições Físicas do Runtime CloudFront Functions (Bloqueantes)
1. **Orçamento rígido de `10.240 bytes` (`10 KB`):**
   - O código-fonte `.js` enviado à AWS não pode passar de `10.240 bytes`.
   - Quebras de linha **CRLF** no Windows adicionam ~200–300 bytes invisíveis e quebram o deploy (`InvalidParameterValue`).
   - **Regra:** forçar `LF` no arquivo `.js` e manter invariante automatizado `len(bytes) + 64 < 10240`.
2. **Default Cache Behavior bloqueia `POST` em rotas virtuais (`403 Forbidden`):**
   - Se `AllowedMethods` do comportamento padrão for `["GET", "HEAD", "OPTIONS"]`, qualquer `POST /auth/ntt-trocar-senha` recebe `403` do CloudFront **antes** da função `viewer-request` rodar.
   - **Regra:** rotas virtuais respondidas pela própria CloudFront Function devem usar **`GET`** com parâmetros na query string, blindadas contra CSRF por `Sec-Fetch-Site: same-origin` + header customizado `X-Requested-With: XMLHttpRequest` + `Cache-Control: no-store`.
3. **Sincronia Tripla de Identidade (`DynamoDB` ↔ `S3` ↔ `KVS`):**
   - Todo colaborador ativo precisa existir simultaneamente em:
     1. `DynamoDB` (`PK=COLAB#<id>, SK=META`, campos `funcional` e `senha`);
     2. `S3` (`web/data/colaboradores.json`, usado pelo autocomplete);
     3. `CloudFront KVS` (`u:<funcional>`, usado pelo login na borda).
   - O teste E2E (`test_e2e.py`) deve verificar a paridade exata entre as 3 fontes (`58 == 58 == 58`).

---

## 4. Read Models Materializados no S3 (`0 RCU`), Prefixos Privados e `aws s3 sync --delete` (`LL-0030`)

### 4.1. Read Model JSON no S3 + Reconciliação de Delta no Cliente
Para telas gerenciais que cruzam todas as entidades (ex.: **Relatório do Gestor** com matriz de `58 colaboradores × 21 cursos = 1.218 células`):
- **Não faça `Scan` nem 58 `Query` em tempo real no DynamoDB.**
- Gere uma view materializada `web/data/relatorio-gestor.json` no S3 durante o pipeline de seed/consolidação (`0 RCU` na leitura, entregue pelo CloudFront em `< 50 ms`).
- No navegador (`app.js`), aplique **Reconciliação de Delta em Memória**: mescle o JSON estático com as alterações realizadas na sessão atual (`state.sessionValidatedCourses`), recalculando contagens, percentuais e reordenando a tabela instantaneamente.
- Proteja o JSON com **RBAC em Dupla Camada**:
  1. **UI:** item de menu oculto (`hidden`) se `state.loggedInColabId !== GESTOR_COLAB_ID`;
  2. **Borda (CloudFront Function):** interceptação de `/data/relatorio-gestor.json` validando o hash SHA-256 do ID/funcional do gestor no cookie HMAC e retornando `403 Forbidden` para qualquer outro colaborador.

### 4.2. Isolamento de Prefixos Privados no Mesmo Bucket S3 (`aws_s3_bucket.web`)
Quando um único bucket S3 armazena tanto a SPA pública (`index.html`, `app.js`) quanto prefixos internos (`cache-certificados/*`, `tmp-uploads/*`):
1. **Borda:** CloudFront Function retorna `403 Forbidden` para `uri.indexOf('/cache-certificados') === 0` e `uri.indexOf('/tmp-uploads') === 0`;
2. **Bucket Policy (`infra/cloudfront.tf`):** adicione um statement explícito `"Effect": "Deny"` para o Service Principal `cloudfront.amazonaws.com` nos ARNs `${aws_s3_bucket.web.arn}/cache-certificados/*` e `${aws_s3_bucket.web.arn}/tmp-uploads/*`.

### 4.3. Armadilha Mortal do `aws s3 sync --delete`
Quando o script de publicação (`publish_web.sh`) faz `aws s3 sync web/ s3://$BUCKET/ --delete`, o S3 **apaga** qualquer objeto no bucket que não exista localmente em `web/`.
- **Regra obrigatória:** todo artefato dinâmico ou cache no mesmo bucket DEVE estar listado em `--exclude`:
  ```bash
  aws s3 sync web/ "s3://${BUCKET}/" \
    --delete \
    --exclude "data/colaboradores.json" \
    --exclude "data/relatorio-gestor.json" \
    --exclude "cache-certificados/*" \
    --exclude "certificados/*" \
    --exclude "tmp-uploads/*"
  ```
- Crie um invariante estático (`Inv.12`) que falha o build se qualquer `--exclude` obrigatório for removido do `publish_web.sh`.

---

## 5. Promoção Multi-Conta (`SANDBOX` ↔ `PRODUCAO`), Hardening S3 e Versionamento Automático (`LL-0036`)

### 5.1. Isolamento Multi-Conta e Proteção de Dados
- Separe `SANDBOX` (`AWS_PROFILE=default`, state `terraform.tfstate`) de `PRODUCAO` (`AWS_PROFILE=prod`, state `terraform.tfstate.prod`) na mesma região (`ap-northeast-1`).
- Ative `deletion_protection_enabled = true` e `point_in_time_recovery { enabled = true }` na tabela DynamoDB em ambos os ambientes.
- Na Bucket Policy do `aws_s3_bucket.web` (`infra/cloudfront.tf`), exija obrigatoriamente:
  1. `aws_s3_bucket_ownership_controls` com `ObjectOwnership = "BucketOwnerEnforced"`;
  2. Statement `DenyInsecureTransport` (`Condition: Bool { "aws:SecureTransport": "false" }`);
  3. Statement `DenyPublicAndOACReadOnPrivatePrefixes` bloqueando leitura via CloudFront OAC em `tmp-uploads/*` e `cache-certificados/*`.

### 5.2. Versionamento Automático por Ambiente (`version.json` + Auto-Bump em Produção)
- Em `SANDBOX`, mantenha o visor discreto de versão como `v0.0 (sandbox)`.
- Em todo deploy de `PRODUCAO` (`publish_web.py --ambiente PRODUCAO`), incremente automaticamente o dígito da casa mais à direita (`v0.0 → v0.1 → v0.2...`), gravando em `web/version.json`, injetando o badge no `index.html`/`app.js` e invalidando o CloudFront (`/*`).

### 5.3. Contra-Prova de Paridade Pós-Deploy (`verify_prod_confidence.py`)
- Após cada promoção para `PRODUCAO`, rode auditoria automatizada comparando:
  1. Contagens exatas por prefixo `SK` no DynamoDB (`PROG#`, `CURSO#`, `COLAB#`, `EVID#`, `REVISAO#`, `VARREDURA#`) entre `SANDBOX` e `PRODUCAO`;
  2. Hashes SHA-256 dos objetos S3 (`index.html`, `app.js`, `styles.css`, `colaboradores.json`, `relatorio-gestor.json`, `certificados/manifest.json`);
  3. Probes HTTP Black-Box (`test_security_oscp.py --live --ambiente PRODUCAO`) confirmando `100%` de proteção na borda.

### 5.4. Proibição de IDs CloudFront/KVS Hardcoded em Scripts Multi-Conta (`LL-0036`)
- **Armadilha Real:** um script de deploy com `DIST_ID` hardcoded do `SANDBOX` sincroniza os arquivos S3 na conta de `PRODUCAO` mas falha na etapa `cloudfront create-invalidation` com `NoSuchDistribution`, deixando o edge cache servindo assets antigos.
- **Regra:** scripts de publicação (`publish_web.py`, `verify_prod_confidence.py`) devem resolver dinamicamente `cloudfront_distribution_id`, `s3_bucket_name` e `kvs_arn` a partir do Terraform state do ambiente-alvo (`terraform output -state=...`) ou via `aws cloudfront list-distributions` filtrando pela origem S3 da conta ativa.

### 5.5. Sincronia Quádrupla em Operações CRUD Serverless (`LL-0041`)
- Em arquiteturas serverless de custo zero onde a autenticação roda no CloudFront KVS e o frontend consome views materializadas no S3:
  1. **DynamoDB (`PK=TREINAMENTO#CATALOGO` / `COLAB#<id>`):** fonte primária da verdade;
  2. **S3 `colaboradores.json`:** lookup público mínimo (`id`, `nome`, `perfil`, `papel`, `funcional`);
  3. **S3 `data/relatorio-gestor.json`:** matriz materializada (`N_colabs × N_cursos`) recalculada com preservação das 7 Invariantes Matemáticas (`Inv-M1..M7`);
  4. **CloudFront KeyValueStore (`colab:<funcional>`):** credencial/papel na borda quando há criação, exclusão ou alteração de `funcional`/`papel` de um colaborador.

---

## 6. FinOps Free Tier v2 (`$0.03 / $0.42`), Simulador Diário (`1x/dia`) e Curto-Circuito `O(1)` na Borda (`LL-0037` / `LL-0040`)

### 6.1. Eliminação de Custos Fixos Desnecessários e Telemetria Diária (`sfn_custos.tf`)
- **Regra FinOps:** nunca consulte a API do AWS Cost Explorer em tempo real a partir da UI (**US$ 0,01 por requisição** — 100 refreshes na tela custariam US$ 1,00, mais que toda a infraestrutura mensal!).
- **Padrão Simulador Diário (`0 Lambda`):**
  1. Um **EventBridge Scheduler** (`cron(55 23 * * ? *)`, `America/Sao_Paulo`, Free Tier de 14M invocações/mês) dispara **1x ao dia** a Step Function Express `custos.asl.json`;
  2. A State Machine coleta `DescribeTable` (bytes DynamoDB) + `HeadObject` S3 + `DescribeBudget` e calcula via JSONata (`fragments/custos-simular.jsonata`) o gasto acumulado *pro-rata* (`$0.03`) e a projeção mensal (`$0.42`), gravando `s3://<bucket>/custos-aws.json`;
  3. O visor `#app-cost-viewer` (restrito ao `GESTOR` na UI e na CloudFront Function) lê apenas o JSON estático do S3 (`0 RCU`, `US$ 0,00`), exibindo explicitamente a moeda **`Dólar Americano (USD)`**.
- **Perfis de Capacidade DynamoDB dentro do Free Tier Permanente (`25 RCU / 25 WCU`):**
  - `SANDBOX`: `1 RCU / 1 WCU` fixo (custo `US$ 0,00`);
  - `PRODUCAO`: `5 RCU / 5 WCU` base com Application Auto Scaling elástico até `25 RCU / 25 WCU` (`70%` target utilization), mantendo `100%` dentro do Free Tier permanente da AWS.

### 6.2. Regex UTF-8 Segura na Borda (`ARQ_RE`) para Nomes Canônicos de Certificados (`LL-0037`)
- Em sistemas em língua portuguesa, títulos de cursos e certificados contêm caracteres acentuados (`Introdução`, `Práticas`, `Gonçalo`), parênteses `( )` e vírgulas `,`.
- **Armadilha:** validar `?arquivo=` na CloudFront Function com `/^[A-Za-z0-9._ -]+\.(pdf|png|jpg|jpeg)$/` bloqueia certificados legítimos com `400 Bad Request` (`parametro_invalido`).
- **Padrão Seguro (`< 10.176 B`):** bloquear estritamente caracteres de controle, separadores de diretório (`/`, `\`), metacaracteres (`<>:"|?*`) e `..`, permitindo caracteres imprimíveis Latin-1/UTF-8:
  ```javascript
  var ARQ_RE = /^[^\x00-\x1f\/\\<>:"|?*]{3,220}\.(pdf|png|jpg|jpeg|bmp)$/i;
  ```

### 6.3. Curto-Circuito Local `O(1)` para Entidades Criadas na Sessão (`LL-0040`)
- Quando a CloudFront Function protege `/api/consulta` reescrevendo a querystring `?c=` para o `colabId` do cookie autenticado (prevenção de IDOR para colaboradores comuns) e o fallback estático busca `/consultas/<id>.json` no S3:
  - Um colaborador novato recém-cadastrado na sessão (`isCustomCreated: true`) ainda não possui objeto no S3 nem item no DynamoDB.
  - O frontend DEVE curto-circuitar `consultarColaborador` localmente em `O(1)` via `buildNovatoConsultaPayload(customRosterItem)` antes de emitir requisições de rede.

---

## 7. Camada de Fornecimento de Dados Auditáveis via Step Functions + MCP e Materialização Dual S3 `< 256 KB` (`LL-0043`)

Para expor dados consolidados e séries históricas retroativas a sistemas parceiros (ex.: *Avaliação 360° A2A*, *Data Lake*, *RH*) mantendo `0 Lambda`:

1. **Tabela Dedicada de Auditoria no DynamoDB (`auditoria-desempenho-treinamentos`, `884` itens):**
   - `PK = META#AUDITORIA_360, SK = SNAPSHOT#2026` (`1` item executivo);
   - `PK = DATASET#2026, SK = COLAB#<colabId>` (`58` linhas tabulares com `45` colunas por colaborador);
   - `PK = COLAB#<colabId>, SK = MARCO#<data>#<codigo>` (`187` marcos/conquistas retroativos gamificados);
   - `PK = RANKING#<periodo>, SK = POS#<001..058>#<colabId>` (`638` itens cobrindo `cicloAtual`, `anualConsolidado` e os `9` meses `2026-02..2026-10`).
2. **Materialização Dual S3 contra `States.DataLimitExceeded` (`256 KB`) em `s3:getObject` (`LL-0043`):**
   - **Armadilha Real:** ler um dataset analítico completo (`dataset-consolidado-2026.json`, `~302 KB`) diretamente via `arn:aws:states:::aws-sdk:s3:getObject` na Step Functions Express falha com `States.DataLimitExceeded` (limite rígido de `262.144 bytes` por estado).
   - **Padrão Materialização Dual S3:**
     - `auditoria-360/dataset-consolidado-2026.json` (`~302 KB`), `auditoria-360/dataset-tabular-2026.csv` (`58 × 45`) e `auditoria-360/marcos-conquistas-2026.jsonl` (`187` linhas) para ingestão direta S3/Data Lake;
     - `auditoria-360/dataset-tabular-api-2026.json` (`~134 KB < 190 KB`) omitindo arrays brutos redundantes para leitura síncrona ultrarrápida na State Machine `consolidador-treinamentos-auditoria` (`POST /integracao/auditoria-360`).
3. **Autenticação Multi-Cliente com Escopos por Sistema Consumidor (`Secrets Manager`):**
   - Segredo `consolidador-treinamentos/integracao-clientes-api-keys` com mapa `clientes[clientId]` (`avaliacao-360-a2a`, `datalake-ntt`, `rh-corporativo`), cada um com `apiKey` própria e `escopos[]` (`dataset:read`, `colaborador:read`, `marcos:read`, `ranking:read`), validado em `auditoria-validar-api-key.jsonata` usando `$not(...)` e zero eco de segredo.
4. **Servidor MCP (`JSON-RPC 2.0` stdio — `scripts/mcp/servidor_auditoria_360_mcp.py`):**
   - Expõe 6 tools semânticas (`obter_resumo_executivo_360`, `listar_dataset_tabular_360`, `obter_dossie_treinamentos_colaborador`, `obter_historico_marcos_conquistas`, `consultar_ranking_ciclo_mensal`, `exportar_insumo_avaliacao_360`) prontas para acoplamento no Gate 4 do pipeline multi-agente `avaliacao-enterprise-a2a`.
