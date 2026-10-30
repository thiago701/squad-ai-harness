# Layout, Responsivo, Dark Mode e Acessibilidade (Eixos 6–8)

> **Quando ler:** ao aprofundar a validação visual, de responsividade e de acessibilidade ao vivo.
> **Restrição real:** você valida com o que o navegador já expõe (DOM/estilos computados/árvore de acessibilidade). Não dependa de injetar libs externas (axe-core via CDN) — CSP e a Linha de Defesa desaconselham carregar/rodar script de terceiro.

---

## §Layout — regressão visual (Eixo 6)

O que **screenshot prova**: nada com precisão (JPEG comprimido). Serve de âncora visual para o humano.
O que **prova de verdade**: `preview_inspect` (estilos computados + bounding box) e checagens de DOM.

Checagens determinísticas:

```
# Scroll horizontal do body (quebra clássica de responsivo)
preview_eval(serverId, "document.documentElement.scrollWidth > window.innerWidth")   → deve ser false

# Overflow / corte de um container
preview_inspect(serverId, ".card", {styles:["overflow","width","height"]})

# Sobreposição: comparar bounding boxes de dois elementos que não deviam colidir
preview_inspect(serverId, "header")   → box A
preview_inspect(serverId, "main")     → box B  (A.bottom <= B.top?)

# Elemento visível e com tamanho > 0
preview_inspect(serverId, "[data-testid=cta]", {styles:["display","visibility","opacity"]})
```

**Falha 🔴:** `scrollWidth > innerWidth` (body rola lateral); conteúdo essencial `display:none`/`opacity:0` sem intenção; boxes sobrepostos escondendo texto; container com `overflow` cortando conteúdo crítico.

**Anti-padrão:** aprovar layout "porque a screenshot parece ok". Meça as caixas.

---

## §Responsivo — breakpoints (Eixo 7)

`preview_resize` emula viewport e esquema de cor. Presets: `mobile` 375×812, `tablet` 768×1024, `desktop` 1280×800. Também aceita `width`/`height` custom.

Bateria mínima:

```
preview_resize(serverId, {preset:"mobile"})
preview_snapshot(serverId)     → menu/hambúrguer acessível? conteúdo empilha? CTA visível?
preview_eval(serverId, "document.documentElement.scrollWidth > window.innerWidth")  → false

preview_resize(serverId, {preset:"tablet"})
preview_snapshot(serverId)

preview_resize(serverId, {preset:"desktop"})
preview_snapshot(serverId)
```

Para URL externa: `mcp__claude-in-chrome__resize_window`.

**Falha 🔴:** navegação some no mobile sem alternativa; conteúdo exige scroll horizontal; toque/target < 24px em controle essencial; texto sobreposto ao reduzir.

### Dark mode

```
preview_resize(serverId, {preset:"desktop", colorScheme:"dark"})
preview_inspect(serverId, "body", {styles:["color","background-color"]})   → há contraste real?
preview_snapshot(serverId)                                                 → nada "sumiu" no escuro
```

**Falha 🔴:** texto e fundo com contraste insuficiente no dark; elementos "brancos em branco"/"pretos em preto"; ícones invisíveis.

---

## §Acessibilidade — spot-check WCAG 2.2 (Eixo 8)

Não é auditoria completa (isso é trabalho dedicado do frontend). É um **spot-check** dos itens de maior risco, feito com o que o navegador expõe.

### 1. Nome acessível de todo controle interativo
A árvore de acessibilidade (`preview_snapshot` / `read_page`) já traz `role` + `name`. Varra: todo `button`, `link`, `textbox`, `checkbox` tem **nome** não vazio?

```
preview_snapshot(serverId)   → procure controles com name vazio (ícone sem aria-label, input sem <label>)
```
**Falha 🔴 (WCAG 4.1.2):** controle interativo sem nome acessível.

### 2. Navegação e foco por teclado
```
preview_eval(serverId, "document.activeElement && document.activeElement.outerHTML.slice(0,80)")
# dispare Tab e re-leia o activeElement para conferir a ordem e se o foco não fica preso
```
**Falha 🔴 (WCAG 2.1.2):** armadilha de foco (não sai de um modal por teclado); foco invisível; ordem de tab ilógica.

### 3. Estrutura semântica
```
preview_eval(serverId, "[...document.querySelectorAll('h1,h2,h3')].map(h=>h.tagName+':'+h.textContent.trim()).slice(0,20)")
preview_eval(serverId, "[...document.querySelectorAll('main,nav,header,footer,[role]')].length")
```
**Falha 🟡→🔴:** sem `<h1>`; saltos de nível (h1→h3); ausência de landmarks (`main`/`nav`).

### 4. Contraste (checagem pontual)
```
preview_inspect(serverId, "<seletor de texto>", {styles:["color","background-color","font-size","font-weight"]})
```
Calcule a razão de contraste dos valores retornados. Mínimo WCAG AA: **4.5:1** (texto normal), **3:1** (texto grande ≥ 18.66px bold / 24px).
**Falha 🔴 (WCAG 1.4.3):** texto essencial abaixo do mínimo.

### 5. Imagens e formulários
```
preview_eval(serverId, "[...document.images].filter(i=>!i.alt).length")            → imagens sem alt
preview_eval(serverId, "[...document.querySelectorAll('input,select,textarea')].filter(e=>!e.labels?.length && !e.getAttribute('aria-label')).length")  → campos sem label
```
**Falha 🔴:** imagem informativa sem `alt` (WCAG 1.1.1); campo de formulário sem label associado (WCAG 3.3.2).

### 6. Alvos de Toque e Clique — WCAG 2.2 SC 2.5.8 (Target Size Minimum $\ge 24\times 24\text{px}$)
Controles interativos não podem ser minúsculos. No desktop/geral o piso normativo WCAG 2.2 AA é **$24\times 24\text{px}$**; no mobile a ergonomia motora (Thumb Zone) recomenda **$44\times 44\text{px}$**:
```
preview_eval(serverId, "[...document.querySelectorAll('button,a,input,select,[role=button]')].map(el=>{const r=el.getBoundingClientRect();return {sel:el.tagName,w:Math.round(r.width),h:Math.round(r.height)}}).filter(x=>x.w>0 && (x.w<24 || x.h<24))")
```
**Falha 🔴 (WCAG 2.5.8):** controle interativo visível com largura ou altura `< 24px`.
**Atenção 🟡 (Ergonomia Mobile):** controle primário no mobile `< 44px`.

### 7. Foco Não Obscurecido — WCAG 2.2 SC 2.4.11 (Focus Not Obscured)
Ao navegar com `Tab`, o elemento focado (`document.activeElement`) **não pode ficar escondido** atrás de `header` sticky, `footer` fixo, barra de cookies ou FAB flutuante:
```
preview_eval(serverId, "(() => { const f = document.activeElement?.getBoundingClientRect(); const s = [...document.querySelectorAll('header,footer,[data-sticky]')].map(e=>e.getBoundingClientRect()); return {focused: f, sticky: s}; })()")
```
**Falha 🔴 (WCAG 2.4.11):** interseção geométrica onde um overlay fixo/sticky encobre totalmente (ou parte crítica de) `document.activeElement`.

### 8. Alinhamento de Grade (Subgrid) e Vazamento de Style Guide
Em grades de cards (`display: grid`), cards na mesma linha horizontal (`Math.abs(a.top - b.top) <= 4`) devem terminar na mesma base (`Math.abs(a.bottom - b.bottom) <= 2`, garantido via `grid-template-rows: subgrid`). Além disso, inspecione se há vazamento de estilos inline mágicos (`style="color: #..."`) violando os Design Tokens.

### 9. Verificador Determinístico de Snapshot DOM (`scripts/verificador_ui_dom.py`)
Para julgar automaticamente as caixas coletadas por `preview_inspect` / `preview_eval`, execute:
```bash
python skills/validador-navegador/scripts/verificador_ui_dom.py --snapshot dom_snapshot.json
```
O script calcula interseção 2D de foco contra overlays sticky (WCAG 2.4.11), valida tamanho de alvos (WCAG 2.5.8), detecta overflow horizontal, verifica alinhamento de cards na mesma linha e emite veredito estruturado `PRONTO` ou `NAO_PRONTO`.

> `preview_eval`/`javascript_tool` aqui são **inspeção** (leem o DOM), não correção. Nunca "conserte" a a11y por eval — corrija o **componente-fonte** (o `especialista-frontend` é o dono da correção) e re-valide.

---

## Contribuição para o veredito

| Eixo | 🔴 bloqueante típico | 🟡 atenção típico |
|---|---|---|
| 6 Layout | body rola horizontal; conteúdo cortado; colisão de caixas | cards da mesma linha desalinhados (falta `subgrid`) |
| 7 Responsivo | nav some no mobile; dark ilegível; alvo `< 24px` (WCAG 2.5.8) | alvo mobile entre `24px` e `43px`; breakpoint feio |
| 8 A11y | controle sem nome; armadilha de foco; foco encoberto por sticky (WCAG 2.4.11); contraste < AA | falta landmark; ordem de heading; estilo inline mágico |

Um 🔴 em qualquer eixo → **NÃO PRONTO**. Correções de a11y/visual voltam ao `especialista-frontend`; a codificação de um teste de regressão visual/a11y volta ao `especialista-qualidade`.
