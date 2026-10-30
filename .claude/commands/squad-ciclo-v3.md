# /squad-ciclo-v3 — roda UM ciclo do Loop de Evolução V3

Execute UM ciclo do loop definido em `loops/v3/loop-evolucao-v3.md`, na ordem do backlog de ciclos de lá (primeiro ciclo não-fechado e não-bloqueado).

Protocolo obrigatório (resumo; a fonte é a spec do loop):
1. Leia `loops/v3/loop-evolucao-v3.md` (régua + backlog) e `loops/v3/trilha.jsonl` (estado).
2. Pré-registre a hipótese em `docs/plano-evo-v3/cicloN-*-hipotese.md` ANTES de qualquer medição.
3. Execute a alavanca com propriedade exclusiva de arquivos; respeite as proibições (gabarito/holdout/bench/protected-ruler) e a cegueira quando a alavanca tocar dados de avaliação.
4. Meça pela bateria (`v3-checks` no preview harness enquanto o Bash tool estiver morto) — a medição é o juiz, nunca a autoavaliação.
5. Decida keep/adjust/discard, registre na trilha (append-only, com model_id) e no `squad_decision_log`.
6. PARE nos gates humanos: adjudicação de gabarito, commits/PRs, paths protegidos, promoção de proxy, mudança de régua.

Nada é commitado pelo ciclo; entregas ficam no working tree para o GATE 2 humano.
