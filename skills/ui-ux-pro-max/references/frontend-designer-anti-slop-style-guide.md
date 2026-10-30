# Direção Estética Frontend Designer, Mandato Anti-"AI Slop" e Contrato de Style Guide

> **Quando ler:** ao definir direção visual de páginas web, dashboards, SaaS, landing pages ou sistemas corporativos no `ui-ux-pro-max`, ou ao preparar o handoff de `MASTER.md` / tokens W3C DTCG para implementação no `especialista-frontend`.
> **Procedência:** padrões sintetizados e reescritos em PT-BR a partir de `anthropics/skills/frontend-design`, `vercel-labs/web-interface-guidelines`, `emilkowalski/skills`, `Dammyjay93/interface-design`, especificação W3C DTCG 2025/2026 (OKLCH) e APCA 0.98G (WCAG 3.0 Draft).

---

## 1. O Mandato Anti-"AI Slop" (Combate à Convergência Distributiva)

Modelos de linguagem sem direção estética explícita convergem para a média estatística da web — gerando interfaces genéricas instantaneamente reconhecíveis como "template de IA" (*AI Slop*). Antes de emitir qualquer recomendação visual ou gerar `MASTER.md`, aplique este filtro:

### 1.1. O que é PROIBIDO por padrão ("AI Slop")
1. **Paleta Clichê Roxo-Azul sobre Branco:** fundos brancos lavados com gradientes lineares `indigo-500 -> purple-600`, botões brilhantes sem semântica e sombras difusas coloridas sem propósito funcional.
2. **Grade Simétrica de 3 Cards Clones:** fileiras de 3 caixas idênticas com ícone dentro de círculo pastel, título genérico de 2 palavras e texto de 2 linhas sem hierarquia de leitura.
3. **Hero Previsível Sem Ponto Focal:** badge arredondado ("✨ Novo recurso com IA"), título centralizado genérico, subtítulo cinza pálido e dois botões lado a lado sem demonstração tangível do produto.
4. **Tipografia Neutra Invisível sem Escala:** uso preguiçoso de `Inter`/`Roboto`/`Arial` com pesos uniformes (`400`/`500`) onde título, subtítulo e corpo diferem apenas por `2px` de tamanho.
5. **Emojis como Iconografia de Produto:** usar `🚀`, `📊`, `🔒`, `⚡` no lugar de ícones SVG vetoriais com traço (`stroke-width`) e grid óptico consistentes.

### 1.2. Os 5 Arquétipos Estéticos Intencionais
Ao iniciar um projeto (`Step 1` e `Step 2`), comprometa-se com um arquétipo claro ligado ao domínio do produto:

| Arquétipo | Atmosfera & Superfície (60%) | Estrutura & Grid (30%) | Acento & Tipografia (10%) |
|---|---|---|---|
| **1. Editorial / Conhecimento** | Papel quente (`oklch(0.975 0.008 80)`) ou tinta profunda | Bordas hairline (`1px solid`), colunas assimétricas estilo revista | Serif de alto contraste nos títulos (*Newsreader*, *Instrument Serif*) + terracota/vermilion |
| **2. Swiss International / Dados** | Neutro técnico puro (`oklch(0.985 0.003 250)`) | Grid modular exposto, alinhamento tabular rigoroso, alta densidade | Grotesca precisa (*General Sans*, *Plus Jakarta Sans*) + `tabular-nums` + azul cobalto/verde sinal |
| **3. Dark Technical / DevOps & IA** | Carbono/Obsidiana (`oklch(0.14 0.02 260)`) | Superfícies elevadas por luminância (`L = 0.18` a `0.22`) + bordas translúcidas sutis | Monospace técnica (*JetBrains Mono*, *Geist Mono*) + acento cirúrgico âmbar, ciano ou verde ácido |
| **4. Bento Assimétrico / Produto SaaS** | Contraste suave entre canvas (`L = 0.96`) e cards (`L = 1.00`) | Célula principal dominante ($2\times 2$) + células secundárias alinhadas via CSS `subgrid` | Display geométrica (*Bricolage Grotesque*, *Space Grotesk*) + microinterações táteis |
| **5. Industrial Utilitário / Operações** | Cinza mineral neutro sem distração decorativa | Densidade alta (`--density 8-9`), foco em status, atalhos de teclado (`Ctrl+K`) e tabelas | Alto contraste AA/AAA (> 7:1), códigos monoespaçados e semântica estrita de cores de alerta |

---

## 2. Arquitetura Perceptual de Cores: Regra 60-30-10 em `OKLCH` e Contraste APCA (`Lc`)

Nunca distribua cores em proporções iguais. Estruture a paleta do Design System usando a proporção **60-30-10** ancorada em **luminância perceptual (`OKLCH`)** e validada simultaneamente por **WCAG 2.2** e **APCA 0.98G ($L_c$)**:

1. **60% — Superfície Dominante (Canvas & Background):** define a atmosfera luminosa (`--color-surface-base`). No modo escuro, nunca use preto puro (`#000000`) como superfície única — use tons de ardósia/obsidiana (`oklch(0.13 0.02 260)`) e aplique **Elevação Silenciosa (*Whisper-Quiet Elevation* — `Dammyjay93/interface-design`)** subindo `L` em passos sutis ($\Delta L = 0.02\text{ a }0.04$: `0.17`, `0.21`) com bordas hairline de `1px solid` via `color-mix()` em vez de sombras pretas pesadas.
2. **30% — Estrutura Secundária (Cards, Navegação, Bordas, Texto Secundário):** cria agrupamento Gestalt (`--color-surface-card`, `--color-border-subtle`, `--color-text-secondary`).
3. **10% — Acento Semântico & CTA Primário:** reservado exclusivamente para a ação principal da tela (`--color-interactive-primary-default`) e indicadores de estado (`success`, `warning`, `error`). Se tudo destaca, nada destaca.
4. **Limiares Perceptuais APCA ($L_c$):** texto fluente longo exige **$|L_c| \ge 75$**; texto de corpo padrão exige **$|L_c| \ge 60$** (além de WCAG 2.2 AA $\ge 4.5:1$); títulos grandes exigem **$|L_c| \ge 45$**; bordas de controles e ícones essenciais exigem **$|L_c| \ge 30$**.

---

## 3. Coreografia de Movimento e Física de Microinterações (`emilkowalski/skills`)

Movimento em UI profissional **explica relações espaciais** (de onde o elemento veio e para onde foi), nunca enfeita por vaidade:

- **Orçamento Temporal e Saída Rápida:** controles respondem em `120ms–200ms`; transições de entrada de modais/popovers usam `200ms–260ms` com curva de desaceleração (`cubic-bezier(0.22, 1, 0.36, 1)`); transições de fechamento/saída usam `140ms–180ms`.
- **Proibição de `ease-in` e de `scale(0)`:** nunca use `ease-in` em respostas de UI; nunca anime entradas a partir de `scale(0)` — inicie sempre em `scale(0.95–0.97)` + `opacity: 0`.
- **Física de Molas e Interrompibilidade:** priorize molas criticamente amortecidas (`bounce: 0.15`) e transições CSS interrompíveis que revertem suavemente se o usuário clicar no meio do trajeto.
- **Zero Layout Shift (CLS = 0):** jamais anime `width`, `height`, `top`, `left` ou `margin`. Anime exclusivamente propriedades compostas na GPU (`transform`, `opacity`, `filter`, `clip-path`) ou use a **View Transitions API** nativa.
- **Acessibilidade Vestibular:** toda coreografia (CSS ou GSAP) deve desativar deslocamentos espaciais sob `@media (prefers-reduced-motion: reduce)`, preservando apenas cross-fades suaves de opacidade.

---

## 4. Contrato de Handoff: `ui-ux-pro-max` $\to$ `especialista-frontend` $\to$ `validador-navegador`

Quando o `ui-ux-pro-max` atua em conjunto com a Squad AI, a passagem de bastão segue 3 artefatos verificáveis:

1. **Direção Visual (`design-system/<slug>/MASTER.md`):** gerada pelo `ui-ux-pro-max` com arquétipo, paleta, par tipográfico, dials (`--variance`, `--motion`, `--density`) e anti-padrões bloqueados.
2. **Materialização e Auditoria Estática (`especialista-frontend`):** converte os tokens para variáveis CSS semânticas (`OKLCH` + `light-dark()`) e JSON W3C DTCG, aplica as **Vercel Web Interface Guidelines** (`URL as State`, formulários ergonômicos, `Roving Tabindex`, `Safe Triangle`, `INP <= 200ms`) e valida via `skills/especialista-frontend/scripts/auditor_style_guide_tokens.py` (contraste WCAG 2.2 + APCA $L_c$, zero cores mágicas, zero `scale(0)`/layout-thrashing e 7 estados interativos).
3. **Prova de Runtime no DOM (`validador-navegador`):** inspeciona a aplicação rodando via `preview_inspect` e `skills/validador-navegador/scripts/verificador_ui_dom.py` (alvos $\ge 24\times 24\text{px}$, foco não obscurecido por sticky headers, inputs mobile $\ge 16\text{px}$ sem bloqueio de `paste`, alinhamento de cards e zero scroll horizontal).
