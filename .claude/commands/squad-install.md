---
description: Instala, atualiza ou valida o SquadAI Harness e suas 106 skills em todos os ambientes agênticos da máquina (100% Go 1.24.3 nativo) e diagnostica o perfil multi-PC (CPU / iGPU / NPU / GPU CUDA).
argument-hint: [acao: all | detect | verify | compute]
origin: squad-ai
---

Você está executando o comando **/squad-install** — fachada fina sobre a skill **`instalar-skills`** (`skills/instalar-skills/SKILL.md`) e o instalador nativo `.\squad-harness.exe install` (Go 1.24.3, `CGO_ENABLED=0`). A versão legada em Python (`install-squad-ai.py`) foi aposentada e desativada.

Escopo / pedido: **$ARGUMENTS** (atende também aos gatilhos em linguagem natural **"instale squad ai"**, **"instale as skills"** e **"instalei as skills"**).

Siga a ordem exata abaixo conforme a intenção do usuário:

1. **Instalar ou atualizar o SquadAI Harness em todas as ferramentas ("instale squad ai" / "instale as skills" / vazio):**
   - Se `.\squad-harness.exe` não existir na máquina, compile com `$env:CGO_ENABLED="0"; go build -trimpath -ldflags="-s -w" -o squad-harness.exe ./cmd/squad-harness`.
   - `.\squad-harness.exe install detect` — detecta todas as ferramentas agênticas instaladas na estação (`Claude Code`, `Google Antigravity`, `Cursor`, `GitHub Copilot`, `OpenAI Codex`, `Windsurf`, `Gemini CLI`, `Cline`, `OpenCode`, `Qwen`, `DeepSeek Harness`, `Resolve AI`).
   - `.\squad-harness.exe install` — instala e sincroniza em paralelo as 106 skills canônicas (+ comandos `/squad-*`) em todas as ferramentas presentes na máquina (incluindo `~/.agents/skills`), com porta de segurança fail-closed, manifesto `.squad-ai-manifest.json` (SHA-256) e remoção de artefatos legados.
   - `.\squad-harness.exe compute` — diagnostica o hardware do PC atual (`cpu` puro, `cpu+igpu`, `cpu+igpu+npu`, `cpu+dgpu`) em modo somente leitura.

2. **Pós-instalação / validação ("instalei as skills" / `verify`):**
   - `.\squad-harness.exe install verify` — confere byte-a-byte (LF normalizado) todas as 106 skills instaladas em todos os destinos ativos.
   - `.\squad-harness.exe gate` — valida as 106 skills canônicas, UTF-8, Linha de Defesa de Prompt, Go-Exclusive Lock, SEKG, 25 especialistas JEV e gates de entrega.
   - `.\squad-harness.exe compute` — exibe a rota ativa do `CognitiveComputeRouter` (`C0_GO_DETERMINISTIC` em PCs só com CPU, `C1_LOCAL_ACCEL_ASSIST` em PCs com OpenVINO/ORT/iGPU/NPU/CUDA, `C2_LLM_SPECIALIST`).

**Regras inegociáveis:** nunca invoque scripts legados (`install-squad-ai.py` ou `squad-ai-orchestrator`); toda instalação e sincronização multi-ferramenta ocorre exclusivamente via `.\squad-harness.exe install`.
