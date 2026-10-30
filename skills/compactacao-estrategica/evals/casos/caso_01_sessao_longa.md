# Caso 01 — Sessão Longa com 5 Sprints

## Input
Sessão com 5 sprints implementados (AI-1 a AI-5), 180 testes passando,
múltiplos padrões estabelecidos, próximo sprint pendente.

## Esperado
Checkpoint compacto (< 500 tokens) preservando:
- Contagem de testes: 180 passed
- Commits de cada sprint (hash + mensagem)
- Padrão GIT_INDEX_FILE
- Constraints LGPD/CFM ativos
- Próximo item do backlog

## Critério de Sucesso
- Tamanho do checkpoint < 40% do contexto original
- Todos os 8 itens críticos presentes
- Nenhum output verboso de pytest/bash
