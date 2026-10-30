---
description: REMEMBER da entrega — grava o desfecho REAL (success|failure|partial) de uma entrega em memory/episodes.jsonl a partir do preflight dela (run_id, tier, CTX, skills), ou invalida um episódio que um oráculo refutou. Fecha o laço de memória do squad-pipeline (Fase 7.5); o harness mede novidade contra essas entregas, não contra o canário.
argument-hint: <slug> <success|failure|partial> [--conceitos ...] | --invalida <run_id> --motivo "..."
origin: squad-ai
---

Você está executando o comando **/squad-remember** — o fecho de toda entrega (Onda 2 / I8 do plano de evolução de 11/10/2026). Fachada fina sobre `scripts/remember.py`: zero tokens de API, nenhuma inferência — o desfecho vem de quem o conhece.

Alvo: **$ARGUMENTS**.

Modelo **haiku** basta, ferramentas `Bash`, `Read`:

1. Rode, na raiz do repositório, UMA das formas:

   ```bash
   # entrega que passou pelo /squad-preflight (lê .claude/pipeline/<slug>/00-preflight.meta.json)
   python -X utf8 scripts/remember.py --slug <slug> --outcome <success|failure|partial> [--conceitos <dominio ...>]

   # entrega sem preflight (declare o run_id e as skills usadas)
   python -X utf8 scripts/remember.py --run-id <id> --outcome <desfecho> --skills <skill ...>

   # um oraculo refutou um episodio antigo (regressao no nightly, bug reaberto)
   python -X utf8 scripts/remember.py --invalida <run_id> --motivo "<por que>" [--por <run_id do oraculo>]
   ```

2. Regras que você NÃO relaxa:
   - **Desfecho = fato.** `success` só com GATE 2 verde e aprovação humana; `partial` quando entregou com débito declarado; `failure` quando abortou ou o gate reprovou. Nunca grave `success` por "parece ok".
   - **Idempotente.** Re-rodar para o mesmo `run_id` não duplica (o script diz `nada gravado`). Para corrigir um desfecho, não reescreva: `--invalida` o antigo e grave um novo com `--run-id <id>-v2`.
   - **Append-only.** `memory/episodes.jsonl` é local (nunca versionado) e nunca é editado à mão.
   - O canário do gate (`ops/run.py harness`) grava em `memory/episodes-canario.jsonl`; não misture.

3. Reporte ao motor em **uma linha**: `remember <run_id>: outcome=<desfecho> skills=<n> conceitos=<n>` (ou `remember: invalidado <run_id>`).

> **Quando rodar:** na Fase 7.5 do `squad-pipeline`, depois do Commit — ou ao encerrar a tarefa, mesmo abortada (aí o desfecho é `failure`). Vinte entregas gravadas é o mínimo (`memoria.MINIMO_HISTORICO`) para o estágio MEMORY do harness passar a decidir "território novo" com base em entregas reais.

**Entrega:** a linha de resumo. O comando não planeja, não executa e não promove nada a skill — promoção segue gated no `aprendizado-continuo`.
