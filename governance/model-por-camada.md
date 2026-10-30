# Campo `model` por camada (I12, Onda 3)

Cada skill declara no frontmatter o modelo da sua camada na cascata (`orchestration/cascata-3-camadas.md`).
A regra é declarativa (JSON, porque o repositório é stdlib pura): `governance/model-por-tipo.json`.

## A regra

| Modelo | Camada | Skills (das 43 que não tinham `model`) |
|---|---|---|
| `opus` | 2, fronteira | 12: arquitetura/trade-offs, segurança, banco, review e arbitragem, auditoria externa, promoção a instinto |
| `sonnet` | 1, econômica | 22: implementação, investigação de erro, padrões, scaffold, pipeline, especialistas de engenharia |
| `haiku` | 1, mais leve | 9: catálogo/consulta e operação mecânica de infra e observabilidade (decisão D6 do dono) |

- Cada skill está em exatamente uma regra. Skill nova, fora de toda regra, recebe o `default` (`sonnet`).
- `model:` já declarado nunca é sobrescrito. As 45 skills que já tinham o campo ficam como estão.
- Skill fora das regras que já declara `model` não é reportada como divergente, nem com `--forcar`.

## Como rodar

```
python -X utf8 scripts/model_por_skill.py --raiz . --check          # observacional
python -X utf8 scripts/model_por_skill.py --raiz . --write          # uma vez
python -X utf8 scripts/model_por_skill.py --raiz . --write --forcar # só para realinhar divergentes
```

- **No gate (`--check`)**: registra o relatório `model: N skills · faltantes X · escritas Y · divergentes Z · default W`.
  Sai com 1 se houver faltantes; no gate, trate isso como aviso. Virar bloqueio é decisão humana, como qualquer gate.
- **`--write` uma vez** nas 43 skills; a segunda execução não altera nenhum byte. A linha entra logo após `name:`,
  com o mesmo CRLF/LF do arquivo, e o bloco `description: >` fica intacto.
- O script só opera em `skills/*/SKILL.md`. A cópia em `.claude/skills/` é sincronizada à parte, nunca por ele.

## Por que `enforce_residencia` continua `false`

`governance/token-optimization.yaml` mantém `routing.enforce_residencia: false`. A política (cascata §4 e §6) manda
observar e logar primeiro. Declarar `model:` registra a intenção, mas não mede o que de fato rodou. Bloquear sem
baseline seria chutar o limiar, e limiar novo exige ADR. Só passa a `true` depois de um baseline medido: o histograma
abaixo com **N = 20 entregas reais com custo medido** (decisão do dono em 11/10/2026 — o mesmo mínimo que a memória
usa para decidir, `MINIMO_HISTORICO = 20`, e que o Gate A do roadmap exige; registrado em
`governance/token-optimization.yaml` como `enforce_residencia_apos_entregas`), a regra provada em caso sintético e a
ativação por decisão humana. `python -X utf8 scripts/histograma_camadas.py --raiz .` imprime a prontidão
("X de 20 entregas reais com custo medido") a partir de `memory/episodes.jsonl` (episódios `tipo=entrega` do
`/squad-remember` com `custo`, descontadas as invalidações). Este documento não altera a flag.

## Como ler o histograma

```
python -X utf8 scripts/histograma_camadas.py [--sli memory/sli.jsonl] [--desde YYYY-MM-DD] [--json]
```

- Agrupa `memory/sli.jsonl` por `camada_modelo` bruto: `camada-0` (determinístico), model-id real
  (`opus` é camada 2; `sonnet` e `haiku`, camada 1) ou **não informado** (`null`).
- Colunas: eventos, eventos com `tokens` e soma de `in`/`out` **só** dos eventos com `tokens`.
  Cache (`cache_r`/`cache_w`) não é somado.
- `—` significa sem usage real no grupo. Não é zero e nunca é estimado.
- Linha com `tokens=null` conta evento, não custo. Linhas não-JSON são puladas e contadas no rodapé.
- É distribuição por camada, não custo por skill (o SLI não registra a skill) e não prova economia.
  `scripts/squad_cost_report.py` publica a visão normalizada em camada-0/1/2 para o `/squad-cost`.
