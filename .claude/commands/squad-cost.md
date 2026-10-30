---
description: Análise FinOps/TCO da arquitetura (arquiteto-cloud-aws) + custo de contexto/tokens (context-policy). Build-vs-buy.
argument-hint: [alvo: arquitetura AWS | fatura | build-vs-buy | custo de contexto]
origin: squad-ai
---

Você está executando o comando **/squad-cost** — fachada fina do papel Cost Optimizer (FinOps) e da disciplina de custo de contexto.

Alvo: **$ARGUMENTS**

Invoque a skill **`arquiteto-cloud-aws`** (FinOps/TCO, modelo sonnet→opus) e, para custo de tokens/janela de contexto, aplique a política **`context-policy`** (Token & Context Optimizer):

1. **TCO da infraestrutura (`arquiteto-cloud-aws`):** rightsizing, Savings Plans / Reserved Instances / Spot, AWS Budgets, Cost Explorer, **free tier first**. Compare sempre o custo de **construir código próprio vs. usar serviço gerenciado** (build-vs-buy) — incluindo o custo do time de engenharia.
2. **Custo de contexto (`context-policy`):** orçamento de tokens por fase, quando compactar (fronteiras lógicas), limites `≤10 MCPs / ≤80 tools`, e o ganho de refatorar skills monolíticas para hub+references (padrão −87% tokens).
3. **Model routing como economia:** haiku para exploração, sonnet para implementação, opus só para arquitetura/segurança/debug complexo — corta 60–70% do custo de inferência.

**Arbitragem:** custo é **P3** — só decide depois de P1-Simplicidade e P2-Performance. Nunca sacrifique simplicidade para economizar.

**Entrega:** análise de TCO com recomendação priorizada (quick wins primeiro), estimativa de economia e, quando relevante, veredito build-vs-buy fundamentado.

---

## Modo "custo de tarefa" / painel por ciclo (R3 + R12)

Além do FinOps de infra, o `/squad-cost` agora lê `squad-ai/metricas/custo_tokens.json` (custo de tokens por tarefa, registrado pelo `squad-pipeline` em `.claude/pipeline/<slug>/custo.md`) e responde:

- **gasto de tokens por tarefa e por ciclo** (real vs orçado por tier);
- **tarefas que estouraram o orçamento** e a causa (escopo legítimo vs desperdício de contexto);
- **economia real do roteamento de modelo** (haiku/sonnet vs tudo-opus);
- **painel por ciclo (R12):** total do ciclo + tendência, no formato de métrica tipo DORA de custo.

> Alvo `custo de contexto` no `$ARGUMENTS` foca tokens/janela; alvo `arquitetura AWS | fatura | build-vs-buy` foca infra (FinOps). Custo é **P3**: informa, não tiraniza.

## Custo por entrega (Onda 1 / I15, 11/10/2026)

O usage real de cada sessão chega ao `memory/sli.jsonl` pelo hook Stop (`hooks/stop_extract_telemetry.py`). Para ver tokens frescos por sessão casados com o preflight de cada entrega e o agregado por tier, rode `python -X utf8 scripts/relatorio_entrega.py` (ou `python ops/run.py relatorio-custo`, que também grava `custo.md` na pasta de cada entrega). Sem `--com-ids` o relatório não traz run_id, slug nem enunciado — é o que pode sair da estação de trabalho (D11).
