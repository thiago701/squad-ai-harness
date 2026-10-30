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

---

## 3. Checklist de Auditoria Heurística Rápida para PRs de Frontend

Antes de submeter qualquer PR ou declarar uma tela pronta no review:

- [ ] **Feedback Imediato:** Cada clique em botão, tab ou toggle produz resposta visual (<100ms)?
- [ ] **Alvos Adequados (Fitts):** Todos os controles têm área de clique $\ge 44\times 44\text{px}$ no mobile e $\ge 24\times 24\text{px}$ no desktop?
- [ ] **Redução de Carga (Hick):** Formulários longos estão divididos em etapas lógicas com indicador de progresso?
- [ ] **Prevenção de Erros:** Há proteção contra cliques duplos em botões de ação? Os inputs possuem máscaras amigáveis?
- [ ] **Saída de Emergência:** Modais e drawers fecham com a tecla `Escape` e clique no backdrop?
- [ ] **Mensagens Construtivas:** Mensagens de erro explicam o que houve e como o usuário pode resolver?
- [ ] **Chunking de Dados:** Dados densos (documentos, moedas, telefones) estão formatados em blocos legíveis?
- [ ] **Consistência:** O vocabulário e os componentes visuais são idênticos aos do restante da aplicação?
