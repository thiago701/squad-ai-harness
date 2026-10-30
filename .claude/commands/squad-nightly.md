---
description: Rotina noturna agendada (Proactive Scheduler) — drift-check, verificação de stack/links e /review com diff de nota.
argument-hint: [perfil: rápido | completo]
origin: squad-ai
---

Você está executando o comando **/squad-nightly** — fachada fina do **Proactive Scheduler** (rotina não-interativa, roda sem o usuário pedir).

Perfil: **$ARGUMENTS** (padrão: completo)

Acione o módulo **`scheduler`** e execute a bateria noturna de higiene proativa do ecossistema:

1. **Drift-check:** detecte divergências entre as superfícies espelhadas (README, copilot-instructions, vault, registry, listas de agentes hardcoded). Sinalize nomes inexistentes referenciados (ex.: `arquiteto-finops`), paths quebrados e skills fora do registry.
2. **Verificação de stack:** cheque versões/JEPs/preços AWS desatualizados nas skills (conteúdo datado "2026") e gate de links externos.
3. **Conformidade estrutural (rubrica §0.4):** rode `python scripts/auditoria_skills.py` e reporte a tabela machine-checkable — description acima do **teto 1500** (outliers), references **sub-linkadas**, cobertura de `evals/` (dívida priorizada), e ausência de Linha de Defesa/`origin`. Compare com a rodada anterior: **regressões** = nova skill sem Defesa, novo outlier de description, reference que deixou de ser linkada. (Roda também na suíte pytest via `test_auditoria_skills.py`.)
4. **Quality snapshot:** rode o **`/review`** do ecossistema e compute o **diff de nota** contra o baseline; aponte regressões. Quando quiser juízo independente por skill, use **`/squad-judge <skill>`** (cego à autoria, anti-inflação — ver `quality/independent-judge.md`).
5. **Governança do board e do laço score_after (V3 Fase 2, 2026-07-09):**
   - **Drift do registry:** rode `python scripts/generate_registry.py --check` — divergência disco↔registry é achado do relatório (não regenere na rotina; proponha PR).
   - **Auditoria score_after (contrato fitness v1.1):** rode `python scripts/backlog_score_audit.py --since 2026-07-09` — lista itens EVOLVE fechados como DONE sem `score_after` ou sem fonte declarada em `evidence` (contrato no `_comment` de `skills/backlog.json`). Report-only por padrão; `--enforce` (exit 1) só após GATE humano de adoção.
   - **WIP do board:** rode `python scripts/nightly_wip_check.py` — conta itens DOING por pilar (skills/subagents/cognition, excluindo surface-only); mais de 3 num pilar = flag no relatório (`--enforce` opcional, exit 1).
6. **Memória:** consolide o resumo da rotina e registre achados datados em `scheduler/` (relatórios com data).

**Modo seguro (gated, not autonomous):** a rotina **apenas detecta e reporta** — não corrige nem comita automaticamente. Para cada achado, proponha um PR/ação, mas exija aprovação humana. Nunca rode comando destrutivo.

**Entrega:** relatório noturno datado com drift encontrado, stack desatualizada, diff de nota e lista priorizada de ações sugeridas. Achados acionáveis viram chips/tarefas para o dia seguinte (ver /squad-daily-checkin).
