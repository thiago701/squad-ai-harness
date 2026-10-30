# Heurísticas de Usabilidade, Ergonomia Cognitiva e Leis de UX para Interfaces Modernas

> **Quando ler:** ao conceber, prototipar, codificar ou auditar interfaces de usuário (UIs), SPAs e fluxos interativos.
> **Princípio imutável:** interfaces não devem exigir esforço cognitivo desnecessário. P1-Simplicidade na experiência humana precede sofisticação tecnológica.

---

## 1. As 10 Heurísticas de Usabilidade de Jakob Nielsen (NN/g) adaptadas a SPAs Modernas

As 10 heurísticas clássicas de Nielsen traduzidas para a arquitetura de interfaces reativas, componentes standalone e gerenciamento de estado moderno:

| # | Heurística | Princípio na Web Moderna / SPA | Anti-padrão a Evitar |
|---|---|---|---|
| 1 | **Visibilidade do status do sistema** | Fornecer feedback perceptível imediato (<100ms) para qualquer ação. Em operações assíncronas >1s, exibir progresso determinístico ou skeleton contextual. Informar claramente o estado de sincronização e conectividade. | Clicar em botão e não haver resposta visual; tela branca durante carregamento de rota sem indicador; spinner genérico bloqueando a tela inteira. |
| 2 | **Correspondência entre sistema e mundo real** | Utilizar linguagem, conceitos e metáforas familiares ao usuário final (DDD tático na UI). Formatar moedas, datas, números e endereços de acordo com o locale do usuário (`Intl.NumberFormat`, `Intl.DateTimeFormat`). | Exibir termos técnicos de banco de dados (ex: "Registro persistido com ID 4892"); códigos de erro HTTP crus ("Erro 422: Unprocessable Entity"); formato de data ISO em relatórios de negócios. |
| 3 | **Controle e liberdade do usuário** | Oferecer saída de emergência clara em qualquer fluxo (botão "Cancelar", fechamento via tecla `Escape` em modais e drawers). Permitir desfazer ações destrutivas reversíveis (padrão Undo via toast temporizado de 5s a 10s) em vez de interromper o usuário com confirmações invasivas. | Modais sem botão visível de fechar que não respondem ao `Esc`; fluxos tipo labirinto sem opção de retorno; falta de mecanismo para cancelar upload ou requisição longa. |
| 4 | **Consistência e padrões (Lei de Jakob)** | Manter consistência interna (mesmo design token, espaçamento e comportamento em todas as telas) e consistência externa (seguir convenções da web moderna: ícone de engrenagem para configurações, lupa para busca, carrinho/sacola no topo direito). | Botão primário verde em uma tela e azul em outra; links que abrem em nova aba sem aviso prévio; mudar a posição da barra de navegação entre páginas. |
| 5 | **Prevenção de erros** | Eliminar condições propensas a erros antes que ocorram. Validar campos em tempo real (inline) com debounce; mascarar inputs formatados sem quebrar o cursor; desabilitar de forma contextual ou aplicar throttle no botão de submit para evitar requisições duplicadas. | Permitir que o usuário preencha um formulário complexo de 20 campos para só apontar erros genéricos após o clique em submeter; permitir submissão múltipla por duplo-clique acidental. |
| 6 | **Reconhecimento em vez de recordação** | Tornar elementos, ações e opções visíveis. Utilizar histórico de buscas, autocomplete inteligente e chips de filtros selecionados visíveis e removíveis. Não forçar o usuário a memorizar códigos ou IDs de uma tela para digitar na seguinte. | Exigir digitação manual de código de filial ou ID de cliente existente; formulários em etapas que apagam os dados preenchidos na etapa anterior ao voltar. |
| 7 | **Flexibilidade e eficiência de uso** | Acomodar usuários novatos e experientes. Fornecer aceleradores de navegação (atalhos de teclado globais como `Ctrl+K` para busca e comando, `Ctrl+Enter` para submissão ágil), permitindo que usuários frequentes operem em alta velocidade. | Interfaces lentas que exigem uso exclusivo de mouse para operações repetitivas de alta frequência (ex: caixas bancárias, sistemas de faturamento). |
| 8 | **Estética e design minimalista** | Diálogos não devem conter informações irrelevantes ou raramente necessárias. Cada elemento visual extra compete com as informações prioritárias, diminuindo sua visibilidade relativa. Preservar o espaço em branco (whitespace) como elemento ativo de respiro e foco. | Dashboards sobrecarregados com dezenas de gráficos piscantes; textos densos sem hierarquia tipográfica clara; excesso de bordas e divisores visuais pesados. |
| 9 | **Ajudar usuários a reconhecer, diagnosticar e recuperar erros** | Mensagens de erro devem ser expressas em linguagem clara (sem códigos herméticos), apontar precisamente o problema na tela e sugerir construtivamente uma solução viável imediata. | Mensagens como "Ocorreu um erro inesperado"; mensagens de validação genéricas no topo da página sem indicar quais campos estão incorretos. |
| 10 | **Ajuda e documentação** | Embora seja melhor que o sistema possa ser usado sem documentação, disponibilizar textos assistivos contextuais (helper text sob campos críticos, tooltips com atraso calibrado) e documentação de suporte facilmente pesquisável e orientada à tarefa. | Manuais em PDF estáticos de 200 páginas fora do contexto da aplicação; tooltips que aparecem instantaneamente e cobrem o campo que o usuário está preenchendo. |

---

## 2. Leis Fundamentais de UX e Ergonomia Cognitiva

As leis psicológicas e biométricas que governam a percepção e o tempo de reação humano na interação com software:

### 2.1. Lei de Fitts (Tempo de Aquisição de Alvos)
$$T = a + b \log_2 \left( \frac{2D}{W} \right)$$
- **Definição:** O tempo necessário para alcançar rapidamente um alvo é função da distância até o alvo ($D$) e do tamanho do alvo ($W$).
- **Aplicação prática em UI:**
  - Botões de ação primária (CTAs) devem ser substancialmente maiores que ações secundárias ou terciárias.
  - Alvos de toque interativos em dispositivos móveis devem ter no mínimo **$44 \times 44\text{px}$** (e nunca inferiores ao critério WCAG 2.2 de $24 \times 24\text{px}$).
  - Fixar ações críticas em bordas ou cantos da tela (ex: barra inferior no mobile, topo fixo no desktop) reduz o tempo de alcance para perto do valor mínimo porque a borda atua como um limite físico "infinito".

### 2.2. Lei de Hick (Hick-Hyman - Sobrecarga de Decisão)
$$T = b \log_2(n + 1)$$
- **Definição:** O tempo que uma pessoa leva para tomar uma decisão aumenta logaritmicamente com o número ($n$) e a complexidade das opções disponíveis.
- **Aplicação prática em UI:**
  - **Progressive Disclosure:** Exponha apenas os dados e opções necessários para o momento atual. Divida formulários e cadastros complexos em etapas lógicas (Wizards multi-passo).
  - Limite escolhas simultâneas em menus suspensos e barras de navegação. Agrupe opções em categorias semânticas bem delineadas.
  - Destaque uma única recomendação como "Padrão" ou "Mais escolhido" para reduzir a paralisia de escolha.

### 2.3. Lei de Miller e Chunking de Informação
- **Definição:** A memória de curto prazo de um ser humano adulto médio suporta reter apenas cerca de **$7 \pm 2$** pedaços (chunks) de informação simultaneamente.
- **Aplicação prática em UI:**
  - **Chunking Estrutural:** Divida números e dados densos em blocos assimiláveis:
    - CPF: `000.000.000-00`
    - Telefone: `(11) 90000-0000`
    - Cartão de crédito: `0000 0000 0000 0000`
    - Código IBAN / Pix: agrupado em blocos legíveis com botão de cópia com um clique.
  - Limite listas não categorizadas e tabelas sem paginação ou paginação virtualizada.

### 2.4. Lei de Jakob (Expectativas de Padrões Mentais)
- **Definição:** Os usuários passam a maior parte do tempo em outros sites e aplicações. Eles esperam que a sua interface funcione da mesma maneira que as ferramentas com as quais já estão acostumados.
- **Aplicação prática em UI:**
  - Não tente reinventar padrões universais da web (ex: comportamento de checkbox, botão de voltar, atalhos de navegação, carrinho de compras, barra de busca com ícone de lupa).
  - Inovações devem resolver dores reais de negócio, não quebrar modelos mentais sedimentados.

### 2.5. Efeito Estética-Usabilidade
- **Definição:** Usuários frequentemente percebem designs esteticamente harmoniosos e atraentes como interfaces mais fáceis de usar, demonstrando maior tolerância a pequenos atritos ou falhas operacionais temporárias.
- **Aplicação prática em UI:**
  - Harmonia de cores (paletas baseadas em relações HSL calibradas), ritmo vertical estrito, tipografia com escalas proporcionais e microinterações polidas aumentam a confiança do usuário corporativo.
  - Estética nunca substitui a usabilidade funcional, mas catalisa sua adoção.

### 2.6. Princípio da Robustez de Postel
- **Definição:** "Seja conservador no que você produz; seja liberal no que você aceita."
- **Aplicação prática em UI:**
  - Campos de entrada devem aceitar variações razoáveis de dados (ex: aceitar documento com ou sem pontos e traços, telefone com espaços ou hifens) e normalizar o dado de forma transparente nos bastidores.
  - Nunca bloqueie o usuário com mensagens ranzinzas quando o frontend puder inferir e formatar o valor com segurança.

### 2.7. Regra do Pico-Fim (Peak-End Rule)
- **Definição:** As pessoas avaliam uma experiência amplamente com base em como se sentiram no momento mais intenso (pico — seja positivo ou negativo) e no momento final (fim), em vez de calcular a média aritmética de cada segundo da jornada.
- **Aplicação prática em UI:**
  - Otimize obsessivamente os pontos de maior fricção (ex: tela de checkout, confirmação de transferência, resolução de pendência).
  - O momento final deve ser recompensador: telas de sucesso com confirmação clara, comprovante gerado instantaneamente e próximo passo evidente.

### 2.8. Limiar de Doherty (`< 400ms`) e Responsividade `INP <= 200ms`
- **Definição (Walter J. Doherty, 1982):** A produtividade e o engajamento do usuário disparam quando o computador e o humano interagem em um ritmo (**`< 400ms`**) que garante que nenhum dos dois precise esperar pelo outro.
- **Aplicação prática em UI:**
  - Feedback tátil/visual instantâneo em **`< 100ms`** e **Interaction to Next Paint (`INP <= 200ms`)** cedendo a main thread via `await scheduler.yield()`.
  - Uso de **Optimistic UI** com rollback seguro para ações frequentes (favoritar, reordenar, alternar status) e skeletons estruturais para leituras de rede entre `150ms` e `1s`.

### 2.9. Lei de Tesler (Lei da Conservação da Complexidade)
- **Definição (Larry Tesler):** Todo sistema possui uma quantidade inerente e irredutível de complexidade. A única escolha de engenharia é **quem carrega essa complexidade**: o código do sistema ou o usuário humano.
- **Aplicação prática em UI:**
  - O engenheiro frontend deve absorver a complexidade no código: preenchimento automático de endereço via CEP, inferência automática da bandeira do cartão, cálculo em tempo real de impostos/parcelas com Signals (`computed()`) e defaults inteligentes baseados no histórico.

### 2.10. Lei do Túnel de Accot-Zhai (`Steering Law`) e `Safe Triangle`
$$T = a + b \int_C \frac{ds}{W(s)}$$
- **Definição:** O tempo para conduzir um ponteiro por um caminho delimitado (túnel de comprimento $D$ e largura $W$) cresce proporcionalmente a $D/W$.
- **Aplicação prática em UI:**
  - Menus em cascata obrigam o cursor a viajar por corredores estreitos; implemente o **Safe Triangle (Corredor Triangular de Intenção de Hover)** ou substitua cascatas de 3+ níveis por **Mega-Menus** ou **Command Palette (`Ctrl+K`)**.

---

## 3. Normas Internacionais de Ergonomia: ISO 9241-110:2020 e Bastien & Scapin (1993)

### 3.1. Os 7 Princípios de Interação da ISO 9241-110:2020
1. **Adequação à Tarefa (*Suitability for the user's tasks*):** o fluxo reflete o objetivo humano real, não a modelagem relacional de tabelas do banco.
2. **Autodescrição (*Self-descriptiveness*):** cada tela e componente deixa evidente onde o usuário está, o que pode fazer e qual o estado atual (`default`, `hover`, `focus-visible`, `active`, `loading`, `disabled`, `error`).
3. **Conformidade com as Expectativas (*Conformity with user expectations*):** vocabulário, ícones e atalhos previsíveis (Enter submete, Escape fecha, Ctrl+K busca).
4. **Adequação ao Aprendizado (*Learnability*):** descoberta progressiva (*progressive disclosure*), empty states instrutivos e feedback imediato que consolida o modelo mental.
5. **Controlabilidade (*Controllability*):** o usuário inicia, pausa, cancela (`AbortController`), desfaz (`Undo`) e compartilha o estado exato da tela via URL (`URL as State`).
6. **Robustez contra Erros de Uso (*Use error robustness*):** prevenção ativa, tolerância de formato (Postel), preservação dos dados digitados em caso de falha de rede e confirmação explícita apenas em ações destrutivas irreversíveis.
7. **Engajamento do Usuário (*User engagement*):** acabamento artesanal (Anti-"AI Slop"), zero layout shift (`CLS < 0.1`) e microinterações naturais (`Spring Physics`).

### 3.2. Os 8 Critérios Ergonômicos de Bastien & Scapin (18 Subcritérios)
- **C1. Condução:** Presteza (*Prompting*), Agrupamento/Distinção por Localização e por Formato (Gestalt), Feedback Imediato e Legibilidade (contraste WCAG 2.2 AA + **APCA $|L_c| \ge 60$**).
- **C2. Carga de Trabalho:** Brevidade (Concisão nos rótulos + **Ações Mínimas medidas via KLM-GOMS**, eliminando alternâncias teclado↔mouse) e Densidade Informacional equilibrada.
- **C3. Controle Explícito:** Ações Explícitas do Usuário (nada submete sozinho sem intenção clara) e Controle do Usuário sobre processamentos em andamento.
- **C4. Adaptabilidade:** Flexibilidade (múltiplos caminhos para a mesma meta: mouse, teclado, Command Palette) e Consideração da Experiência do Usuário (novato vs especialista).
- **C5. Gestão de Erros:** Proteção contra Erros, Qualidade das Mensagens de Erro (Tríade: *O que* + *Por que* + *Como resolver*) e Correção Rápida (foco automático no primeiro campo inválido).
- **C6. Homogeneidade / Coerência:** Design Tokens W3C DTCG semânticos garantindo identidade visual e comportamental unificada.
- **C7. Significado dos Códigos e Denominações:** Rótulos orientados a verbo de ação ("Transferir R$ 250,00" em vez de "OK") e ícones universais acompanhados de texto/label.
- **C8. Compatibilidade:** Alinhamento com o contexto físico, cultural e operacional do usuário (locale `pt-BR`, formatos Pix/CPF/CNPJ, acessibilidade LBI).

---

## 4. Checklist de Auditoria Heurística e Ergonômica para PRs de Frontend

Antes de submeter qualquer PR ou declarar uma tela pronta no review:

- [ ] **Feedback Imediato & Doherty (`< 100ms` / `INP <= 200ms`):** Cada clique em botão, tab ou toggle produz resposta visual imediata sem bloquear a main thread?
- [ ] **Alvos Adequados (Fitts & Hit Target Expansion):** Todos os controles têm área de toque real $\ge 44\times 44\text{px}$ no mobile e $\ge 24\times 24\text{px}$ no desktop (usando `::after` se o ícone visual for menor)?
- [ ] **Economia Motora (KLM-GOMS & Roving Tabindex):** O fluxo principal pode ser concluído 100% pelo teclado sem alternância forçada teclado $\leftrightarrow$ mouse?
- [ ] **Redução de Carga (Hick & Tesler):** A complexidade foi absorvida pelo sistema (auto-preenchimento, cálculos reativos, progressive disclosure)?
- [ ] **Fricção Zero em Formulários (Vercel Guidelines):** Botão de submit não está pré-desabilitado sem motivo; foco vai para o 1º erro; colagem (`paste`) permitida; `font-size >= 16px` no mobile?
- [ ] **URL as State & Controlabilidade (ISO 9241-110):** Filtros, abas, busca e paginação sobrevivem ao `F5` e ao botão Voltar? Modais fecham com `Escape`?
- [ ] **Mensagens Construtivas & Chunking:** Erros seguem a tríade (*O que + Por que + Como resolver*) e dados densos estão formatados em blocos legíveis?
- [ ] **Contraste Duplo (WCAG 2.2 AA + APCA $L_c$):** Texto normal atinge $\ge 4.5:1$ e $|L_c| \ge 60$ (ou $\ge 75$ para leitura fluida)?
