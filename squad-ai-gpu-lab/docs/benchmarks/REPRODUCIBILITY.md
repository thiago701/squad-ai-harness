# Relatório G — Guia Completo de Reprodutibilidade Científica (`REPRODUCIBILITY.md`)

> **Laboratório:** `squad-ai-gpu-lab` · **Ambiente Operacional:** Windows 11 (`x86_64`), PowerShell-first
> **Garantia de Reprodutibilidade (§12):** Todos os geradores de dados sintéticos, grafos temporais CSR, matrizes e séries de telemetria deste laboratório são **100% determinísticos (sem sementes aleatórias não-controladas)** e compilam **100% offline** sem necessidade de download de crates externos.

---

## 1. Especificação Exata do Ambiente de Referência

| Componente | Versão / Especificação Verificada na Estação |
|---|---|
| **Sistema Operacional** | Windows 11 (`windows/amd64`), modelo `Samsung 550XCJ/550XCR` |
| **CPU** | `Intel(R) Core(TM) i7-10510U CPU @ 1.80GHz` (`4` núcleos físicos, `8` processadores lógicos, `2304 MHz`) |
| **Memória RAM** | `16.984.416.256 bytes` (`~16,2 GiB` RAM física) |
| **GPU Dedicada (dGPU)** | `NVIDIA GeForce MX110` (`2048 MiB` VRAM total, Maxwell `GM108` Compute Capability `sm_50`, `2` SMs, barramento `64-bit`, clock `1006 MHz`) |
| **Driver NVIDIA / CUDA** | Driver WDDM `451.67` (`27.21.14.5167`), `C:\Windows\System32\nvcuda.dll` (CUDA Driver API `11.0` / `11000`) |
| **Toolchain Go** | `go1.24.3 windows/amd64` (`CGO_ENABLED=0`) |
| **Toolchain Rust** | `rustc 1.99.1 (58cf8f9c3 2026-10-13)` / `cargo 1.99.1 (5f94df478 2026-08-27)` (`stable-x86_64-pc-windows-msvc`) |

---

## 2. Estrutura de Diretórios do Laboratório

Para respeitar integralmente a trava de pureza Go do repositório principal ([`internal/gates/gopurity.go`](file:///c:/Users/tgg_/ClaudeProjects/squad-ai-harness/internal/gates/gopurity.go)), o laboratório está organizado em duas superfícies sincronizadas:

1. **[`templates/squad-ai-gpu-lab/`](file:///c:/Users/tgg_/ClaudeProjects/squad-ai-harness/templates/squad-ai-gpu-lab/Cargo.toml)** — O **Workspace Cargo executável completo em Rust** (contendo os 6 crates fundacionais em `crates/*`, as 10 POCs independentes em `pocs/poc-001..poc-010`, e os binários `tools/gpu-probe` e `tools/reproducibility`).
2. **[`squad-ai-gpu-lab/`](file:///c:/Users/tgg_/ClaudeProjects/squad-ai-harness/squad-ai-gpu-lab/)** — A **Superfície Documental, Contratos MCP, Resultados Brutos e Cliente Go** na raiz do repositório (`docs/*`, `integration/contracts/*`, `integration/go-mcp-client/*`, `benchmarks/raw-results/benchmark_results.json`).

---

## 3. Passo a Passo para Reproduzir Todos os Testes e Benchmarks (PowerShell)

Execute os comandos abaixo no PowerShell a partir da raiz do repositório (`c:\Users\tgg_\ClaudeProjects\squad-ai-harness`):

### Passo 1 — Sondar a GPU Física via Driver API (`nvcuda.dll`) e Executar Smoke Test PTX (`sm_50`)

```powershell
$env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"
Push-Location .\templates\squad-ai-gpu-lab
cargo run --release --bin gpu-probe
Pop-Location
```

**Saída esperada (JSON em 1 linha):**
- `"status":"GPU_ACTIVE"`, `"device_name":"GeForce MX110"`, `"sm_arch":"sm_50"`, `"total_vram_mb":2048`, `"usable_lab_budget_mb":768`, além da decomposição de latência entre execução não-amortizada (`smoke_1024x128_unamortized_us`) e execução com VRAM residente (`smoke_1024x128_resident_us`).

### Passo 2 — Executar a Bateria Completa de Testes Unitários e de Integração dos 18 Crates Rust + GPU

```powershell
$env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"
Push-Location .\templates\squad-ai-gpu-lab
cargo test --release
Pop-Location
```

**O que este comando valida:**
- `gpu-runtime`: *borrow checking* de `DeviceSliceMut::split_at_mut` (`cuda-core`) e execução real dos 4 kernels PTX (`batch_dot_product_f32`, `tiled_gemm_f32`, `csr_pagerank_spmv_f32`, `batch_risk_fusion_f32`) na `NVIDIA GeForce MX110`.
- `kumo-adapter`: parser `PQL`, tokenizador 5D `RelGT` e bloqueio estrito de arestas futuras ($\tau(e) > t_{\text{anchor}}$).
- `poc-001` a `poc-010`: validação matemática de todas as hipóteses contra os baselines.
- `mcp-server`: despacho de tools JSON-RPC 2.0 e benchmark de Loopback TCP Keep-Alive.

### Passo 3 — Executar a Suíte Científica Completa de Benchmarks (`Small`, `Medium`, `Large`, `XL`, $N=20$)

```powershell
$env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"
Push-Location .\templates\squad-ai-gpu-lab
cargo run --release --bin reproducibility
Pop-Location
```

### Passo 4 — Executar os Baselines Go (Grupos A e B) e Testar o Cliente Go MCP + Cabeçalho `.kdg`

```powershell
go test -v ./squad-ai-gpu-lab/integration/go-mcp-client/...
```

### Passo 5 — Verificar que a Arquitetura Principal da SquadAI Continua 100% Íntegra e Verde no Gate

```powershell
.\squad-harness.exe gate
```

**Resultado obrigatório:** `Overall Passed: true` (`6/6` nós do DAG aprovados, zero violações em `VerifyGoExclusiveLock` e zero alertas em `secretscan`).
