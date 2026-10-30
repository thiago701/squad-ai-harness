---
description: Panorama do estado atual — fase do pipeline, gates pendentes, artefatos, WORKING-CONTEXT e pendências.
argument-hint: [escopo: pipeline | repo | memória]
origin: squad-ai
---

Você está executando o comando **/squad-status** — fachada fina de observabilidade do orquestrador. Operação **somente leitura**.

Escopo: **$ARGUMENTS** (se vazio, reporte o panorama completo).

Consulte a skill **`squad-pipeline`** e a camada de memória para montar um panorama factual (sem alterar nada):

1. **Estado do pipeline:** fase atual, tier de tamanho classificado (Step 0), e qual GATE está pendente (GATE 1 / GATE 2 / nenhum).
2. **Artefatos de fase:** liste o que existe em `.claude/plans/` (`.prd.md`, `relatorio-research.md`, `.plan.md`, `relatorio-verificacao.md`) e seu status.
3. **WORKING-CONTEXT:** leia `memory/WORKING-CONTEXT.md` — verdade operacional atual, restrições e filas. Mostre o último resumo de sessão (funcionou/falhou/pendente).
4. **Repositório:** estado do git (branch, arquivos modificados/pendentes), sem executar nada destrutivo.
5. **Pendências e bloqueios:** itens aguardando aprovação humana, gates vermelhos, drift detectado.
6. **Custo do ciclo (R3/R12):** leia `squad-ai/metricas/custo_tokens.json` — total de tokens do ciclo, tarefas que estouraram o orçamento e a economia de roteamento. Reporte como painel resumido (não bloqueia; é observabilidade de P3).

**Entrega:** painel conciso em tabela Markdown com fase, gate pendente, artefatos, pendências e próximo passo recomendado (ex.: "rode /squad-build" ou "aprove o GATE 1"). Não execute ações — apenas reporte.
