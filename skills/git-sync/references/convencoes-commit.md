# Convenções de commit — git-sync (JEV)

Regras determinísticas usadas pelo JEV (`scripts/git/jev_git.py`) para agrupar e
nomear commits. Mesma convenção da identidade (`AGENTS.md` §6).

## Formato

```
<tipo>(<escopo>): <descrição imperativa curta em PT-BR>

[corpo opcional: o porquê, não o como]
```

- **Tipos:** `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `build`, `ci`, `style`.
- **Descrição:** imperativa, minúscula, sem ponto final.

## Mapeamento path → (tipo, escopo) do JEV

| Prefixo do path | Tipo | Escopo |
|---|---|---|
| `constraints.txt`, `requirements*`, `pyproject.toml`, `package.json`, `*.lock` | `build` | `deps` |
| `.github/`, `hooks/`, `.gitleaks.toml`, `.pre-commit-config.yaml` | `ci` | `ci`/`hooks` |
| `tests/`, `test_*` | `test` | `testes` |
| `docs/`, `README*`, `SECURITY.md`, `AGENTS.md`, `CONTRIBUTING.md`, `CHANGELOG*` | `docs` | conforme |
| `skills/`, `labs/`, `scripts/`, `src/` | `feat` | área |
| `.gitignore` | `chore` | `higiene` |
| status `D` (remoção) | `chore` | `higiene` |
| status `R` (renome/move) | `refactor` | `moves` |
| status `A`/`??` sem categoria | `feat` | top-dir |
| `M` sem categoria | `chore` | top-dir (neutro e honesto) |

## Ordem canônica dos commits

`build → ci → fix → refactor → docs → test → feat → chore`
(leitura de log e review mais limpas; dependências entram antes de quem as usa).

## Regra TDD (agrupamento)

Quando existe **exatamente um** grupo de código e **um** grupo de teste, os testes
entram no mesmo commit do código (padrão RED→GREEN→REFACTOR da Squad). Com vários
grupos de código, os testes seguem separados (`test(testes)`).

## Mensagem determinística (sem LLM)

O JEV gera o assunto por template (verbo por tipo + contagem) e o corpo com os paths
fatuais. O LLM redige **apenas** quando o humano pede mensagem narrativa — via
`--mensagem "<intenção>"`, que vira o resumo do assunto:

```bash
python scripts/git/squad_sync.py execute --mensagem "remove artefatos obsoletos"
# → chore(higiene): remove artefatos obsoletos
```
