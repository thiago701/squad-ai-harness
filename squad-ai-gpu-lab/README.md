# SquadAI GPU Intelligence Lab (`squad-ai-gpu-lab`)

> **Missão:** Investigar, desenvolver e comparar cientificamente módulos experimentais de computação de alto desempenho e inteligência preditiva para o **SquadAI Harness v0.8.0** utilizando **Go + MCP + Rust + NVIDIA CUDA (`nvcuda.dll` / PTX `sm_50`) + NVIDIA Kumo (`PQL` + `RelGT` + `ICL`)**.
> **Restrição Inegociável Cumprida:** A arquitetura principal em Go 1.24.3 (`cmd/`, `internal/`, `pkg/`, `go.mod`) permaneceu **100% intocada** e o gate `.\squad-harness.exe gate` permanece **100% verde (`6/6 PASS`)**.

---

## 1. Índice dos 7 Entregáveis Obrigatórios (§12 do Prompt Master)

| Código | Documento Oficial | Escopo Científico e Executivo |
|---|---|---|
| **A** | [`docs/ARCHITECTURE_AUDIT.md`](file:///c:/Users/tgg_/ClaudeProjects/squad-ai-harness/squad-ai-gpu-lab/docs/ARCHITECTURE_AUDIT.md) | Auditoria completa do código-fonte Go v0.8.0 e Catálogo de 10 Gaps confirmados por evidência (`GAP-01` a `GAP-10`). |
| **B** | [`docs/TECHNOLOGY_FEASIBILITY.md`](file:///c:/Users/tgg_/ClaudeProjects/squad-ai-harness/squad-ai-gpu-lab/docs/TECHNOLOGY_FEASIBILITY.md) | Pesquisa aprofundada sobre NVIDIA Kumo (`KumoRFM-2`, `RelGT`, `PQL`, `NIM`), `NVIDIA/cuda-rust` (`cuda-oxide`, `cutile-rs`, `cuda-core`, `cuda-async`) e matriz de viabilidade. |
| **C** | [`docs/POC_CATALOG.md`](file:///c:/Users/tgg_/ClaudeProjects/squad-ai-harness/squad-ai-gpu-lab/docs/POC_CATALOG.md) | Catálogo das 10 POCs independentes em Rust (`POC-001` a `POC-010`), hipóteses falsificáveis e resultados. |
| **D** | [`docs/SCIENTIFIC_BENCHMARK_REPORT.md`](file:///c:/Users/tgg_/ClaudeProjects/squad-ai-harness/squad-ai-gpu-lab/docs/SCIENTIFIC_BENCHMARK_REPORT.md) | Medições reais na `NVIDIA GeForce MX110 (sm_50)` e `Core i7-10510U` ($N=20$) nas escalas `Small`, `Medium`, `Large` e `XL` contra os Grupos A–H. |
| **E** | [`docs/GPU_MCP_RANKING.md`](file:///c:/Users/tgg_/ClaudeProjects/squad-ai-harness/squad-ai-gpu-lab/docs/GPU_MCP_RANKING.md) | Ranking científico ponderado `0–100` (`30/25/15/10/10/10`), atribuição `Rust vs CUDA vs Kumo vs IPC` e classificação de recomendação. |
| **F** | [`docs/EXECUTIVE_REPORT.md`](file:///c:/Users/tgg_/ClaudeProjects/squad-ai-harness/squad-ai-gpu-lab/docs/EXECUTIVE_REPORT.md) | Relatório executivo para decisão arquitetural: top POCs, POCs descartadas, riscos, custos e roadmap gradual. |
| **G** | [`docs/REPRODUCIBILITY.md`](file:///c:/Users/tgg_/ClaudeProjects/squad-ai-harness/squad-ai-gpu-lab/docs/REPRODUCIBILITY.md) | Guia passo a passo para reproduzir a sondagem de GPU, testes e benchmarks 100% offline no PowerShell. |

---

## 2. Mapa de Código e Artefatos do Laboratório

- **Workspace Rust Completo (18 Crates):** [`templates/squad-ai-gpu-lab/Cargo.toml`](file:///c:/Users/tgg_/ClaudeProjects/squad-ai-harness/templates/squad-ai-gpu-lab/Cargo.toml)
  - [`crates/gpu-runtime`](file:///c:/Users/tgg_/ClaudeProjects/squad-ai-harness/templates/squad-ai-gpu-lab/crates/gpu-runtime/src/lib.rs) — Loader FFI `nvcuda.dll`, 4 kernels PTX `.version 6.5 .target sm_50`, `DeviceSliceMut::split_at_mut` (`cuda-core`) e `ResidentVramArena` (`ADR-017`).
  - [`crates/cpu-baselines`](file:///c:/Users/tgg_/ClaudeProjects/squad-ai-harness/templates/squad-ai-gpu-lab/crates/cpu-baselines/src/lib.rs) — Baselines Grupo C (Rust CPU Single-Thread SIMD) e Grupo D (Rust CPU Multi-Thread `std::thread::scope`).
  - [`crates/kumo-adapter`](file:///c:/Users/tgg_/ClaudeProjects/squad-ai-harness/templates/squad-ai-gpu-lab/crates/kumo-adapter/src/lib.rs) — Grafo temporal CSR `.kdg`, corte anti-leakage ($\tau(e) \le t_{\text{anchor}}$), parser `PQL`, tokenizador 5D `RelGT` e atenção `ICL`.
  - [`crates/mcp-server`](file:///c:/Users/tgg_/ClaudeProjects/squad-ai-harness/templates/squad-ai-gpu-lab/crates/mcp-server/src/lib.rs) — Servidor MCP JSON-RPC 2.0 (`stdio` e Loopback TCP Keep-Alive) com contexto CUDA persistente.
  - [`crates/benchmark-core`](file:///c:/Users/tgg_/ClaudeProjects/squad-ai-harness/templates/squad-ai-gpu-lab/crates/benchmark-core/src/lib.rs) & [`crates/telemetry`](file:///c:/Users/tgg_/ClaudeProjects/squad-ai-harness/templates/squad-ai-gpu-lab/crates/telemetry/src/lib.rs) — Estatísticas (`p50`, `p95`, `p99`, `CI95`), métricas preditivas (`Precision`, `Recall`, `F1`, `AUROC`, `Brier`) e ranking `0–100`.
  - [`pocs/poc-001`](file:///c:/Users/tgg_/ClaudeProjects/squad-ai-harness/templates/squad-ai-gpu-lab/pocs/poc-001-predictive-failure/src/lib.rs) .. [`pocs/poc-010`](file:///c:/Users/tgg_/ClaudeProjects/squad-ai-harness/templates/squad-ai-gpu-lab/pocs/poc-010-anomaly-intelligence/src/lib.rs) — Os 10 mini-projetos independentes.
  - [`tools/gpu-probe`](file:///c:/Users/tgg_/ClaudeProjects/squad-ai-harness/templates/squad-ai-gpu-lab/tools/gpu-probe/src/main.rs) & [`tools/reproducibility`](file:///c:/Users/tgg_/ClaudeProjects/squad-ai-harness/templates/squad-ai-gpu-lab/tools/reproducibility/src/main.rs) — Executáveis CLI de sondagem e benchmark científico.
- **Cliente Go MCP e Contratos:** [`integration/go-mcp-client/client.go`](file:///c:/Users/tgg_/ClaudeProjects/squad-ai-harness/squad-ai-gpu-lab/integration/go-mcp-client/client.go) e [`integration/contracts/mcp_gpu_lab_contracts.json`](file:///c:/Users/tgg_/ClaudeProjects/squad-ai-harness/squad-ai-gpu-lab/integration/contracts/mcp_gpu_lab_contracts.json).
- **Resultados Brutos em JSON:** [`benchmarks/raw-results/benchmark_results.json`](file:///c:/Users/tgg_/ClaudeProjects/squad-ai-harness/squad-ai-gpu-lab/benchmarks/raw-results/benchmark_results.json).
