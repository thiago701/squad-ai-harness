# ADRs da Comissão — Laboratório Kumo ML + CUDA-Rust para SquadAI Harness (`[v2]` pós-R2/R3)

> **Status:** Aprovado por unanimidade (`6/6 SEM DÚVIDAS` na Rodada 3).
> **Arbitragem:** `P1-Simplicidade > P2-Performance > P3-CustoBaixo` · Segurança e Pureza Go (`CGO_ENABLED=0`) inegociáveis.

---

## Consenso Direto (Sem Conflito na Rodada 1)
1. **5 POCs mapeadas 1-para-1 aos 5 Gaps Cognitivos/Operacionais do SquadAI Harness v0.8.0**, mais **1 Ponte de Interoperabilidade Go ↔ Rust** validada para resolver o GAP-06.
2. **Proibição absoluta de CGO (`import "C"`) no SquadAI Harness em Go**, preservando o binário estático `squad-harness.exe` (`CGO_ENABLED=0`) e `go.mod` sem dependências externas.
3. **Hospedagem do Workspace Rust em `templates/stacks/rust-kumo-cuda-labs/`**, garantindo 100% de conformidade com `VerifyGoExclusiveLock` (`internal/gates/gopurity.go:124`).

---

## Decisões Arquiteturais Arbitradas (ADRs)

### ADR-025 `[v2]` — Topologia de Comunicação Go (`CGO_ENABLED=0`) ↔ Microserviço Rust (`kumo-cuda-sidecar`)
- **Decisão:** Adotar uma **Arquitetura Dual-Channel Zero-CGO** entre o SquadAI Harness (Go 1.24.3) e o microserviço Rust 1.99.1:
  1. **Canal de Controle e RPC Rápido:** **JSON-RPC 2.0 Persistente (NDJSON Framing)** sobre `stdio` pipe (processo filho residente mantido *warm*) e `TCP Loopback 127.0.0.1` com `keep-alive` e token efêmero de sessão (`X-Squad-IPC-Token`), utilizando apenas a stdlib do Go (`net`, `bufio`, `encoding/json`).
  2. **Canal de Dados Pesados (Grafos CSR e Tensores):** **Arena Binária Zero-Copy Alinhada a 64 bytes (`.kdg` — *Kumo DiskGraph Snapshot*)** com envelope de integridade `SHA-256`, lida diretamente pelo Rust sem serializar megabytes de nós/arestas via JSON.
- **Por quê (P1 > P2 > P3 + Segurança):** Preserva `go.mod` com zero dependências externas (P1), elimina o custo de `140–175 ms` de spawn de processo no Windows mantendo latência de RTT em `< 0,25 ms` (P2), custa US$ 0 (P3) e impede conexões externas via bind estrito em `127.0.0.1` + validação de hash SHA-256 (Segurança).
- **Rejeitado:**
  - *CGO (`extern "C"` / `.dll` linkada no Go)* — Rejeitado por violar `internal/gates/gopurity.go` e destruir a compilação cruzada `CGO_ENABLED=0`.
  - *gRPC / Protobuf sobre HTTP/2* — Rejeitado por exigir dependências externas (`google.golang.org/grpc`) no `go.mod`, violando `gopurity.go:173`.
  - *CLI Subprocess Spawn por requisição* — Rejeitado para o *hot-path* (medido como baseline comparativo: ~140 ms de overhead de criação de processo no Windows).
- **Condições `[v2]` (incorporadas da R2 — Arquiteto C e D):** Limite máximo de frame IPC de `1 MiB`, encerramento automático no `EOF` do `stdin` (zero processos órfãos) e *Circuit Breaker* no cliente Go com fallback instantâneo para a Camada C0 se o sidecar estiver offline.

---

### ADR-026 `[v2]` — Combinação das Trilhas `cutile-rs` (Tile) e `cuda-oxide` (SIMT) do `NVIDIA/cuda-rust`
- **Decisão:** Estruturar a crate base do microserviço em torno dos 4 pilares do repositório oficial **`NVIDIA/cuda-rust`**, atribuindo cada modelo de programação de kernel à classe de algoritmo ideal:
  - **Host Runtime (`cuda_core` + `cuda_async`):** Gerenciamento de contexto, streams assíncronos, eventos de telemetria em nanossegundos e **verificação em tempo de compilação de empréstimos disjuntos (`split_at_mut_device`)** através da fronteira CPU→GPU (`#[forbid(unsafe_code)]` em todas as POCs).
  - **Trilha Tile (`cutile-rs` — `Tile2D<f32, 16, 16>`):** Aplicada às **operações densas de atenção e álgebra tensorial** na **POC-02 (Kumo RelGT Hybrid Attention)** e na **POC-03 (Cross-Encoder Verifier & Tensor Reranker)**.
  - **Trilha SIMT (`cuda-oxide` — Thread/Warp/Block Kernels):** Aplicada aos **algoritmos irregulares em grafos esparsos CSR** na **POC-01 (DiskGraph Temporal Frontier & 5D Tokenization)**, na **POC-04 (JEV GNN Message Passing & Taint Analysis)** e na **POC-05 (AIOps Multi-Hop Cascade & IMO Predictor)**.
- **Por quê (P1 + P2):** Segue a recomendação oficial da NVIDIA para `cuda-rust` (usar `cutile-rs` em Rust estável para workloads tensoriais em blocos e `cuda-oxide` SIMT onde indexação por thread/warp em grafos CSR é indispensável), mantendo 100% de compatibilidade com `rustc 1.99.1` stable.
- **Rejeitado:**
  - *Usar apenas SIMT manual para multiplicação matricial densa* — Mais propenso a erro e verboso que `cutile-rs` (viola P1).
  - *Exigir compilador `rustc` nightly customizado com LLVM/Pliron externo* — Impediria compilação imediata na estação Windows 11 com `rustc 1.99.1` stable.
- **Condições `[v2]` (incorporadas da R2 — Arquiteto B e F):** Incluir gerador/inspecionador de assembly **PTX (`nvptx64-nvidia-cuda`)** verificável e guarda `AdmitVRAMMultiTenant` (ADR-017) que seleciona automaticamente entre dispositivo CUDA elegível e o executor determinístico `SimdTileCpuBackend` com paridade de cosseno $\ge 0.9999$.

---

### ADR-027 `[v2]` — Arquitetura Kumo (`DiskGraph` + `PQL` + `RelGT` 5D + `ICL`) 100% em Rust Nativo
- **Decisão:** Implementar a pilha completa de **Relational Deep Learning (RDL)** inspirada na Kumo AI diretamente em Rust:
  1. **`DiskGraph` (POC-01):** Formato binário CSR alinhado a 64 bytes com carimbo temporal por aresta (`timestamp_unix`) e amostrador temporal estrito (`edge.timestamp <= anchor_time`) que elimina *temporal data leakage*.
  2. **Tokenização Multi-Elemento 5D (POC-01/POC-02):** Cada nó amostrado recebe representação explícita nas 5 dimensões do RelGT (*Features*, *Entity Type*, *Hop Distance*, *Time Delta*, *Local Structure*).
  3. **Compilador/Executor `PQL` + `RelGT` + `In-Context Learning` (POC-02):** Parser declarativo `PREDICT <agg_func>(<table.col>, <start>, <end>, <unit>) [op <val>] FOR EACH <entity.pk> [ASSUMING <filter>]` acoplado à atenção híbrida (Local Subgraph + Global Centroids) e inferência *in-context* (zero-shot sobre histórico rotulado anterior a `anchor_time`).
- **Por quê (P2 + P3):** Substitui as heurísticas cegas de contagem em `internal/cognitive/memory/memory.go` e `cultivator.go` por predição relacional calibrada com zero custo de tokens de LLM ($0 API) e zero dependência de Python.
- **Rejeitado:**
  - *Achatamento manual de tabelas (Table Flattening / SQL Joins estáticos)* — Perde a topologia multi-hop e a dinâmica temporal que diferenciam o Kumo RelGT.
- **Condições `[v2]` (incorporadas da R2 — Arquiteto C e E):** Particionamento temporal obrigatório ($t_{\text{context}} < t_{\text{anchor}} \le t_{\text{target}}$) validado por teste automatizado anti-*leakage*.

---

### ADR-028 `[v2]` — Promoção Segura `assist_only → verified` (POC-03) e Soberania Determinística no Tribunal JEV (POC-04)
- **Decisão:**
  1. **POC-03 (`cuda-rust-reranker`):** Só promove uma decisão do roteador de `HitPolicyAssistOnly` para `HitPolicyVerified` (destravando o ADR-014 em `internal/compute/router.go`) quando o **Cross-Encoder Verifier em Tiles (`cutile-rs`)** atingir simultaneamente **Paridade de Cosseno $\ge 0.99$** (FP16/INT8-Calibrated vs. FP32) e **Score de Verificação Cruzada $\ge 0.75$**.
  2. **POC-04 (`jev-gnn-tribunal`):** O modelo **GNN + Taint Analysis em SIMT (`cuda-oxide`)** substitui os **18 especialistas `passDefault`** (`internal/jev/engine.go:164`), mas opera em **conjunção estrita (OR lógico de bloqueio)** com os 7 especialistas determinísticos de segurança. Nenhum veredito de ML pode converter um `BLOCK` determinístico em `APPROVE`.
- **Por quê (Segurança Cláusula Pétrea):** Garante ganho real de Recall estrutural (capturando vulnerabilidades multi-função e quebras de arquitetura hexagonal que regex lineares perdem) com **risco zero de regressão em segurança**.

---

## Registro de Votação — Rodada 2 e Confirmação Rodada 3

| Arquiteto | Papel | Voto R2 | Condição Incorporada na `[v2]` | Confirmação R3 |
|---|---|---|---|---|
| **Arquiteto A** | `arquiteto-minimalista` | **APROVO (4/4)** | Workspace único em `templates/stacks/rust-kumo-cuda-labs/` | **SEM DÚVIDAS** |
| **Arquiteto B** | `arquiteto-performance` | **APROVO (4/4)** | Warm-up separado + $N=10$ repetições + guarda ADR-017 | **SEM DÚVIDAS** |
| **Arquiteto C** | `engenheiro-seguranca` | **APROVO (4/4)** | `#[forbid(unsafe_code)]` + OR lógico no JEV + anti-*leakage* | **SEM DÚVIDAS** |
| **Arquiteto D** | `engenheiro-devops` | **APROVO (4/4)** | Dual-Transport JSON-RPC 2.0 + Arena `.kdg` + fallback Go C0 | **SEM DÚVIDAS** |
| **Arquiteto E** | `engenheiro-especificacao` | **APROVO (4/4)** | Tokenização 5D RelGT + gramática PQL completa + ICL | **SEM DÚVIDAS** |
| **Arquiteto F** | `rust-pro` (`cuda-rust`) | **APROVO (4/4)** | `cutile-rs` (denso) + `cuda-oxide` (esparso) + emissão PTX | **SEM DÚVIDAS** |
