# Catraca de Qualidade Contínua (Quality Ratchet): Invariantes Estáticos + Baterias Comportamentais em Serverless & Edge

> **Origem:** sistema de qualidade contínua do projeto *Consolidador de Treinamentos* (`Inv.1..12` + Baterias `Q1..Q12` + Corpus S3 `test_continuous_s3.py`, out/2026).
> **Vínculos:** `LL-0024` a `LL-0031`, `LL-0036` a `LL-0043` · `instinto-0013` a `instinto-0016`, `instinto-0019`.

---

## 1. O Princípio da Catraca de Qualidade (Quality Ratchet)

Em arquiteturas serverless low-code (`Step Functions + JSONata + CloudFront Functions + SPA estática + S3`), os bugs mais perigosos **não acontecem dentro de funções isoladas de negócio** — eles acontecem nas **fronteiras de integração e formato**:
- Quebra de linha `CRLF` no Windows que estoura o limite de `10.240 bytes` da CloudFront Function;
- Rota virtual na borda chamada com `POST` que o Default Cache Behavior do CloudFront rejeita com `403` antes da função rodar;
- `$now()` em JSONata que retorna data UTC e rejeita certificados às 21h BRT como "data futura";
- Operador unário `!` em JSONata que o AWS Step Functions rejeita em tempo de execução (`QueryEvaluationError`);
- Objeto S3 `> 256 KB` lido via `s3:getObject` na Step Functions Express (`States.DataLimitExceeded`);
- Corrida de `AbortController` na UI quando o usuário troca rápido de colaborador no autocomplete;
- `aws s3 sync web/ s3://... --delete` que apaga silenciosamente Read Models dinâmicos (`relatorio-gestor.json`) e caches privados (`cache-certificados/*`).

**Regra da Catraca:** nenhum bug ou lição aprendida (`LL-NN`) é dado como resolvido apenas com o patch no código. No mesmo commit, ele DEVE gerar:
1. **Um Invariante Estático Rápido (`< 2 s`):** verificação determinística de AST/bytes/regex em `scripts/check_invariantes.py`;
2. **Um Teste Comportamental Executável (`< 5 s`):** simulação fiel do runtime em `scripts/test_continuous_quality.py`.

---

## 2. Os 12 Invariantes Estáticos de Referência (`check_invariantes.py`)

| # | Invariante | O que protege |
|---|---|---|
| **Inv.1** | `0 Lambda` em `infra/*.tf` e `statemachines/*.asl.json` | Impede deriva arquitetural e custo de compute não autorizado |
| **Inv.2** | Exatamente `2 dynamodb:Query` em `consulta.asl.json` (0 Secrets Manager na leitura) | Garante latência `< 1 s` e custo zero de Secrets Manager no caminho crítico |
| **Inv.3** | `≤ 60 linhas` de JSONata por estado; expressões `> 5 linhas` em `fragments/*.jsonata`; zero operador unário `!` | Mantém legibilidade/testabilidade do ASL e impede `QueryEvaluationError` no Step Functions |
| **Inv.4** | Uma única definição de `$norm` (`fragments/norm.jsonata`), espelhada no `app.js` | Evita divergência silenciosa de normalização entre backend e frontend |
| **Inv.5** | Nenhum segredo ecoa em `Output` de estado (`apiKey`, `SecretString`) | Evita vazamento de credencial no envelope do `StartSyncExecution` |
| **Inv.6** | `statemachines/*.asl.json` válidos + todas as variáveis `${...}` casam com `infra/*.tf` | Impede erro de `templatefile` no `terraform plan/apply` |
| **Inv.7** | `0 http:invoke` / `aws_cloudwatch_event_connection` | Preserva escopo e simplicidade do MVP |
| **Inv.8** | `casamento.metodo` presente em toda evidência gravada | Garante rastreabilidade e auditabilidade de cada certificado |
| **Inv.9** | **Zero PII / Account ID / Funcional no Git via Digest SHA-256** | Varre `git ls-files` comparando hashes SHA-256 dos tokens contra lista negra (sem expor os segredos no scanner) |
| **Inv.10** | **Segurança Frontend (CSP) + Orçamento de Bytes da CloudFront Function** | Proíbe `innerHTML`/`outerHTML`/`style=` inline; exige `basic_auth.js` em LF com `len(bytes) + 64 < 10240`; proíbe `POST` em rotas virtuais `/auth/*` |
| **Inv.11** | **Higiene UTF-8 Anti-Mojibake** | Varre todo arquivo de texto e JSON de seed/dados contra sequências UTF-8 corrompidas (`Ã£`, `Ã§`, `Ã©`, `\ufffd`) |
| **Inv.12** | **Guardas de Regressão (`LL-01..LL-32`)** | Fuso BRT `-0300`, proteção `--exclude` no `s3 sync --delete`, tokens CSS `:root`, paridade `index.html === dev.html`, projeção `< 256 KB` na SFN Express |

---

## 3. Como Testar CloudFront Functions Localmente sem Deploy (`Bateria Q1`)

CloudFront Functions usam o runtime `cloudfront-js-2.0` (subconjunto ECMAScript 5.1 + extensões `crypto` e `cf.kvs()`). **Nunca faça deploy no CloudFront para descobrir se a função tem erro de sintaxe ou de lógica.**

Execute o arquivo real `infra/cf_function/basic_auth.js` dentro de um contexto isolado `vm` do Node.js via subprocesso Python (`test_continuous_quality.py`), injetando um mock de `cf.kvs()` e o módulo `crypto` nativo:

```javascript
const fs = require('fs');
const vm = require('vm');
const crypto = require('crypto');

const code = fs.readFileSync('infra/cf_function/basic_auth.js', 'utf8');
const kvsStore = {
  'u:999001': crypto.createHash('sha256').update('999001:999001').digest('hex') + '|colab-01',
  'session_secret': 'test-secret-256-bits'
};

const sandbox = {
  require: (mod) => {
    if (mod === 'crypto') return crypto;
    if (mod === 'cloudfront') return {
      kvs: () => ({
        get: async (key) => {
          if (key in kvsStore) return kvsStore[key];
          throw new Error('Key not found: ' + key);
        }
      })
    };
    throw new Error('Unsupported module: ' + mod);
  },
  Buffer, String, Object, Array, Number, Boolean, Date, Math, RegExp, JSON, Error,
  parseInt, encodeURIComponent, decodeURIComponent
};

vm.createContext(sandbox);
vm.runInContext(code, sandbox);
// Agora invoque sandbox.handler(event) para testar todos os cenários!
```

### Cenários Obrigatórios da Bateria `Q1` (CloudFront Function):
1. **Orçamento físico:** `LF` puro (`\r\n` ausente) e `len(bytes) + 64 < 10240`;
2. **Sem credencial:** `GET /index.html` → `401 Unauthorized` com `WWW-Authenticate: Basic`;
3. **Login por funcional/senha no KVS:** `Authorization: Basic base64(999001:999001)` → passa para origem com header `x-colab-id: colab-01`;
4. **Emissão e validação de cookie `__Host-ntt_session`:** `/auth/ntt-login` emite cookie HMAC válido; requisição subsequente só com cookie autentica sem Basic Auth;
5. **Troca de senha (`GET /auth/ntt-trocar-senha`):** funciona com `Sec-Fetch-Site: same-origin` + `X-Requested-With: XMLHttpRequest`, e retorna **`403 CSRF`** sem esses headers;
6. **Bloqueio de prefixos privados:** `/cache-certificados/x.pdf` e `/tmp-uploads/x.pdf` → **`403 Forbidden`**;
7. **RBAC do Relatório do Gestor na borda:** `/data/relatorio-gestor.json` retorna **`403 Forbidden`** para colaborador comum e passa apenas quando autenticado com o ID/funcional do gestor.

---

## 4. Paridade N-Way de Funções Compartilhadas (`Bateria Q2`)

Quando uma função pura (como `norm(s)`: minúsculas, sem acentos NFD, pontuação convertida em espaço, espaços colapsados) precisa existir em múltiplas linguagens (`JSONata` no Step Functions, `Python` nos scripts de seed/varredura e `JavaScript` no frontend):
1. Crie uma **fixture única da verdade** (`tests/fixtures/norm/norm-casos.json`) com 30+ casos de borda (acentos compostos, hífens colados, underscores, espaços múltiplos, strings vazias);
2. Na bateria de qualidade (`Q2`), avalie cada caso simultaneamente na implementação Python e na implementação JavaScript (`node -e` carregando a função extraída do `web/app.js`) e compare com o esperado da fixture (`100%` de igualdade exata).

---

## 5. Oráculo Contínuo com Corpus Espelho no S3 (`test_continuous_s3.py` + `Bateria Q5`)

Para garantir que evoluções no parser de certificados, no catálogo de cursos ou nas views materializadas nunca degradem silenciosamente os resultados reais da equipe:
1. Mantenha no S3 (`s3://<bucket>/cache-certificados/test-corpus/golden-baseline.json`) um **oráculo determinístico** contendo os totais esperados da equipe (ex.: `58` colaboradores, `21` cursos no catálogo, `333` conclusões pré-sync -> `334` pós-sync, `119` itens acionáveis na revisão, contagens por curso e por método de casamento);
2. Na **Bateria `Q5`** (local, `< 1 s`) e no **`test_continuous_s3.py`** (live contra S3 + DynamoDB):
   - Valide que a soma da matriz `relatorio-gestor.json` (`58 × 21 = 1.218` células) bate exatamente com `cursosConcluidos` de cada linha e com as contagens do `seed-items.json` / DynamoDB;
   - Valide a sincronia tripla de identidade (`DynamoDB META == S3 colaboradores.json == CloudFront KVS`).

---

## 6. As 7 Invariantes Matemáticas Universais de Dashboards Analíticos (`Bateria Q6`)

Em telas executivas e matrizes gerenciais, bugs de arredondamento ou de escopo de denominador (ex.: incluir células `Não Aplicáveis / N/A` no denominador de progresso) destroem a confiança nos dados. Codifique na **Bateria `Q6`** estas 7 invariantes matemáticas universais (`Inv-M1..M7`):

| Código | Invariante Matemática Universal | Fórmula Verificada em Todo Render / Sync |
|---|---|---|
| **Inv-M1** | **Partição Exata da Matriz** | `concluidos + pendentes === aplicaveis` e `aplicaveis + naoAplicaveis === totalCelulas` (`N_colabs × N_cursos`) |
| **Inv-M2** | **Complementaridade de Percentuais** | `pctCompleto + pctPendente === 100.0%` (calculado estritamente sobre `aplicaveis`, nunca sobre `totalCelulas` bruto) |
| **Inv-M3** | **Consistência Marginal (Linha × Coluna)** | `∑(concluidos por colaborador) === ∑(concluidos por curso) === KPI Global Realizados` |
| **Inv-M4** | **Subconjunto Obrigatórios ⊆ Geral** | `obrigConcluidos <= geralConcluidos` e `obrigPossiveis <= geralAplicaveis` em toda linha e no total |
| **Inv-M5** | **Monotonicidade Temporal (`serieHistorica`)** | `acumulado[t] <= acumulado[t+1]` (incluindo entregas de sábado/domingo/feriado) e `acumulado[ultimo] === totalConcluidos` |
| **Inv-M6** | **Monotonicidade de Ranking (`Top N`)** | `mediaCursosConcluidos(Top 5) >= mediaCursosConcluidos(Top 10) >= mediaCursosConcluidos(Top 15)` |
| **Inv-M7** | **Idempotência Estrita de Sincronização** | `reconcile(reconcile(state)) === reconcile(state)` em 5+ execuções consecutivas (zero deriva de contadores ou horas) |

---

## 7. Contra-Prova Física Direta (Repositórios de Arquivos + ETL × Matriz de Produção) (`Bateria Q7`)

Nunca confie apenas em fixtures sintéticas quando o sistema consolida diretórios reais (OneDrive/SharePoint) e relatórios de ETL:
1. Na **Bateria `Q7`**, execute a função real de varredura física sobre os diretórios espelhados e o parser de bullets do ETL (`0` órfãos não casados);
2. Compare **célula a célula (`1.218 / 1.218`)** o resultado produzido pelo JavaScript (`reconcileRelatorioGestorWithSession(rawRg)` hidratado pelo `manifest.json`) contra a matriz recém-gerada a partir do sistema de arquivos;
3. Audite a separação exata entre **horas em dias úteis** (`horasUteisEfetivas`, barra azul) e **horas adiantadas em fim de semana ou feriado nacional** (`horasFdsFeriadoEfetivas`, barra roxa), garantindo `diasTotaisDedicados === diasUteisDedicados + diasFdsFeriadoDedicados`.

---

## 8. Consistência de Nomes Multi-Camadas (`NFC == NFD`), Rename em Cascata e Política P0 Anti-Falso-Negativo (`Bateria Q8`)

Quando o nome do colaborador é chave de cruzamento com certificados PDF (`<Curso> - <Nome>.pdf` e chave `PRIM_ULT#` no DynamoDB):
1. **Equivalência Unicode (`NFC == NFD`):** garanta que `norm()` produza a mesma saída para strings compostas (`NFC`, padrão Windows/Linux) e decompostas (`NFD`, padrão macOS/OneDrive);
2. **Validação Multi-Camadas na Edição de Nome (`validateCollaboratorFullName`):**
   - Bloqueie (`ok: false`) nomes com 1 única palavra, abreviações/iniciais isoladas (`"Jr"`, `"A."`), caracteres delimitadores (`" - "`, `/`, `\`) ou colisão exata de homônimo (`nomeNorm`);
   - Emita alerta de alto risco com confirmação em 2 etapas quando houver supressão de sobrenome (assimetria de subconjunto com PDFs existentes) ou mudança de chave `PRIM_ULT#`;
3. **Rename em Cascata (`renameCollaboratorCascade`) + Preservação de `aliases`:**
   - Ao renomear um colaborador, preserve o nome anterior em `aliases[]` e propague o novo nome atomicamente para `uploadedCertsRegistry`, `arquivoSugerido`, `lastAdaptedData` e `relatorioGestorState`;
4. **Política P0 Anti-Falso-Negativo (`resolveUploadedCertAntiFalseNegative` — Zero Cobrança Indevida):**
   - Antes de exibir qualquer curso como `PENDENTE`/`ATRASADO`, reconcilie por 4 camadas (ID canônico `colabId:cursoId` -> `funcional` -> `norm(nome)`/`aliases` -> `PRIM_ULT#` não-ambíguo + sufixo do arquivo `.pdf`). Se houver certificado válido enviado na sessão ou manifesto S3, promova imediatamente para `REALIZADO` e remova de `alertas`.

---

## 9. Suíte Contínua de Segurança e Pentest OSCP (`scripts/test_security_oscp.py` — Baterias `S1..S7`)

Integre ao `run_tests.py` (`make test`) a suíte `test_security_oscp.py` validando continuamente 90+ checks offline e 12 probes HTTP Black-Box (`--live`) contra `SANDBOX` e `PRODUÇÃO` (detalhamento completo em `engenheiro-seguranca/references/pentest-oscp-continuo-e-hardening-borda.md`).

---

## 10. Testes Contínuos Comportamentais em VM Node.js para Consistência Operacional (`Bateria Q11`)

Invariantes estáticos (regex sobre HTML/JS) não bastam para garantir que fluxos interativos complexos continuem íntegros após refatorações. Na **Bateria `Q11`**, carregue o código real do `web/app.js` em uma VM Node.js com DOM sintético rastreável e execute fim-a-fim os 3 pilares operacionais:

1. **Ciclo Completo de Login, Memorização e Logout (`openAuthGateScreen` → `submitAuthGateLogin` → `closeAuthGateScreen` → `logoutNttSession`):**
   - Verifique que o formulário `<form id="ntt-auth-gate-form">` contém inputs semânticos compatíveis com gerenciadores de senha (`autocomplete="username"` e `type="password"` + `autocomplete="current-password"`), que `toggleAuthGatePasswordVisibility()` alterna `password ↔ text` com `aria-pressed`, e que `submitAuthGateLogin()` invoca `navigator.credentials.store(new PasswordCredential(...))`, grava apenas `ntt_remembered_user` e `ntt_remember_login` em `localStorage` (**jamais a senha em texto claro**) e preserva o identificador lembrado após `logoutNttSession()`.
2. **Determinismo da Matriz RBAC (`PermissionBus`) e Composição Ortogonal (`COLABORADOR_ADMIN`):**
   - Valide em tempo de execução para todos os papéis (`COLABORADOR`, `COLABORADOR_ADMIN`, `GESTOR`, `ADMIN` e papel desconhecido → fallback restritivo `COLABORADOR`) que `PermissionBus.can(role, perm)` respeita estritamente a matriz de menor privilégio e que `COLABORADOR_ADMIN` preserva 100% da visão de colaborador (`view_own_dashboard`, `upload_own_cert`) somada às permissões de manutenção (`view_manter`, `crud_*`), sem acessar `/relatorio-gestor.json` ou `/custos-aws.json` exclusivos do `GESTOR`/`ADMIN`.
3. **Consistência Operacional de Transições CRUD (`58 → 59 → 58` Colaboradores, `1.218` Células):**
   - Execute em sequência atômica `createCollaborator` (`58 → 59` colaboradores, `1.239` células) → `updateCollaborator` (mudança de nome + cascata em `aliases[]` e mudança de perfil `DEV_QA → LIDER_TECNICO` recalculando elegibilidade imediatamente) → `deleteCollaborator` (retorno exato a `58` colaboradores e `1.218` células com limpeza de órfãos e preservação das 7 Invariantes Matemáticas Universais `Inv-M1..M7`).

---

## 11. Simulação de Estresse Multi-Componente (`N` Programas × `M` Cursos) e Catraca de Guide Style (`LL-0042`)

Para garantir que a inclusão futura de novos programas e cursos ou ajustes visuais não quebrem o layout nem as regras de negócio:

1. **Simulação Não-Destrutiva de Escalabilidade (`4 → 7` Programas, `21 → 30` Cursos) com Reversão Canônica:**
   - Em `table-layout: fixed`, sincronize dinamicamente o `<colgroup>` (`syncMatrixTableColgroup`: `3` colunas fixas + `M` colunas `.rg-col-course`) antes de renderizar o cabeçalho de 2 linhas (`appendMatrixProgramGroupCells`, onde `∑ colspan === M`);
   - Ative automaticamente `.colab-ind-matrix__table--expanded` quando `M > 21`, aplique a paleta cromática cíclica (`T1`, `T2`, `BEDEVOPS`, `OPENAI` + `ALT1..ALT4` via `resolveProgramMatrixThemeKey`) e desambigue siglas curtas (`buildProgramShortLabels`) quando múltiplos programas compartilharem o mesmo prefixo;
   - Ao final do teste em VM Node.js, reverta integralmente o estado e comprove que a matriz retorna exatamente a `4` programas, `21` cursos e `1.218` células (`58 × 21`).
2. **Isolamento de Elegibilidade de Novato:**
   - Para colaboradores recém-cadastrados na sessão (`isCustomCreated: true`), restrinja a obrigatoriedade inicial estritamente aos `12` cursos fundamentais `/^T[12]\./i` (`Trilha 1` + `Trilha 2`), impedindo que cursos opcionais com `obrigatorioCiclo` (como `OPENAI.CSP` ou novos programas) inflem a meta do novato.
3. **Auditoria Automática de Guide Style e Tokens CSS:**
   - **Zero Variáveis CSS Órfãs:** `check_invariantes.py` (`Inv.12`) extrai todas as declarações `--token:` e todos os usos `var(--token)` em `web/styles.css`, falhando imediatamente se qualquer token referenciado não estiver declarado em `:root`;
   - **Paridade `index.html === dev.html` e Família Única de Ícones (`--font-emoji`):** valide igualdade 1:1 entre os shells HTML, proíba glifos monocromáticos legados (`⌕`, `▤`, `⊞`, `★`) e garanta geometria idêntica em pills irmãos da sidebar (`#app-version-viewer` e `#app-cost-viewer` com moeda explícita `Dólar Americano (USD)`).

---

## 12. Onboarding de Colaborador Novato (`0` Treinamentos), Sugestores Interativos, Validações Informativas e Inspeção Visual de Screenshots em E2E (`Bateria Q9` — `LL-0040`)

Ao testar o cadastro de entidades novas em sessão (`isCustomCreated: true`) que ainda não existem no backend/S3, ocorrem **4 armadilhas sutis de fronteira** que só aparecem quando combinamos VM Node.js (`Bateria Q9`) com regressão visual em navegador real (`Chrome Headless CDP`):

1. **Autopreenchimento Reativo de E-mail ao Abrir Modal Vazio (`emailAutoTouched`):**
   - **Armadilha:** inicializar uma flag `emailAutoSynced = Boolean(prefillEmail)` como `false` quando o modal abre vazio (`+ Cadastrar novato` no Relatório do Gestor) impede que a digitação subsequente do nome atualize o campo de e-mail.
   - **Guarda (`Q9.6a` + `Inv.12`):** rastrear `colabEditModalState.emailAutoTouched = false` na abertura do modal e só marcá-la como `true` quando o usuário editar manualmente `#colab-edit-email` ou clicar em um chip sugestor.
2. **Curto-Circuito Local `O(1)` em `consultarColaborador` para Novato Customizado:**
   - **Armadilha:** se o frontend chamar `GET /api/consulta?c=<novato>` na borda CloudFront para um novato recém-cadastrado na sessão, a CloudFront Function reescreve `c` para o `colabId` do cookie autenticado (proteção anti-IDOR) ou o S3 retorna `403 Forbidden` para `consultas/<novato>.json` inexistente.
   - **Guarda (`Q9.8` + `Inv.12`):** verificar `if (customRosterItem)` (`r.isCustomCreated === true`) no início de `consultarColaborador` e resolver localmente via `buildNovatoConsultaPayload(customRosterItem)` em `O(1)`, exibindo imediatamente o banner `#novato-onboarding-banner` (*Guia Rápido de Primeiros Passos*).
3. **Distinção Estrita entre `c.evidencia` (Instruções) e `c.evidenciaEncontrada` (Comprovante Realizado) na Matriz Individual:**
   - **Armadilha:** todo curso do catálogo possui o objeto `c.evidencia` (contendo `arquivo_sugerido` e pasta de entrega). Testar `Boolean(c.evidencia)` em `renderIndividualCourseMatrix` faz um novato com `0` treinamentos aparecer com **`21 realizados · 0 pendentes`** na pílula de resumo da matriz individual!
   - **Guarda (`Q9.8` + `Inv.12`):** proibir estaticamente `const hasEvid = Boolean(c.evidencia);` e exigir `Boolean(c.evidenciaEncontrada || c.evidencia_encontrada)`, validando que `#ind-matrix-summary-pill` exiba exatamente `"0 realizados · 12 pendentes"` para novatos.
4. **Simetria de Limpeza Pós-Delete (`58 → 59 → 58`) mesmo sobre `rawView` Mutado em Memória:**
   - **Armadilha:** quando `reconcileRelatorioGestorWithSession(relatorioGestorState.rawView)` roda após criar um novato, a linha customizada passa a existir em `rawView`. Se `deleteCollaborator` remover o override mas `reconcileRelatorioGestorWithSession` não filtrar linhas `row.isCustomCreated` cujo `id` não está mais ativo em `colabEditOverrides`/`state.roster`, o contador permanece preso em `59`!
   - **Guarda (`Q9.10`):** exigir que `reconcileRelatorioGestorWithSession` preserve `isCustomCreated: true` na linha reconciliada, filtre linhas customizadas órfãs e que `refreshGestorViewsAfterRosterMutation()` re-renderize ambas as visões do Gestor incondicionalmente.
5. **Inspeção Visual Obrigatória dos Screenshots Capturados no E2E:**
   - Em todo teste E2E em navegador headless (`Chrome CDP` / `Playwright`), **nunca dê o teste por concluído apenas pelo exit code `0` do script**: inspecione visualmente os PNGs gerados (`view_file`) para detectar discrepâncias visuais (como pílulas secundárias ou modais de fundo).

---

## 13. Auditoria Gerencial 360°, Dataset Tabular Retroativo e Camada API/MCP (`Bateria Q10` — `LL-0043`)

Quando o sistema fornece indicadores auditáveis para sistemas irmãos (ex.: *Avaliação 360° A2A*, *Data Lake* e *RH*):
1. **Bijeção Matemática de Rankings Mensais (`Q10.4` / `Q10.5`):** valide que tanto `posicao_ranking_ciclo` quanto cada mês de `seriesRanking.mensalCalendario` (`2026-02` a `2026-10`) formem uma permutação exata `1..N` (`set(range(1, 59))`), sem buracos nem colisões;
2. **Consistência Temporal de Entregas (`Q10.6`):** `sum(distribuicao_mensal_entregas.values()) === cursos_concluidos_total` para cada um dos `58` colaboradores;
3. **Isolamento de Escopo por Cliente na Borda API/MCP (`Q10.11..Q10.16`):** teste no `TestState` e no servidor MCP (`JSON-RPC 2.0`) que credenciais válidas de um consumidor com escopo restrito sejam negadas (`403 escopo_insuficiente`) ao consultar escopos de outros consumidores, e que `apiKey` nunca ecoe no payload de saída;
4. **Proibição Estática do Operador Unário `!` em JSONata do AWS Step Functions (`Inv.3` / `LL-31` / `LL-0043`):** proibir via regex `(?<![=!<>])!\s*(?:\$[A-Za-z_]|exists\b|\()` em `statemachines/fragments/*.jsonata`, exigindo `$not(...)` para evitar `QueryEvaluationError` em produção;
5. **Orçamento Rígido `< 256 KB` em `s3:getObject` na Step Functions Express (`Inv.12` / `LL-32` / `LL-0043`):** exigir que `auditoria.asl.json` consuma a projeção compacta `auditoria-360/dataset-tabular-api-2026.json` (`< 190 KB`) e nunca o arquivo analítico bruto (`> 262.144 B`).

---

## 14. Consistência Operacional Cruzada Multi-Plano (`Bateria Q12` — `LL-0043`)

Para garantir que nenhuma operação (ingestão, envio de certificado, edição em cascata, backfill retroativo ou geração de dataset 360°) crie deriva entre camadas, execute em toda build a **Auditoria Cruzada 4-Planos (`Bateria Q12`, 12 cenários)**:
1. **Paridade de Universo 4-Planos (`Q12.1`):** `06-colaboradores-s3.json` (sem Gestor) `==` `07-relatorio-gestor.json` `==` `08-auditoria-360.json` `==` `auditoria-360-tabular-2026.csv` (`58 == 58 == 58 == 58`);
2. **Sincronia Matemática Individual 58/58 (`Q12.2`):** para cada um dos `58` colaboradores, `cursos_aplicaveis`, `cursos_concluidos_total` e `cursos_pendentes_aplicaveis` na Auditoria 360° coincidem `1:1` com a matriz pós-manifesto do Relatório do Gestor (`334/682 = 49,0%`, `Thiago Gonçalo Gomes = 16/16`);
3. **Paridade Tabular CSV `58 × 45` e JSONL `187` Marcos (`Q12.3` / `Q12.4`):** validação célula a célula entre CSV/JSONL exportados para Data Lake e o JSON canônico;
4. **Determinismo Idempotente do ETL e Contagem DynamoDB (`Q12.9` / `Q12.10`):** reexecutar `build_auditoria_360_dataset` em memória deve produzir exatamente os mesmos KPIs e `884` itens DynamoDB (`1 META_AUDITORIA + 58 LINHA_DATASET_COLAB + 187 MARCO_CONQUISTA + 638 ITEM_RANKING`);
5. **Paridade de Seletores DOM Críticos (`Q12.12`):** verificar que todos os IDs manipulados pelo JS (`#colab-ind-matrix-summary`, `#colab-ind-matrix-tbody`, `#rg-indiv-matrix-modal`, `#ntt-auth-gate-form`, `#gd-toggle-ols-metrics-btn`, `#novato-onboarding-banner`, `#app-cost-viewer`, `#app-version-viewer`) existem identicamente em `web/index.html`, `web/dev.html` e `web/app.js`.
