# Prioridades imutáveis (função de arbitragem)

> **Pack:** comum (always-on) · **Origin:** `squad-ai`
> Invariante. O detalhe vive em [`AGENTS.md §2`](../../AGENTS.md) e [`RULES.md`](../../RULES.md). Não duplicar.

A função de desempate de **toda** decisão técnica. **Número menor vence.**

```
P1 Simplicidade  >  P2 Performance  >  P3 Custo Baixo
        └────────── SEGURANÇA NUNCA É NEGOCIÁVEL (acima da função) ──────────┘
```

| # | Prioridade | O que sempre exige |
|---|---|---|
| **P1** | **Simplicidade** | Menor complexidade acidental que atende ao requisito. Na dúvida entre duas soluções, a mais simples. |
| **P2** | **Performance** | Só prevalece sobre P1 com **SLA explícito documentado** (meta registrada pelo `arquiteto-performance`). |
| **P3** | **Custo Baixo** | Roteamento de modelo por custo, free tier primeiro, menos tokens. Nunca às custas de P1/P2. |

## Regra de desempate

1. Conflito entre prioridades → **vence a de número menor** (P1 antes de P2 antes de P3).
2. P2 só passa na frente de P1 quando há **SLA explícito** que a simplicidade não cumpre — e a meta é registrada em ADR.
3. Toda escolha que pesou P1×P2×P3 vira **ADR** em `memory/decisoes/`. Decisão não registrada não aconteceu.

## Quando segurança vira veto

A segurança **não participa** da função — está **acima** dela. É cláusula pétrea:

- Qualquer prioridade que conflite com segurança **perde**: segurança vence sempre.
- Vulnerabilidade crítica = 🔴 **bloqueante**: para tudo, trava o gate (GATE 2/PR).
- **Nenhuma aprovação humana** libera um 🔴 — o caminho é corrigir, não autorizar.

> Lema: *autônoma para fazer o trabalho, gated para cruzar a linha.* P1 > P2 > P3, e segurança acima de tudo.
