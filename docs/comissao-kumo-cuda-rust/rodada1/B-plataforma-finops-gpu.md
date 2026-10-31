# Memo — Arquiteto B (Performance, GPU Local & FinOps · `arquiteto-performance` + `inferencia-gpu-local`)

## Posição em 5 linhas
O estudo empírico do `SquadAI Harness v0.8.0` mostra que a Camada C0 em Go resolve tarefas léxicas em `0,55–9,5 ms`, mas o `internal/compute/router.go` trava toda inferência semântica em `HitPolicyAssistOnly` (ADR-014) e possui regras rígidas de orçamento de VRAM (ADR-017: reserva de sistema `1280 MB`, margem de segurança `512 MB`, proibição de co-alocar Embedding + Laya + LLM em 12 GB). O microserviço Rust com **Kumo + `NVIDIA/cuda-rust`** deve operar na **Camada C1.5 (Coprocessador Preditivo e Tensorial Nativo)**, entregando ganho de throughput e precisão onde o Go puro é limitado por GC, ausência de SIMD/GPU Tile IR e algoritmos puramente léxicos.

## Propostas concretas
1. **P2 (Performance) — Tiles 2D Alinhados (`cutile-rs`) para Atenção RelGT e Cross-Encoder:** Implementar blocos `Tile<f32, 16, 16>` alinhados em cache/shared-memory (`#[repr(C, align(64))]`) para multiplicação matricial em blocos (Tiled GEMM) e softmax fundido (Online Safe Softmax estilo FlashAttention), reduzindo tráfego de memória global/RAM.
2. **P2 + P3 — Governança de VRAM integrada ao `cuda-core` / `cuda-async`:** Antes de alocar `DeviceBuffer<T>` na GPU, o runtime Rust consulta o guarda `AdmitVRAMMultiTenant` (espelhando `internal/compute/router.go:394`). Na estação atual (`GeForce MX110`, `2048 MiB` total -> `768 MiB` útil após reserva de 1280 MB do Windows), tenants pesados fazem *graceful fallback* automático em $< 5\text{ }\mu\text{s}$ para o executor `CpuTileSimdBackend` do próprio Rust, mantendo paridade de cosseno $= 1.0000$.
3. **P2 — Metodologia Científica de Benchmark ($N = 10$ repetições após warm-up):** Medir $p50, p95, \text{IQR}, \mu \pm \sigma$, throughput (ops/s), alocação de memória e qualidade preditiva ($F_1$, $\text{ROC-AUC}$/calibração, $\text{MAE}$ e paridade de cosseno) comparando **Go Baseline AS-IS** vs. **Rust + Kumo + CUDA-Rust**.

## Respostas às tensões do meu domínio
- **T2 (Comunicação Go ↔ Rust):** Medir 3 transportes: (1) Subprocess Spawn CLI (`~140 ms` no Windows — reprovado para hot-path), (2) Persistent TCP Loopback / Pipe NDJSON-RPC (`< 0,25 ms` por RTT), e (3) Binary Shared File / `mmap` Arena (`< 0,05 ms` de leitura de subgrafo).
- **T4 (Heterogeneidade de Hardware):** Seguir a regra de ouro da skill `inferencia-gpu-local`: warm-up explícito fora do request, residência em memória e medição honesta separando tempo de transporte IPC, tempo de kernel e qualidade do modelo.
- **T6 (Desenho Experimental):** Cada uma das 5 POCs terá uma hipótese nula ($H_0$) e alternativa ($H_1$) com limiar quantitativo de aprovação.

## Riscos e armadilhas
- 🔴 **Cold-start oculto no benchmark:** Medir apenas 1 execução mistura paginação do SO com tempo de kernel. Mitigação: 3 rodadas de warm-up descartadas + $N = 10$ rodadas cronometradas em nanossegundos (`std::time::Instant`).
- 🟠 **Saturação de VRAM em GPUs de entrada (2 GB MX110):** Tentar alocar modelos grandes na MX110 causa OOM ou swap PCIe lento. Mitigação: `VramAdmissionGuard` no `cuda-core` que exige margem livre $\ge 512\text{ MB}$ e chaveia para execução Tile em CPU com zero falha.

## Dúvidas que SÓ o usuário pode responder (com default)
- **Q2:** Nas tabelas de benchmark, devemos exibir tanto a latência *in-process* do motor Rust quanto a latência *end-to-end* chamada a partir do cliente Go via IPC? *(Default: Sim, reportar ambas as métricas separadamente para transparência científica total).*

## O que eu vetaria se visse no plano
- Veto **números inventados ou estimados como se fossem medidos**: todo número do relatório executivo deve vir da execução real do binário compilado nesta estação (`ProvenanceMeasured` — nível V4).
