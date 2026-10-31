# Memo — Arquiteto A (Minimalista · `arquiteto-minimalista`)

## Posição em 5 linhas
A Squad AI v0.8.0 em Go (`CGO_ENABLED=0`) já é rápida em tarefas léxicas e determinísticas (Camada C0), mas sofre de **5 lacunas estruturais** onde grafos relacionais temporais, álgebra tensorial e análise inter-procedural são necessários. Em vez de criar 5 microserviços separados (anti-padrão *microservice sprawl*), proponho **1 único binário/workspace modular em Rust 1.99.1 (`kumo-cuda-lab`)** hospedado em `templates/stacks/rust-kumo-cuda-labs/`, contendo as 5 POCs como *crates* internas acopladas a 1 servidor IPC leve. Assim preservamos 100% da pureza do Go (`gopurity.go` intacto), zero dependências externas no `go.mod`, e entregamos todas as 5 POCs num único artefato coeso.

## Propostas concretas
1. **P1 (Simplicidade) — Monólito Modular Experimental em Cargo Workspace:** Um único workspace Rust em `templates/stacks/rust-kumo-cuda-labs/` com 1 crate de infraestrutura (`cuda_rust_core`, emulando/encapsulando `cuda-core`, `cuda-async`, `cutile-rs` e `cuda-oxide`), 5 módulos/crates de POC (`poc01_diskgraph`, `poc02_pql_relgt`, `poc03_cuda_reranker`, `poc04_jev_gnn`, `poc05_aiops_imo`) e 1 binário unificado (`kumo-cuda-sidecar`) que expõe tanto CLI/Benchmark quanto servidor IPC para o Go.
2. **P1 + P2 — Comunicação Go ↔ Rust via JSON-RPC 2.0 Framing Persistente (NDJSON/L4 sobre Pipe/Loopback) + Arena Binária CSR (`mmap`):** Sem gRPC pesado (que exigiria `protobuf` e `google.golang.org/grpc` no `go.mod`, violando a regra de stdlib pura em `gopurity.go:173`!). O Go usa apenas `net`/`os/exec`/`encoding/json`/`encoding/binary` da stdlib para conversar com o sidecar Rust mantido *warm*.
3. **P3 (Custo Zero) — Zero Crates Externas Desnecessárias:** Construir os núcleos matemáticos (CSR alinhado, parser PQL, RelGT 5D + atenção em Tiles `cutile-rs`, kernels SIMT `cuda-oxide` e protocolo IPC) usando a stdlib do Rust 1.99.1 (Edição 2024), eliminando tempo de download de centenas de crates e riscos de supply chain.

## Respostas às tensões do meu domínio
- **T1 (Isolamento Go × Rust):** Hospedar todo o código Rust em `templates/stacks/rust-kumo-cuda-labs/`. O `internal/gates/gopurity.go` (linha 124) isenta explicitamente `templates/` por ser catálogo de stacks-alvo e laboratório. O núcleo da Squad AI permanece 100% Go.
- **T2 (Protocolo Go ↔ Rust):** Rejeito CGO (proibido por `gopurity.go:84-88`) e rejeito gRPC (exige deps externas no `go.mod`, proibido por `gopurity.go:173`). O vencedor por P1 e compatibilidade estrita com stdlib Go é **NDJSON-RPC 2.0 Persistente sobre Loopback TCP `127.0.0.1` / Stdio Pipe + Arquivo Binário CSR Alinhado (`mmap`)**.

## Riscos e armadilhas
- 🔴 **Quebrar o `VerifyGoExclusiveLock`:** Se qualquer `.rs` ou `Cargo.toml` for colocado na raiz ou em `internal/`, o gate do Go falha imediatamente. Mitigação: isolar estritamente em `templates/stacks/rust-kumo-cuda-labs/`.
- 🟠 **Overhead de spawn por requisição:** Chamar o binário Rust via `exec.Command` a cada requisição adiciona ~140 ms no Windows. Mitigação: modo daemon residente (*warm*) com pool de conexão keep-alive.

## Dúvidas que SÓ o usuário pode responder (com default)
- **Q1:** O microserviço Rust deve rodar como processo sidecar sob demanda (iniciado pelo Go quando necessário) ou como serviço independente sempre ativo? *(Default: híbrido — suporta modo daemon persistente via TCP loopback/stdio e modo batch CLI para benchmarks científicos).*

## O que eu vetaria se visse no plano
- Veto **CGO (`import "C"`)** no Go: destrói o build estático `CGO_ENABLED=0` e viola `gopurity.go`.
- Veto **5 processos/servidores separados** para as 5 POCs: multiplica consumo de RAM/VRAM por 5 sem necessidade.
