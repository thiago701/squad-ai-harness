# squad-pipeline · reference — Fase 0.5 RETRIEVE e Fase 7.5 REMEMBER (laço de memória)

> Conteúdo movido VERBATIM do hub `../SKILL.md` (ciclo 4 do Loop V3, 2026-07-09) — progressive
> disclosure. **Nota de resolução de paths:** os caminhos relativos abaixo permanecem como no hub e
> se resolvem a partir de `skills/squad-pipeline/` (raiz da skill), não deste subdiretório.

## Fase 0.5 — RETRIEVE (recuperar antes de planejar) · R6

Após o Step 0 e **antes** do Plano, rode o **RETRIEVE** do ReasoningBank (R2): puxe as trajetórias
e instintos já aprendidos no `domain` da tarefa. Isso evita reaprender e repetir becos sem saída.

- **Como:** `/squad-recuperar <domain e palavras-chave>` (ou o motor faz `grep` em
  `.claude/banco-padroes/<domain>.md` + `anti-padroes.md` + `.claude/instintos/`, top-3 por `confidence`).
- **Saída:** "padrões anteriores neste domínio: …" + "becos a evitar: …" — entra como contexto do Plano.
- **Sem match:** siga normal (ausência de evidência ≠ evidência; não invente padrão).
- **Tier:** recomendado em small+; opcional em trivial. Custo baixíssimo (modelo haiku).

## Fase 7.5 — REMEMBER (consolidar depois de entregar) · R2

Fecha o laço aberto pelo RETRIEVE (Fase 0.5): após o Commit (ou ao encerrar a tarefa, mesmo
abortada), o motor registra **um episódio idempotente por run** com o REMEMBER de entrega
(I8, Onda 2 — `scripts/remember.py`, fachada `/squad-remember`):

```
python -X utf8 scripts/remember.py --slug <slug> --outcome success|failure|partial [--conceitos <domínio>]
python -X utf8 scripts/remember.py --run-id <id> --outcome failure --skills <skills>      # sem preflight
python -X utf8 scripts/remember.py --invalida <run_id> --motivo "nightly refutou" [--por <run_id>]
```

- Lê `.claude/pipeline/<slug>/00-preflight.meta.json` (run_id, tier, CTX, **skills do RETRIEVAL**) e
  `custo.md` (se `/squad-cost --gravar` rodou) — não reexecuta o harness.
- Grava `tipo=entrega` em `memory/episodes.jsonl` — idempotente por `run_id` (re-execução não duplica).
  Conceitos no mesmo vocabulário do canário (`tier:`, `ctx:`) mais os que você passar.
- **O canário do gate grava em `memory/episodes-canario.jsonl`** (`ops/run.py harness`): a memória de
  entrega não se mistura com planos sintéticos. O estágio MEMORY do harness mede a novidade contra as
  entregas reais e só cai no canário quando ainda não há nenhuma.
- **Invalidação:** um registro `tipo=invalidacao` aponta o `run_id` refutado; `memoria.historico`
  passa a ignorá-lo (e nunca devolve a invalidação em si). Ledger append-only: nada é reescrito.
- O episódio alimenta o fitness R3 e é o que o RETRIEVE recupera nas próximas tarefas do domínio.
- O caminho antigo (`scripts/cognitive_core/cli.py consolidate`) continua válido para episódios de
  outros tipos (`task`, `review`, `ciclo-cognitivo`); entregas do pipeline usam o REMEMBER acima.
- **Gated:** o registro do episódio é factual (o que aconteceu); promoção a instinto/skill continua
  passando pelo rito do `aprendizado-continuo` — nunca automática.
