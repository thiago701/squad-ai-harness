# Instrumentos de Navegador — `preview_*` × `claude-in-chrome`

> **Quando ler:** ao decidir/operar QUAL toolset usar, carregar o `claude-in-chrome`, montar o `launch.json`, ou depurar o que a página faz.
> **Princípio-raiz:** **text-first, pixels-for-proof.** Asserção vem do DOM/aria/console/rede; screenshot é só evidência humana.

---

## 1. Decisão: qual instrumento

| Alvo | Instrumento | Como começa |
|---|---|---|
| Dev server do **próprio projeto** (código local) | **`preview_*`** (padrão preferido) | `preview_start("<nome-do-launch>")` |
| **URL arbitrária** — staging, prod read-only, sistema de terceiro | **`claude-in-chrome`** (MCP, deferido) | carregar via `ToolSearch` → `navigate` |

Regra de ouro: **se o código está neste repositório e sobe um servidor, use `preview_*`.** Ele integra `launch.json`, HMR, logs do servidor, console do browser e rede num toolset text-first. Só caia para `claude-in-chrome` quando o alvo é uma URL que você não sobe localmente.

Nunca use `Bash` para subir o servidor de preview (ex.: `npm run dev &`) — use `preview_start`. E nunca use as ferramentas genéricas de computador para dirigir o preview do projeto quando um `preview_*` específico resolve.

---

## 2. Toolset `preview_*` (dev server do projeto)

| Ferramenta | Para quê | Assinatura essencial |
|---|---|---|
| `preview_start` | subir/reusar o dev server nomeado no `launch.json` (cria o arquivo se faltar) | `preview_start(name)` |
| `preview_list` | listar servidores rodando + obter `serverId` | `preview_list()` |
| `preview_stop` | parar um servidor | `preview_stop(serverId)` |
| `preview_logs` | stdout/stderr do **servidor** (erros de build/SSR) | `preview_logs(serverId, {level?: 'all'\|'error', search?, lines?})` |
| `preview_console_logs` | **console do navegador** (log/info/warn/error/debug) | `preview_console_logs(serverId, {level?: 'all'\|'error'\|'warn', lines?})` |
| `preview_network` | listar requisições **ou** inspecionar um corpo de resposta | `preview_network(serverId, {filter?: 'all'\|'failed', requestId?})` |
| `preview_snapshot` | **árvore de acessibilidade**: texto exato, roles, UIDs (PREFERIR a screenshot) | `preview_snapshot(serverId)` |
| `preview_inspect` | texto, classe, tag, id, **estilos computados**, bounding box de um seletor | `preview_inspect(serverId, selector, {styles?: [..]})` |
| `preview_click` | clicar num seletor CSS | `preview_click(serverId, selector, {doubleClick?})` |
| `preview_fill` | preencher input/textarea/select | `preview_fill(serverId, selector, value)` |
| `preview_resize` | viewport responsivo + emular dark mode | `preview_resize(serverId, {preset?: 'mobile'\|'tablet'\|'desktop', width?, height?, colorScheme?: 'light'\|'dark'})` |
| `preview_screenshot` | JPEG da página (**evidência**, não oráculo de estilo) | `preview_screenshot(serverId)` |
| `preview_eval` | **só depuração/inspeção** — rodar JS, ler estado, `location.reload()` | `preview_eval(serverId, expression)` |

**Presets de `preview_resize`:** `mobile` 375×812 · `tablet` 768×1024 · `desktop` 1280×800.

> ⚠️ `preview_eval` é **só para inspecionar/depurar** (ler variáveis, recarregar, disparar hover). **Não implemente correções de UI por `preview_eval`** — qualquer mudança no DOM via eval é temporária e some no reload. Corrija o **arquivo-fonte** e deixe o HMR/reload refletir.

### 2.1. `.claude/launch.json`

`preview_start(name)` sobe a configuração `name`. Se o arquivo não existir, crie-o primeiro:

```json
{
  "version": "0.0.1",
  "configurations": [
    { "name": "web", "runtimeExecutable": "npm", "runtimeArgs": ["run", "dev"], "port": 5173 }
  ]
}
```

Exemplos por stack:

```json
{ "name": "angular", "runtimeExecutable": "npm", "runtimeArgs": ["run", "start"], "port": 4200 }
{ "name": "vite",    "runtimeExecutable": "npm", "runtimeArgs": ["run", "dev"],   "port": 5173 }
{ "name": "next",    "runtimeExecutable": "npm", "runtimeArgs": ["run", "dev"],   "port": 3000 }
{ "name": "static",  "runtimeExecutable": "npx", "runtimeArgs": ["serve","-l","8080","."], "port": 8080 }
```

Inclua **apenas** os servidores que você realmente precisa previsualizar. `port` deve bater com a porta real que o comando expõe.

### 2.2. Reuso e reload

- `preview_start` **reusa** o servidor se já estiver rodando — não sobe duplicado.
- Se o framework tem **HMR** (Angular/Vite/Next), não precisa recarregar após editar o fonte.
- Sem HMR: `preview_eval(serverId, "window.location.reload()")` e re-asserte.

---

## 3. Toolset `claude-in-chrome` (URLs arbitrárias)

Está **deferido**: carregue os schemas via `ToolSearch` **antes** de chamar. Uma única chamada carrega o núcleo (a instrução do servidor MCP recomenda batelar tudo que a tarefa precisa numa só chamada):

```
ToolSearch({ query: "select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__read_console_messages,mcp__claude-in-chrome__read_network_requests,mcp__claude-in-chrome__form_input", max_results: 12 })
```

| Ferramenta (`mcp__claude-in-chrome__…`) | Para quê |
|---|---|
| `tabs_context_mcp` | contexto das abas / do browser conectado (comece por aqui) |
| `tabs_create_mcp` / `tabs_close_mcp` | abrir/fechar aba |
| `navigate` | ir para uma URL |
| `read_page` | **árvore de acessibilidade** da página (texto/role/UID) — equivalente ao `preview_snapshot` |
| `get_page_text` | texto renderizado da página |
| `find` | localizar elemento por texto/descrição |
| `computer` | ações genéricas (mover/clicar/digitar/screenshot/scroll) por coordenada/UID |
| `form_input` | preencher campos de formulário |
| `file_upload` / `upload_image` | anexar arquivo/imagem |
| `read_console_messages` | console do navegador (erros de JS) |
| `read_network_requests` | requisições de rede (status, payload) |
| `javascript_tool` | rodar JS na página (**só inspeção/depuração**, como o `preview_eval`) |
| `resize_window` | redimensionar a janela (responsivo) |
| `gif_creator` | gravar um GIF do fluxo (evidência de jornada) |
| `list_connected_browsers` / `select_browser` / `switch_browser` | escolher o browser conectado |

**Pré-condição:** um browser precisa estar **conectado** ao MCP. Se `list_connected_browsers`/`tabs_context_mcp` não retornar browser, a validação ao vivo está **indisponível** — reporte INDISPONÍVEL (não PRONTO). Ver `codificar-playwright.md §CI`.

---

## 4. Text-first, pixels-for-proof — operacionalizado

| Quero asserir… | Ferramenta certa | Ferramenta ERRADA |
|---|---|---|
| Texto/estrutura/roles presentes | `preview_snapshot` / `read_page` | screenshot |
| Cor, fonte, padding, tamanho, posição | `preview_inspect` (estilos computados + bounding box) | screenshot (JPEG não prova cor) |
| Erro de JavaScript ocorreu | `preview_console_logs` / `read_console_messages` (`level: error`) | "parece ok na foto" |
| API respondeu certo | `preview_network` / `read_network_requests` (`filter: failed`) | assumir pelo texto |
| Estado mudou após clicar | novo `preview_snapshot` e comparar | screenshot |
| **Evidência humana** do resultado | `preview_screenshot` / `gif_creator` | — |

> A árvore de acessibilidade (`preview_snapshot`/`read_page`) é **melhor que screenshot** para verificar texto e presença de elementos: devolve o texto exato e os roles, sem você adivinhar de pixels.

---

## 5. Fluxo de depuração (quando um eixo falha)

Ordem determinística para achar a causa antes de tocar o código:

```
1. preview_console_logs (level: error)  → há erro de JS/stack trace?
2. preview_network (filter: failed)      → alguma requisição 4xx/5xx/pendurada?
3. preview_logs (level: error)           → o SERVIDOR logou erro de build/SSR?
4. preview_snapshot / preview_inspect    → o elemento existe? qual o estado/estilo real?
5. preview_eval (só para inspecionar)    → ler window/estado do app, confirmar hipótese
6. Ler o CÓDIGO-FONTE                     → diagnosticar a causa raiz
7. Editar o arquivo-fonte + re-validar    → NUNCA corrigir por eval (some no reload)
```

Achado 🔴 só é válido com a **evidência observada** desse fluxo (texto do erro, URL+status, seletor+valor) — nunca "talvez haja um problema".

---

## 6. Erros comuns

- **Subir servidor que não prova nada.** Se a mudança não é observável no browser, não rode `preview_start`. Diga e devolva ao especialista certo.
- **Screenshot como oráculo de estilo.** JPEG comprimido → use `preview_inspect`.
- **Esquecer de carregar `claude-in-chrome` via `ToolSearch`** antes de chamar (InputValidationError).
- **Corrigir bug via `preview_eval`.** Temporário; some no reload. Corrija o fonte.
- **Digitar segredo real** num formulário. Use dados de teste; screenshot pode vazar o que está na tela.
