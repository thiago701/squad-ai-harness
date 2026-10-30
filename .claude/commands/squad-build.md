---
description: Executa o pipeline gated completo (Intake→Plan→GATE 1→Scaffold→TDD→Review→GATE 2→Commit) via squad-pipeline.
argument-hint: <objetivo/feature a construir> [--backend java|python]
origin: squad-ai
---

Você está executando o comando **/squad-build** — a fachada principal do **Core Orchestrator**.

Objetivo do usuário: **$ARGUMENTS**

Invoque a skill **`squad-pipeline`** e conduza o pipeline gated de ponta a ponta, com a cerimônia proporcional ao blast radius:

1. **Step 0 — Classificador de tamanho** (`trivial | small | standard | large`). O tier define quais fases rodam.
2. **Intake** (`engenheiro-especificacao`) → **Research & Reuse** (haiku) → **Plan** (`arquiteto-minimalista`, opus, com Pattern Grounding). Produza os artefatos em `.claude/plans/`.
3. **🚦 GATE 1 — aprovação humana.** Plano simples o suficiente? `P1>P2>P3` respeitado? Não avance sem aprovação.
4. **Scaffold** (estrutura via generator quando aplicável) → **TDD** (`especialista-qualidade` + `engenheiro-clean-architect`, sonnet): red → green → refactor.
5. **Gatilho de segurança automático:** se o diff tocar **auth, input de usuário, queries, criptografia ou secrets**, acione `engenheiro-seguranca` (opus) em modo bloqueante — vulnerabilidade crítica = 🔴 encerra o avanço.
6. **Review** (`tech-lead-review`, opus): rode os quality gates executáveis (via **`verificacao-loop`**) e exija o relatório **READY/NOT READY**. Pre-Report Gate: só reporte achados com >80% de confiança.
7. **🚦 GATE 2 — aprovação humana.** Diff revisado, gates verdes, sem secrets. Não comite sem aprovação.
8. **Commit** (`engenheiro-devops`): mensagem convencional + `Co-Authored-By`. **Memória:** registre resumo de sessão e ADR se houve decisão.

**Regras duras (gated, not autonomous):** nunca apague arquivos, sobrescreva config crítica sem backup, exponha secrets, instale deps sem justificar ou rode comando destrutivo sem confirmação. Handoff entre fases SEMPRE por artefato em arquivo (sem estado oculto).

**Arbitragem:** `P1-Simplicidade > P2-Performance > P3-CustoBaixo`. Segurança fora da escala — nunca negociada.
