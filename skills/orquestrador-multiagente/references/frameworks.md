# Frameworks de Orquestração — escolha por modelo de controlo

> Procedência: material user-provided (2026-07-15). Números de setup/linhas/tokens são **comparativos
> ilustrativos, não confirmados** — ver `PROCEDENCIA.md`. O *modelo de controlo* de cada framework é o
> critério de decisão robusto; os minutos exatos, não.

## Tabela comparativa

| Dimensão | LangGraph | CrewAI | AutoGen (AG2) | LlamaIndex Workflows | Pydantic AI |
|---|---|---|---|---|---|
| Setup | ~18 min; curva íngreme (exige esquemas de estado) | ~8 min; papéis e tarefas intuitivos | ~22 min; ambientes de conversa complexos | ~15 min; foco em RAG | ~10 min; tipos nativos |
| Linhas p/ protótipo | Alta (80–150) | Baixa (30–60) | Média | Média (nós+eventos) | Baixa |
| Controlo de fluxo | **Máquina de estados por grafo** (ciclos+ramos explícitos) | Pipelines sequenciais/hierárquicos | **Modelo de atores** (conversa, seleção de orador probabilística) | **Orientado a eventos** (pub-sub assíncrono) | Estruturas programáticas + validação de esquema |
| Recuperação de erro | **Excelente** (caminhos de erro no grafo) | Média (risco de loop se ferramenta falha) | Boa (feedback conversacional) | Média (erro vira evento; fiação manual) | **Excelente** (validação estrita barra dado corrompido) |
| Eficiência de tokens | **Alta** (transições explícitas evitam reenvio) | Moderada (coordenação hierárquica gasta) | **Baixa** (chat de grupo → cada agente recebe histórico completo) | Alta (extração cirúrgica) | Alta (passagem estruturada+validação local) |

### Heurística de seleção
- **Fluxo com ciclos/ramificações e recuperação de erro forte** → LangGraph (grafo determinístico).
- **Time pequeno, papéis claros, protótipo rápido** → CrewAI (mas cuidado com loop quando ferramenta falha).
- **Debate/negociação entre agentes** → AutoGen/AG2 (aceitar o custo de tokens do chat de grupo).
- **Pipeline de recuperação/ingestão (RAG)** → LlamaIndex Workflows.
- **Contrato de dados rígido, familiaridade Pydantic** → Pydantic AI.

## STORM (STate-ORiented Management) — mediação de estado na escrita

Alternativa ao isolamento por **árvore de trabalho git por agente** (que adia conflitos para uma fusão
cara depois). O STORM **medeia o estado no momento da escrita**: monitoriza as interações com o espaço
de trabalho partilhado em tempo real, garante visão consistente do código e **deteta/mitiga conflitos
de edição imediatamente**.

- Ganhos empíricos reportados: **+18,7** (Commit0-Lite) e **+1,4** (PaperBench) vs isolamento git.
  *(números user-provided — não confirmados nesta absorção; ver PROCEDENCIA.md)*
- Lição arquitetural (robusta): **gestão de estado explícita > isolamento tardio** para colaboração MAS.

## Camada cognitiva opcional (ToM/BDI + solver simbólico)

Teoria da Mente (ToM) + modelos Crença-Desejo-Intenção (BDI) integrados com **resolvedores simbólicos**
para verificação lógica permitem avaliar matematicamente a correção de decisões colaborativas (ex.:
alocação de recursos), mitigando a variabilidade comportamental do LLM. Use quando a correção precisa
ser *provada*, não apenas plausível.
