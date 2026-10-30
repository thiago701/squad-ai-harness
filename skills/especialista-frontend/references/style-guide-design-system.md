# Style Guide, Design System Architecture, CSS Baseline 2025/2026 e Doutrina Frontend Designer

> **Quando ler:** ao estruturar tokens de design (W3C DTCG), construir ou auditar um Style Guide, escolher paleta perceptual (OKLCH), aplicar primitivas modernas de CSS zero-JS ou elevar o acabamento visual de interfaces contra o anti-padrão de "AI Slop".
> **Princípios governantes:** P1-Simplicidade > P2-Performance > P3-CustoBaixo. O Style Guide é a única fonte de verdade visual do ecossistema; nenhum valor de cor, espaçamento, raio ou tipografia deve ser arbitrário ("mágico") nos componentes.

---

## 1. Arquitetura de Design Tokens (Padrão W3C DTCG 2025/2026 + OKLCH)

Design Tokens são as decisões mínimas e indivisíveis de design armazenadas como dados estruturados e auditáveis. Adotamos o formato canônico do **W3C Design Tokens Community Group (DTCG)** em **3 camadas estritas**:

```
[ Nível 1: Tokens Primitivos / Globais ]
   (Escalas perceptuais OKLCH/HSL, dimensões base 8pt — NUNCA usados direto em componentes)
                   ↓
[ Nível 2: Tokens Semânticos / Contextuais ]
   (Propósito funcional: --color-surface-card, --color-text-primary, --color-interactive-primary-default)
                   ↓
[ Nível 3: Tokens de Componente ]
   (Escopo local mapeado para semânticos: --btn-bg, --card-padding, --input-border-radius)
```

### 1.1. Esquema JSON W3C DTCG (`tokens.json`)

Todo arquivo de tokens segue as propriedades prefixadas por `$` (`$type`, `$value`, `$description`) e referências por alias `{grupo.token}` (validadas determinísticamente por `scripts/auditor_style_guide_tokens.py`):

```json
{
  "primitive": {
    "color": {
      "$type": "color",
      "neutral-50": { "$value": "#f8fafc", "$description": "Fundo claro base (OKLCH 0.98 0.005 250)" },
      "neutral-900": { "$value": "#0f172a", "$description": "Tinta escura principal (OKLCH 0.18 0.03 260)" },
      "brand-600": { "$value": "#1d4ed8", "$description": "Ação primária com contraste >= 4.5:1 contra branco" }
    },
    "space": {
      "$type": "dimension",
      "1": { "$value": "8px" },
      "2": { "$value": "16px" },
      "3": { "$value": "24px" }
    }
  },
  "semantic": {
    "surface": {
      "$type": "color",
      "base": { "$value": "{primitive.color.neutral-50}" },
      "card": { "$value": "#ffffff" }
    },
    "text": {
      "$type": "color",
      "primary": { "$value": "{primitive.color.neutral-900}" },
      "on-primary": { "$value": "#ffffff" }
    },
    "interactive": {
      "$type": "color",
      "primary-default": { "$value": "{primitive.color.brand-600}" }
    }
  },
  "component": {
    "button": {
      "bg": { "$type": "color", "$value": "{semantic.interactive.primary-default}" },
      "text": { "$type": "color", "$value": "{semantic.text.on-primary}" },
      "padding-inline": { "$type": "dimension", "$value": "{primitive.space.2}" }
    }
  }
}
```

### 1.2. Espaço de Cor Perceptualmente Uniforme (`OKLCH`, `light-dark()` e `color-mix()`)

Por que **OKLCH** supera HSL/RGB na construção de paletas de Design System:
- No HSL, `hsl(60, 100%, 50%)` (amarelo) e `hsl(240, 100%, 50%)` (azul) têm a mesma "luminosidade" matemática (`50%`), mas luminosidade perceptual radicalmente oposta — gerando quebras de contraste WCAG ao trocar matizes ou converter para dark mode.
- Em **`oklch(L C H)`**, o canal **`L` (Lightness perceptual, `0` a `1`)** reflete a luminância real percebida pelo olho humano: manter `L` constante ao girar o matiz `H` preserva a razão de contraste previsível.

```css
/* ==========================================================================
   NÍVEL 1 & 2: TOKENS PERCEPTUAIS OKLCH + LIGHT-DARK() NATIVO
   ========================================================================== */
:root {
  color-scheme: light dark;

  /* Primitivos em OKLCH (L = luminância perceptual, C = croma, H = matiz) */
  --primitive-brand-500: oklch(0.58 0.20 258);
  --primitive-brand-600: oklch(0.50 0.21 258);
  --primitive-brand-700: oklch(0.43 0.19 258);

  --primitive-neutral-50:  oklch(0.985 0.004 250);
  --primitive-neutral-100: oklch(0.960 0.006 250);
  --primitive-neutral-200: oklch(0.915 0.010 250);
  --primitive-neutral-700: oklch(0.350 0.025 255);
  --primitive-neutral-900: oklch(0.180 0.028 260);
  --primitive-neutral-950: oklch(0.130 0.025 260);

  --primitive-success-600: oklch(0.52 0.16 150);
  --primitive-warning-600: oklch(0.62 0.16 75);
  --primitive-danger-600:  oklch(0.53 0.21 25);

  /* Escala de Espaçamento Modular (Base 8pt) */
  --space-0: 0px;
  --space-0-5: 4px;
  --space-1: 8px;
  --space-1-5: 12px;
  --space-2: 16px;
  --space-3: 24px;
  --space-4: 32px;
  --space-6: 48px;
  --space-8: 64px;

  /* Raios, Elevação e Curvas de Movimento */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-full: 9999px;

  --duration-fast: 150ms;
  --duration-normal: 240ms;
  --ease-out-quart: cubic-bezier(0.25, 1, 0.5, 1);
  --ease-standard: cubic-bezier(0.4, 0, 0.2, 1);

  /* Nível 2: Tokens Semânticos com light-dark() sem duplicar media queries */
  --color-surface-base: light-dark(var(--primitive-neutral-50), var(--primitive-neutral-950));
  --color-surface-card: light-dark(oklch(1 0 0), var(--primitive-neutral-900));
  --color-surface-subtle: light-dark(var(--primitive-neutral-100), oklch(0.22 0.025 260));

  --color-text-primary: light-dark(var(--primitive-neutral-900), var(--primitive-neutral-50));
  --color-text-secondary: light-dark(var(--primitive-neutral-700), oklch(0.78 0.015 250));
  --color-text-on-primary: oklch(1 0 0);

  --color-interactive-primary-default: light-dark(var(--primitive-brand-600), var(--primitive-brand-500));
  --color-interactive-primary-hover: color-mix(in oklch, var(--color-interactive-primary-default) 88%, black);
  --color-interactive-focus-ring: var(--primitive-brand-500);

  --color-border-subtle: light-dark(var(--primitive-neutral-200), oklch(0.28 0.02 255));
  --color-feedback-error: var(--primitive-danger-600);
}
```

---

## 2. Escala Tipográfica Proporcional, Pareamento e Ritmo Óptico

### 2.1. Escala Fluida (`clamp()`) e Refinamento Óptico
- **Display / H1:** `clamp(2rem, 1.5rem + 2vw, 3.25rem)` (`line-height: 1.1`, `letter-spacing: -0.025em`, `text-wrap: balance`).
- **H2:** `clamp(1.5rem, 1.25rem + 1vw, 2.25rem)` (`line-height: 1.18`, `letter-spacing: -0.015em`, `text-wrap: balance`).
- **H3:** `1.25rem` (20px, `line-height: 1.3`, `text-wrap: balance`).
- **Body Default:** `1rem` (16px, `line-height: 1.55`, `max-width: 65ch`, `text-wrap: pretty` para eliminar palavras órfãs no fim de parágrafos).
- **Dados Numéricos / Tabelas / KPIs:** `font-variant-numeric: tabular-nums` obrigatório em tabelas financeiras, contadores, timers e badges de preço para evitar jitter horizontal ao atualizar dígitos.

### 2.2. Matriz de Pareamento Tipográfico (Display + Body + Mono)
Para combater a monotonia visual (ver §6), combine uma fonte de **personalidade estrutural nos títulos** com uma **sans-serif legível de alta altura-x no corpo** e uma **monospace técnica para código/IDs**:
- **Editorial / Conhecimento:** Serif de alto contraste (*Instrument Serif*, *Newsreader*, *Playfair Display*) + Sans humanista (*Plus Jakarta Sans*, *Source Sans 3*) + *JetBrains Mono*.
- **Técnico / Developer / Cloud:** Geométrica/Grotesca expressiva (*Space Grotesk*, *Bricolage Grotesque*, *Geist*) + *Geist Sans* / *IBM Plex Sans* + *Geist Mono* / *IBM Plex Mono*.
- **Corporativo / Finanças / Dados:** Grotesca suíça precisa (*General Sans*, *Satoshi*, *Manrope*) + `tabular-nums` estrito em todas as métricas.

---

## 3. Os 7 Estados Canônicos de Componentes Interativos

Todo componente interativo (botões, inputs, selects, cards acionáveis) deve declarar explicitamente seus **7 estados fundamentais**:

| # | Estado | Gatilho / Seletor CSS | Feedback Visual Obrigatório | Acessibilidade Requerida |
|---|---|---|---|---|
| 1 | **Default (Idle)** | Estado base | Superfície em repouso, rótulo nítido ($\ge 4.5:1$). | Nome acessível presente via DOM ou `aria-label`. |
| 2 | **Hover** | `@media (hover: hover) { :hover }` | Derivação de tom (ex.: `color-mix()`), cursor `pointer`. | Isolado em `@media (hover: hover)` para não "grudar" em telas de toque. |
| 3 | **Focus-Visible** | `:focus-visible` | Anel nítido (`outline: 2px solid var(--color-interactive-focus-ring); outline-offset: 2px`). | **PROIBIDO `outline: none` sem anel substituto de alto contraste ($\ge 3:1$).** |
| 4 | **Active / Pressed** | `:active` | Sensação tátil de clique (`transform: scale(0.98)`). | Cancelável no `pointerup` fora do alvo (WCAG 2.5.2). |
| 5 | **Loading / Busy** | `[aria-busy="true"]` | Largura preservada, spinner sutil ou shimmer; bloqueia duplo submit. | `aria-busy="true"` + anúncio em live region se necessário. |
| 6 | **Disabled** | `:disabled`, `[aria-disabled="true"]` | Opacidade controlada, `cursor: not-allowed`. | Preferir `aria-disabled="true"` quando o usuário precisar ler tooltip do motivo. |
| 7 | **Error / Invalid** | `[aria-invalid="true"]` | Borda `--color-feedback-error` + ícone + mensagem inline. | Vinculado à mensagem via `aria-describedby`. |

---

## 4. Layout Moderno e Primitivas CSS Baseline 2025/2026 (Zero-JS UI)

Seguindo **P1-Simplicidade** e **P3-CustoBaixo (bundle zero)**, nunca instale bibliotecas JavaScript pesadas para resolver problemas que o CSS nativo moderno resolve com aceleração de hardware:

### 4.1. Container Queries (`@container`) e CSS Subgrid
Componentes reagem ao espaço do próprio container (`container-type: inline-size`), e grades de cards usam `subgrid` para alinhar cabeçalhos, corpos e rodapés horizontalmente entre cards vizinhos com textos de tamanhos diferentes:

```css
.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 280px), 1fr));
  gap: var(--space-3);
}

.card-item {
  display: grid;
  grid-row: span 3;
  grid-template-rows: subgrid; /* Alinha título, corpo e rodapé entre todos os cards da linha */
  gap: var(--space-2);
  padding: var(--space-3);
  background: var(--color-surface-card);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md);
}
```

### 4.2. CSS Anchor Positioning (Zero-JS Tooltips / Popovers / Menus)
Substitui bibliotecas de posicionamento JS em popovers e tooltips nativos (`[popover]`):

```css
.trigger-btn {
  anchor-name: --menu-trigger;
}

.floating-popover {
  position: fixed;
  position-anchor: --menu-trigger;
  position-area: block-end span-inline-end;
  position-try-fallbacks: flip-block, flip-inline;
  margin-block-start: var(--space-1);
}
```

### 4.3. Coreografia Nativa de Entrada/Saída (`@starting-style` + View Transitions)
Para animar `<dialog>` e `[popover]` nativos saindo de `display: none` sem timers em JS:

```css
dialog[open] {
  opacity: 1;
  transform: translateY(0);
  transition: opacity var(--duration-normal) var(--ease-out-quart),
              transform var(--duration-normal) var(--ease-out-quart),
              display var(--duration-normal) allow-discrete;
}

@starting-style {
  dialog[open] {
    opacity: 0;
    transform: translateY(8px);
  }
}
```

Para troca de estado/rota em Angular (`withViewTransitions()`), atribua `view-transition-name` único ao elemento compartilhado e proteja sempre com `@media (prefers-reduced-motion: reduce)`.

---

## 5. Doutrina Frontend Designer & Combate ao "AI Slop"

Agentes de IA sem direção estética convergem estatisticamente para clichês genéricos ("AI Slop"). O `especialista-frontend`, em par com `ui-ux-pro-max`, aplica regras estritas de **Design Craft**:

| Clichê de "AI Slop" (PROIBIDO) | Direção de Alta Costura (OBRIGATÓRIO) |
|---|---|
| Gradiente roxo/azul genérico sobre fundo branco puro em toda tela SaaS | **Regra 60-30-10 com Atmosfera:** 60% superfície dominante calibrada (ex.: off-white editorial `oklch(0.98 0.008 85)` ou slate profundo), 30% superfície estrutural/bordas de 1px, 10% acento semântico cirúrgico. |
| Grade simétrica de 3 cards idênticos com ícone em círculo colorido e texto vago | **Hierarquia Assimétrica / Bento Intencional:** destaque o dado primário (2× largura ou tipografia display) e agrupe dados secundários por densidade real de leitura. |
| Tipografia monótona (mesma fonte, pesos 400/500 tímidos, títulos sem contraste) | **Contraste Tipográfico Dramático:** saltos claros entre Display (`font-weight: 700/800`, `tracking` negativo) e metadados (`0.75rem`, uppercase com `letter-spacing: 0.06em` ou `tabular-nums`). |
| Valores mágicos espalhados (`#3b82f6`, `padding: 13px`, `z-index: 99999`) | **Disciplina de Tokens Auditável:** 100% derivado de variáveis CSS semânticas e camadas de `z-index` nomeadas (`--z-dropdown: 100`, `--z-sticky: 200`, `--z-modal: 300`, `--z-toast: 400`). |
| Emojis usados como ícones de interface em produção (`🚀`, `✨`, `🔥`) | **Iconografia Vetorial Consistente:** SVGs monocromáticos ou duotone com `stroke-width` uniforme (`1.5px` ou `1.75px`), `aria-hidden="true"` quando decorativos. |

---

## 6. Governança Executável do Style Guide (`auditor_style_guide_tokens.py`)

Antes de abrir PR ou avançar para o `validador-navegador`, execute o auditor determinístico da skill:

```bash
python skills/especialista-frontend/scripts/auditor_style_guide_tokens.py --tokens tokens.json --css src/styles.css
```

O script verifica automaticamente:
1. **Árvore W3C DTCG:** presença de `$type` e `$value`, resolução de aliases `{a.b.c}`, detecção de referências órfãs e ciclos circulares.
2. **Contraste WCAG 2.2:** cálculo exato de luminância relativa e razão de contraste (`>= 4.5:1` texto normal AA, `>= 3.0:1` texto grande/UI, `>= 7.0:1` AAA).
3. **Linter de CSS de Componente:** bloqueio de cores mágicas fora de `:root`, proibição de `outline: none` sem `:focus-visible`, exigência de `@media (prefers-reduced-motion: reduce)` quando há animações e cobertura dos 7 estados interativos.
