# Memo — Arquiteto D (Operação, AIOps & Ponte IPC Go↔Rust · `engenheiro-devops` + `monitor-aiops`)

## Posição em 5 linhas
O `SquadAI Harness v0.8.0` opera como binário estático Go (`squad-harness.exe`) com memória vigiada (`GOMEMLIMIT = 256 MiB`) e supervisão por Windows Job Objects (`internal/runtime/jobobject`). Para que as 5 POCs em Rust atuem como **complementos operacionais reais** da Squad AI em Go, o microserviço Rust (`kumo-cuda-sidecar`) deve expor um contrato **JSON-RPC 2.0 idêntico ao padrão MCP do `internal/mcp/server.go`**, permitindo que o Go invoque qualquer POC via pipe `stdio` persistente ou socket `127.0.0.1` com telemetria de latência em microssegundos, health-check de GPU/CPU e fallback transparente caso o binário Rust não esteja ativo.

## Propostas concretas
1. **P1 + P2 — Protocolo Dual-Transport Go ↔ Rust (`Stdio JSON-RPC 2.0` + `Loopback TCP Keep-Alive` + `Binary CSR File`):**
   - Transporte 1 (`stdio` / persistent pipe): o Go inicia `kumo-cuda-sidecar --serve-stdio` uma única vez e envia linhas JSON-RPC 2.0 (`kumo.diskgraph.sample`, `kumo.pql.predict`, `cuda.rerank.verify`, `jev.gnn.evaluate`, `aiops.imo.predict`). Latência de IPC $< 0,15\text{ ms}$.
   - Transporte 2 (`tcp://127.0.0.1:<port>`): para múltiplos clientes Go concorrentes (ex.: CLI + Monitor AIOps `:8765` + Control Center `:9090`).
   - Transporte 3 (`Zero-Copy Binary Snapshot .kdg`): arquivo binário CSR alinhado em disco lido diretamente pelo Rust sem trafegar o grafo pelo pipe JSON.
2. **P2 — Evolução do Escalonador 8D IMO e Monitor AIOps (POC-05):**
   - No `internal/scheduler/scheduler.go`, substituir o chute estático de cold-start (`400 MB`/`25 MB`) e o EWMA 1D (`EWMAAlpha=0.30`) por uma chamada ao preditor relacional Kumo + `cuda-async` (POC-05), que estima `EstimatedRSSMB`, `EstimatedVRAMMB` e `p95DurationMs` condicionados às 8 dimensões reais da tarefa.
   - No `internal/aiops/aiops.go`, substituir o `blast_radius` estático (`42` e `89`) pelo cálculo probabilístico de propagação em 3 saltos sobre a topologia descoberta (`.tf`, `.tfvars`, OpenAPI, LocalStack).

## Respostas às tensões do meu domínio
- **T1 & T2 (Comunicação Go ↔ Rust sem CGO):** O cliente Go usa apenas `net`, `bufio` e `encoding/json` da biblioteca padrão do Go 1.24.3. Se o microserviço Rust estiver desligado, o cliente Go aplica o padrão *Circuit Breaker* (`internal/compute/router.go:151`) e degrada graciosamente para a lógica Go C0 em `< 1 ms`.
- **T6 (Observabilidade Científica):** Todo response do microserviço Rust inclui `execution_telemetry`: `kernel_time_us`, `ipc_serialize_us`, `backend_used` (`CUDA_TILE_GPU` ou `RUST_SIMD_TILE_CPU`), `vram_admitted` e `cosine_parity`.

## Riscos e armadilhas
- 🔴 **Processos órfãos no Windows:** Se o processo pai Go encerrar abruptamente, um sidecar mal gerenciado ficaria órfão. Mitigação: no modo `--serve-stdio`, o Rust encerra imediatamente (`EOF` no `stdin`); no modo TCP, possui `--idle-timeout-sec`.
- 🟠 **Bloqueio de porta em ambiente corporativo:** Porta fixa pode colidir. Mitigação: bind em `127.0.0.1:0` (porta efêmera anunciada no stdout) ou `--serve-stdio` (zero portas de rede).

## Dúvidas que SÓ o usuário pode responder (com default)
- **Q4:** Devemos incluir um cliente Go funcional e testado (`go_bridge_bench_test.go` / cliente IPC) que chama o binário Rust compilado em tempo real para medir a latência real da ponte Go↔Rust? *(Default: Sim, obrigatório para provar cientificamente a comunicação Go↔Rust na estação).*

## O que eu vetaria se visse no plano
- Veto dependência de containers Docker pesados ou brokers externos (Kafka/Redis/RabbitMQ) apenas para comunicar Go e Rust na mesma máquina.
