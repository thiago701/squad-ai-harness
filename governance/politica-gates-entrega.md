# Gates de entrega — `database-schema-gate` + `environment-infrastructure-gate`

> Fonte da configuração: [`politica-gates-entrega.json`](politica-gates-entrega.json) (esquema:
> [`politica-gates-entrega.schema.json`](politica-gates-entrega.schema.json)). Marcas `[OK]/[AN]/[GAP]/[DIV]/[SEC]`,
> níveis V0–V5 e regras de sigilo: [`politica-evidencias-sigilo-qualidade.md`](politica-evidencias-sigilo-qualidade.md).
> Código: `scripts/gates/` (núcleo, orquestração, CLI) sobre `scripts/execucao/` (motor, monitor, watchdog).

## 1. O que decide e quem decide

Uma única função decide a progressão: `scripts/gates/nucleo.py::decidir_entrega`. O comando de push do
harness, o hook `pre-push`, o review, a verificação remota e o checkpoint de deploy chamam essa função —
não há mecanismos paralelos com decisões contraditórias.

| Estado | Significado | Autoriza? |
|---|---|---|
| `PASS` | contrato atendido; diferenças só as autorizadas e compatíveis com a etapa | **sim** (único) |
| `BLOCKED` | divergência proibida, segredo, dependência não resolvida | não |
| `INCONCLUSIVE` | sem acesso, sem permissão, sem evidência, suspeita não resolvida | não |
| `STALE` | evidência vencida ou invalidada (commit, política, fingerprint) | não — exige nova execução |

Precedência ao agregar: BLOCKED > STALE > INCONCLUSIVE > PASS. Gate obrigatório ausente, parcial,
cancelado ou em timeout bloqueia. O resultado é vinculado a commit, **árvore analisada** (tree do commit ou
estado da árvore de trabalho), destino e checkpoint, política (versão + hash + origem), ambientes/escopo,
fingerprints estruturais/de configuração, revisões de infraestrutura, data e validade — `status` recusa
resultado de outro destino/checkpoint, de árvore diferente ou datado no futuro.

**O que é analisado.** Em `push`/`remoto`/`deploy` os gates leem o **commit entregue**, materializado direto do
banco de objetos (`ls-tree` + `cat-file`) num diretório temporário — sem `git archive`, que aplicaria
`export-ignore`/`export-subst` e filtros smudge/LFS do próprio commit; symlinks e submódulos não são
materializados. O `pre-push` pode enviar uma ref diferente do HEAD e o que não foi commitado não vai para o
remoto. Em `review`/`planejamento` o objeto é a árvore de trabalho: rastreados, staged, modificados e **não
rastreados não ignorados** entram na varredura de segredos e nos detectores de escopo.

## 2. A política vale a partir da versão REVISADA

A política é lida de `git show <base>:governance/politica-gates-entrega.json`, onde `<base>` é o que o
servidor já tem no destino (para push, o SHA remoto informado ao `pre-push`). Consequências:

- o subagente (ou qualquer automação) **não cria exceção para liberar o próprio bloqueio**: a exceção só
  vale depois de entrar no destino por merge revisado;
- push **direto** para destino abrangido que altere a política é BLOCKED;
- exceção (`mudancasPlanejadas`, `diferencasPermitidas`, `falsosPositivosSegredo`) exige `aprovacao.por` ∈
  `comum.aprovadoresExcecoes`, não pode ser identidade de agente, tem `validaAte` e vale só na etapa/ambiente
  declarados;
- sem política na base: política **embutida** conservadora (detectores ligados, nenhuma exceção).

## 3. Checkpoints

| Checkpoint | Quando | O que roda |
|---|---|---|
| `planejamento` | GATE 1 (pipeline) | estático: contratos, migrations, código, infra declarada; dependências externas levantadas |
| `review` | `tech-lead-review` / G5.5 do `fase-gates.yaml` | tudo, com os ambientes do destino (sem `--destino`: o branch padrão do remoto, registrado na cobertura) |
| `push` | `squad_sync.py execute --push` e hook `pre-push` | segredos em **todo** push; os dois gates nos destinos abrangidos |
| `remoto` | workflow proposto (freeze-patch) | sem credenciais de ambiente: estático + evidências |
| `deploy` | último passo antes de migrar/implantar | coleta nova; validade curta (`validadeEvidenciaMinutos.deploy`) |

`--somente <gate>` vale **só** em `review`/`planejamento`: a decisão sai como `PARCIAL` (nunca `LIBERADO`), o
resultado é gravado à parte e nunca é lido por `status`, publicado como status remoto nem aceito para push,
merge ou deploy; o exit 0 só significa "os gates selecionados passaram". `--publicar-status` só vale em
`push`/`remoto`/`deploy` e publica para o commit efetivamente analisado.

Uma comparação representa um instante: reduzimos o intervalo entre validação e ação e revalidamos antes
do deploy; não é possível eliminar alteração concorrente feita por terceiros depois da coleta.

## 4. `database-schema-gate`

- **Bancos com adaptador:** PostgreSQL (catálogo `pg_catalog`, nunca `information_schema`, que filtra por
  privilégio) + Flyway (checksum idêntico ao do Flyway) e DynamoDB (`DescribeTable`/`DescribeTimeToLive`,
  IaC CloudFormation/SAM). Liquibase e outros motores: **[GAP]** → INCONCLUSIVE, nunca PASS.
- **Compara:** tabelas/colunas, tipo/tamanho/precisão, nulabilidade/default, PK/FK, unique/check, índices
  (com ordenação/predicado e colunas `INCLUDE`), sequences/identidade, collation não padrão, FK `ON DELETE` e
  `ON UPDATE`, rótulos de enum, views (colunas + hash da definição), triggers (hash + habilitado/desabilitado),
  funções, histórico/ordem/checksum/estado das migrations (respeitando o baseline do Flyway); DynamoDB: chave,
  GSI/LSI (chaves e projeção), stream, TTL.
- **Não presume fonte da verdade:** cada ambiente é confrontado com o contrato estrutural versionado e as
  migrations da revisão; a matriz entre ambientes é informativa.
- **Normaliza** ordenação e representação (casts, parênteses, aliases de tipo, nomes gerados de constraint).
- **Permissão ≠ inexistência:** histórico sem SELECT → INCONCLUSIVE; catálogo parcial → INCONCLUSIVE.
- **Taxonomia:** divergência inesperada · migration (pendente/divergente/fora de ordem) · incompatível com
  o código · planejada e autorizada · operacional fora do escopo · inconclusiva.
- **Somente leitura:** serviço libpq (`pg_service.conf` + `.pgpass` fora do repositório; `PGPASSWORD` é
  removido do ambiente do filho), `default_transaction_read_only=on` + `BEGIN READ ONLY` conferido na
  resposta, `statement_timeout`/`lock_timeout`/`connect_timeout`, no máximo duas sessões curtas e sequenciais
  por coleta (catálogo; histórico só se permitido), guarda estática
  que recusa SQL com DDL/DML. Papel de leitura mínimo: `CONNECT` + `SELECT` só na tabela de histórico.

## 5. `environment-infrastructure-gate`

Confronta **código → configuração efetiva → infraestrutura declarada → ambiente observado**:

- **segredos** (todo push): commits a enviar (inclusive intermediários e o conteúdo introduzido no próprio
  merge), árvore do commit entregue (inclusive arquivos que passaram a casar `.gitignore`), artefatos proibidos
  (tfstate, plano, `.env` real, keystores); na review também index, modificados e não rastreados. Sha remoto
  desconhecido → varre tudo que nenhuma ref remota conhece; leitura incompleta (timeout, saída truncada, blob
  ausente) → erro/INCONCLUSIVE, nunca "limpo"; UTF-16 é decodificado; em binário os padrões de alta
  confiança continuam sendo procurados; arquivo acima de 32 MB → INCONCLUSIVE (exceção só por caminho + blob).
  Catálogo: formatos específicos (AWS, GitHub, Slack, JWT, chave privada — inclusive PEM escapado numa linha
  de JSON/.env —, URL com credencial…) e atribuições em `.properties`/`.env`/YAML/compose, JSON/dicionário com
  chave entre aspas (qualquer caixa), XML, connection string `Password=…;`, `.npmrc`, `.netrc`, config do
  Docker e literais em código (`senha`, `pwd`, `secret`…), classificados por contexto (força da chave,
  metadado como `_ENV`/`_PATH`, tipo de arquivo, referência/expressão, frase com palavras gramaticais,
  sentinela sem entropia como `sk-SEGREDO-123`). Valor com palavra "senha/secret" mas com outro conteúdo
  (`Senha@Forte2026`) continua credencial. Cache por blob+tipo fica **fora** do repositório e não é usado em
  `remoto`/`deploy` (no executor local ele está no mesmo domínio de confiança do agente).
  Credencial → BLOCKED; suspeita → INCONCLUSIVE; fictício comprovado/referência → não bloqueia. Nunca exibe o
  valor. Já presente no remoto → bloqueio mantido, exposição registrada, tarefa de rotação + saneamento
  que **só fecha por confirmação humana** (apagar o arquivo não revoga a credencial nem limpa o histórico
  remoto); sem force push automático. Exclusões: só `.gitleaks.toml` (semântica do gitleaks; nunca isenta artefato
  proibido) e `falsosPositivosSegredo` **da base** — cada um com caminho EXATO, padrão, `hashLinha` (conteúdo da
  linha; credencial nova na mesma linha não herda) e `validaAte` obrigatório (`python -m scripts.gates
  segredo-fp` gera o esqueleto sem o valor). `diferencasPermitidas` nunca alcança `segredo-literal`.
- **configuração:** precedência das fontes declaradas (properties, yaml, env, json, variáveis do IaC);
  obrigatórios, tipos/formatos, segredo como referência, conta/região, domínios permitidos, referência cruzada
  entre ambientes (marcador comparado como token: `dev` não casa em `devolucao`); código × contrato
  (parâmetros consumidos); configuração implantável que nenhum contrato/infra/exclusão cobre → INCONCLUSIVE.
- **infraestrutura:** revisão do clone × **prevista** (declarada, nunca inferida pelo nome da branch) ×
  **aplicada** (evidência do pipeline de infra); Terraform estático (versões fixadas, lockfile, módulos,
  variáveis, backend/workspace, conta/região, outputs exigidos); plano especulativo como **evidência**.
  O gate **nunca executa** terraform (nem `init`/`plan`, que baixam e rodam código de terceiros).
- **ambiente observado** (só com perfil de leitura autorizado): identidade/conta, existência/estado de
  segredos e recursos referenciados — existência ≠ valor funcional ≠ acesso da aplicação (registrados à parte;
  acesso efetivo é **[GAP]**).
- **endpoints:** sintaxe sempre; DNS/TLS/conexão/sonda segura só com `endpoints.verificarRede`; resultado
  diferenciado (malformado, DNS, recurso inexistente, TLS, bloqueio de rede, autenticação/autorização,
  transitório, não verificável do executor). 200 não é o único critério; endpoint privado fora da VPC não é
  "inválido"; certificado abaixo de `tlsDiasMinimos` é falha de TLS; a sonda só usa GET/HEAD/OPTIONS e recusa
  caminho com CR/LF/espaço (que enfileiraria outra requisição).

## 6. Camadas de bloqueio e alcance REAL

| Camada | Implementação | Alcance comprovado | Limite |
|---|---|---|---|
| Comando de push do harness | `scripts/git/squad_sync.py` chama `push_autorizado` antes do `git push` (com o sha da branch enviada) | push pelo harness não sai com gate reprovado (teste com remoto real) | quem roda `git push` direto não passa por aqui |
| `pre-push` | `ops/hooks/pre-push` (instalado por `ops/install-hooks.sh`) | bloqueia `git push` comum no clone com o hook instalado; verifica o **commit de cada ref enviada** (stdin do hook), nunca o HEAD nem o diretório de trabalho | `--no-verify` (e seus prefixos) e `-c core.hooksPath=` ignoram o hook; hooks não são clonados ([git-push](https://git-scm.com/docs/git-push), [gitfaq](https://git-scm.com/docs/gitfaq)) |
| Guarda de comando (proposta) | hook PreToolUse `scripts/gates/guarda_comando.py` (`governance/freeze-patches/settings.deny-no-verify.json`) | recusa `--no-verify` e prefixos, `core.hooksPath` por `-c`/`--config-env`/`GIT_CONFIG_*`/`git config`, `SQUAD_HARNESS_RAIZ` e force push — em qualquer segmento do comando, depois de invólucros (`env`, `timeout`, `nice`, `command`…) e dentro de `bash -c`/`eval` | script em arquivo, alias, função ou outra linguagem passam por fora — não é fronteira de segurança |
| Integridade do próprio mecanismo | `scripts/gates/integridade.py` | push direto para destino abrangido que altera código/política/hook dos gates, **dependências que eles executam** (`scripts/aws/{contratos,cfn,guarda_somente_leitura}.py`, `checar_rastreados_proibidos.py`, `squad_sync.py`, `kanban/`), inicializadores de pacote, módulos `.py` da raiz ou `.gitattributes` é BLOQUEADO — inclusive promoção entre destinos (vai por PR: refs de rastreamento locais são forjáveis). O gate **não importa nem executa** código do repositório analisado | mesmo domínio de confiança do executor: bloqueia o caminho comum e deixa parte dos contornos evidente; ref forjada, script intermediário ou edição local do próprio gate não deixam rastro — a barreira é o servidor + CODEOWNERS |
| Validação remota (merge/promoção) | workflow + ruleset **propostos** em `governance/freeze-patches/` | required status check bloqueia merge e push direto na branch protegida ([docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches#require-status-checks-before-merging)) | repo **privado** de conta pessoal exige GitHub **Pro**; Actions de push/PR estão desligados por decisão de custo |
| Recepção no servidor | — | pre-receive com lógica própria só no GitHub Enterprise Server ([docs](https://docs.github.com/en/enterprise-server@latest/admin/enforcing-policies/enforcing-policy-with-pre-receive-hooks/about-pre-receive-hooks)) | github.com não oferece rejeição prévia customizada; push rulesets são regras fixas |

Nenhuma camada local "impede todo push remoto". Sem rejeição no servidor, o bloqueio fica no harness e o
merge/promoção é barrado remotamente quando o plano e a configuração do repositório permitirem. O status de
commit publicado pelo harness (`--publicar-status`, desligado por padrão) é **atestação**, não prova
inviolável: quem tem escrita pode publicar status igual; exigir fonte específica requer GitHub App.

## 7. Dependências externas e notificação

- Achado com dependência de terceiros vira tarefa `gate-dep-<chave>` em `skills/backlog.json` (status
  `BLOCKED`), com divergência, ambiente sanitizado, impacto, mudança necessária, responsável **só se
  documentado** (senão a lacuna é registrada), ordem, critério de aceite e evidência exigida.
- A tarefa só fecha quando nova execução que **cobre o escopo** dela (mesmo destino, a parte que produz o
  achado rodou **sem lacuna** — nenhuma INCONCLUSIVE/STALE geral naquela parte —, o ambiente foi comparado)
  não encontra o achado; push para outro destino ou verificação parcial não fecha nada. Exposição de
  credencial já no remoto nunca fecha sozinha (rotação é confirmação humana). Marcada DONE à mão com o achado presente → reaberta. O texto da tarefa
  (board versionado) é sanitizado e não leva os valores esperado/observado.
- Solicitação externa é preparada como texto (`dependencias.rascunho_solicitacao`); abrir chamado ou enviar
  mensagem exige integração e autorização — o gate não faz.
- Notificações deduplicadas em `.cache/gates/notificacoes.jsonl`: 1ª ocorrência completa; recorrência em uma
  linha; histórico até a resolução confirmada por nova verificação.

## 8. O que o gate NUNCA faz

DDL, DML, migrate, sincronização de bancos, `apply`/`destroy`/import/alteração de state, atualização silenciosa
de dependência, leitura de dados de negócio ou de valor de segredo, cópia de dados de produção, conexão a
ambiente não autorizado, `--no-verify`, credencial alternativa, transformar timeout/cancelamento/falta de
resposta em aprovação.
