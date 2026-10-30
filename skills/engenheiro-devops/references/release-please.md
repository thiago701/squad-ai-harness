# release-please — Conventional Commits → Changelog Automático

> **Padrão da Squad AI** para gerar releases versionadas (SemVer) e CHANGELOG.md a partir de Conventional Commits, com integração nativa ao GitHub Actions.

## Por que release-please

Manter versão e changelog manualmente é fonte clássica de erro: número errado, entrada esquecida, BREAKING CHANGE não anunciada. O **release-please** (mantido pelo Google) lê o histórico de commits desde o último release, agrupa por tipo (feat, fix, BREAKING) e abre um **PR de release** que, ao ser merged, dispara a tag e a publicação.

Comparado a alternativas:

| Ferramenta | Trade-off |
|------------|-----------|
| **release-please** | ✅ Padrão da squad. PR-based (humano aprova), suporta multi-package, integra fluxo Maven/Gradle/Node. |
| semantic-release | Mais opinionado, dispara release direto sem PR — pode publicar sem revisão humana. |
| changesets | Excelente para monorepo TS/JS, fricção em Java. |
| Jenkins manual | Status quo legado — abandonar. |

## Fluxo

```
┌─────────────────────────────────────────────────────────────┐
│ Dev faz commits Conventional → push em main                  │
│   feat(pedido): permite múltiplos itens                      │
│   fix(outbox): corrige relay duplicando eventos              │
│   feat!: remove campo legacy_status                          │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ release-please-action (em cada push em main):                │
│   1. Lê commits desde última tag                             │
│   2. Calcula próximo SemVer:                                 │
│      - feat → minor (0.5.0 → 0.6.0)                          │
│      - fix  → patch (0.6.0 → 0.6.1)                          │
│      - feat!|BREAKING CHANGE → major (0.6.1 → 1.0.0)         │
│   3. Abre/atualiza PR "chore(main): release 0.6.0":          │
│      - Atualiza pom.xml (<version>)                          │
│      - Atualiza CHANGELOG.md                                 │
│      - Atualiza .release-please-manifest.json                │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Tech Lead revisa PR → merge                                  │
│   - Cria tag v0.6.0                                          │
│   - Cria GitHub Release com changelog                        │
│   - Workflow de deploy roda em cima da tag                   │
└─────────────────────────────────────────────────────────────┘
```

## Setup em projeto Java/Maven

### 1. `release-please-config.json` (raiz)

```json
{
  "$schema": "https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json",
  "release-type": "maven",
  "include-component-in-tag": false,
  "include-v-in-tag": true,
  "bump-minor-pre-major": true,
  "bump-patch-for-minor-pre-major": true,
  "draft": false,
  "prerelease": false,
  "packages": {
    ".": {
      "package-name": "pedidos-api",
      "changelog-path": "CHANGELOG.md",
      "extra-files": [
        "pom.xml",
        "bootstrap/pom.xml",
        "domain/pom.xml",
        "application/pom.xml",
        "infrastructure/pom.xml"
      ]
    }
  }
}
```

**Notas importantes:**
- `release-type: maven` → release-please entende `<version>` em pom.xml e atualiza inclusive parent + filhos.
- `bump-minor-pre-major: true` → enquanto versão for `0.x.y`, `feat` bumpa minor, `fix` bumpa patch (comportamento conservador antes do 1.0.0).
- `extra-files` → todos os pom.xml dos módulos do projeto Maven multi-module gerado pela Squad AI.

### 2. `.release-please-manifest.json` (raiz)

```json
{
  ".": "0.1.0"
}
```

Inicializa com a versão atual. Em projetos novos: `0.1.0`.

### 3. Workflow GitHub Actions

```yaml
# .github/workflows/release-please.yml
name: release-please

on:
  push:
    branches: [main]

permissions:
  contents: write
  pull-requests: write

jobs:
  release-please:
    runs-on: ubuntu-latest
    steps:
      - uses: googleapis/release-please-action@v4
        id: release
        with:
          config-file: release-please-config.json
          manifest-file: .release-please-manifest.json

  publish:
    needs: release-please
    if: ${{ needs.release-please.outputs.release_created == 'true' }}
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write   # OIDC para WIF
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ needs.release-please.outputs.tag_name }}

      - uses: actions/setup-java@v4
        with:
          java-version: '25'
          distribution: 'temurin'
          cache: maven

      - name: Configure AWS via OIDC
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/gha-release
          aws-region: us-east-1

      - name: Build & Push
        run: |
          mvnd -T 1C verify
          mvnd -pl bootstrap -am jib:build -Dimage=ghcr.io/${{ github.repository }}:${{ needs.release-please.outputs.tag_name }}
```

## Conventional Commits — guia rápido

```
<tipo>[escopo opcional][!]: <descrição>

[corpo opcional]

[BREAKING CHANGE: descrição]
[Refs: #123]
```

Tipos canônicos da Squad AI:

| Tipo | Bump | Quando usar |
|------|------|-------------|
| `feat` | minor | Nova funcionalidade visível ao usuário ou consumidor da API |
| `fix` | patch | Correção de bug em comportamento existente |
| `feat!` ou `BREAKING CHANGE:` | **major** | Mudança incompatível: API removida, schema migrado destrutivamente, evento renomeado |
| `perf` | patch | Otimização sem mudança funcional (entra em CHANGELOG seção própria) |
| `refactor` | (nenhum) | Não aparece no CHANGELOG público |
| `docs` | (nenhum) | Idem |
| `test` | (nenhum) | Idem |
| `chore` | (nenhum) | Idem |
| `ci` | (nenhum) | Idem |
| `build` | (nenhum) | Idem |
| `revert` | patch | Aparece no CHANGELOG como reverso |

### Exemplos da squad

```bash
# Nova feature em bounded context "pedidos"
git commit -m "feat(pedidos): permite múltiplos itens no mesmo aggregate"

# Bug em outbox
git commit -m "fix(outbox): publica eventos em lote para evitar duplicidade"

# BREAKING — campo do evento removido
git commit -m "feat(pedidos)!: remove campo legacy_status do evento PedidoConfirmado

BREAKING CHANGE: consumers que lêem legacy_status devem migrar para status_v2.
Migration grace period: 30 dias. Ver ADR-0014."
```

## Hook de validação local (opcional)

Para garantir que devs não quebrem o padrão antes do push:

```bash
# .husky/commit-msg ou pre-commit
#!/usr/bin/env bash
npx --yes commitlint --edit "$1"
```

```js
// commitlint.config.js
module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'scope-enum': [2, 'always', [
      'pedidos', 'pagamentos', 'estoque',  // bounded contexts
      'shared', 'config', 'ci', 'docs', 'deps'
    ]],
  },
};
```

## CHANGELOG.md gerado (exemplo real)

```markdown
# Changelog

## [0.6.0](https://github.com/empresa/pedidos-api/compare/v0.5.0...v0.6.0) (2026-04-19)

### ⚠ BREAKING CHANGES

* **pedidos:** remove campo legacy_status do evento PedidoConfirmado

### Features

* **pedidos:** permite múltiplos itens no mesmo aggregate ([a1b2c3d](.../commit/a1b2c3d))
* **pagamentos:** integra Pix com webhook idempotente ([e4f5g6h](.../commit/e4f5g6h))

### Bug Fixes

* **outbox:** publica eventos em lote para evitar duplicidade ([i7j8k9l](.../commit/i7j8k9l))

### Performance Improvements

* **pedidos:** índice parcial em outbox_event reduz lag em 80% ([m0n1o2p](.../commit/m0n1o2p))
```

## Sinais de saúde

- ✅ PRs de release abrem automaticamente em < 1 minuto após push em main
- ✅ Tag e CHANGELOG sempre coerentes — zero divergência manual
- ✅ Workflow de deploy escutando `release.published` (não `push`) deploya somente release real
- ✅ BREAKING CHANGES exigem revisão humana (PR não auto-merge)

## Anti-padrões

- ❌ **Auto-merge no PR de release** — perde a chance de revisão antes de publicar versão major.
- ❌ **Misturar fix e feat no mesmo commit** — bump fica errado, escolha um.
- ❌ **Esquecer escopo em monorepo** — sem escopo, release-please não consegue separar bumps por módulo.
- ❌ **Usar tags manuais junto com release-please** — ferramenta perde sincronia. Escolha uma forma.

## Referências cruzadas

- `engenheiro-devops/SKILL.md` — política de CI/CD e Conventional Commits
- `java25-spring-boot/references/maven4-guide.md` — Maven 4 multi-module
- [Documentação oficial release-please](https://github.com/googleapis/release-please)
- [Conventional Commits 1.0.0](https://www.conventionalcommits.org/)
