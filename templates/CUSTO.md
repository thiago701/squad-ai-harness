# custo.md — Orçamento de tokens da tarefa `<slug>` · R3

> **Onde vive:** `.claude/pipeline/<slug>/custo.md` (um por tarefa do pipeline).
> **Quem preenche:** o motor `squad-pipeline` declara o orçamento no Plano (Fase 3) e registra
> o real a cada fase. **Por quê:** P3 (Custo Baixo) é prioridade — sem medir, não há gestão.

- **tier:** `<trivial | small | standard | large>`
- **orçamento declarado:** `<N>k` tokens (estimado no Plan)
- **modelo-base por fase:** haiku (pesquisa) · opus (plano/review/segurança) · sonnet (build/test)

| Fase | Modelo | Estimado | Real | Acumulado |
|---|---|---:|---:|---:|
| 1. Intake | sonnet | 15k | — | — |
| 2. Pesquisa (RETRIEVE) | haiku | 8k | — | — |
| 3. Plano | opus | 25k | — | — |
| 4. Scaffold | sonnet | 20k | — | — |
| 5. TDD | sonnet | 60k | — | — |
| (gatilho) Segurança | opus | 15k | — | — |
| 6. Review | opus | 30k | — | — |
| 7. Commit | sonnet | 10k | — | — |
| **Total** | | **<soma>** | — | — |

> **Tetos de referência por tier** (calibrar com o histórico em `squad-ai/metricas/custo_tokens.json`):
> trivial ~10k · small ~40k · standard ~150k · large ~500k.

## ⚠️ Alerta de 80%

Ao cruzar **80% do orçamento declarado**, o motor **pausa e reporta** ao humano:

> "A tarefa `<slug>` consumiu 80% do orçamento (`<real>`/`<orçado>`). Continuar, re-rotear para
> modelo mais barato, ou re-escopar?"

Nunca estoure em silêncio. Estourar para entregar **simples e correto** é aceitável **com
registro**; estourar por **desperdício de contexto** (MCPs demais, re-leitura) é o que o alerta caça.

## Veredito de custo (preencher no fechamento)

- **real vs orçado:** `<real>` / `<orçado>` → `<dentro | estourou>`
- **causa (se estourou):** `<escopo legítimo | desperdício de contexto>`
- **economia de roteamento estimada:** `<%>` vs tudo-opus
