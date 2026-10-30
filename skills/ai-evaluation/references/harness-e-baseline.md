# Harness de avaliação — execução reproduzível, comparação e relatório

> Referência da skill `ai-evaluation`.

## 1. Estrutura mínima

```text
benchmark/
├── eval-set/
│   ├── manifest.yaml         # versão, N, composição por subgrupo, consentimento
│   ├── fotos/
│   └── casos.jsonl           # {"caso_id","foto_id","theme_id","seed"}
├── runs/
│   └── 2026-08-24T14-02_gemini-flash-image_v1/
│       ├── config.json       # provedor, modelo, prompt_ref, resolução, passos, código (git sha)
│       ├── resultados.jsonl  # uma linha por caso (formato §6 do hub)
│       ├── imagens/
│       └── resumo.json       # agregados com IC
├── baselines/
│   └── BASELINE.json         # ponteiro para o run congelado + selos
└── run.py                    # um comando, sem passo manual
```

`config.json` precisa conter o **git sha** do código: sem isso, "o mesmo modelo" pode ter rodado
em pipelines diferentes e a comparação é inválida.

## 2. Um comando, sem passo manual

```bash
python benchmark/run.py --provider gemini --eval-set v2 --tag baseline
python benchmark/run.py --provider fal-kontext --eval-set v2 --tag cand-01
python benchmark/compare.py --base baseline --cand cand-01
```

Se reproduzir exige "abrir o notebook e rodar as células", não é reproduzível — é uma demo.

## 3. Agregação honesta

```python
import numpy as np

def resumo(xs: list[float]) -> dict:
    a = np.asarray(xs, dtype=float)
    return {
        "n": int(a.size),
        "p50": float(np.percentile(a, 50)),
        "p95": float(np.percentile(a, 95)),
        "p99": float(np.percentile(a, 99)),
        "media": float(a.mean()),
        "desvio": float(a.std(ddof=1)) if a.size > 1 else 0.0,
    }
```

- **Percentis, não média**, para latência. A média esconde o evento ruim; o p95 é o que a fila sente.
- **N sempre visível** ao lado do número.
- **Excluir falhas do cálculo de latência** e reportá-las separadamente — senão uma queda na taxa
  de sucesso aparece como "ficou mais rápido".

## 4. Comparação pareada — a forma correta de A/B

O mesmo caso (mesma foto, mesmo tema, mesma seed) roda nos dois braços. Compare **as diferenças
por par**, não as médias dos grupos: isso remove a variação entre fotos, que costuma ser maior
que a diferença entre modelos.

```python
d = np.array(cand) - np.array(base)            # diferenças pareadas
media_d = d.mean()
ic95 = 1.96 * d.std(ddof=1) / np.sqrt(d.size)  # intervalo de confiança
vence = d > 0
print(f"Δ={media_d:+.3f} ± {ic95:.3f}  (vence em {vence.sum()}/{d.size} pares)")
```

**Leitura:** se o intervalo de confiança **inclui zero**, a diferença é indistinguível de ruído —
reporte "sem diferença detectável com N=X", nunca "o candidato é melhor". Além do IC, reporte
**em quantos pares** o candidato venceu; 11 de 12 é um sinal forte mesmo com N pequeno.

## 5. Relatório de comparação (template)

```markdown
## cand-01 (fal-kontext) × baseline (gemini-flash-image) — eval-set v2, N=60

| Eixo | Baseline | Candidato | Δ pareado (IC95) | Vence em | Veredito |
|---|---|---|---|---|---|
| Identidade (similaridade) | 0,61 | 0,64 | +0,03 ± 0,02 | 41/60 | 🟢 ganho |
| Nota humana "postaria?"   | 72%  | 78%  | +6 pp ± 5 pp   | —      | 🟢 ganho |
| Latência p95 e2e (s)      | 13,1 | 16,8 | +3,7 ± 1,1     | 12/60  | 🔴 regressão |
| Custo/imagem (US$)        | 0,040| 0,042| +0,002         | —      | 🟡 |
| Taxa de sucesso           | 97%  | 95%  | −2 pp          | —      | 🟡 |

**Decisão:** REJEITADA. Ganho real de qualidade, mas +3,7 s no p95 estoura o SLA de 15 s
ponta a ponta. Reavaliar se o tempo de pré-processamento cair.
**Selo:** medido · 2026-08-24 · git sha abc1234 · seeds fixas.
```

Uma tabela, um veredito, uma justificativa. Sem prosa de convencimento.

## 6. Armadilhas

| Armadilha | Como evitar |
|---|---|
| Seed diferente entre braços | Fixar por caso; abortar se o provedor ignorar a seed |
| Conjunto mudou entre as rodadas | Versionar o eval-set; rerodar o baseline se mudar |
| Comparar horários diferentes | Provedor tem variação por hora; intercalar os braços |
| Excluir falhas de um braço e não do outro | Regra única de exclusão, aplicada aos dois |
| Escolher a métrica depois de ver o resultado | Metas e métricas registradas em ADR antes de medir |
| Otimizar a métrica em vez do produto | Manter a nota humana como âncora final |
| Média esconder subgrupo | Reportar por subgrupo demográfico sempre |

## 7. Loop de melhoria (§26 do briefing)

```text
ANALISAR → IMPLEMENTAR (1 variável) → TESTAR → BENCHMARK → COMPARAR COM BASELINE
   → GANHO comprovado em ≥1 eixo sem regressão crítica?  ── sim → aceita, vira baseline
                                                          └─ não → rejeita e registra
```

**Não aceite uma mudança por ser tecnicamente mais sofisticada.** LangGraph mais elegante,
adaptador de identidade mais moderno, upscaler mais novo — nada disso entra sem número. A régua é
sempre a mesma: *isso aumenta a probabilidade do produto funcionar bem num evento real?*
