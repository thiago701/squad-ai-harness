# Instalar o ecossistema SquadAI Harness em Todas as Ferramentas Agênticas

Sincroniza concorrentemente as 106 skills canônicas e comandos `/squad-*` do **SquadAI Harness (`v0.8.0`)** em todos os ambientes agênticos instalados na estação (`Claude Code`, `Google Antigravity`, `Cursor`, `GitHub Copilot`, `OpenAI Codex`, `Windsurf`, `Gemini CLI`, `Cline`, `OpenCode`, `Qwen`, `DeepSeek Harness`, `Resolve AI` e `~/.agents/skills`).

**100% Go 1.24.3 nativo (`CGO_ENABLED=0`) · offline · idempotente · porta de segurança fail-closed · manifesto SHA-256 (`.squad-ai-manifest.json`).** O antigo instalador Python (`install-squad-ai.py`) foi desativado e substituído pelo binário único `squad-harness.exe`.

## TL;DR

```powershell
# 1) Detectar ferramentas agênticas presentes na estação (somente leitura)
.\squad-harness.exe install detect

# 2) Instalar/sincronizar em todas as ferramentas presentes (paralelo via goroutines)
.\squad-harness.exe install

# 3) Conferir integridade byte-a-byte (LF normalizado) e rodar o gate unificado
.\squad-harness.exe install verify
.\squad-harness.exe gate
```

## Subcomandos

| Comando | O que faz |
|---|---|
| `.\squad-harness.exe install detect` | Detecta todas as ferramentas agênticas presentes no host (12 ferramentas suportadas no catálogo). |
| `.\squad-harness.exe install` | Audita as 106 skills canônicas (UTF-8, Linha de Defesa, Secret Scan), sincroniza em paralelo todas as ferramentas instaladas, atualiza `.claude/commands` e remove artefatos legados. |
| `.\squad-harness.exe install verify` | Verifica integridade byte-a-byte (LF normalizado) de todas as 106 skills em cada ferramenta ativa. Sai `≠ 0` se houver drift ou ausência. |
| `.\squad-harness.exe install --target <ids>` | Instala sob demanda em ferramentas específicas (ex.: `--target cursor,copilot,windsurf`). |
| `.\squad-harness.exe compute` | Diagnostica o hardware da estação (`cpu`, `cpu+igpu`, `cpu+igpu+npu`, `cpu+dgpu`) e exibe as rotas C0/C1/C2. |

## Garantias

- **Idempotente e concorrente:** reinstalar só grava arquivos cujo conteúdo mudou (comparação normalizada LF + SHA-256).
- **Porta de segurança fail-closed:** skills sem Linha de Defesa de Prompt, com UTF-8 inválido ou achado HIGH/CRITICAL no scanner são bloqueadas antes da cópia.
- **Rastreável:** gera `.squad-ai-manifest.json` em cada destino ativo e aposenta manifestos legados.
- **Offline/corporativo:** binário estático Go 1.24.3 com zero dependências externas.
