# Referência — Release Management (Conventional Commits, release-please)

> Parte da skill `engenheiro-devops`. Carregue sob demanda. Hub: `../SKILL.md`.
## Release Management — Conventional Commits + release-please

Versionamento manual e CHANGELOG manual são fontes clássicas de erro (número errado, entrada esquecida, BREAKING CHANGE não anunciado). A Squad AI padroniza **release-please** (mantido pelo Google) como ferramenta de release:

- **Cada push em `main` reabre/atualiza um PR "chore(main): release X.Y.Z"** com `pom.xml`, `CHANGELOG.md` e manifest atualizados.
- **SemVer automático** a partir dos commits: `feat` → minor, `fix` → patch, `feat!` ou `BREAKING CHANGE:` → major.
- **Tech Lead revisa e merge** — só então a tag é criada e o deploy escuta `release.published`.
- **Multi-module Maven** suportado via `extra-files` apontando pros poms filhos gerados pelo scaffold da Squad AI.

Guia completo com `release-please-config.json`, workflow GitHub Actions com OIDC/WIF, tabela de tipos Conventional Commits, commitlint local e exemplo real de CHANGELOG:

**→ Ver `engenheiro-devops/references/release-please.md`**

Sinais de saúde:
- ✅ PR de release abre em < 1 minuto após push em main.
- ✅ Zero divergência manual entre tag e CHANGELOG.
- ✅ BREAKING CHANGES exigem revisão humana (PR não auto-merge).
- ❌ Misturar `feat` e `fix` no mesmo commit — bump sai errado.
- ❌ Auto-merge do PR de release — perde revisão antes de publicar versão major.

---

