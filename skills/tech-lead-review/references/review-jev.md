# Review com Camada JEV — arquitetura, política de escalação e evidência

> **Fonte:** Proposta 1 aprovada — `labs/jev-ecosystem/docs/04-propostas-evolucao.md`.
> Benchmark completo: `labs/jev-code-review/docs/RELATORIO-FINAL.md` (44 PRs, cenários A/B/C/D).

## 1. Arquitetura

```
Context Builder → Cognitive Router → {ferramentas determinísticas · camada JEV · LLM}
        → Evidence Graph → Risk Aggregator → Quality Gate → Review Report + Risk Map
```

A camada JEV (`labs/jev-code-review/src/jev_review`) decompõe o review em **~47
microdecisões tipadas** (Choice/Score/Noul + probabilidade + confiança) em 10 domínios —
incluindo as 9 regras de Object Calisthenics como decisões independentes e
`correctness.race` — com achado ancorado em evidência (arquivo:linha).

## 2. Resultados medidos (44 PRs)

| Cenário | Motor | Recall | Veredito | Custo/PR | p50 |
|---|---:|---:|---:|---:|---:|
| A — skill original fiel | LLM v4-pro | 0,868 | 0,364 | US$ 0,0018 | 4,6 s |
| B — evoluída SEM Jev (49 perguntas) | LLM flash | 0,985 | 0,705 | US$ 0,0029 | 6,8 s |
| **C — JevSim + ferramentas (padrão)** | código | **1,000** | **1,000** | **US$ 0,00** | **3 ms** |
| D — híbrido (C + escalação) | JevSim + v4-pro | 1,000 | 0,886 | US$ 0,0003 | 8 ms |
| D-strict — escalação estrita + cap | JevSim + v4-pro | 0,959 | 0,932 | US$ 0,0005 | 8,5 ms |

## 3. Política de escalação (aprovada pelo gate)

- **Padrão:** cenário C (JEV encerra; 0 chamadas LLM).
- **Escalação obrigatória:** segurança critical/high e regressão HIGH → LLM avançado.
- **Cap de severidade:** achados vindos da escalação em domínios não-segurança não
  podem inflar severidade (causa raiz do over-blocking 27/44, corrigida no ciclo 7).
- **PR de alto risco:** modo D-strict (cobertura extra a US$ 0,0005/PR).

## 4. Status do Jev real

- `JevSim` (determinístico) — usado em todos os benchmarks; é o piso.
- `TypeSafeJev` — conector wire-compatible com `api.typesafe.ai/v1/systemone`
  implementado e testado por contrato (`tests/test_typesafe.py`); **validação com a
  API real pendente** de `TYPESAFE_API_KEY`. Rodar as mesmas suítes com o provider
  typesafe e deixar o Quality Gate anti-regressão decidir a adoção final.

## 5. Como re-medir

```bash
cd labs/jev-code-review
python run.py --benchmark          # re-roda A/B/C/D + gate anti-regressão
```
