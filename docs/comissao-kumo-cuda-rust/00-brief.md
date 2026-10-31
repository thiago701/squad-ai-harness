# BRIEF DA COMISSÃO — Laboratório Experimental Kumo ML + CUDA-Rust para SquadAI Harness
> **Motor:** `squad-pipeline` (tier `large` — Pesquisa Aplicada & Laboratório Experimental).
> **Data:** 2026-10-31 · **Origem:** `squad-ai`
> **Arbitragem:** `P1-Simplicidade > P2-Performance > P3-CustoBaixo`. Segurança e Pureza Go (`CGO_ENABLED=0`) no núcleo são inegociáveis.

---

## 1. Pedido (verbatim resumido sem perda de requisitos)
- Desenvolver um **microserviço experimental de laboratório** composto por uma **coleção de POCs de módulos complementares à Squad AI**.
- Estudar profundamente:
  1. **Tecnologia KUMO** (`Kumo AI` / `KumoRFM` / `KumoRFM-2`, `RelGT` — *Relational Graph Transformer*, `PQL` — *Predictive Query Language*, `DiskGraph` em Rust para indexação NVMe/mmap e amostragem de subgrafos temporais sem vazamento do futuro, e *In-Context Learning* sobre esquemas relacionais heterogêneos).
  2. **Repositório `NVIDIA/cuda-rust`** (`https://github.com/NVIDIA/cuda-rust` — crates host `cuda-bindings`, `cuda-core`, `cuda-async` com extensão do *borrow checker* do Rust através da fronteira de lançamento CPU→GPU, e as duas trilhas de kernels: **`cutile-rs`** baseada em CUDA Tile IR em Rust estável e **`cuda-oxide`** baseada em SIMT PTX via Rust MIR/Pliron).
- Analisar a **Squad AI atual (`SquadAI Harness v0.8.0` em Go 1.24.3)** e levantar **gaps reais no código-fonte** e estratégias de evolução.
- Instituir uma **Comissão de Arquitetos** (6 papéis ortogonais + Revisor Independente) para relacionar todas as necessidades, arbitrar tensões via ADRs e validar cada necessidade com uma **POC concreta em Rust**.
- Considerar a hipótese central de combinar **Machine Learning com KUMO + RUST + CUDA com GPU e RUST**, mantendo a **Squad AI em Go (`CGO_ENABLED=0`)** e projetando/medindo o **meio de comunicação ideal entre Go e Rust**.
- Entregar uma **tabela com ranking dos projetos (POCs)** com maiores ganhos e diferenciais e um **Relatório Executivo com métodos científicos de experimentação** (hipóteses formais, baseline Go AS-IS vs. POCs Rust+Kumo+CUDA, estatística descritiva $p50, p95, \text{IQR}, \mu \pm \sigma$ com $N \ge 5$).

---

## 2. Diagnóstico Factual do Código Atual da Squad AI (`v0.8.0` Go 1.24.3)
A inspeção estática e dinâmica do código-fonte em `cmd/squad-harness` e `internal/` revelou **6 gaps concretos e mensuráveis**:

| ID | Módulo Atual (Go 1.24.3) | Evidência no Código-Fonte | Limitação / Gap Real |
|---|---|---|---|
| **GAP-01** | `internal/cognitive/sekg/sekg.go` | `GraphCSR` serializado em JSON (`sekg.db`), carregado inteiro em heap (`GOMEMLIMIT=256MiB`, `main.go:40`), `AnalyzeImpact` (linhas 377–489) faz busca 1-hop/2-hop sem timestamp por aresta. | **Sem armazenamento `DiskGraph` zero-copy (`mmap`) e sem amostragem temporal (`anchor_time`)**: sofre de *temporal leakage* ao analisar histórico e não gera os 5 tokens multidimensionais do Kumo `RelGT`. |
| **GAP-02** | `internal/cognitive/memory/memory.go` & `cultivator/cultivator.go` | `computeSurpriseLocked` (linhas 108–121) usa apenas `0.50 + 0.50 * unseen/len(skills)`; `HarvestCandidates` (linhas 34–52) usa limiar fixo `MinVerifiedOccurrences = 3`. | **Ausência de `PQL` (Predictive Query Language) e `KumoRFM` (`RelGT` + ICL)**: incapaz de responder consultas preditivas sobre o grafo relacional `Developer ↔ Commit ↔ Module ↔ Skill ↔ GateEpisode`. |
| **GAP-03** | `internal/compute/router.go` & `internal/cognitive/router/router.go` | `router.go` usa apenas BM25 léxico + 10 sinônimos (`ptEnSynonyms`, linhas 51–62). `compute/router.go` (linhas 5–6, 449) crava `HitPolicyAssistOnly` porque falta um verificador Cross-Encoder nativo. | **Bloqueio do ADR-014 (`assist_only`)**: sem um **Cross-Encoder Verifier & Tensor Reranker** rápido e determinístico (paridade $\cos \ge 0.99$), a Squad AI rejeita *cache hits* semânticos e perde recall em queries sem sobreposição léxica. |
| **GAP-04** | `internal/jev/engine.go` & `internal/sonar/sonar.go` | Em `build25Specialists()` (`internal/jev/engine.go:155-204`), **18 dos 25 especialistas JEV usam `passDefault`**, retornando sempre `APPROVE, 1.0, 0.95`! Só 7 especialistas usam regex lineares (`regexp.MustCompile`). | **Cegueira estrutural e inter-procedural no Tribunal JEV**: regex por linha não detecta violação de fronteira hexagonal entre pacotes, fluxo de taint (`Source → Sink`), acoplamento cíclico ou quebra semântica de contrato. |
| **GAP-05** | `internal/scheduler/scheduler.go` & `internal/aiops/aiops.go` | `CheckAdmission` (`scheduler.go:94-99`) chuta `400 MB` ou `25 MB` no cold-start e usa EWMA 1D (`EWMAAlpha=0.30`). `aiops.go` (linhas 551, 797) usa `blast_radius` estático (`42` e `89`). | **Sub/super-alocação de memória no IMO 8D e Blast Radius fixo no AIOps**: ignora a interação não-linear entre tamanho do grafo, concorrência, VRAM multi-tenant (ADR-017) e topologia de falhas em cascata. |
| **GAP-06** | `internal/gates/gopurity.go` & `internal/hooks/hooks.go` | `VerifyGoExclusiveLock` (`gopurity.go:143`) proíbe CGO (`.c/.h`) e arquivos `.rs` fora de `skills/` e `templates/`. Spawn de processo no Windows custa ~140–170 ms (`BENCHMARKS-V080.md`). | **Fronteira Go (`CGO_ENABLED=0`) ↔ Rust**: exige protocolo IPC sem CGO com processo residente (*warm*) e/ou arena binária zero-copy (`mmap`) para que chamadas Go→Rust custem sub-milissegundo. |

---

## 3. Fatos de Plataforma e Tecnologias Estudadas (Verificados)
1. **KUMO (`KumoRFM` / `RelGT` / `PQL` / `DiskGraph`)**:
   - **PQL (Predictive Query Language):** sintaxe declarativa `PREDICT <agg_expr> [horizon] FOR EACH <entity.pk> [ASSUMING <cond>]`.
   - **RelGT (Relational Graph Transformer):** tokeniza cada nó do subgrafo temporal amostrado em **5 elementos**: (1) *Features*, (2) *Entity/Table Type*, (3) *Hop Distance*, (4) *Temporal Delta ($\Delta t$)* e (5) *Local Structural Signature*, combinando atenção local na vizinhança com atenção global por centróides e *In-Context Learning (ICL)* zero-shot.
   - **DiskGraph (Rust):** motor nativo em Rust que indexa grafos relacionais em layout CSR compacto para leitura direta do disco/NVMe (`mmap`) sem explodir a RAM.
2. **`NVIDIA/cuda-rust` (`https://github.com/NVIDIA/cuda-rust`)**:
   - **Host Runtime (`cuda-bindings`, `cuda-core`, `cuda-async`):** gerencia contexto, streams, eventos e estende as regras de *ownership* e *borrow checker* do Rust através da fronteira CPU→GPU (ex.: partição disjunta de buffers mutáveis `split_at_mut_device` antes do lançamento do kernel).
   - **Trilha `cutile-rs` (Tile Model):** roda em **Rust estável (`1.89+`, estação atual com `rustc 1.99.1`)**, operando sobre blocos tensoriais multidimensionais (`Tile<T, [M, N]>`) livres de *data race* por construção.
   - **Trilha `cuda-oxide` (SIMT Model):** programação granular por thread/warp/bloco (`#[kernel]`, índices `thread_idx_x`, `block_idx_x`, reduções de warp em memória compartilhada).
3. **Ambiente da Estação Atual (`WORKSTATION` Windows 11)**:
   - Toolchains instaladas e verificadas: `go1.24.3 windows/amd64` e `rustc 1.99.1 (58cf8f9c3 2026-10-13)` / `cargo 1.99.1`.
   - GPU detectada via `nvidia-smi`: `GeForce MX110` (`2048 MiB`, driver `451.67`). Conforme a lei empírica já codificada no `BENCHMARKS-V080.md` (H6) e `internal/compute/router.go`, a `MX110` possui apenas 2 GB de VRAM; portanto, a arquitetura `cuda-rust` deve implementar o trait `ComputeBackend` com **duas execuções verificáveis**: o dispatcher `CudaDriverBackend` (PTX/Tile com guarda de admissão VRAM ADR-017) e o executor `SimdTileCpuBackend` determinístico em Rust puro, garantindo 100% de execução real e paridade matemática ($\cos \ge 0.9999$) em qualquer estação!

---

## 4. Tensões que a Comissão Precisa Resolver ($T_1 \dots T_6$)
- **T1 (Isolamento Go × Rust):** Como organizar o microserviço Rust e suas 5 POCs dentro do repositório sem quebrar `VerifyGoExclusiveLock` (`internal/gates/gopurity.go`) nem introduzir CGO no Go?
- **T2 (Protocolo de Comunicação Go ↔ Rust):** Qual meio de comunicação entre o binário Go (`squad-harness`) e o microserviço Rust (`kumo-cuda-sidecar`) oferece a melhor relação P1 (Simplicidade) × P2 (Latência $< 0,5\text{ ms}$) × P3 (Zero Custo)?
- **T3 (Fidelidade Matemática Kumo RelGT + PQL em Rust):** Como implementar `DiskGraph`, `PQL` e `RelGT` (5D Tokenization + Local/Global Attention + ICL) em Rust enxuto, sem depender de gigabytes de pacotes Python/PyTorch?
- **T4 (Arquitetura `NVIDIA/cuda-rust` em Estações Heterogêneas):** Como aplicar os contratos de segurança de memória de `cuda-core`/`cuda-async` e os dois paradigmas de kernel (`cutile-rs` Tile e `cuda-oxide` SIMT) garantindo execução determinística tanto em RTX 3060/4090 quanto na estação atual (`MX110` / CPU)?
- **T5 (Segurança e Governança Gated):** Como garantir que nenhuma predição probabilística de ML (Kumo/GNN) substitua cegamente uma regra pétrea de segurança (ex.: SQLi, segredo vazado, ADR-014)?
- **T6 (Desenho Experimental Científico):** Quais métricas, oráculos de teste e protocolos estatísticos ($N$ repetições, $p50, p95, \text{IQR}, \mu \pm \sigma$, $F_1$, erro médio absoluto MAE, paridade de cosseno) ranquearão cientificamente as 5 POCs?

---

## 5. Papéis Convocados para a Comissão
- **Arquiteto A (`arquiteto-minimalista`):** Topologia mínima do microserviço e fronteira Go↔Rust sem inchamento.
- **Arquiteto B (`arquiteto-performance` + `inferencia-gpu-local`):** Latência, throughput, orçamento de RAM/VRAM (ADR-017) e benchmark científico.
- **Arquiteto C (`engenheiro-seguranca` + `rust-unsafe-security`):** STRIDE da ponte IPC Go↔Rust, isolamento de `unsafe` na FFI CUDA, invariantes determinísticos vs. ML.
- **Arquiteto D (`engenheiro-devops` + `monitor-aiops`):** Ciclo de vida do sidecar, integração com MCP/AIOps e escalonador 8D IMO.
- **Arquiteto E (`engenheiro-especificacao` + `arquiteto-ia`):** Modelagem do Grafo Relacional Temporal, gramática PQL e arquitetura Kumo RelGT + ICL.
- **Arquiteto F (`rust-pro` + Especialista Ad-Hoc `Kumo + NVIDIA/cuda-rust`):** Desenho das crates `cuda-core`, `cuda-async`, `cutile-rs`, `cuda-oxide` e das 5 POCs em Rust 1.99.1 (Edição 2024).
- **Revisor Independente (`tech-lead-review`):** Auditoria final contra todos os requisitos verbatim do usuário.
