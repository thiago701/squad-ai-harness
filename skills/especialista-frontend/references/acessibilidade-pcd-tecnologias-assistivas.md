# Acessibilidade, Ergonomia e Usabilidade para Pessoas com Deficiência (PcD)

> **Quando ler:** ao projetar, codificar, refatorar ou auditar interfaces digitais para garantir autonomia, conforto e inclusão plena a Pessoas com Deficiência (PcD) e usuários de tecnologias assistivas.
> **Marco Legal e Ético:** A acessibilidade web é um direito fundamental garantido pela **Lei Brasileira de Inclusão da Pessoa com Deficiência (LBI - Lei nº 13.146/2015, Art. 63)**, pelo **eMAG (Modelo de Acessibilidade em Governo Eletrônico)** e pelo padrão internacional **WCAG 2.2**. Software inacessível é defeito crítico de engenharia e risco jurídico direto.

---

## 1. Matriz de Tecnologias Assistivas e Perfis de Usuários PcD

Pessoas com deficiência interagem com o software através de diferentes dispositivos de entrada e saída. A interface deve ser projetada para ser agnóstica ao mecanismo de controle:

```
+----------------------------------------------------------------------------------+
|                            PERFIS E TECNOLOGIAS ASSISTIVAS                       |
+--------------------------+--------------------------------+----------------------+
| Perfil de Deficiência    | Tecnologia Assistiva Primária  | Barreira Crítica     |
+--------------------------+--------------------------------+----------------------+
| 1. Cegueira Total        | Leitores de Tela (NVDA,        | Botões sem label,    |
|                          | VoiceOver, JAWS, TalkBack),    | imagens sem alt,     |
|                          | Displays Braille Atualizáveis  | SPAs sem focus trap  |
+--------------------------+--------------------------------+----------------------+
| 2. Baixa Visão           | Ampliadores de tela (ZoomText, | Quebra de layout com |
|                          | lupa do SO), temas de alto     | zoom 400%, contraste |
|                          | contraste                      | insuficiente (<4.5:1)|
+--------------------------+--------------------------------+----------------------+
| 3. Discromatopsia        | Filtros monocromáticos,        | Instruções baseadas  |
|    (Daltonismo)          | simuladores de cor             | unicamente em cor    |
+--------------------------+--------------------------------+----------------------+
| 4. Deficiência Motora    | Navegação exclusiva por        | Alvos pequenos (<24px|
|    (Tremores, Paralisia, | teclado, acionadores (switches)| time-outs sem aviso, |
|    Amputações, ELA)      | eye-tracking, digitação por voz| arraste obrigatório  |
+--------------------------+--------------------------------+----------------------+
| 5. Surdez e Hipoacusia   | Legendas sincronizadas,        | Áudios/vídeos sem    |
|                          | tradutores de Libras virtuais  | legenda, alertas     |
|                          | (VLibras, Hand Talk)           | exclusivamente sonoro|
+--------------------------+--------------------------------+----------------------+
| 6. Neurodivergência      | Modo de leitura, tipografia    | Animações piscantes, |
|    (TDAH, Dislexia, TEA, | aberta, bloqueadores de ruído  | sobrecarga de opções,|
|    Déficit Cognitivo)    |                                | formulários labirinto|
+--------------------------+--------------------------------+----------------------+
```

---

## 2. Padrões de Engenharia para Deficiência Visual

### 2.1. Leitores de Tela e Semântica do DOM (Cegueira)
Leitores de tela não leem a tela gráfica; eles constroem uma **árvore de acessibilidade (Accessibility Tree)** a partir da árvore semântica do DOM.
1. **Controles Customizados com ARIA Completo:** Se criar um componente que não seja um `<button>` ou `<input>` nativo, é obrigatório declarar `role`, `tabindex="0"`, gerenciamento de `keydown` (`Enter`/`Space`) e atributos de estado (`aria-expanded`, `aria-checked`, `aria-selected`).
   ```html
   <!-- Componente Acordeão Acessível -->
   <button
     type="button"
     class="accordion-trigger"
     [attr.aria-expanded]="isAberto()"
     aria-controls="secao-detalhes-1"
     id="gatilho-detalhes-1">
     <span>Detalhes da Fatura</span>
     <span class="icone-seta" aria-hidden="true">{{ isAberto() ? '▲' : '▼' }}</span>
   </button>

   <div
     id="secao-detalhes-1"
     role="region"
     aria-labelledby="gatilho-detalhes-1"
     [hidden]="!isAberto()">
     <p>Conteúdo detalhado da fatura...</p>
   </div>
   ```
2. **Textos Alternativos Significativos em Imagens (WCAG 1.1.1):**
   - Imagens informativas: `alt="Gráfico de barras mostrando crescimento de 15% na receita no 3º trimestre"`.
   - Imagens puramente decorativas: `alt=""` e `aria-hidden="true"` (para que o leitor de tela as ignore sem ruído).

### 2.2. Baixa Visão e Reflow Responsivo (WCAG 1.4.10)
- O layout da aplicação deve suportar **zoom de até 400%** no navegador desktop sem que o texto se sobreponha e sem exigir rolagem bidimensional (scroll horizontal). O conteúdo deve se reorganizar fluidamente em uma única coluna vertical (equivalente a uma viewport de `320px` de largura CSS).
- Unidades de medida tipográfica devem utilizar **`rem` ou `em`**, nunca `px` fixos em tamanhos de fonte de leitura, permitindo que a preferência do sistema operacional do usuário seja respeitada.

### 2.3. Espaçamento de Texto Customizável (WCAG 1.4.12 Text Spacing)
O CSS não pode quebrar se o usuário aplicar sua própria folha de estilos assistiva para dislexia ou baixa visão com os seguintes limites:
- Altura de linha (`line-height`): pelo menos 1.5 vezes o tamanho da fonte.
- Espaçamento de parágrafo: pelo menos 2 vezes o tamanho da fonte.
- Espaçamento entre letras (`letter-spacing`): pelo menos 0.12 vezes o tamanho da fonte.
- Espaçamento entre palavras (`word-spacing`): pelo menos 0.16 vezes o tamanho da fonte.

---

## 3. Padrões de Engenharia para Deficiência Motora e Física

### 3.1. Navegação Exclusiva por Teclado e Acionadores (Switches)
Pessoas com tetraplegia ou distrofia muscular frequentemente utilizam acionadores de pressão ("switches") operados pela cabeça, queixo ou sopro, mapeados para as teclas `Tab` e `Enter`.
- **Zero Armadilhas de Foco (WCAG 2.1.2):** O foco de teclado deve ser capaz de entrar e sair de qualquer componente sem ficar preso.
- **Ordem de Tabulação Lógica (WCAG 2.4.3):** A ordem de navegação visual deve corresponder estritamente à ordem da árvore do DOM. Nunca use `order` do CSS Flexbox ou Grid de maneira a inverter drasticamente a ordem lógica de foco.
- **Focus Appearance (WCAG 2.2 SC 2.4.13):** O indicador de foco precisa ter espessura mínima de **2px**, contraste $\ge 3:1$ contra o fundo e contra o estado sem foco.

### 3.2. Cancelamento de Ponteiro e Tolerância a Tremores (WCAG 2.5.2)
Para pessoas com tremores essenciais ou Parkinson:
- Dispare ações no evento **`mouseup` / `pointerup`**, nunca no `mousedown`. Isso permite que o usuário que clicou por engano arraste o cursor ou dedo para fora do botão antes de soltar, cancelando a ação indesejada.
- **Tamanho de Alvo Generoso (WCAG 2.2 SC 2.5.8):** Área de clique de no mínimo **$44 \times 44\text{px}$** no mobile e desktop para controles primários, prevenindo toques errôneos em alvos adjacentes.

### 3.3. Sem Limites Rígidos de Tempo (WCAG 2.2.1)
- Sessões bancárias ou formulários transacionais não devem deslogar subitamente o usuário sem aviso prévio.
- **Aviso e Prorrogação:** Quando um timeout de sessão for inevitável por segurança regulatória, exibir um aviso modal acessível pelo menos **2 minutos antes da expiração**, permitindo que o usuário estenda a sessão com uma tecla única (`Space` ou `Enter`).

---

## 4. Padrões de Engenharia para Deficiência Auditiva

### 4.1. Sinalização Visual para Eventos Sonoros (Canal Auditivo Alternativo)
- Se a aplicação emitir qualquer bipe sonoro de erro, chamada recebida ou notificação, deve haver imediatamente um equivalente visual claro (um toast na tela, animação de destaque no cabeçalho ou vibração tátil via `navigator.vibrate` em dispositivos móveis).

### 4.2. Integração com Tradutores Virtuais de Libras (Língua Brasileira de Sinais)
- Para a maioria das pessoas surdas alfabetizadas em Libras no Brasil, o português escrito é uma segunda língua com estrutura gramatical diferente.
- Garanta suporte a plugins de tradução em Libras (como VLibras e Hand Talk), mantendo a semântica de texto pura e sem bloquear a injeção do widget acessível.

---

## 5. Padrões de Engenharia para Neurodivergência e Saúde Mental

### 5.1. Sensibilidade ao Movimento e Prevenção de Crises (Epilepsia Fotossensível)
- **Zero Flashes Rápidos (WCAG 2.3.1):** Nenhuma animação ou efeito visual pode piscar mais de 3 vezes em qualquer intervalo de 1 segundo (risco crítico de indução a crises epilépticas).
- **Respeito Absoluto a `prefers-reduced-motion`:**
  Pessoas com distúrbios vestibulares (labirintite, tontura crônica) e autismo podem sofrer náuseas intensas ou sobrecarga sensorial com animações de parallax ou transições volumétricas. Desative movimentos desnecessários:
  ```css
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
      scroll-behavior: auto !important;
    }
  }
  ```

### 5.2. Autenticação Cognitiva Acessível (WCAG 2.2 SC 3.3.8)
- Pessoas com discalculia, dislexia ou perda de memória recente enfrentam imensas barreiras com CAPTCHAs que exigem cálculos matemáticos ou cópia de caracteres distorcidos.
- **Regras:**
  - Suporte total a colagem (`paste`) em campos de senha e códigos de autenticação em duas etapas (2FA/OTP), permitindo o uso de gerenciadores de senhas (Bitwarden, 1Password).
  - Priorize autenticação biométrica via WebAuthn / Passkeys.
  - Se utilizar verificação de segurança, utilize métodos que não exijam esforço cognitivo (ex: autenticação baseada em confirmação por e-mail ou notificação push no aplicativo do banco).

---

## 6. Checklist de Validação Real de Acessibilidade PcD

Antes de submeter código para review, o desenvolvedor deve realizar uma rodada de checagem com tecnologias assistivas:

- [ ] **Navegação com Leitor de Tela:** O fluxo crítico foi exercitado com NVDA (Windows) ou VoiceOver (Mac/iOS) com a tela desligada ou olhos vendados? Os rótulos fazem sentido?
- [ ] **Navegação 100% por Teclado:** É possível completar o cadastro e submeter o formulário usando apenas `Tab`, `Shift+Tab`, `Space`, `Enter` e `Escape`?
- [ ] **Zoom de 400%:** O zoom de 400% foi ativado no navegador desktop e não há texto cortado nem scroll horizontal?
- [ ] **Simulação de Daltonismo:** A interface foi inspecionada sob filtros de Protanopia e Deuteranopia (via Chrome DevTools / Accessibility)? O status de erro continua discernível sem a cor vermelha?
- [ ] **Prefers-Reduced-Motion:** Ao ativar a opção "Reduzir movimento" no sistema operacional, todas as transições pesadas são silenciadas?
- [ ] **Conformidade Legal LBI / WCAG 2.2 AA:** Zero violações bloqueantes no `@axe-core/playwright`?
