# Equipe de Pesquisa Multiagente, Vereditos Out-of-Sample, Platô de Varredura e Ledger Anti-Reteste

> **Procedência:** padrões arquiteturais extraídos e reescritos em português brasileiro a partir da análise de `@thedelost` (`CLAUDE CODE REGISTRY TIP · 10 REPOS · ONE .CLAUDE FOLDER`) e do curso técnico de `@hanakoxbt` (*How to Build an AI Quant Research Team with Claude Code*, out/2026). Nenhum código externo foi copiado; os algoritmos de verificação foram implementados do zero em stdlib (`../scripts/veredito_plat_ledger.py`).

---

## 1. As 3 Primitivas que Aterrisam em `.claude/` e Higiene de Ingestão

Todo componente instalado num ambiente agêntico cai em uma de **três categorias estruturais**, cada qual com um papel distinto na proteção da janela de contexto e da segurança:

| Primitiva | Onde vive | Mecanismo de Contexto / Execução | Regra de Ouro |
|---|---|---|---|
| **1. Subagents** | `.claude/agents/*.md` | **Trabalho delegado em contexto isolado** (*isolated context*). O agente principal (`lead`) envia a tarefa e recebe apenas o artefato/veredito final. | **Um especialista por papel ou linguagem** (`one reviewer per language`) e **menor privilégio de tools** (*least agency*). |
| **2. Skills** | `skills/*/SKILL.md` | **Carregamento progressivo** (*progressive load*). Apenas `name` e `description` ficam residentes no contexto; o corpo (`body idle`) e `references/` só entram quando há *match*. | **Descrição enxuta (≤ 500 chars)** e conteúdo denso separado em `references/`. |
| **3. Hooks** | `.claude/settings.json` / `hooks/` | **Guarda-corpo determinístico** (*deterministic*). Dispara em chamadas de ferramentas (`PreToolUse` em `Edit\|Write\|Bash`). | **Código de saída `2` (`exit 2`) bloqueia a chamada** na hora — faz o agente parar nas suas regras em vez de parar para perguntar a você. |

### Higiene ao consumir registries e marketplaces externos
Catálogos públicos oferecem centenas de agentes e skills gratuitos, mas **copiar tudo para `.claude/` destrói a atenção do modelo e infla o custo de sessão**:
1. **Leia o `README` antes de copiar qualquer arquivo** (`reading the README before anything is copied`) e passe pela `auditoria-skill-externa`.
2. **Instale seletivamente apenas o que será usado no ciclo atual** (`only what gets used this week was copied`).
3. **Orquestração sob demanda:** prefira empacotar fluxos de coordenação como *skills* carregadas sob demanda (padrão `am-will/swarms`) em vez de manter prompts de orquestração gigantes sempre residentes.

---

## 2. Desacoplamento "Analista vs. Mesa" (*Analyst vs. Desk*) e `THE LINE`

Um modelo de linguagem respondendo de memória sobre dados ou métricas que não verificou produz apenas **um palpite mais convincente** (*"A smarter model with no data is just a more convincing guess"*). Em sistemas multiagentes de engenharia, pesquisa ou finanças:

1. **A IA pensa; o servidor/código calcula:** nenhum agente da equipe calcula métricas estatísticas, coberturas ou indicadores de cabeça. O agente formula a hipótese/regra e invoca a ferramenta determinística (via MCP ou script local); o motor executa sobre a base histórica e devolve o resultado.
2. **Dados íntegros (*Point-in-Time* e sem viés de sobrevivência):** antes de testar qualquer hipótese, valide se o dataset inclui itens descontinuados/falhos (*survivorship bias*) e se os registros usam a data em que a informação ficou disponível, não a data de referência retroativa (*look-ahead bias*).
3. **Divisão Temporal Obrigatória (*Train vs. Held-Out*):** toda avaliação é dividida por um corte temporal explícito (`ano_corte` / `timestamp_corte`). Regras são calibradas apenas na janela anterior e reexecutadas intocadas na janela retida (*held-out*). **Divisões aleatórias (*random splits*) sobre séries temporais são recusadas por design**, pois vazam o futuro no passado.
4. **O Veredito como Contrato Imutável entre Agentes:** todo estudo termina com um de **3 vereditos fixos** calculados pelo código (nenhum agente pode argumentar contra o veredito):
   - **`DATA_VALIDATED`** — superou o benchmark nos **dois** eixos (ex.: crescimento/throughput **e** retorno ajustado ao risco/estabilidade) tanto na janela de treino quanto na janela *held-out* que nunca viu;
   - **`TRADE_OFF`** — superou o benchmark em apenas um dos eixos (decisão cabe ao humano);
   - **`NO_EDGE`** — não superou o benchmark em treino ou *held-out*.
5. **A Linha Divisória (`THE LINE` — *The agents research, your code executes*):**
   - Nenhuma ferramenta exposta aos agentes de IA tem permissão para executar ordens financeiras, alterar produção ou disparar efeitos irreversíveis.
   - Os agentes pesquisam, validam e entregam o código revisado; a execução em produção roda em código determinístico sob chaves controladas pelo humano.

---

## 3. Topologia de 5 Agentes com Separação Criador × Avaliador

> **Princípio inegociável:** *"O agente que teve a ideia nunca deve ser o agente que a avalia."* Em um único chat, ele sempre é.

| Papel (`subagent`) | Modelo (`model`) | Ferramentas permitidas (*Least Agency*) | Missão estrita e restrições |
|---|---|---|---|
| **`lead`** *(sessão principal)* | `opus` | Coordenação / delegação + leitura do ledger | Transforma uma pergunta em plano, aciona o `scout` antes de qualquer teste e decide o próximo passo com base no veredito. |
| **`scout`** | `sonnet` | Apenas consulta de metadados/cobertura (`query_warehouse`) | Confirma universo, intervalo de datas, campos necessários, lacunas e integridade *point-in-time* antes de rodar qualquer estudo. **Proibido de rodar testes/backtests.** |
| **`sweeper`** | `sonnet` | Execução de grade e coleta (`run_sweep`, `run_backtest`, `fetch_job`) | Testa uma regra em uma **grade completa de configurações** (ex.: 5×4 = 20 células em 1 chamada), nunca em um ponto único. Devolve o veredito de cada célula sem arredondar, suavizar ou esconder falhas, indicando se as células `DATA_VALIDATED` formam um **platô (`plateau`)** ou um **pico isolado (`isolated_peak`)**. |
| **`skeptic`** | `opus` | Desafio e teste de estresse (`challenge_finding`, `run_backtest`) | **Roda no modelo mais forte de propósito** (*"Gerar ideias é barato; matar ideias ruins é onde o dinheiro é economizado"*). Seu único trabalho é fazer o resultado falhar: testa anos *held-out*, parâmetros vizinhos, outros universos e o pior período de queda (*drawdown*). Se não conseguir quebrar, lista tudo o que tentou. |
| **`librarian`** | `haiku` | Apenas busca no catálogo (`search_library`) | Localiza estratégias/padrões já documentados com evidência prévia que se aplicam à pergunta. **Proibido de rodar testes.** |

### Detecção de Platô (`plateau`) vs. Pico Isolado (`isolated_peak`)
Uma hipótese real se sustenta nas configurações vizinhas; um acerto por sorte morre um passo ao lado:
- **`plateau` (Robusto):** existem pelo menos $K \ge 2$ células `DATA_VALIDATED` ortogonalmente adjacentes na grade de parâmetros (ou componente conexa mínima cobrindo vizinhança em ambas as dimensões).
- **`isolated_peak` (Sorte / Overfitting):** células `DATA_VALIDATED` aparecem isoladas, cercadas por `NO_EDGE` ou `TRADE_OFF`. Mesmo que a célula isolada tenha números excelentes, ela é **reprovada** como overfitting.

---

## 4. Ledger Compartilhado (`research.md`) e as 4 Leis Invariantes

Para que a equipe acumule inteligência em vez de repetir investigações (*"the team compounds"*), todos os agentes compartilham um único arquivo de registro (`research.md` ou `.claude/pipeline/<slug>/ledger.md`) que **todo agente lê primeiro e escreve por último**:

```markdown
## Q-014  <a pergunta ou hipótese em uma linha>
status:   open | accepted | dead
verdict:  DATA_VALIDATED | TRADE_OFF | NO_EDGE
sweep:    <tamanho da grade>, plateau | isolated_peak | none
skeptic:  <ponto mais fraco encontrado, ou lista de tudo o que tentou sem quebrar>
next:     <próximo passo, ou "do not retest without a new reason">
```

### As 4 Leis que toda a equipe obedece:
1. **Registro antes do resumo:** todo experimento é gravado no ledger com seu veredito *antes* de produzir qualquer resumo narrativo.
2. **Promoção estrita:** apenas resultados `DATA_VALIDATED` avançam para o estágio seguinte (varredura $\to$ cético $\to$ aceite).
3. **`NO_EDGE` é resultado, não erro:** uma hipótese sem ganho recebe `status: dead` e `next: "do not retest without a new reason"`. Tentar retestar um item `dead` sem fornecer uma razão/evidência nova explícita é **bloqueado deterministicamente**.
4. **Sobrevivência ao `skeptic`:** uma hipótese só recebe `status: accepted` se formou `plateau` no `sweeper` **e** o `skeptic` registrou os ataques realizados sem conseguir quebrá-la.
