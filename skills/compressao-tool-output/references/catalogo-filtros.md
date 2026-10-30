# Catálogo de filtros — o que cada um preserva e por quê

Medições abaixo são de **corpus sintético de regressão** (`--self-test` + smoke), não de produção.
Regra-zero do V3 vale aqui: número medido é medido, estimativa é declarada como estimativa.

| Filtro | Prioridade | Redução medida (verde / vermelho) | Trava anti-perda |
|---|---:|---|---|
| `test-pytest` | 90 | −97% / −92% | `unless` no atalho verde; `FAILED`/`E `/`Traceback` protegidos |
| `build-maven` | 90 | — / — (corpus mínimo) | `BUILD FAILURE`, `[ERROR]`, `Tests run:` protegidos |
| `git-status` | 80 | — | `fatal:`/`error:` protegidos; hints do git descartados |
| `docker-build` | 85 | — | `failed to solve` e `ERROR` protegidos; progresso de camada descartado |
| `terraform-plan` | 85 | — | `will be destroyed`, `forces replacement`, `Plan:` protegidos |
| `error-stacktrace` | 60 | — | `Caused by:` e frames próprios protegidos; framework/stdlib descartado |
| `generic-output` | 1 | — | fallback conservador: qualquer linha com erro/falha sobrevive |

> Colunas vazias = **não medido ainda**. Preencher rodando o filtro sobre log real do projeto e
> registrando o par (linhas antes, linhas depois) em `_local-artifacts/compressao-metricas.jsonl`.

## Racional por filtro

### `test-pytest`
O ganho grande está no caso verde: 945 testes passando produzem ~35–400 linhas que carregam
**uma** informação ("passou"). O atalho `matchOutput` colapsa isso numa linha — e a cláusula
`unless` garante que `1 failed, 944 passed` **não** seja lido como verde. No caso vermelho,
descarta pontinhos, cabeçalho de plataforma e frames de `site-packages`, e mantém `FAILED`,
o assert e o sumário. Frames de biblioteca são ruído: a falha está no **nosso** código.

### `build-maven`
Maven imprime `Downloading from central:` centenas de vezes e `[INFO] ---` como separador. Nada
disso decide nada. O que decide: `[ERROR]`, `Tests run: N, Failures: F`, `BUILD SUCCESS/FAILURE`
e as cadeias `Caused by:`. Atenção ao `unless` do atalho — Maven pode imprimir `BUILD SUCCESS`
com testes pulados, então `Failures: [1-9]` e `Errors: [1-9]` bloqueiam o atalho.

### `git-status`
Metade da saída são hints (`(use "git add <file>..." to update...)`) escritos para humano
iniciante. O agente não precisa deles. Sobra: branch, divergência com o remoto, arquivos.

### `docker-build`
Buildkit emite uma linha de progresso por camada por segundo. Sinal: o `#N ERROR`, a linha
`failed to solve` e o digest final. Cuidado: **não** descartar `RUN` que falhou.

### `terraform-plan`
O item que **nunca** pode sumir é `will be destroyed` / `forces replacement` — é a diferença
entre um plano seguro e um incidente. Por isso estão em `preserve.errorPatterns`, mesmo não
sendo erro: no contexto de infra, destruição é a informação de maior consequência.

### `error-stacktrace`
Cinquenta frames de Spring AOP / `org.junit` / `node_modules` não ajudam ninguém. Preserva a
mensagem, os frames do pacote próprio e toda cadeia `Caused by:` — a causa raiz mora no último
`Caused by:`, e por isso `tailLines` nunca é zero aqui.

## Como adicionar um filtro (checklist)

1. **Antes de criar, tente estender.** Um `match.commands` novo num filtro existente resolve na
   maioria dos casos (P1-Simplicidade). Filtro é dívida.
2. Copie o esqueleto de [`dsl-filtros.md`](dsl-filtros.md) e preencha `preserve` **primeiro** —
   decida o que é intocável antes de decidir o que cortar.
3. Escreva pelo menos **dois** `tests[]`: um caso verde e um caso vermelho. O caso vermelho
   precisa de `expectedNotContains` com o símbolo de sucesso.
4. Rode `python3 scripts/comprimir.py --self-test`.
5. Rode contra um log real do projeto com `--verify`. Se o veredito mudar, o filtro está errado.
6. Filtro de projeto (`.squad/filtros/`) exige hash em `trust.json`:
   `sha256sum meu-filtro.json`.

## Perfis de agressividade

| Perfil | Quando | Efeito |
|---|---|---|
| `padrao` | Pipeline normal, gates verdes | Como definido no JSON |
| `investigacao` | `error-investigator` na caça à causa raiz | `deduplicate: false`, `maxLines` ×3, `dropPatterns` de framework desligado |
| `auditoria` | Evidência de bug fix, relatório de segurança | Compressão **desligada** — guarde o bruto |

O perfil não é um filtro novo: é um override aplicado em cima do filtro escolhido. Quando em
dúvida entre perder sinal e gastar token, **gaste o token** — a Squad já decidiu que rigor vale
2,2× em tokens.
