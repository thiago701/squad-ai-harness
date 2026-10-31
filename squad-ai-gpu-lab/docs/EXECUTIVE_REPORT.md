# Relatório F — Relatório Executivo para Decisão Arquitetural (`EXECUTIVE_REPORT.md`)

> **Destinatário:** Liderança Técnica / Arquiteto Principal da SquadAI Harness
> **Laboratório:** `squad-ai-gpu-lab` · **Status da Arquitetura Principal Go:** **100% Intocada** (`.\squad-harness.exe gate` verde `6/6 PASS`)
> **Princípio de Arbitragem:** **P1‑Simplicidade > P2‑Performance > P3‑CustoBaixo** (Segurança = cláusula pétrea bloqueante).

---

## 1. Sumário Executivo da Investigação

A comissão multidisciplinar auditou integralmente o código-fonte do **SquadAI Harness v0.8.0** em Go 1.24.3, investigou as tecnologias **NVIDIA Kumo (`KumoRFM`/`RelGT`/`PQL`)** e **NVIDIA CUDA Rust (`NVIDIA/cuda-rust` + `nvcuda.dll`)**, e construiu um laboratório experimental completo em Rust (`templates/squad-ai-gpu-lab/`) contendo **6 crates fundacionais**, **10 POCs executáveis**, **cliente Go MCP** e **4 kernels PTX nativos (`.version 6.5 .target sm_50`)** que executaram fisicamente na GPU local **`NVIDIA GeForce MX110 (2 GiB VRAM)`**.

### Veredito Central da Comissão:
1. **A arquitetura principal em Go 1.24.3 NÃO deve ser migrada para Rust.** O monólito Go atual é rápido (`< 5 ms` de boot), seguro e livre de dependências externas.
2. **Os maiores ganhos de inteligência e qualidade vêm dos modelos relacionais temporais estilo Kumo (`PQL` + `RelGT` 5D + `ICL` + grafo CSR binário `.kdg`) executados nativamente em Rust (`POC-001`, `POC-002`, `POC-007`)**, que elevam o `F1` de `0.00–0.57` para **`0.94–1.00`** em `< 700 µs` sem depender do container proprietário NVIDIA NIM (que é inviável em GPUs de 2 GiB).
3. **Na GPU `GeForce MX110 (sm_50)`, o ganho real de hardware existe APENAS quando os dados permanecem residentes na VRAM (`ResidentVramArena`) e a carga ultrapassa o ponto de cruzamento (`N >= 2.048` vetores em `POC-006` ou matrizes $\ge 128\times 128$ em `POC-008`)**, alcançando **até 4,81× de speedup real fim a fim (incluindo IPC MCP) em recuperação semântica `XL` (`32.768×128`)** e **até 7,59× sobre Rust CPU / 21,05× sobre Go em multiplicação matricial `512×512`**.
4. **Duas hipóteses de uso de GPU/Kumo foram cientificamente refutadas (`POC-005` e `POC-009`):** para predição de RAM do escalonador IMO e predição de sucesso de agentes, regressores tabulares simples na CPU (`Ridge + Quantil P95` e `Empirical Bayes`) empatam em precisão (`F1 = 1.00`, `OOM = 0%`) e rodam em **`13–68 µs`**, tornando GPU ou GNN desnecessários.

---

## 2. POCs com Maior Valor Comprovado (Recomendadas para Evolução Controlada)

| Prioridade | POC / Componente | Ganho Mensurado Comprovado | Como Integrar no Futuro (Sem Quebrar o Monólito Go) |
|---:|---|---|---|
| **P1 (Imediato — Correção em Go Puro)** | **Descobertas de `POC-005` (`GAP-08`) e `GAP-01`** | Elimina `100%` das sub-alocações OOM do escalonador IMO (`MAE` cai de `182,1 MB` para `8,0 MB` em `13,6 µs`) e corrige a cegueira de GPU em `DetectWorkstation`. | **Não exige nem mesmo chamar Rust em produção:** basta corrigir a linha [`scheduler.go:204`](file:///c:/Users/tgg_/ClaudeProjects/squad-ai-harness/internal/scheduler/scheduler.go#L204) para gravar o RSS real do Job Object + buffer quantílico P95 direto em Go! |
| **P2 (Curto Prazo — MCP Sidecar Persistente)** | **`POC-006` (Semantic Retrieval Accelerator c/ VRAM Residente) + Correção do `GAP-02` (`Keep-Alive`)** | Eleva `Recall@3` de `0.44` para **`0.96`** sobre as 106 skills + GraphRAG e acelera corpora `Large`/`XL` em **2,19× a 4,81× fim a fim** mantendo o corpus na VRAM da `GeForce MX110`. | Substituir o spawn por chamada em [`rustbridge.go`](file:///c:/Users/tgg_/ClaudeProjects/squad-ai-harness/internal/compute/rustbridge.go) por conexão persistente `Keep-Alive` ao `mcp-server` do laboratório, com despacho híbrido automático (`N < 2048` na CPU Rust em `19 µs`; `N >= 2048` na GPU Residente). |
| **P3 (Médio Prazo — Inteligência Preditiva Relacional)** | **`POC-002` (Dependency Impact `.kdg`) + `POC-001` (Predictive Failure `RelGT`) + `POC-007` (Predictive Quality)** | Elevam `F1` de impacto de contrato de `0.57` para **`1.00`** (payload `.kdg` **12,86× menor** que JSON), `F1` de falhas emergentes de `0.00` para **`0.94`** (`Brier -82,9%`) e `F1` de regressão de PR de `0.00` (`passDefault`) para **`1.00`**. | Expor como ferramentas MCP opcionais (`lab_poc_001`, `lab_poc_002`, `lab_poc_007`) acionadas nos gates `/squad-quality-gate` e `cultivator` quando o binário do laboratório estiver presente. |

---

## 3. POCs Que NÃO Compensam Integrar como Módulos GPU/Kumo (Descartadas ou Restritas)

1. **`POC-005` (`poc-005-intelligent-scheduler`) como módulo GPU/Kumo — DESCARTADO PARA GPU/KUMO:**
   - *Motivo:* A fórmula `Ridge + Quantil P95` resolve o problema em `13,6 µs` na CPU. Deve ser portada como 15 linhas de Go nativo em `internal/scheduler/scheduler.go`, sem IPC nem GPU.
2. **`POC-009` (`poc-009-agent-perf-predictor`) como módulo GNN/GPU — DESCARTADO PARA GPU/KUMO:**
   - *Motivo:* O estimador `Empirical Bayes (Beta-Binomial)` na CPU atinge exatamente o mesmo `F1 = 1.0000` (`Brier = 0.0190`) em `68,1 µs`. Portar o estimador Beta-Binomial direto em `internal/cognitive/router/router.go`.
3. **`POC-004` (`poc-004-cognitive-graph-accel`) em GPU para grafos pequenos ($< 16.384$ nós) — RESTRITO A GRAFOS GIGANTES:**
   - *Motivo:* Para o SEKG típico de um repositório ($< 2.048$ nós), o PageRank CSR em CPU (`1,45 ms` em Go / `1,51 ms` em Rust) é 2× mais rápido que alocar e transferir para a `GeForce MX110` (`3,12 ms`).
4. **Container Oficial NVIDIA NIM (`nvcr.io/nvidia/sdgm/kumo-relational`) na estação local — INVIÁVEL:**
   - *Motivo:* Exige GPUs Datacenter (`A100`/`H100`/`L40S` com 24–80 GiB VRAM) e stack Python/Docker pesada, incompatível com `GeForce MX110 (2 GiB VRAM, sm_50)`.

---

## 4. Riscos Técnicos, Custos e Governança (`gopurity.go` & `ADR-017`)

| Risco Identificado | Severidade | Mitigação Implementada no Laboratório |
|---|---|---|
| **Violação da trava de linguagem exclusiva Go (`internal/gates/gopurity.go`)** | 🔴 Alta (Bloqueante no Gate) | Todo o código Rust (`.rs`, `Cargo.toml`) foi isolado em `templates/squad-ai-gpu-lab/` (diretório oficialmente isento para catálogos multi-stack), mantendo `.\squad-harness.exe gate` **100% VERDE (`6/6 PASS`)**. |
| **Exaustão de VRAM na `GeForce MX110 (2048 MiB)` causando travamento do Windows 11 WDDM** | 🔴 Alta | `crates/gpu-runtime` impõe o guardrail `ADR-017`: reserva `1280 MiB` para o SO e limita a `ResidentVramArena` a `768 MiB`, com fallback transparente para `cpu-baselines` se `cuMemAlloc_v2` recusar alocação. |
| **Latência de Cold Start CUDA (`~882 ms`) e `CreateProcessW` (`~45 ms`)** | 🟡 Média | O servidor `mcp-server` mantém o `CudaContext` e os slots de VRAM residentes vivos entre chamadas via Loopback TCP Keep-Alive (`194,3 µs`). |
| **Dependência de compilador `nightly` (`cuda-oxide` / `cutile-rs`)** | 🟡 Média | Evitada: todos os 18 crates do laboratório compilam em **Rust `stable 1.99.1` 100% offline** carregando kernels PTX `.version 6.5 .target sm_50` via FFI direta em `nvcuda.dll`. |

---

## 5. Roadmap Gradual Recomendado e Decisões Humanas Pendentes (GATE 1)

### Fase 1 — Ganhos Imediatos em Go Puro (Zero Risco, Zero Dependência Nova)
- [ ] **Decisão Humana 1:** Autorizar a correção de 15 linhas em `internal/scheduler/scheduler.go:204` (`GAP-08`) para ler o RSS real do Job Object e aplicar o buffer quantílico P95 validado na `POC-005`?
- [ ] **Decisão Humana 2:** Autorizar a substituição dos 9 stubs `passDefault` em `internal/jev/engine.go` pelas fórmulas relacionais leves validadas na `POC-007` e `POC-009`?

### Fase 2 — Integração do Coprocessador MCP Persistente (`Keep-Alive` + `.kdg`)
- [ ] **Decisão Humana 3:** Autorizar a atualização de `internal/compute/rustbridge.go` (`GAP-02`) para reutilizar uma conexão TCP Keep-Alive persistente com o servidor MCP do `squad-ai-gpu-lab`?
- [ ] **Decisão Humana 4:** Autorizar a ativação das tools MCP `lab_poc_006_semantic_retrieval` (com VRAM residente para $N \ge 2.048$), `lab_poc_002_dependency_impact` (`.kdg`) e `lab_poc_001_predictive_failure` (`RelGT` + `PQL`) como aceleradores opcionais de Camada C1?
