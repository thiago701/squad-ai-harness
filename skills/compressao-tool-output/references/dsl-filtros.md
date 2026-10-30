# DSL de filtro — semântica campo a campo

Um filtro é um JSON declarativo. Sem código, sem `eval`, sem shell. O motor
(`scripts/comprimir.py`) é o único executável.

## Esqueleto

```json
{
  "id": "test-pytest",
  "label": "Pytest",
  "description": "Preserva falhas, tracebacks e o sumário terminal do pytest.",
  "category": "test",
  "priority": 90,
  "match": {
    "outputTypes": ["test-pytest"],
    "commands": ["^(?:pytest|python\\s+-m\\s+pytest)\\b"],
    "patterns": ["=+\\s+(?:\\d+\\s+)?(?:passed|failed|errors?)", "^E\\s+", "^FAILED "]
  },
  "rules": { "...": "ver abaixo" },
  "preserve": {
    "errorPatterns": ["FAILED", "ERROR", "Traceback", "AssertionError"],
    "summaryPatterns": ["=+ .*(passed|failed)"]
  },
  "tests": [
    { "name": "falha simples", "input": "…", "expected": "…" }
  ]
}
```

## Seleção do filtro (`match`)

Ordem de resolução, primeiro que casar vence; empate resolve por `priority` (maior vence):

| Campo | Efeito |
|---|---|
| `match.commands` | Regex contra a **linha de comando** (`--cmd`). É o sinal mais forte e mais barato. |
| `match.patterns` | Regex contra as primeiras ~200 linhas da saída. Usado quando o comando é desconhecido (ex.: saída vinda de um pipe). |
| `match.outputTypes` | Classe declarada explicitamente por quem chama (`--tipo test-pytest`). Vence tudo. |
| — nenhum casou — | Cai em `generic-output`. |

> **Regra P1:** não crie um filtro novo quando um `match.commands` extra num filtro existente
> resolve. Filtro é dívida de manutenção; o catálogo enxuto é feature.

## Regras de transformação (`rules`) — ordem de execução é fixa

| # | Campo | Tipo | O que faz |
|---|---|---|---|
| 1 | `stripAnsi` | bool | Remove sequências ANSI de cor/controle **antes** de qualquer regex. Sem isso todo padrão falha em terminal colorido. |
| 2 | `replace` | `[{from, to}]` | Substituições ordenadas. Uso típico: normalizar caminhos absolutos (`/home/runner/work/x/x/` → `…/`) e timestamps voláteis. |
| 3 | `matchOutput` | `[{when, then, unless}]` | **Atalho.** Se `when` casar e nenhum `unless` casar, devolve `then` e encerra. É o que transforma 400 linhas de verde em `pytest: 95 passed (12.3s)`. |
| 4 | `dropPatterns` | `[regex]` | Remove linhas de ruído (progresso, pontinhos, linhas vazias). |
| 5 | `includePatterns` | `[regex]` | Marca linhas **acionáveis**. Linha marcada é imune aos cortes de tamanho (7 e 8). |
| 6 | `collapsePatterns` | `[regex]` | Sequência de linhas que casam vira uma só + `(×N)`. |
| 6 | `deduplicate` | bool | Colapsa linhas duplicadas **consecutivas**. Opt-in por filtro. |
| 7 | `truncateLineAt` | int | Truncamento por linha, seguro para Unicode (não corta no meio de um grafema). |
| 8 | `headLines` / `tailLines` / `maxLines` | int | Corte de tamanho. `head` + `tail` preservam começo e fim; o miolo vira `… (N linhas elididas)`. |
| 9 | `onEmpty` | string | Mensagem quando o filtro consome tudo. **Obrigatório.** |
| 10 | `maxChars` | int | Teto duro final (padrão 10 000). Cabeça + cauda; o miolo vira `… (N caracteres omitidos; refaça …)`. Único corte que vence o sinal. |

## Preservação (`preserve`) — a trava anti-perda-de-sinal

```json
"preserve": {
  "errorPatterns":   ["FAILED", "ERROR", "Traceback", "Caused by:"],
  "summaryPatterns": ["Tests run:", "BUILD (SUCCESS|FAILURE)"]
}
```

- Linha que casa `errorPatterns` ou `summaryPatterns` **nunca** é removida — nem por
  `dropPatterns`, nem por `maxLines`, nem por head/tail.
- Se a preservação sozinha estourar `maxLines`, o corte acontece **no que não é erro**; se ainda
  assim estourar, `maxLines` cede. Sinal vence tamanho, sempre.

## `matchOutput` — o atalho e sua cláusula de segurança

```json
"matchOutput": [
  {
    "when":   "=+ (\\d+) passed(?:, (\\d+) warnings?)? in ([\\d.]+)s =+",
    "then":   "pytest: $1 passed ✅ ($3s)",
    "unless": ["failed", "error", "^E\\s+", "Traceback"]
  }
]
```

`unless` **não é opcional na prática**: sem ele, uma saída com `1 failed, 94 passed` casa o
padrão de sucesso e a compressão reporta verde num build vermelho. Esse é o único bug realmente
perigoso desta skill — por isso `--self-test` reprova qualquer `matchOutput` sem `unless` cujo
`then` contenha um símbolo de sucesso (`✅`, `OK`, `passed`, `SUCCESS`).

## `tests[]` inline — obrigatório

```json
"tests": [
  {
    "name": "não pode reportar verde com 1 falha",
    "input": "FAILED tests/test_a.py::test_a\n===== 1 failed, 94 passed in 3.1s =====",
    "expectedContains": ["FAILED", "1 failed"],
    "expectedNotContains": ["✅"]
  }
]
```

`comprimir.py --self-test` roda todos os `tests[]` de todos os filtros. Filtro sem teste é
rejeitado no carregamento. Filtro com teste vermelho pode ser **validado para inspeção** mas
**não é instalado nem carregado** — a mesma política do upstream.

## Erros de filtro são fail-open

Filtro com regex inválida, campo desconhecido, arquivo > 256 KB ou `tests[]` vermelho é
**pulado com aviso**; os demais continuam funcionando e, no pior caso, cai em `generic-output`.
Um filtro quebrado nunca pode derrubar o comando que ele deveria só resumir.
