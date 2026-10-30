---
description: Captura o objetivo, classifica o tamanho (Step 0) e produz o plano (.prd.md + .plan.md) até o GATE 1.
argument-hint: <objetivo de negócio em linguagem natural> [--backend java|python]
origin: squad-ai
---

Você está executando o comando **/squad-plan** — a fachada fina das fases iniciais do pipeline gated.

Objetivo do usuário: **$ARGUMENTS**

Invoque a skill **`squad-pipeline`** e conduza APENAS as fases de planejamento (não implemente nada ainda):

1. **Step 0 — Classificador de tamanho.** Classifique o blast radius em `trivial | small | standard | large` (arquivos tocados, deps novas, ambiguidade, área sensível). Declare o tier e quais fases ele ativa.
2. **Intake / Descoberta.** Acione `engenheiro-especificacao` para capturar objetivo, critérios de aceite e restrições. Produza `.claude/plans/<slug>.prd.md`.
3. **Research & Reuse** (haiku, "pesquise antes de codar"). Acione o agente de pesquisa para inventariar código e padrões existentes no repositório antes de propor solução nova. Produza `relatorio-research.md`.
4. **Plan.** Acione `arquiteto-minimalista` (opus) para desenhar a solução mais simples (anti-overengineering), com **Pattern Grounding** (referencie padrões reais já presentes no repo). Produza `.claude/plans/<slug>.plan.md`. Se houver decisão de stack/custo relevante, consulte `arquiteto-cloud-aws`.

**Arbitragem:** `P1-Simplicidade > P2-Performance > P3-CustoBaixo`. Segurança nunca é negociável.

**Pare no GATE 1.** Apresente o plano e peça aprovação humana explícita antes de avançar para Scaffold/TDD. Não inicie implementação grande sem spec aprovada. Para construir após a aprovação, instrua o usuário a rodar **/squad-build**.
