# Autonomia graduada (JEV) — o Batman decide simples e médio; o humano só o crítico

> Código: `scripts/batman/jev_batman.py` (classificador) + `_decidir_pendentes` em
> `scripts/batman/shift.py` (executor no loop). Testes: `tests/test_jev_batman.py`
> (12) + `tests/test_batman_decidir.py` (5). Em divergência, vale o código testado.

## 1. O problema que resolve

O modelo anterior tratava autonomia por **categoria** (edição = N2, marco = N3). Isso
deixava o turno parando por coisas que ele mesmo podia decidir (e enfileirava N3 sem
explicar o porquê). O novo modelo classifica por **complexidade + confiança + evidência**:

```
decisão pendente → classificar_decisao(tipo, alvo, n_arquivos, criticos, tem_teste)
        │
        ├─ simples (conf ≥ 0,8) ─→ EXECUTA (N0–N2) + evidência no journal
        ├─ média  (conf 0,5–0,8) ─→ VERIFICA (gate determinístico do tipo)
        │                              verde → executa · vermelho → escala com o resultado
        └─ alta/crítica (conf < 0,5 ou N3 absoluto) ─→ ESCALA (fila N3 com motivo exato)
```

## 2. Tipos e freios

| tipo | complexidade/nível | freio |
|---|---|---|
| `leitura` | simples · N0 | nenhum |
| `teste_benchmark` | simples · N1 | nenhum |
| `edicao_trivial` | simples · N2 | gate `validate_skills` quando verificação é pedida |
| `edicao_docs` | média · N2 | −0,25 se toca área crítica; gate `validate_skills` |
| `edicao_codigo` | média · N2 | **TDD obrigatório** (−0,3 sem teste); gate pytest curado |
| `auto_evolucao` | média · N2 | doutrina de segurança imutável (nunca editar Linha de Defesa/N3) |
| `criar_jev` | média · N2 | benchmark + Quality Gate anti-regressão (gate labs JEV) |
| `github_branch` | média · N2 | publicar (push/PR merge) continua N3 |
| `limpeza_tmp` | simples · N2 | somente `tmp/batman/*` do próprio turno |
| `harvest_evolucao` | média · N2 | materializar colheita do harvester (base 0,85; gate `validate_skills`); merge segue N3 — ver `harvest-evolucao.md` |
| `commit`/`push`/`merge`/`delete`/`config`/`deps`/`credenciais` | **crítica · N3** | **absoluto — nunca gradua** (doutrina AGENTS.md) |

## 3. Confiança determinística (sem LLM)

Base por tipo (0,7–1,0) com desconto por sinais objetivos:
- área crítica tocada (`security/`, `governance/`, workflows, settings): **−0,25**
- mais de 10 arquivos: **−0,15**
- código sem teste (viola TDD): **−0,30**

Limiares: **≥ 0,8 executa · 0,5–0,8 verifica · < 0,5 escala.**

## 4. Critérios de gate — humano só quando necessário

1. N3 absolutos (commit/push/merge/delete/config/deps/credenciais) — sempre humano.
2. Confiança < 0,5 — humano (sem gate que salve).
3. Gate determinístico vermelho — humano, **com o resultado do gate no motivo**.
4. Tipo desconhecido — humano (nunca inventar autonomia).
5. Comando autônomo que falhou na execução — humano com o erro.

Toda escalação escreve na fila `scheduler/logs/batman-n3-pendentes.jsonl`:
`{ts, ciclo, tipo, alvo, motivo, nivel}` — o humano decide de manhã **sabendo o porquê**,
sem investigar.

## 5. Operação

- O LLM da skill escreve `scheduler/batman-decisoes.json` com as decisões do ciclo
  (formato: `{"decisoes": [{"tipo", "alvo", "cmd", "n_arquivos"?, "criticos"?,
  "tem_teste"?, "gate"?}]}`).
- O runner processa o arquivo **a cada ciclo** (`_decidir_pendentes`) e o renomeia
  `.done-<hora>` (idempotente).
- Fora do turno: `python scripts/batman/shift.py decidir` (exit 2 se algo escalou).

## 6. Evidência e honestidade

- Cada decisão executada → linha no journal com nível, alvo, complexidade, confiança.
- Cada escalação → motivo exato + resultado do gate.
- Estatística do turno: `estatica_autonomia(journal)` → % de ações N0–N2 vs N3 —
  reportada no relatório matinal (meta: N3 apenas quando realmente necessário).
