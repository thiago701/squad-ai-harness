# Instalar o ecossistema Squad AI no `.claude/`

Importa skills, agents, commands, templates, workflows, memory e docs do orquestrador
Squad AI para um diretório `.claude/`, deixando o Claude pronto para usar a squad.

**Stdlib pura · offline · idempotente · com backup, rollback, manifesto e verify.** Só precisa de **Python 3.8+**.

## TL;DR

```bash
# 1) ver o que será feito (não escreve nada)
python install-squad-ai.py plan --target ~/.claude

# 2) instalar (cria backup do que sobrescrever)
python install-squad-ai.py install --target ~/.claude

# 3) conferir integridade
python install-squad-ai.py verify --target ~/.claude
```

Windows: `./install-squad-ai.ps1 install --target $HOME\.claude` · Linux/macOS: `./install-squad-ai.sh install --target ~/.claude`

## Subcomandos

| Comando | O que faz |
|---|---|
| `plan` | Dry-run: lista NEW/UPDATE/SAME e duplicidades. Não escreve nada. |
| `install` | Instala/atualiza. Faz **backup** do que for sobrescrito. Gera manifesto, índice, relatório e log. |
| `verify` | Confere cada arquivo instalado contra o **hash** do manifesto. Sai ≠ 0 se houver drift/ausência. |
| `rollback` | Restaura o último backup (`--backup TS` para um específico) e remove o que foi criado. |
| `index` | (Re)gera `SKILLS-INDEX.md` (skills por domínio). |
| `baseline` | (Re)gera `squad-ai-manifest.json` (snapshot da fonte: hash por arquivo + `aggregate_sha256`) para auditoria de integridade. |

## Opções

- `--target DIR` destino do `.claude` (default `~/.claude`). Use `./.claude` para instalar no projeto.
- `--source DIR` raiz do repo Squad AI (default: a pasta do script).
- `--config J` perfil de exportação (JSON; veja `squad-ai-install.json`).
- `--force` sobrescreve arquivos sensíveis (ex.: `.env`), que por padrão são preservados.
- `--quiet` menos saída.

## Garantias

- **Idempotente:** reinstalar não muda nada que já está igual (compara por SHA-256).
- **Seguro:** nunca apaga nem sobrescreve sem backup; sensíveis preservados sem `--force`.
- **Reversível:** `rollback` volta ao estado anterior.
- **Rastreável:** `squad-ai-manifest.json`, `squad-ai-install-report.md` e `squad-ai-install.log` no destino.
- **Offline/corporativo:** zero rede, zero dependência externa.

Detalhes: [`docs/INSTALLATION.md`](docs/INSTALLATION.md) · Reverter: [`docs/ROLLBACK.md`](docs/ROLLBACK.md) · Skills: [`docs/SKILLS-INDEX.md`](docs/SKILLS-INDEX.md) · Evidências: [`docs/INSTALL-VALIDATION-REPORT.md`](docs/INSTALL-VALIDATION-REPORT.md)
