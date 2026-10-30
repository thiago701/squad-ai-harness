# Protocolo de Validação — 8 Eixos + Veredito

> **Quando ler:** ao executar a bateria de validação ao vivo e emitir o veredito.
> **Princípio:** valide **comportamento observável**, não existência. `200 OK` com erro no console = falha.

Notação: as chamadas abaixo usam `preview_*` (projeto próprio). Para URL externa, o equivalente `claude-in-chrome` está entre colchetes.

---

## Eixo 1 — Smoke / Carga

**Exerce:** a página abre, o root renderiza, não há tela branca nem erro fatal de boot.

```
preview_start("web")            [claude-in-chrome: navigate(url)]
preview_snapshot(serverId)      [read_page] → o root tem conteúdo? (não vazio/spinner infinito)
preview_console_logs(serverId, {level:"error"})  → zero erro fatal de boot
preview_logs(serverId, {level:"error"})          → o servidor não caiu no build/SSR
```

**Falha 🔴:** snapshot vazio/só spinner; erro fatal no console; servidor 500 no boot.

## Eixo 2 — Jornada feliz (crítica, ponta a ponta)

**Exerce:** o fluxo de negócio principal completo (ex.: login → criar recurso → ver na lista → abrir detalhe).

```
Para cada passo:
  preview_click(serverId, "<seletor>")  / preview_fill(serverId, "<seletor>", "<valor teste>")
  preview_snapshot(serverId)  → ASSERTE que o estado mudou (texto/rota/lista esperada apareceu)
```

**Falha 🔴:** a jornada não completa; um passo não avança; o resultado final não aparece no DOM.
Capture um `preview_screenshot` (ou `gif_creator`) do estado final como evidência.

## Eixo 3 — Formulário & input inválido

**Exerce:** validação client-side, mensagens de erro, e os estados **vazio / carregando / erro**.

```
preview_fill(serverId, "#campo", "<inválido: vazio, formato errado, limite+1>")
preview_click(serverId, "button[type=submit]")
preview_snapshot(serverId)  → a mensagem de erro esperada apareceu? o submit foi bloqueado?
# repetir com entrada VÁLIDA → deve avançar
```

**Falha 🔴:** aceita inválido; não mostra erro; ou trava mesmo com entrada válida.
Aplique os limites do `especialista-qualidade`: `0, 1, MAX, MAX+1`, nulo/vazio, formato errado.

## Eixo 4 — Console / erros de JS

**Exerce:** nenhum erro de JavaScript durante toda a sessão.

```
preview_console_logs(serverId, {level:"error"})   [read_console_messages]
```

**Falha 🔴:** qualquer `error` (não-warning) disparado durante o fluxo. Warning = 🟡.
Registre o **texto do erro + stack** como prova.

## Eixo 5 — Rede / saúde de API

**Exerce:** as requisições que a jornada dispara respondem certo.

```
preview_network(serverId, {filter:"failed"})   → lista 4xx/5xx e erros de rede
preview_network(serverId, {requestId:"<id>"})  → inspeciona o corpo de uma resposta específica
```

**Falha 🔴:** requisição crítica 4xx/5xx, pendurada (sem resposta), ou payload de erro.
Registre **método + URL + status** de cada falha.

## Eixo 6 — Layout / regressão visual

**Exerce:** elementos posicionados, sem overflow/corte, sem sobreposição, sem scroll horizontal do body.

```
preview_inspect(serverId, "<seletor>", {styles:["overflow","width","position"]})  → estilos reais
preview_eval(serverId, "document.documentElement.scrollWidth > window.innerWidth")  → há scroll horizontal? (inspeção)
preview_screenshot(serverId)  → evidência humana do layout
```

**Falha 🔴:** conteúdo cortado/quebrado; body rola horizontal; elementos sobrepostos.
Detalhe em `acessibilidade-responsivo.md §Layout`.

## Eixo 7 — Responsivo & dark mode

**Exerce:** o layout sobrevive a mobile/tablet/desktop e ao dark mode.

```
preview_resize(serverId, {preset:"mobile"})   → re-snapshot + re-screenshot
preview_resize(serverId, {preset:"tablet"})
preview_resize(serverId, {preset:"desktop", colorScheme:"dark"})   [claude-in-chrome: resize_window]
```

**Falha 🔴:** quebra em viewport comum; conteúdo inacessível no mobile; dark mode ilegível.
Detalhe em `acessibilidade-responsivo.md §Responsivo`.

## Eixo 8 — Acessibilidade (spot-check)

**Exerce:** navegação por teclado, nomes acessíveis, semântica, contraste.

```
preview_snapshot(serverId)  → todo controle interativo tem NOME acessível (role + name)?
preview_inspect(serverId, "<botão>", {styles:["color","background-color"]})  → contraste ≥ 4.5:1?
preview_eval(serverId, "document.activeElement.tagName")  → foco navega e não fica preso?
```

**Falha 🔴:** armadilha de foco; controle sem nome acessível; contraste abaixo do mínimo em texto essencial.
Detalhe em `acessibilidade-responsivo.md §Acessibilidade`.

---

## Regras de execução

1. **Ordem + fail-fast.** Rode 1→8; pare na primeira falha bloqueante **para reportar**, mas colete o máximo de evidência antes.
2. **Text-first.** Toda asserção vem de snapshot/inspect/console/network. Screenshot é evidência, não asserção.
3. **Re-asserção após ação.** Depois de `click`/`fill`, um **novo** `preview_snapshot` confirma a mudança de estado. Não presuma.
4. **Prova obrigatória por 🔴.** Seletor/URL/status real + log/screenshot. Sem prova, não é achado.
5. **Diagnóstico no fonte.** Bug encontrado → leia o código, corrija o **arquivo**, re-valide o eixo. Nunca corrija por `eval`.

---

## Veredito padronizado (canônico)

```
═══════════════════════════════════════════
  VALIDAÇÃO DE NAVEGADOR — <alvo/URL> — <data>
  Instrumento: preview_* | claude-in-chrome   Viewport: <preset>
═══════════════════════════════════════════
  1. Smoke / Carga ............ ✅ / ❌
  2. Jornada feliz ............ ✅ / ❌  (<fluxo exercido>)
  3. Formulário & inválido .... ✅ / ❌
  4. Console (erros JS) ....... ✅ / ❌  (N erros)
  5. Rede / API ............... ✅ / ❌  (N req falhas)
  6. Layout / visual .......... ✅ / ❌
  7. Responsivo & dark ........ ✅ / ❌
  8. Acessibilidade ........... ✅ / ❌

  Achados:
    🔴 <bloqueante — seletor/URL/status + evidência>
    🟡 <atenção>

  ─────────────────────────────────────────
  VEREDITO: PRONTO ✅   |   NÃO PRONTO ❌
  ─────────────────────────────────────────
```

Regra: **um único 🔴 = NÃO PRONTO** (idêntica ao `verificacao-loop`). 🟡/🔵/⚪ não bloqueiam.

---

## Exemplo end-to-end — validar um Task Manager (login → criar → concluir)

Cenário: app web local com login, criação de tarefa e marcação de concluída.

```
# Setup
preview_start("web")                     → serverId = "srv_1"
preview_snapshot("srv_1")                → vê form de login (roles: textbox "email", textbox "senha", button "Entrar")

# Eixo 1 — Smoke
preview_console_logs("srv_1",{level:"error"})   → 0 erros ✅

# Eixo 2 — Jornada feliz
preview_fill("srv_1", "#email", "teste@exemplo.dev")     # dado de TESTE, nunca real
preview_fill("srv_1", "#senha", "senha-de-teste-123")
preview_click("srv_1", "button[type=submit]")
preview_snapshot("srv_1")                → rota /tarefas, heading "Minhas Tarefas" apareceu ✅
preview_click("srv_1", "[data-testid=nova-tarefa]")
preview_fill("srv_1", "#titulo", "Comprar café")
preview_click("srv_1", "[data-testid=salvar]")
preview_snapshot("srv_1")                → item "Comprar café" na lista ✅
preview_click("srv_1", "[data-testid=concluir-0]")
preview_snapshot("srv_1")                → item marcado como concluído (aria-checked=true) ✅

# Eixo 4 + 5 — Console + Rede durante a jornada
preview_console_logs("srv_1",{level:"error"})   → 0 ✅
preview_network("srv_1",{filter:"failed"})       → 0 falhas (POST /tarefas = 201) ✅

# Eixo 7 — Responsivo + dark
preview_resize("srv_1",{preset:"mobile"})        → lista legível, botão visível ✅
preview_resize("srv_1",{preset:"desktop",colorScheme:"dark"})  → contraste ok ✅

# Evidência
preview_screenshot("srv_1")              → foto do estado final
```

Veredito resultante:

```
═══════════════════════════════════════════
  VALIDAÇÃO DE NAVEGADOR — localhost:5173 (Task Manager) — 2026-07-05
  Instrumento: preview_*   Viewport: mobile+desktop/dark
═══════════════════════════════════════════
  1. Smoke / Carga ............ ✅
  2. Jornada feliz ............ ✅  (login → criar tarefa → concluir)
  3. Formulário & inválido .... ✅  (título vazio bloqueado; erro exibido)
  4. Console (erros JS) ....... ✅  (0 erros)
  5. Rede / API ............... ✅  (0 falhas; POST /tarefas 201)
  6. Layout / visual .......... ✅
  7. Responsivo & dark ........ ✅
  8. Acessibilidade ........... 🟡  (checkbox de concluir sem label textual — nome só por ícone)

  Achados:
    🟡 [data-testid=concluir-0] não tem nome acessível textual (aria-label ausente).

  ─────────────────────────────────────────
  VEREDITO: PRONTO ✅   (com 1 atenção 🟡 a corrigir em seguida)
  ─────────────────────────────────────────
```

Próximo passo: como a jornada login→criar→concluir é **crítica**, codifique-a em Playwright durável e entregue ao `especialista-qualidade` → ver `codificar-playwright.md`.
