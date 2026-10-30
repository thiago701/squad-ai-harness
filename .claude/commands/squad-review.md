---
description: Code review final com tech-lead-review — 4 severidades, Pre-Report Gate (>80%), veredito READY/NOT READY.
argument-hint: [escopo: diff atual | <arquivo/PR> | descrição]
origin: squad-ai
---

Você está executando o comando **/squad-review** — fachada fina do papel Code Reviewer.

Escopo da revisão: **$ARGUMENTS** (se vazio, revise o diff atual do working tree).

Invoque a skill **`tech-lead-review`** (modelo recomendado: **opus**) e conduza a revisão:

1. **Inspecione o diff/working tree.** Use Read, Grep e Glob (somente leitura).
2. **Classifique cada achado** em 4 severidades: 🔴 bloqueante · 🟡 atenção/necessário · 🔵 sugestão · ⚪ nit/observação.
3. **Pre-Report Gate:** só reporte achados com **>80% de confiança**. HIGH/CRITICAL exigem **prova** (snippet + cenário concreto). Pule preferências meramente estilísticas.
4. **Arbitre** conflitos de design pela função `P1-Simplicidade > P2-Performance > P3-CustoBaixo` (máx. 3 rodadas de consenso; o Tech Lead decide).
5. **Gatilho de segurança:** se o diff toca auth/input/queries/cripto/secrets, escale para **`engenheiro-seguranca`** — crítico é 🔴 bloqueante e não-negociável.
6. **Lente Veracode (sempre):** invoque **`validacao-veracode`** no diff — `veracode_precheck.py` + `veracode_gate.py --perfil maximo` (inclua o `results.json` do Pipeline/Policy Scan se existir). Veredito `BLOQUEADO` ⇒ **NOT READY**; anexe o `veredito.md` ao relatório. Em repositório bancário/pagamentos use `--perfil bancario` (e `--release` no gate de release).

**Entrega:** relatório de review com veredito **READY / NOT READY** auditável (com a lente `rev-veracode` anexada) e, se aprovado e houve decisão, um ADR. Para validar os gates técnicos (cobertura, lint, build), use **/squad-quality-gate**.
