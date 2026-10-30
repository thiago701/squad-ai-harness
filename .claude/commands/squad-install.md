---
description: Instala, atualiza ou valida a Squad AI e suas skills em todos os ambientes agênticos da máquina e diagnostica o perfil multi-PC (CPU / iGPU / NPU / GPU CUDA).
argument-hint: [acao: instalar | verificar | estacao | calibrar]
origin: squad-ai
---

Você está executando o comando **/squad-install** — fachada fina sobre a skill **`instalar-skills`** (`skills/instalar-skills/SKILL.md`) e o instalador `install-squad-ai.py`.

Escopo / pedido: **$ARGUMENTS** (atende também aos gatilhos em linguagem natural **"instale squad ai"**, **"instale as skills"** e **"instalei as skills"**).

Siga a ordem exata abaixo conforme a intenção do usuário:

1. **Instalar ou atualizar a Squad AI ("instale squad ai" / "instale as skills" / vazio):**
   - `python install-squad-ai.py detectar` — mostra os destinos principais presentes (`.claude`, `.dsh`, `RAI CLI`) e outras ferramentas detectadas (`Codex`, `Gemini`, `Antigravity`, `Cursor`, `OpenCode`, `Windsurf`, `Qwen`, `Cline`).
   - `python install-squad-ai.py instalar-todos` — instala em paralelo nos destinos principais presentes, com porta de segurança fail-closed, backup e manifesto SHA-256.
   - `python install-squad-ai.py estacao` — diagnostica o hardware do PC atual (`cpu` puro, `cpu+igpu`, `cpu+igpu+npu`, `cpu+dgpu`) em modo somente leitura.
   - Se `.\squad-harness.exe` não existir na máquina, compile com `$env:CGO_ENABLED="0"; go build -o squad-harness.exe ./cmd/squad-harness` e execute `.\squad-harness.exe compute`.

2. **Pós-instalação / validação ("instalei as skills" / `verificar`):**
   - `python install-squad-ai.py verify` — confere os hashes SHA-256 instalados contra o manifesto.
   - `.\squad-harness.exe gate` — valida as 106 skills canônicas, UTF-8, Linha de Defesa de Prompt, SEKG, 25 especialistas JEV e gates de entrega.
   - `.\squad-harness.exe compute` — exibe a rota ativa do `CognitiveComputeRouter` (`C0_GO_DETERMINISTIC` em PCs só com CPU, `C1_LOCAL_ACCEL_ASSIST` em PCs com OpenVINO/ORT/iGPU/NPU/CUDA, `C2_LLM_SPECIALIST`).
   - `python -m scripts.accel.model_cards list` — verifica se os modelos opcionais de GPU/NPU estão presentes em `~/.squad-ai/models/`.

3. **Configurar e calibrar aceleração neural no PC atual (`calibrar` — opcional):**
   - `python install-squad-ai.py estacao --aplicar --calibrar --rapido` — cria `~/.squad-ai/venv-neural`, instala apenas os pacotes compatíveis com o hardware deste PC, valida o modelo `multilingual-e5-small` e grava a política medida em `~/.squad-ai/workstation.json`.

**Regras inegociáveis:** nunca use `--force` nem `--podar` sem confirmação explícita do humano; sempre informe o comando de rollback (`python install-squad-ai.py rollback --target <raiz>`).
