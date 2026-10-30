# squad-pipeline · reference — Clean code na escrita e lente `rev-clean`

> Movido do hub para manter o corpo residente no orçamento (2026-10-28).

## Fases 4–5 e pós-Fase 5

A régua é a do Sonar-First — cognitiva **≤ 15** (`S3776`), ciclomática **≤ 15** (`S1541`), parâmetros **≤ 7**
(`S107`), **zero supressão inline** — medida também pelo linter da stack, para valer em segundos e sem servidor:

1. **Scaffold (Fase 4):** o projeto nasce com a configuração do linter, antes da primeira linha de domínio —
   Go: o `.golangci.yml` canônico de `../../golang-pro/references/clean-code-e-lint.md` §3; Python: os blocos `[tool.ruff.lint]` + `[tool.complexipy]` canônicos de
   `../../aws-lambda-python/references/clean-code-python.md` no `pyproject.toml`. O handler/adaptador nasce separado do domínio puro.
2. **TDD (Fase 5) — estrutural antes de comportamental:** quando a mudança pede refatoração, ela vai num commit
   próprio **antes** da regra nova, com a suíte verde antes e depois ("faça a mudança ficar fácil, depois faça a
   mudança fácil"); código sem teste ganha teste de caracterização primeiro.
3. **Validação incremental:** a cada unidade entregue, o linter da stack nos arquivos tocados — zero achado novo
   antes de seguir (mesmo ritmo da Fase C do Sonar-First). Exceção só na **configuração revisada**, com o porquê.
4. **Lente (pós-Fase 5, pré-Review):** `tech-lead-review` roda a parte mecânica e o checklist **P1.CLEAN** e grava
   `05d-clean.md`. Teto estourado ou supressão nova no código tocado = 🟡 AGUARDANDO (volta à Fase 5, ou decisão escrita
   do dono no GATE 2); afrouxar teto na configuração sem ADR com medição = 🔴 (catraca); ferramenta ausente = MAJOR nomeado, nunca verde.
   Comandos e critérios: `../../tech-lead-review/references/lente-clean-code.md`.
