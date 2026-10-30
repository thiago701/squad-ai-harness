---
description: Roda o loop cerebro-dev definido em loops/cerebro-dev-loop.md — executa UMA micro-tarefa de código Java/Python até build+testes verdes, lint 0 e cobertura ≥ alvo, com memória episódica e parada em PR gated.
argument-hint: "[requisito] [stack: java|python] [opcional: tentativas=3 cobertura=90]"
---

Execute o loop especificado em `loops/cerebro-dev-loop.md` (raiz deste repositório).
Leia esse documento primeiro e siga os passos da volta exatamente.

Resumo do contrato: peça e trave as entradas (`requisito`, `stack`, orçamento — default
3 tentativas / cobertura linha ≥90%, avisando quando usar default); no setup, crie o
worktree `workspaces/<tarefa>/`, pré-registre as bandas e grave o hash em
`memory/episodes.jsonl`; a cada volta faça UMA mudança (lições episódicas antes,
Q-table/tools antes de LLM), RODE o check (`mvn -q test`+JaCoCo ou
`pytest -q`+`ruff`+`coverage`) e COLE a saída no transcript — a parada é lida dessa
evidência; mantenha só o que não regrediu. Estados de parada: sucesso (Pronto colado ⇒
branch + PR + episódio), sem-progresso (2 voltas), bloqueado (chamar humano), esgotado
(orçamento). Erro ou estouro de teto NUNCA é sucesso. Escrita só em `workspaces/`,
`memory/`, `reports/` e branch isolada; `master` intocável; merge/push/deploy/efeito
externo exigem aprovação humana.

Inputs inline (se houver): $ARGUMENTS — se vazio, pergunte as entradas declaradas.
