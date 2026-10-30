# Engenharia de Interação, Web Interface Guidelines, Física de Movimento e Ergonomia Preditiva

> **Quando ler:** ao implementar formulários de alta conversão, navegação complexa por teclado (`Roving Tabindex`), sincronização de estado na URL (`URL as State`), microinterações baseadas em física (`Spring Physics`), menus em cascata (`Safe Triangle`), otimização de `INP <= 200ms` e contraste perceptual **APCA (`Lc`)**.
> **Procedência:** síntese autoral em PT-BR dos padrões de `vercel-labs/web-interface-guidelines` (`web-design-guidelines`), `emilkowalski/skills` (*Animations on the Web*), `Dammyjay93/interface-design`, normas **ISO 9241-110:2020** / **Bastien & Scapin (1993)**, modelos motores **KLM-GOMS** / **Steering Law (Accot-Zhai)** e **APCA 0.98G (WCAG 3.0 Draft)**.

---

## 1. Vercel Web Interface Guidelines — Regras de Produção para Engenharia de UI

### 1.1. Ergonomia de Formulários e Inputs de Fricção Zero
1. **Nunca pré-desabilite o botão de Submit para forçar validação:** botões `disabled` sem explicação violam a Presteza (Bastien & Scapin) e não recebem foco de teclado. Mantenha o botão habilitado; ao submeter com dados inválidos, exiba os erros inline e **mova o foco programaticamente para o primeiro campo inválido**.
2. **Submissão por Teclado Nativa:**
   - Em formulários de linha única (`<input>`), pressionar `Enter` submete imediatamente.
   - Em `<textarea>`, `Enter` insere quebra de linha e **`Ctrl+Enter` / `Cmd+Enter`** dispara a submissão.
3. **Preservação Dimensional em Submissões Assíncronas (`aria-busy="true"`):**
   - Durante o envio, desative cliques repetidos via guarda de estado (`isSubmitting()`), aplique `aria-busy="true"` e exiba o indicador de progresso **preservando a largura e o rótulo original do botão** (evitando layout shift horizontal).
4. **Atributos Semânticos de Teclado Virtual, Autofill e Colagem Livre:**
   - Associe sempre `<label for="...">` clicável a cada controle.
   - Declare o par `type` + `inputmode` (`numeric`, `decimal`, `tel`, `email`, `search`) e `autocomplete` (`username`, `current-password`, `one-time-code`, `cc-number`, `postal-code`).
   - Desative corretores ortográficos em códigos, e-mails e identificadores: `spellcheck="false" autocapitalize="none" autocorrect="off"`.
   - **Liberdade de Colagem (WCAG 2.2 SC 3.3.8):** é **proibido** bloquear `onpaste` em qualquer campo (incluindo senhas, confirmação de e-mail, Pix ou OTP).
   - **Prevenção de Auto-Zoom Forçado no Mobile (iOS Safari):** todo `<input>`, `<select>` e `<textarea>` em viewports móveis deve ter **`font-size >= 1rem` (`16px`)**. Fontes menores que `16px` forçam zoom intrusivo no Safari iOS e quebram o viewport.
   - **Auto-expansão CSS Zero-JS:** use `field-sizing: content` (com `min-block-size` e `max-block-size`) em `<textarea>` para crescer conforme o texto sem listeners JS de `scrollHeight`.

```html
<!-- Exemplo Angular 22: Formulário Ergonômico de Fricção Zero -->
<form (submit)="onSubmit($event)" novalidate>
  <div class="field-group">
    <label for="otp-code">Código de verificação (6 dígitos)</label>
    <input
      id="otp-code"
      type="text"
      inputmode="numeric"
      autocomplete="one-time-code"
      spellcheck="false"
      autocapitalize="none"
      [attr.aria-invalid]="otpInvalido() ? 'true' : null"
      aria-describedby="otp-hint otp-error" />
    <small id="otp-hint" class="helper-text">Você pode colar o código recebido por SMS ou app.</small>
    @if (otpInvalido()) {
      <p id="otp-error" class="error-message" role="alert">
        Código incompleto. Digite os 6 números enviados para seu celular.
      </p>
    }
  </div>

  <button type="submit" class="btn-primary" [attr.aria-busy]="salvando()">
    @if (salvando()) {
      <span class="spinner-inline" aria-hidden="true"></span>
    }
    <span>Confirmar código</span>
  </button>
</form>
```

### 1.2. URL como Fonte de Verdade de Estado (`URL as State` & Deep-Linking)
- **Persistência em Query Params:** filtros ativos, termo de busca, aba selecionada, ordenação de tabela, paginação e ID de painel/modal inspecionado devem refletir nos query parameters da URL (`?q=pix&status=pendente&page=2&sort=data:desc`).
- **Benefício Ergonômico (ISO 9241-110 Controllability):** permite atualizar a página (`F5`) sem perder o trabalho, compartilhar o link exato com um colega, abrir em nova aba (`Ctrl+Click` em links `<a>` reais) e usar os botões Voltar/Avançar do navegador com restauração de posição de rolagem (`withInMemoryScrolling({ scrollPositionRestoration: 'enabled' })` no Angular Router).

### 1.3. Engenharia de Teclado Avançada (`Roving Tabindex` & Expansão de Hit Target)
- **Roving Tabindex (WAI-ARIA APG):** em grupos compostos (Tabs, Toolbars, Radio Groups, Menus e Data Grids), apenas **um** item do grupo possui `tabindex="0"` (o item ativo); os demais possuem `tabindex="-1"`. O usuário entra no grupo com `Tab`, navega entre os itens com as **Setas (`ArrowLeft`/`ArrowRight`/`ArrowUp`/`ArrowDown`)**, `Home` e `End`, e sai do grupo no próximo `Tab`.
- **Expansão Invisível de Área de Toque (Hit Target Expansion):** quando um controle visual precisa ser compacto (ex.: botão de fechar `16x16px` ou ícone em linha densa), expanda sua área clicável para **$\ge 24\times 24\text{px}$ no desktop** e **$\ge 44\times 44\text{px}$ no mobile** usando pseudo-elemento `::after`:

```css
.compact-icon-btn {
  position: relative;
   inline-size: 20px;
  block-size: 20px;
}

.compact-icon-btn::after {
  content: "";
  position: absolute;
  inset: -12px; /* Expande 20px -> 44x44px de área de toque real */
}
```

---

## 2. Física de Movimento e Microinterações (`emilkowalski/skills` & Design Craft)

Microinterações comunicam causalidade, hierarquia espacial e confirmação tátil. Seguindo a disciplina de Design Engineering (Emil Kowalski / Linear / Vercel):

| Regra de Movimento | Diretriz Técnica Obrigatória | Anti-Padrão Bloqueado (🔴/🟡) |
|---|---|---|
| **1. Orçamento Temporal Estrito** | Controles interativos (hover/press/toggle): **`120ms–200ms`**. Modais/Popovers/Drawers: entrada em **`200ms–260ms`**, saída mais rápida em **`140ms–180ms`** (nunca fazer o usuário esperar o fechamento). | Transições de UI `> 300ms` ou usar a mesma duração lenta para abrir e fechar. |
| **2. Proibição de `ease-in` em Respostas de UI** | Toda resposta a input humano deve começar com velocidade alta e desacelerar suavemente: use `cubic-bezier(0.22, 1, 0.36, 1)` (`ease-out-quint`/`quart`). | Usar `ease-in` ou `linear` em aberturas de menu/modal (gera sensação de atraso/travamento). |
| **3. Proibição de Entrada `scale(0)`** | Elementos que surgem na tela (popovers, tooltips, modais, toasts) devem iniciar em **`scale(0.95)` a `scale(0.97)` com `opacity: 0`** e `translateY(4px–8px)`.Nada no mundo físico surge do volume zero. | Animar de `transform: scale(0)` para `scale(1)` (efeito elástico caricato e artificial). |
| **4. Física de Molas (Spring Physics)** | Para gestos, drags e transições orgânicas via `linear()` CSS ou Web Animations API, use molas criticamente amortecidas ou com bounce sutil (`duration: 0.45s, bounce: 0.15`). | Molas sub-amortecidas com oscilação exagerada em software corporativo/bancário. |
| **5. Interrompibilidade Total** | Se o usuário clicar rapidamente duas vezes (abrir e fechar antes da animação terminar), a transição deve inverter a partir da posição atual (CSS `transition` nativo), sem saltar para o fim do frame. | Keyframes bloqueantes que ignoram reversão de estado no meio do percurso. |
| **6. Composição Exclusiva em GPU** | Anime apenas **`transform`**, **`opacity`**, **`filter`** ou **`clip-path`**. | Animar `width`, `height`, `top`, `left`, `margin` ou `padding` (dispara Layout Reflow + Paint a cada frame e destrói o INP/CLS). |

---

## 3. Modelos Preditivos de HCI: `KLM-GOMS` e `Steering Law` (`Safe Triangle`)

### 3.1. Economia Motora pelo Modelo `KLM-GOMS` (Card, Moran & Newell)
O **Keystroke-Level Model (KLM)** decompõe o tempo de execução de uma tarefa operacional na soma de operadores físicos e mentais:

$$T_{\text{exec}} = \sum \left( T_K + T_P + T_H + T_D + T_M + T_R \right)$$

- **$T_K \approx 0.20\text{s}$ (Keystroke):** pressionar uma tecla ou atalho.
- **$T_P \approx 1.10\text{s}$ (Pointing):** mover o cursor do mouse até um alvo na tela (governado pela Lei de Fitts).
- **$T_H \approx 0.40\text{s}$ (Homing):** deslocar a mão entre o teclado e o mouse.
- **$T_M \approx 1.20\text{s}$ (Mental Preparation):** pausa cognitiva para localizar uma opção ou decidir.
- **$T_R$ (System Response):** latência do sistema (deve respeitar o **Limiar de Doherty $< 400\text{ms}$**, ideal $< 100\text{ms}$).

> **Regra de Engenharia KLM:** Em fluxos de uso frequente (cadastros, triagem, atendimento, financeiro), **cada troca teclado $\leftrightarrow$ mouse custa $2 \times T_H + T_P \approx 1.9\text{s}$**. Projete fluxos 100% operáveis sem tirar as mãos do teclado (`Tab` lógico, `Ctrl+K` Command Palette, `Enter`/`Ctrl+Enter` e autocompletes navegáveis por setas).

### 3.2. Lei do Túnel de Accot-Zhai (`Steering Law`) e o `Safe Triangle`
A **Steering Law** modela o tempo necessário para conduzir um ponteiro através de um caminho estreito ou túnel de comprimento $D$ e largura $W$:

$$T = a + b \int_C \frac{ds}{W(s)} \quad \implies \quad T_{\text{túnel reto}} = a + b \left(\frac{D}{W}\right)$$

- **O Problema Clássico em Menus Cascata:** quando o usuário passa o mouse sobre um item de menu pai e move o cursor **diagonalmente** em direção ao submenu aberto à direita, o cursor cruza outros itens irmãos do menu pai. Sem proteção geométrica, o submenu fecha instantaneamente no meio do trajeto.
- **Solução 1 (Arquitetural — P1):** substituir cascatas profundas ($\ge 2$ níveis) por **Mega-Menus planos** ou **Command Palette (`Ctrl+K`)**.
- **Solução 2 (Geométrica — `Safe Triangle` / Hover Intent Corridor):** calcular se o cursor $(P_x, P_y)$ está dentro do triângulo formado pela posição anterior do mouse $A$, o canto superior esquerdo do submenu $B$ e o canto inferior esquerdo do submenu $C$ (via sinal do produto vetorial baricêntrico), mantendo o submenu aberto enquanto o cursor avança em direção a ele.

---

## 4. Primitivas Web Baseline 2025/2026 & Otimização de `INP <= 200ms`

### 4.1. Invoker Commands API Nativa (`commandfor` e `command`)
Elimine boilerplate de event listeners para abrir/fechar `<dialog>` e `[popover]` usando atributos declarativos HTML nativos com acessibilidade e gestão de foco embutidas pelo navegador:

```html
<button type="button" commandfor="modal-confirmacao" command="show-modal" class="btn-primary">
  Revisar Transferência
</button>

<dialog id="modal-confirmacao" aria-labelledby="modal-titulo">
  <h2 id="modal-titulo">Confirmar envio de Pix</h2>
  <p>Confira os dados antes de autorizar a operação.</p>
  <div class="dialog-actions">
    <button type="button" commandfor="modal-confirmacao" command="close" class="btn-secondary">
      Cancelar
    </button>
  </div>
</dialog>
```

### 4.2. Cessão Cooperativa da Main Thread (`scheduler.yield()`) para `INP <= 200ms`
O **Interaction to Next Paint (INP)** mede a latência entre a interação física do usuário (clique/tecla) e o próximo frame efetivamente pintado na tela (meta verde Core Web Vitals: **`<= 200ms`**):
1. **Pintar o feedback imediato primeiro (< 50ms):** atualize o Signal visual (`isLoading.set(true)`) imediatamente no handler.
2. **Ceder a thread principal antes de processamento pesado:** se houver formatação pesada, filtragem local de grande lista ou telemetria, chame `await scheduler.yield()` (com fallback seguro) para permitir que o navegador pinte o frame de feedback antes de continuar o trabalho:

```typescript
export async function yieldToMainThread(): Promise<void> {
  const globalScheduler = (globalThis as { scheduler?: { yield?: () => Promise<void> } }).scheduler;
  if (globalScheduler && typeof globalScheduler.yield === 'function') {
    await globalScheduler.yield();
    return;
  }
  await new Promise<void>((resolve) => setTimeout(resolve, 0));
}
```

---

## 5. Contraste Perceptual APCA (`Lc` — WCAG 3.0 Draft) + WCAG 2.2

Enquanto a razão de contraste WCAG 2.2 (`4.5:1` / `3.0:1`) trata texto escuro sobre fundo claro e texto claro sobre fundo escuro de forma matematicamente simétrica, a visão humana possui percepção **dependente da polaridade e da frequência espacial** (espessura/tamanho da fonte). O algoritmo **APCA (Accessible Perceptual Contrast Algorithm, 0.98G)** calcula o contraste perceptual direcional **$L_c$** (de $-108$ a $+106$):

| Nível de Uso na Interface | Limiar Mínimo APCA ($\|L_c\|$) | Equivalente WCAG 2.2 | Aplicação |
|---|---|---|---|
| **Texto Fluente de Leitura Longa** | **$\|L_c\| \ge 75$** (`90` ideal) | $\ge 7.0:1$ (AAA) | Artigos, tabelas financeiras densas, contratos, relatórios. |
| **Texto de Conteúdo Padrão (`16px` regular)** | **$\|L_c\| \ge 60$** | $\ge 4.5:1$ (AA) | Labels de formulário, descrições de cards, mensagens de status. |
| **Títulos Grandes / Subtítulos (`>= 24px` ou `>= 18.6px bold`)** | **$\|L_c\| \ge 45$** | $\ge 3.0:1$ (AA Large) | Cabeçalhos `H1`–`H3`, KPIs em destaque, botões grandes. |
| **Componentes de UI, Bordas Ativas e Ícones Essenciais** | **$\|L_c\| \ge 30$** | $\ge 3.0:1$ (UI 1.4.11) | Contornos de inputs, divisores funcionais, ícones semânticos. |

> **Verificação automatizada:** execute `python skills/especialista-frontend/scripts/auditor_style_guide_tokens.py --contrast "#0f172a" "#ffffff"` para obter simultaneamente a razão **WCAG 2.2** e o índice perceptual **APCA $L_c$**.
