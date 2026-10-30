# Eval held-out — piloto SkillOpt-Sleep (clean-code-craftsman)

Este diretório tem **dois** evals, de naturezas diferentes:

| Arquivo | Tipo | Para quê |
|---|---|---|
| `evals.json` | qualitativo (Ciclo 8) | revisão humana / `/review` da skill |
| `skillopt-pilot.json` | **objetivo, held-out** (ADR-004) | **sinal de recompensa do gate** do piloto SkillOpt-Sleep |
| `grade.py` | grader stdlib | extrai o código do smell dominante e pontua (hard reward) |

## Por que um eval objetivo

O gate do SkillOpt só aceita uma edição da skill se ela **melhora um score held-out**. Score
precisa ser **objetivo** — por isso a tarefa-piloto é *identificação*: dado um trecho com um
smell dominante, a skill responde com o **código do catálogo** (`F1`, `N1`, `G5`, `G30`, `G6`,
`C5`). O `grade.py` extrai o 1º código da resposta e compara com a referência. É um **proxy**
da competência da skill (não mede a refatoração inteira), mas é reprodutível e gateável.

## Split (anti-overfit)

- **train** (ids 1–6): usado para **propor** edições (o otimizador vê estas).
- **heldout** (ids 7–12): **só para o gate** — nunca usado para propor. Cobre os 6 smells comuns.

Manter o held-out cego é o que impede "melhorar no treino e piorar no geral".

## Como rodar

```bash
# 1) sanidade do dataset (sem API; e o que o CI roda)
python clean-code-craftsman/evals/grade.py --self-check

# 2) produza respostas rodando a skill em cada prompt (custa API) -> answers.jsonl
#    uma linha por tarefa: {"id": 7, "answer": "<resposta da skill>"}

# 3) pontue no held-out (o numero que o gate do SkillOpt compara antes/depois)
python clean-code-craftsman/evals/grade.py --score answers.jsonl --split heldout
```

## Integração com o piloto SkillOpt-Sleep

No ciclo gated (ver `docs/propostas/skillopt-adoption.md` + ADR-004), o `best_skill.md` candidato
só é aceito se o **score held-out subir** vs a versão atual da skill. O fluxo:

```
versao atual da skill --score heldout--> baseline
otimizador propoe best_skill.md (usando train) --score heldout--> candidato
GATE: candidato > baseline ? estagia PR : descarta (rejected-edit buffer)
```

O gate (`grade.py --score ... --split heldout`) é o oráculo. Nada é adotado automaticamente:
o PR estagiado passa por `auditoria-skill-externa` e decisão humana antes do merge.
