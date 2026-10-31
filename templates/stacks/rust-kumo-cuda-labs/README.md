# `squad-kumo-cuda-lab` — Microserviço Experimental de Laboratório (Kumo AI + `NVIDIA/cuda-rust`)

Coleção de **5 Provas de Conceito (POCs)** em **Rust 1.99 (Edição 2024)** + **Ponte Go ↔ Rust Zero-CGO** projetada pela Comissão de Arquitetos (`docs/comissao-kumo-cuda-rust/`) para resolver os 6 *gaps* concretos identificados no núcleo Go do `SquadAI Harness v0.8.0`.

## Arquitetura e Isolamento (`VerifyGoExclusiveLock`)

O núcleo do `SquadAI Harness` permanece **100% em Go 1.24.3 puro (`CGO_ENABLED=0`)**. Este laboratório reside em `templates/stacks/rust-kumo-cuda-labs/` (em total conformidade com `internal/gates/gopurity.go`) e comunica-se com o binário Go via:
1. **Plano de Controle (`stdio` / Loopback TCP Keep-Alive JSON-RPC 2.0):** processo sidecar persistente eliminando o custo de ~145 ms de `CreateProcessW` por invocação no Windows 11.
2. **Plano de Dados (`.kdg` Binary CSR Zero-Copy Arena):** snapshots alinhados a 64 bytes (`align(64)`) mapeados diretamente por Go e Rust sem serialização/deserialização JSON.

## As 5 POCs Implementadas

| POC | Módulo Rust | Gap Go Resolvido | Tecnologias Kumo + `NVIDIA/cuda-rust` |
|---|---|---|---|
| **POC-01** | `src/poc01_diskgraph.rs` | `internal/cognitive/sekg/sekg.go` (JSON em heap + vazamento temporal) | Kumo `DiskGraph` CSR `align(64)` + `cuda-oxide` SIMT Temporal Sampler + Tokenizador 5D `RelGT` |
| **POC-02** | `src/poc02_pql_relgt.rs` | `internal/cognitive/cultivator` & `memory` (limiar fixo = 3) | Kumo `PQL` (`PREDICT ... FOR EACH ... ASSUMING`) + `RelGT` Hybrid Attention `Tile2D<8,8>` + *In-Context Learning* |
| **POC-03** | `src/poc03_cuda_reranker.rs` | `internal/compute/router.go` (BM25 léxico + `AssistOnly` ADR-014) | `cutile-rs` Cross-Encoder Verifier + `cuda-core` `split_at_mut_device` + `INT8_STATIC` ($\cos \ge 0.998$) |
| **POC-04** | `src/poc04_jev_gnn_tribunal.rs` | `internal/jev/engine.go` (**18 de 25 especialistas `passDefault`**) | `cuda-oxide` SIMT 2-Layer Graph Neural Network sobre AST/CFG/Dataflow (Taint, Hexagonal, BOLA, Deadlock, Contrato) |
| **POC-05** | `src/poc05_aiops_imo_predictor.rs` | `internal/scheduler` & `internal/aiops` (EWMA 1D + `blast_radius` 42/89) | Regressor Relacional 8D Kumo (P95 Safety Margin) + `cuda-async` Multi-Stream 3-Hop Dynamic Blast Radius |

## Como Executar os Testes e o Benchmark Científico ($N=10$)

```powershell
$env:PATH = "$HOME\.cargo\bin;$env:PATH"
Set-Location templates\stacks\rust-kumo-cuda-labs

# 1. Rodar toda a suíte de testes unitários e científicos das 5 POCs + Ponte IPC
cargo test --release

# 2. Auditar com Clippy estrito (zero warnings)
cargo clippy --all-targets -- -D warnings

# 3. Executar a bateria científica (N=10 repetições) e imprimir a Tabela Executiva de Ranking
cargo run --release -- --bench-scientific

# 4. Inspecionar o módulo assembly PTX 8.4 (target sm_50+) dos kernels CUDA-Rust
cargo run --release -- --emit-ptx
```

## Exemplo de Cliente Go Zero-CGO (`CGO_ENABLED=0`) para o Sidecar Rust

```go
package kumobridge

import (
	"bufio"
	"fmt"
	"net"
	"time"
)

// Client mantém uma conexão Keep-Alive persistente com o sidecar Rust `squad-kumo-cuda-lab`,
// preservando CGO_ENABLED=0 e reduzindo a latência de 145.2 ms (spawn CLI) para ~50-120 us.
type Client struct {
	conn   net.Conn
	reader *bufio.Reader
}

func DialLoopback(addr string) (*Client, error) {
	conn, err := net.DialTimeout("tcp", addr, 200*time.Millisecond)
	if err != nil {
		return nil, err
	}
	return &Client{conn: conn, reader: bufio.NewReader(conn)}, nil
}

func (c *Client) CallMethod(id int, method string) (string, error) {
	_ = c.conn.SetDeadline(time.Now().Add(25 * time.Millisecond))
	req := fmt.Sprintf("{\"jsonrpc\":\"2.0\",\"id\":%d,\"method\":\"%s\"}\n", id, method)
	if _, err := c.conn.Write([]byte(req)); err != nil {
		return "", err
	}
	return c.reader.ReadString('\n')
}
```
