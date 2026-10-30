# tech-lead-review · reference — Reunião de Consenso, Devolução aos Especialistas e ADR

> Conteúdo movido VERBATIM do hub `../SKILL.md` (ciclo 6c do Loop V3, 2026-07-09) — progressive
> disclosure. O template de ADR abaixo é o "template canônico do tech-lead-review" citado por
> `quality/quality-gates.md` (G3). Os gatilhos de acionamento do consenso e o limite de 3 rodadas
> permanecem no hub.

### Formato de Reunião de Consenso

```
REUNIÃO DE CONSENSO TÉCNICO
Duração: 25 minutos (não negociável — decisões ficam para depois se não houver consenso)

AGENDA FIXA:
  00:00–05:00  Apresentação do ponto de divergência (quem trouxe o tema)
  05:00–15:00  Rodada de posicionamento dos especialistas relevantes
               → Cada especialista fala 2 minutos, sem interrupção
               → Obrigatório: citar qual das 3 prioridades fundamenta a posição
  15:00–20:00  Debate facilitado pelo Tech Lead
               → Tech Lead aponta conflitos de prioridade explicitamente
               → Aplica regra de desempate das 3 prioridades quando necessário
  20:00–25:00  Formulação do consenso ou encaminhamento de nova rodada

RESULTADO POSSÍVEL:
  A) Consenso alcançado → documentado como ADR (Architecture Decision Record)
  B) Sem consenso → Tech Lead decide com base nas 3 prioridades + prazo
  C) Requer mais informação → especialista recebe pergunta específica com prazo
```

### Perguntas de Devolução aos Especialistas

Quando uma entrega de especialista precisa de aprofundamento antes do consenso, o Tech Lead usa este formato de devolução:

```
DEVOLUÇÃO AO ESPECIALISTA: [nome-do-especialista]
ENTREGA REFERENCIADA: [PR / componente / decisão]
PRIORIDADE AFETADA: [P1 / P2 / P3]

PERGUNTA ESPECÍFICA:
[pergunta objetiva, com contexto mínimo necessário]

CRITÉRIO DE ACEITAÇÃO DA RESPOSTA:
[o que a resposta precisa conter para destravar o consenso]

PRAZO: [data/sprint]
IMPACTO SE NÃO RESPONDIDO: [o que acontece se ficarmos sem resposta]
```

**Exemplos de Devolução:**

```
DEVOLUÇÃO AO: arquiteto-performance
ENTREGA: Cache Redis proposto para endpoint /pedidos/{id}
PRIORIDADE AFETADA: P3 (custo) vs P2 (performance)

PERGUNTA: Qual a latência atual medida do endpoint sem cache? O Redis se justifica
          com os dados de p95/p99 reais, ou o problema está na query (índice ausente)?

CRITÉRIO: Preciso do flamegraph ou slow query log antes de aprovar Redis.
          Se o problema for índice ausente, P1 exige a solução mais simples primeiro.

PRAZO: próxima daily
IMPACTO: sem dados, o Redis será recusado — não aprovamos infraestrutura por intuição.
```

```
DEVOLUÇÃO AO: engenheiro-clean-architect
ENTREGA: Interface `ProcessadorDocumento` com 8 métodos

PERGUNTA: Existe variação real e atual que justifica esta interface, ou ela foi criada
          para "o futuro"? Quantas implementações existem hoje?

CRITÉRIO: Se existe apenas 1 implementação e não há variação planejada para esta sprint,
          a interface viola P1 (abstração prematura). Remova-a.

PRAZO: antes do merge
IMPACTO: bloqueante — abstrações prematuras são 🔴 nas nossas regras.
```

---

## Architecture Decision Records (ADR)

Todo consenso técnico relevante deve ser documentado como ADR:

```markdown
# ADR-[número]: [título da decisão]

**Data:** YYYY-MM-DD
**Status:** Proposto | Aceito | Deprecado | Substituído por ADR-X
**Especialistas consultados:** [lista]

## Contexto
[Qual problema estamos resolvendo? Quais restrições existem?]

## Decisão
[O que decidimos fazer? Seja específico.]

## Prioridades aplicadas
P1 (Simplicidade): [como esta decisão honra ou sacrifica P1]
P2 (Performance):  [como esta decisão honra ou sacrifica P2]
P3 (Custo Cloud):  [como esta decisão honra ou sacrifica P3]

## Alternativas consideradas
| Alternativa | Por que foi descartada |
|---|---|
| [opção A] | [razão baseada nas 3 prioridades] |
| [opção B] | [razão baseada nas 3 prioridades] |

## Consequências
**Positivas:** [o que melhora]
**Negativas/Trade-offs:** [o que piora ou fica mais difícil]
**Tech Debt gerado:** [se houver, card criado: #número]

## Critério de revisão
[Quando devemos rever esta decisão? Qual evento ou métrica dispara revisão?]
```
