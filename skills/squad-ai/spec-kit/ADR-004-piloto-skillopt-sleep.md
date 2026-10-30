# ADR-004 — Piloto gated do SkillOpt-Sleep (evolução medível de skills)

| Campo | Valor |
|---|---|
| **Projeto** | Squad AI Skill-Orchestrator |
| **ADR** | ADR-004 (skillopt-sleep) |
| **Data** | 2026-06-21 |
| **Autor(es)** | Squad AI (agente) |
| **Status** | Aceito (piloto) |
| **Decisores** | thiago701 (humano) |

---

## Contexto

Pediu-se avaliar adotar o **microsoft/SkillOpt** (otimizador validation-gated do *documento* de uma skill)
como job da pipeline harvest. O estudo está em [`../../docs/propostas/skillopt-adoption.md`](../../docs/propostas/skillopt-adoption.md).
O SkillOpt tem dois artefatos: o **pacote de pesquisa** (`skillopt-train`, pesado, precisa de
benchmark/env/data + compute) e o **SkillOpt-Sleep** (`skillopt_sleep`, leve, gated, review-then-adopt,
Claude-Code-nativo). Harvester = *descoberta* (largura); SkillOpt = *otimização* (profundidade) — eixos
ortogonais.

## Decisão

1. **REJEITAR** adotar o pacote de pesquisa como job do harvester horário — viola P1>P2>P3 e A10
   (nó errado, timeout 20 min, custo, lacuna de eval, supply chain, redundância com cerebro-vault). Reabrível
   **só por ADR**.
2. **ACEITAR** um **piloto Tier-1**: `skillopt_sleep` como **nó próprio gated**
   (`.github/workflows/skillopt-sleep.yml`) — nightly só a prova determinística (sem secret); ciclo real só
   por dispatch + `ANTHROPIC_API_KEY`, que **estagia** uma proposta (artefato), **nunca adota**.
3. Manter o **Tier-0** já entregue: a skill de referência `microsoft-skillopt` (a disciplina aplicada no
   `/squad-evolve-skills`+`skill-creator`).
4. Supply chain: pin `microsoft/SkillOpt@fc1f827`, auditado (`auditoria-skill-externa` → APROVAR c/
   condições, ver ATTRIBUTIONS §12); não usar o auto-scheduler; toda proposta passa por nova auditoria
   antes de adotar.

## Consequências

- **+** Ganho de skills passa a ser **medível** (gate held-out) sem tocar pesos nem custo de inferência no deploy.
- **+** Risco contido: gated, sandbox, pin por SHA, custo só sob dispatch explícito.
- **−** Há sobreposição com `cerebro-vault`/`/squad-nightly`; ao fim do piloto, **decidir consolidar** (absorver
  mecanismos OU adotar o tool e aposentar o homegrown) — novo ADR. Não manter os dois (P1).
- **Gatilho de reabertura (Tier 2):** piloto com `best_skill.md` de Δ ≥ 0 no eval held-out + custo dentro do
  orçamento → avaliar `skillopt-train` sob demanda para skills com benchmark/env.

## Smoke test (asserção ligada a gate real)

A prova determinística `python -m skillopt_sleep.experiments.run_experiment --persona researcher
--assert-improves` (MockBackend, custo zero) roda no CI nightly: falha se o sono não melhorar ou o gate
held-out não bloquear regressão — é a asserção viva deste ADR.
