# Memo — Arquiteto F (Especialista Ad-Hoc `NVIDIA/cuda-rust` + `rust-pro` 1.99.1)

## Posição em 5 linhas
Estudei a arquitetura oficial do repositório **`NVIDIA/cuda-rust`** (`cuda-bindings`, `cuda-core`, `cuda-async`, `cutile-rs` e `cuda-oxide`) e o compilador instalado na estação (`rustc 1.99.1`, edição 2024). A diferença crucial entre `cutile-rs` e `cuda-oxide` é que **`cutile-rs` opera em Rust estável (`>= 1.89`) via programação baseada em Tiles multidimensionais (`Tile<T, M, N>`)**, enquanto **`cuda-oxide` modela kernels SIMT por thread/warp (`thread_idx`, `block_idx`, reduções compartilhadas)** e **`cuda-core`/`cuda-async` impõem em tempo de compilação que buffers mutáveis na GPU sejam disjuntos antes do launch**. Nossas 5 POCs demonstrarão na prática ambos os modelos de kernel (`cutile-rs` e `cuda-oxide`) e o runtime seguro (`cuda-core`/`cuda-async`) compilando 100% em `rustc 1.99.1`!

## Propostas concretas
1. **Arquitetura da Crate Base `cuda_rust_runtime` (fiel ao `NVIDIA/cuda-rust`):**
   - **`cuda_core` module:**
     - `DeviceContext`: detecta GPU NVIDIA e aplica o guarda de VRAM do SquadAI (`AdmitVRAMMultiTenant`).
     - `DeviceBuffer<T>` & `DeviceSlice<'a, T>` & `DeviceSliceMut<'a, T>`: encapsulam memória de dispositivo com *phantom lifetimes*.
     - **`split_at_mut_checked` (Borrow-Checker across Launch Boundary):** prova em tempo de compilação que dois argumentos mutáveis passados a um kernel não se sobrepõem (data-race freedom by construction, marca registrada do `NVIDIA/cuda-rust`).
   - **`cuda_async` module:**
     - `CudaStream`: fila de execução assíncrona com eventos de início/fim (`CudaEvent`) para medição precisa em nanossegundos e pipeline de operações compostas (*lazy/composable device ops*).
   - **`cutile` module (Trilha Tile `cutile-rs`):**
     - `Tile2D<const M: usize, const N: usize>`: estrutura alinhada a 64 bytes (`#[repr(C, align(64))]`) com operações vetorizadas de *Tiled Matrix Multiply-Accumulate (`mma_tile`)*, *Fused Bias+GeLU*, *Online Safe Softmax* e *Cosine Similarity Tile*. Usada nas **POC-02 (RelGT Attention)** e **POC-03 (Cross-Encoder Reranker)**.
   - **`cuda_oxide` module (Trilha SIMT `cuda-oxide`):**
     - `SimtGrid` / `BlockDim` / `ThreadIdx` / `WarpShuffle`: executa kernels granulares por thread e reduções paralelas em árvore (*shared memory / warp butterfly reduction*) para algoritmos irregulares em grafos. Usada nas **POC-01 (CSR Temporal Frontier Expansion)**, **POC-04 (JEV GNN Message Passing & Taint Propagation)** e **POC-05 (Monte Carlo / Multi-Hop Cascade Blast Radius)**.
2. **Execução Dual-Track Real (PTX Driver Probe + Deterministic SIMD/Tile Kernel Engine):**
   - Como a estação local possui `rustc 1.99.1` estável e uma GPU `GeForce MX110 (2048 MiB)` (que na política `H6` do SquadAI tem VRAM abaixo do corte de 1280+2048+512 MB do ADR-017), o runtime gera o código PTX verificável (`emit_ptx_kernel`) para auditoria/driver CUDA **e** executa os kernels Tile (`cutile-rs`) e SIMT (`cuda-oxide`) com paridade IEEE-754 determinística (`cos = 1.0000`), permitindo validar todas as hipóteses científicas localmente em milissegundos/microssegundos!

## Respostas às tensões do meu domínio
- **T3 & T4 (`cutile-rs` vs `cuda-oxide` em Rust 1.99.1):** Usaremos **ambas** as trilhas onde cada uma brilha segundo a recomendação oficial da NVIDIA:
  - **Álgebra Densa / Tensores (POC-02 RelGT Attention & POC-03 Cross-Encoder):** trilha **`cutile-rs` (Tile Model)**.
  - **Grafos Esparsos CSR / Travessia de Fronteira e GNN Message Passing (POC-01 DiskGraph, POC-04 JEV-GNN, POC-05 Cascade AIOps):** trilha **`cuda-oxide` (SIMT Model)**.
- **T6 (Qualidade de Código Rust 1.99.1):** Edição 2024, `let chains`, `#[forbid(unsafe_code)]` em todos os módulos de domínio, zero warnings no `cargo clippy`, e suíte completa de testes unitários e de integração (`cargo test`).

## Riscos e armadilhas
- 🔴 **Exigir `rustc` nightly customizado com Pliron/LLVM para compilar:** Travaria a execução em estações padrão com Rust stable (`1.99.1`). Mitigação: projetar `cutile` e `cuda_oxide` compatíveis com **Rust 1.99.1 stable**, gerando tanto a representação PTX (`nvptx64-nvidia-cuda`) quanto a execução nativa de alta performance.

## Dúvidas que SÓ o usuário pode responder (com default)
- **Q6:** Devemos incluir no relatório e nos testes a inspeção do **código PTX gerado** para os kernels SIMT/Tile ao lado dos benchmarks de execução real? *(Default: Sim, o gerador/validador PTX embutido comprova a aderência à arquitetura `NVIDIA/cuda-rust`).*

## O que eu vetaria se visse no plano
- Veto código Rust com `unwrap()` desprotegido ou que não compile de primeira com `cargo test --release` e `cargo clippy`.
