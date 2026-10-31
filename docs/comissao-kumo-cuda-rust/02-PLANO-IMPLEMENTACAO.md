# PLANO DE IMPLEMENTAÇÃO E EXPERIMENTAÇÃO CIENTÍFICA — `squad-kumo-cuda-lab`

> **Orquestrador:** `squad-pipeline` · **Alvo Rust:** `rustc 1.99.1 (edição 2024)` · **Alvo Go:** `go 1.24.3 (CGO_ENABLED=0)`
> **Diretório do Laboratório:** `templates/stacks/rust-kumo-cuda-labs/`

---

## 1. Estrutura do Projeto (Monólito Modular Experimental)

```text
templates/stacks/rust-kumo-cuda-labs/
├── Cargo.toml                        # Configuração do pacote Rust 1.99.1 (Edição 2024, Lints estritos)
├── README.md                         # Documentação técnica e guia de execução das 5 POCs + Ponte Go
├── src/
│   ├── lib.rs                        # Raiz da biblioteca exportando runtime CUDA-Rust, 5 POCs e IPC
│   ├── main.rs                       # Binário `kumo-cuda-sidecar` (CLI Benchmark Científico + JSON-RPC 2.0 Server)
│   ├── cuda_rust_runtime.rs          # Camada NVIDIA/cuda-rust: cuda-core, cuda-async, cutile-rs, cuda-oxide + PTX
│   ├── poc01_diskgraph.rs            # POC-01: Kumo DiskGraph 64B CSR + Time-Travel Sampler + 5D RelGT Tokenizer
│   ├── poc02_pql_relgt.rs            # POC-02: Parser PQL + RelGT Local/Global Tile Attention + In-Context Learning
│   ├── poc03_cuda_reranker.rs        # POC-03: Cross-Encoder Verifier Tile Kernel + INT8/FP32 Parity (ADR-014)
│   ├── poc04_jev_gnn_tribunal.rs     # POC-04: JEV GNN Message Passing + SIMT Taint Analysis (18 especialistas)
│   ├── poc05_aiops_imo_predictor.rs  # POC-05: Preditor Relacional 8D IMO (RAM/VRAM) + 3-Hop Dynamic Blast Radius
│   └── ipc_bridge.rs                 # Servidor JSON-RPC 2.0 Persistente (Stdio Pipe + TCP 127.0.0.1 + .kdg Arena)
└── go_bridge_client/
    └── bridge_client_example.md      # Contrato e cliente Go stdlib para invocação sub-ms
```

---

## 2. Fases de Execução e Critérios de Aceite Verificáveis

| Fase | Entrega | Comando de Verificação (Oráculo) | Critério de Pronto (DoD) |
|---|---|---|---|
| **Fase 1** | Comissão de Arquitetos (Brief, 6 Memos R1, ADRs R2/R3, Spec, Plano, Revisão Independente) | Inspeção em `docs/comissao-kumo-cuda-rust/` | `6/6 SEM DÚVIDAS` + matriz de cobertura `100% COBERTO` |
| **Fase 2** | Implementação da Camada `NVIDIA/cuda-rust` (`cuda_rust_runtime.rs`) + 5 POCs (`poc01..poc05`) + `ipc_bridge.rs` | `cargo test --release` e `cargo clippy -- -D warnings` | Zero erros, zero warnings, `#[forbid(unsafe_code)]` ativo, testes unitários de cada POC verdes |
| **Fase 3** | Execução da Suíte Científica de Experimentação ($N = 10$ repetições por POC + Benchmark IPC Go↔Rust) | `kumo-cuda-sidecar.exe --bench-scientific --runs 10` | JSON/Tabelas com $p50, p95, \text{IQR}, \mu \pm \sigma$, $F_1$, $\text{MAE}$, Paridade de Cosseno $\ge 0.99$ |
| **Fase 4** | Validação de Pureza Go e Gates de Entrega do SquadAI Harness | `.\squad-harness.exe gate` | Todos os 6 nós do DAG (`catalog`, `jev`, `go_exclusive_lock`, `sekg`, `delivery_gates`) em `PASS` |
| **Fase 5** | Relatório Executivo Científico & Ranking das POCs | `docs/RELATORIO-EXECUTIVO-KUMO-CUDA-RUST.md` | Ranking multicritério fundamentado em dados empíricos V4 |
