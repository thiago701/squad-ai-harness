# Loops Infinitos de Agentes (IAL) & Salvaguardas de Término

## O que é um IAL
**Infinite Agentic Loop**: execução perpétua e indesejada de chamadas a APIs/ferramentas ou transições
entre agentes **sem** atingir critério de parada/conclusão. Não é um loop de programação comum — emerge
da **interação** entre lógica do agente, semântica do framework, observações de runtime e mecanismos de
término. Amplifica um único pedido em execução longa → **exaustão de custo**, DoS de modelo, crescimento
de contexto e efeitos colaterais externos repetidos.

## Evidência empírica (CONFIRMADO)
Ferramenta de análise estática **IAL-Scan** sobre **6.549** repositórios reais de agentes: **74** achados
potenciais → **68 falhas IAL confirmadas** em **47 projetos**, **precisão 91,9%**. IAL-Scan abstrai o
código em um *Agent IR* independente de framework, constrói um **Agentic Loop Dependence Graph (ALDG)**
e verifica se caminhos de feedback alcançam repetidamente operações caras/que crescem estado sem limite.
Fonte: arXiv **2607.01641**, "When Agents Do Not Stop" (jul/2026) — **verificado nesta absorção**.

## Salvaguardas de mitigação (obrigatórias em produção)

| Mecanismo | Técnica | Impacto |
|---|---|---|
| **Limites de turnos (TTL/Max Turns)** | Teto rígido de iterações/chamadas na thread do orquestrador | Teto de custo por sessão; barra consumo ilimitado de créditos |
| **Deteção de estagnação semântica** | Cache vetorial das últimas mensagens; **similaridade de cosseno** turno-a-turno | Interrompe quando o agente repete a mesma ideia com sinónimos |
| **Disjuntores (circuit breakers) de handoff** | Monitorizar sequências de transferência p/ detetar ciclos repetidos | Impede falhas em cascata e exaustão de filas assíncronas |
| **Idempotência por ID de tarefa** | ID único persistente por tarefa delegada | Mensagens duplicadas/retransmitidas não disparam novos ciclos |
| **Funções de terminação estritas** | Estados finais obrigatórios `completed`/`failed`/`needs_human` no motor | Evita indefinição onde nenhum agente fecha a tarefa |

> Ponte com a Squad: a deteção de estagnação por cosseno espelha o gate de sinónimos do
> `senior-dev-cognitive-evolution`; `needs_human` é o GATE humano. Combine ≥2 salvaguardas — nunca só uma.
