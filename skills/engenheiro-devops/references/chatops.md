# engenheiro-devops · ChatOps (Microsoft Teams como exemplo)
> Quando carregar: operar deploy, rollback, status ou incidente por chat (Microsoft Teams, bot, webhook, Adaptive Cards), desenhar o fluxo de aprovação de produção no canal, trilha de auditoria de comandos, segregação solicitante/aprovador ou limites de segurança do bot.

ChatOps é uma **interface** sobre o pipeline gated, não um atalho em volta dele: o chat pede, o pipeline executa, a máquina de estados
(`contracts/pipeline-state-machine.json`) decide se pode e a evidência volta ao canal. Tudo aqui é descrito como contrato — sem credencial.

## Arquitetura e fronteiras
Contexto: a estação de trabalho só alcança o GitHub pelo proxy, então o bot **não** roda nela; ele roda na infra do banco e fala com o GitHub.

```
Teams (canal) ─comando─▶ Bot (infra do banco) ─workflow_dispatch─▶ GitHub Actions (environment com revisores)
     ▲  Adaptive Card       valida identidade, schema, autorização, incidente, rate limit
     └─────── evidência ◀── grava auditoria (JSONL append-only) ◀── resultado do run
```
- **Webhook** (entrada) só **posta** no canal; comando bidirecional e botão de aprovar exigem **bot** (Bot Framework/Azure Bot Service) ou *outgoing webhook*.
  Cartões via Incoming Webhook suportam todos os elementos nativos do Adaptive Card exceto `Action.Submit`; ações aceitas: `Action.OpenUrl`, `Action.ShowCard`, `Action.ToggleVisibility` e `Action.Execute` (Microsoft Learn, Teams "Cards reference", consultado em 11/10/2026). Como `Action.Execute` exige um bot para receber o invoke `adaptiveCard/action`, o card de aprovação sai do bot.
- Os *Office 365 Connectors* do Teams foram aposentados: anúncio em 03/07/2024, URLs de webhook tiveram de migrar para o novo formato até 31/01/2025 e o desligamento final rodou de 18 a 22/05/2026 (Microsoft 365 Developer Blog, "Retirement of Office 365 connectors within Microsoft Teams", atualizado em 05/02/2026). O mecanismo vigente é o **Workflows** (Power Automate) com gatilho de webhook; limitações documentadas: a mensagem sai com a identidade do bot Workflows (sem ícone/nome próprios) e MessageCard não aceita botões HttpPost — use Adaptive Card. Se o tenant do banco bloquear Workflows por política, a entrada é pelo bot.
  Gatilhos, ações, **licenciamento (HTTP/Request/HTTP with Entra ID são Premium no Power Automate)**, limites e padrões de fluxo: `chatops-power-automate.md`.
- Tokens do bot, URL de webhook e credenciais do GitHub são **segredos no cofre**; nunca em payload, card, log ou repositório.

## Comandos
Contexto: catálogo fechado; qualquer texto fora dele é rejeitado e auditado. Não existe comando destrutivo na v1.

| Comando | Efeito | Natureza | Aprovação |
|---|---|---|---|
| `status [svc]` | versão, último deploy, alarmes | leitura | não |
| `deploy <env> <svc> <versao>` | dispara workflow com a versão **assinada** | mutação | dev/hml: solicitante autorizado · **prod: aprovação nominal** |
| `rollback <env> <svc>` | redeploy da versão anterior assinada | mutação | idem; em prod, mesmo em incidente |
| `incidente abrir <svc> <sev>` | cria ticket (Jira) e ponte; liga modo somente-leitura do serviço | registro | não |
| `incidente fechar <id>` | exige resumo e causa; desliga o modo | registro | comandante do incidente |

## Comando → máquina de estados → aprovação
Contexto: a máquina decide transições do pipeline gated; `aprovacao_humana` não é um estado, é o **parâmetro** de `validar_transicao`
(`contracts/validator.py`). Para produção, o deploy aprovado equivale a `gate2_pendente --gate_aprovado--> commit`.

1. **Comando:** `deploy prod api-exemplo 3f9a1c2`. O bot valida schema, identidade, grupo "pode pedir", modo incidente e rate limit; gera `correlation_id`.
   Pré-requisito: build, testes, `05b-veracode.md` e gate de severidade verdes para o SHA (`references/devsecops.md`).
2. **Pedido de aprovação:** card no canal de aprovação com serviço, versão, gates, `achados_criticos`, solicitante e `expira_em`.
3. **Aprovação nominal:** o bot confere a identidade do clique (ID do Teams, não o texto), grupo `aprovadores-prod`, `aprovador ≠ solicitante`, prazo, uso único do
   `correlation_id`. Só então `validar_transicao("gate2_pendente","gate_aprovado", aprovacao_humana=True, achados_criticos=<n>)`; exige `PERMITIDA`.
4. **Execução:** `workflow_dispatch` com inputs validados; o job usa OIDC e *environment* `production` com revisores obrigatórios e "prevent self-review"
   (segunda trava, independente do bot).
5. **Evidência de volta:** card final com resultado, `run_url`, versão antes/depois, estado dos alarmes e `correlation_id`.

| Situação | Evento na máquina | Resultado |
|---|---|---|
| Aprovado por humano, `achados_criticos=0` | `gate_aprovado` | `PERMITIDA` → `commit` |
| Sem aprovação humana | `gate_aprovado` sem humano | `REQUER_GATE_HUMANO` — não executa |
| `achados_criticos > 0` | `gate_aprovado` | `PROIBIDA` para `commit` |
| Rejeitado | `gate_reprovado` | volta a `tdd`; motivo auditado |
| Cancelado ou expirado | `abortar` | `abortado`; auditado |

`rollback prod` abre um novo pedido pelo mesmo caminho (versão anterior assinada e já implantada); `incidente *` registra, não transita o pipeline.

## Contratos de payload
Contexto: três mensagens com schema versionado; nenhuma carrega segredo (IDs vêm do IdP, valores sensíveis do cofre).

```json
{"schema": "chatops-comando/v1", "comando": "deploy", "ambiente": "prod", "servico": "api-exemplo",
 "versao": "3f9a1c2", "solicitante": {"id": "<object-id-do-solicitante>"},
 "correlation_id": "0b7e7c0e-9a9e-4f55-8a3c-2f6f4a1d5b10", "solicitado_em": "2026-10-11T14:03:22Z"}
```

```json
{"type": "AdaptiveCard", "version": "1.4",
 "body": [{"type": "TextBlock", "weight": "Bolder", "text": "Aprovação de deploy em PRODUÇÃO"},
  {"type": "FactSet", "facts": [
    {"title": "Serviço", "value": "api-exemplo"}, {"title": "Versão", "value": "3f9a1c2 (assinada)"},
    {"title": "Gates", "value": "Veracode · severidade · SBOM"}, {"title": "Expira em", "value": "2026-10-11T14:33:22Z"}]}],
 "actions": [
  {"type": "Action.Execute", "title": "Aprovar", "verb": "aprovar", "data": {"correlation_id": "0b7e7c0e-9a9e-4f55-8a3c-2f6f4a1d5b10"}},
  {"type": "Action.Execute", "title": "Rejeitar", "verb": "rejeitar", "data": {"correlation_id": "0b7e7c0e-9a9e-4f55-8a3c-2f6f4a1d5b10"}}]}
```
(`Action.Execute` pertence ao *Universal Action Model*, introduzido no schema 1.4 do Adaptive Cards; o Teams suporta até a versão 1.6 em desktop e mobile, e a Microsoft recomenda `fallback` para `Action.Submit` em clientes antigos — Microsoft Learn, "Universal Action Model" e Teams "Cards reference", consultados em 11/10/2026.)

```json
{"ts": "2026-10-11T14:10:07Z", "correlation_id": "0b7e7c0e-9a9e-4f55-8a3c-2f6f4a1d5b10", "evento": "executado",
 "comando": "deploy", "ambiente": "prod", "servico": "api-exemplo", "versao": "3f9a1c2", "resultado": "sucesso",
 "solicitante": {"id": "<object-id>"}, "aprovador": {"id": "<object-id>"}, "run_url": "<url-do-run>"}
```
Eventos de auditoria: `solicitado`, `aprovado`, `negado` (com `motivo`), `expirado`, `executado`, `falhou`, `rollback_automatico`.

Schema e teste de contrato (o teste roda no CI do bot; qualquer mudança de payload quebra aqui antes de chegar ao canal):

```json
{"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "chatops-comando/v1",
 "type": "object", "additionalProperties": false,
 "required": ["schema", "comando", "ambiente", "solicitante", "correlation_id", "solicitado_em"],
 "properties": {
  "schema": {"const": "chatops-comando/v1"},
  "comando": {"enum": ["status", "deploy", "rollback", "incidente_abrir", "incidente_fechar"]},
  "ambiente": {"enum": ["dev", "hml", "prod"]},
  "servico": {"type": "string", "pattern": "^[a-z0-9-]{1,63}$"},
  "versao": {"type": "string", "pattern": "^([0-9a-f]{7,40}|v?[0-9]+\\.[0-9]+\\.[0-9]+)$"},
  "solicitante": {"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}}},
  "correlation_id": {"type": "string", "pattern": "^[0-9a-f-]{36}$"},
  "solicitado_em": {"type": "string"}}}
```

```python
# test_contrato.py — payload válido passa; fora do catálogo é rejeitado; nenhuma chave parece credencial
import json, re, jsonschema
SCHEMA = json.load(open("comando.schema.json"))
PROIBIDAS = re.compile(r"token|secret|senha|password|authorization|apikey|credential", re.I)

def chaves(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k; yield from chaves(v)
    elif isinstance(o, list):
        for v in o: yield from chaves(v)

def test_valido_e_sem_credencial():
    p = json.load(open("exemplo-deploy-prod.json"))
    jsonschema.validate(p, SCHEMA)
    assert not [k for k in chaves(p) if PROIBIDAS.search(k)]

def test_rejeita_comando_fora_do_catalogo():
    p = json.load(open("exemplo-deploy-prod.json")); p["comando"] = "drop-database"
    try: jsonschema.validate(p, SCHEMA); assert False
    except jsonschema.ValidationError: pass
```

## Permissões e segregação
Contexto: papéis vêm de grupos do IdP, contas são nominais (sem conta compartilhada) e revisadas periodicamente; autor/revisor/aprovador de produção seguem
`references/frameworks-ti.md § Segregação de ambientes e de funções` — a tabela abaixo cobre só o que é específico do bot.

| Papel | Pode | Não pode |
|---|---|---|
| Leitor | `status` | qualquer mutação |
| Solicitante | `deploy`/`rollback` em dev/hml; **pedir** prod | aprovar o próprio pedido |
| Aprovador de prod | aprovar/rejeitar pedido de prod | ser solicitante do mesmo pedido |
| Comandante de incidente | `incidente fechar`; aprovar rollback durante incidente | aprovar pedido que ele mesmo abriu |
| Administrador do bot | catálogo, limites, grupos | executar ou aprovar produção |

**Nunca a mesma pessoa em produção**, verificado em três pontos independentes: no bot (`ids` distintos), no *environment* do GitHub ("prevent self-review") e na
auditoria (consulta abaixo). Conta de serviço não aprova.

## Limites de segurança
Contexto: o bot é superfície de ataque; cada limite abaixo é testável.
- **Destrutivo:** não há no catálogo. Se um dia entrar (delete, purge, scale-to-zero), exige confirmação em **duas etapas** (digitar serviço+ambiente no card **e**
  aprovação de outra pessoa) e passa por `validar_escalonamento` (operação destrutiva sem confirmação humana = `BLOQUEADA`).
- **Rate limit** por usuário e por serviço (valor definido pelo dono do bot); excedeu = `negado`, motivo `rate_limit`, auditado.
- **Modo somente-leitura em incidente:** com incidente aberto no serviço, só `status` e `incidente *`; `deploy` retorna `negado: incidente_aberto`;
  `rollback` só com aprovação do comandante ≠ solicitante.
- **Anti-replay:** `correlation_id` de uso único; pedido expira; clique repetido não reexecuta.
- **Entrada é dado:** serviço em allowlist, versão por regex (SHA ou SemVer), sem interpolação em shell; texto livre do canal nunca é interpretado como comando.
  Se um LLM ajudar a entender a frase, ele só **propõe** o comando estruturado e o humano confirma (contrato em `references/ia-devops-aiops.md`).

## Oráculo — como provar que foi feito
- **Teste de contrato do payload** verde (`pytest`): comando válido passa no schema `chatops-comando/v1`, comando fora do catálogo é rejeitado e nenhuma chave
  casa `token|secret|senha|password|authorization|apikey|credential`.
- **Auditoria medida no log:** a consulta abaixo devolve `0` violações (todo `executado` em prod tem aprovador presente e diferente do solicitante).
- **Conciliação:** todo run de deploy de prod tem linha de auditoria; diferença vazia (deploy fora do ChatOps é detectado).
- **Negativos:** auto-aprovação vira `negado` (`auto_aprovacao`); `validar_transicao(..., aprovacao_humana=False)` devolve `REQUER_GATE_HUMANO`; em incidente, `deploy` é negado.
- **Fluxo completo em hml:** comando → card → aprovação → execução → card de evidência, com o mesmo `correlation_id` nas linhas `solicitado`, `aprovado`, `executado` e no card.

```bash
# violações = execuções em prod sem aprovador ou com aprovador == solicitante (esperado: 0)
jq -s -e '[.[] | select(.ambiente=="prod" and .evento=="executado")
          | select(.aprovador == null or .aprovador.id == .solicitante.id)] | length == 0' auditoria.jsonl
# conciliação: runs de deploy de prod sem trilha (esperado: saída vazia)
gh run list --workflow deploy-prod.yml --limit 200 --json databaseId --jq '.[].databaseId' | sort > runs.txt
jq -r 'select(.evento=="executado" and .ambiente=="prod") | .run_url | split("/") | last' auditoria.jsonl | sort > trilha.txt
comm -23 runs.txt trilha.txt
```

## Anti-padrões
- **Bot onipotente:** token do bot com permissão ampla de AWS/GitHub em vez de role mínima por ambiente.
- **Auto-aprovação:** solicitante (ou conta compartilhada/de serviço) clica "Aprovar".
- **"ok" no chat:** aprovação por texto sem identidade verificada nem `correlation_id`.
- **Webhook como cofre:** URL de webhook ou token em repositório, card ou log.
- **Comando livre:** bot que interpreta frase e executa shell, sem catálogo nem allowlist.
- **Execução muda:** deploy sem card de evidência de volta ao canal.
- **Trilha no Teams:** usar o histórico do chat (editável, retenção alheia) em vez de log append-only.
- **Deploy em incidente:** permitir `deploy` normal com incidente aberto, sem freeze.

## Checklist de banco
- [ ] Bot hospedado na infra do banco e aprovado por Segurança; a estação de trabalho não executa nada e só alcança o GitHub.
- [ ] Produção apenas com aprovação nominal ≠ solicitante, dentro da janela de mudança; nenhum comando destrutivo no catálogo.
- [ ] Papéis por grupo do IdP, contas nominais, revisão periódica de membros do grupo de aprovadores.
- [ ] Tokens, webhooks e credenciais no cofre, com rotação; nada em payload, card, log ou repositório.
- [ ] Trilha append-only (quem, quando, o quê, resultado, `correlation_id`) retida pelo prazo da política do banco (valor fornecido por Compliance e registrado no runbook; nunca prazo de memória).
- [ ] Ambientes dev/hml/prod segregados (roles distintas); dados sensíveis fora de comandos e cards.
