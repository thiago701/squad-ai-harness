# Caso 02 — Compactação Mid-Session

## Input
Orquestrador no meio do Sprint AI-3, acabou de criar KnowledgeBaseAdapter,
próximo passo é criar BedrockAgentAdapter.

## Esperado
Interromper task atual de forma segura:
1. Confirmar que commit do passo atual foi feito
2. Gerar checkpoint com estado parcial do sprint
3. Marcar claramente "SPRINT AI-3 PARCIAL — retomar em BedrockAgentAdapter"

## Critério de Sucesso
- Estado parcial claramente marcado
- Ponto exato de retomada identificado
- Commits feitos antes da compactação confirmados
