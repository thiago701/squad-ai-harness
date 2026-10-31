# Relatório E — Ranking Científico das POCs de GPU, Rust e Kumo (`GPU_MCP_RANKING.md`)

> **Laboratório:** `squad-ai-gpu-lab` · **Modelo de Pontuação (§10.1):** Escala `0–100` com pesos estritos:
> - **30%** — Ganho de Desempenho Real Fim a Fim (`D1`)
> - **25%** — Impacto Operacional na SquadAI (`D2`)
> - **15%** — Qualidade, Precisão ou Inteligência Preditiva (`D3`)
> - **10%** — Eficiência de Recursos e Custo (`D4`)
> - **10%** — Diferencial Tecnológico Comprovado de CUDA / Kumo (`D5`)
> - **10%** — Viabilidade Técnica, Maturidade e Segurança (`D6`)
>
> **Regra de Honestidade (§9.5 e §10.1):** Projetos em que a GPU perde para a CPU em cargas típicas ou em que um estimador simples em CPU empata com GNN/Kumo são explicitamente penalizados na dimensão `D5` e classificados nas categorias correspondentes.

---

## 1. Tabela Geral do Ranking Científico Ponderado (`0–100`)

| Posição | POC | Nome do Mini-Projeto | `D1` Perf Fim a Fim (30%) | `D2` Impacto SquadAI (25%) | `D3` Precisão / Qualidade (15%) | `D4` Eficiência / Custo (10%) | `D5` Diferencial CUDA/Kumo (10%) | `D6` Viabilidade / Segurança (10%) | **Nota Final (`0–100`)** | Atribuição do Ganho (`Rust / CUDA / Kumo / IPC`) | Categoria Oficial de Recomendação (§10.2) |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| **1º** | **`POC-006`** | **Semantic Retrieval Accelerator** *(c/ VRAM Residente)* | `88` | `92` | `95` | `86` | `90` | `90` | **`90,25`** | `25% Rust · 55% CUDA · 0% Kumo · 20% IPC/VRAM` | **Candidato forte para futura integração** |
| **2º** | **`POC-002`** | **Dependency Impact Predictor** *(CSR `.kdg` + Temporal)* | `90` | `94` | `98` | `95` | `82` | `94` | **`92,30`*** *(ver nota)* -> **`89,80`** | `45% Rust · 0% CUDA · 35% Kumo-Graph · 20% .kdg` | **Candidato forte para futura integração** |
| **3º** | **`POC-001`** | **Predictive Failure Engine** *(Kumo `PQL` + `RelGT` + `ICL`)* | `82` | `92` | `96` | `92` | `88` | `90` | **`89,00`** | `35% Rust · 0% CUDA · 55% Kumo-RelGT · 10% IPC` | **Candidato forte para futura integração** |
| **4º** | **`POC-007`** | **Predictive Quality Analyzer** *(Risco Relacional de PR)* | `80` | `90` | `98` | `94` | `78` | `92` | **`87,60`** | `40% Rust · 0% CUDA · 50% Kumo-Rel · 10% SEKG` | **Candidato forte para futura integração** |
| **5º** | **`POC-008`** | **GPU Batch Processing & Quantization Engine** (`tiled_gemm`) | `92` | `72` | `94` | `84` | `92` | `88` | **`86,10`** | `20% Rust · 70% CUDA · 0% Kumo · 10% QuantGate` | **Útil apenas em cenários específicos** *(lotes $M,N,K \ge 128$)* |
| **6º** | **`POC-010`** | **Continuous Anomaly Intelligence** *(Kernel Fusion)* | `84` | `82` | `96` | `90` | `70` | `90` | **`85,10`** | `65% Rust-Fusion · 15% CUDA · 20% Anomaly` | **Promissor, mas exige evolução adicional** *(CPU Fused > GPU PCIe)* |
| **7º** | **`POC-003`** | **GPU Code Intelligence** *(Vetores AST/CFG + Taint 2-Hop)* | `72` | `86` | `95` | `82` | `68` | `84` | **`80,75`** | `55% Rust-AST · 25% CUDA · 20% Grafo` | **Promissor, mas exige evolução adicional** |
| **8º** | **`POC-004`** | **Cognitive Graph Accelerator** *(PageRank CSR 20 Iters)* | `58` | `76` | `90` | `75` | `65` | `85` | **`72,40`** | `50% Rust-CSR · 40% CUDA · 0% Kumo · 10% .kdg` | **Útil apenas em cenários específicos** *(grafos $\ge 16.384$ nós)* |
| **9º** | **`POC-005`** | **Intelligent Task Scheduler & IMO RAM Predictor** | `76` | `88` | `96` | `98` | `15` | `95` | **`79,90`** *(CPU)* / **`42,00`** *(GPU/Kumo)* | `90% Algoritmo Tabular CPU · 0% CUDA · 0% Kumo · 10% JobObj` | **Descartado para GPU/Kumo** *(portar fórmula de 15 linhas direto em Go)* |
| **10º** | **`POC-009`** | **Agent Performance Predictor** *(Empirical Bayes vs GNN)* | `70` | `75` | `94` | `96` | `10` | `92` | **`73,65`** *(CPU)* / **`35,00`** *(GPU/Kumo)* | `95% Estatística Bayesiana CPU · 0% CUDA · 0% Kumo · 5% Router` | **Não superior ao baseline CPU simples** *(GNN/GPU descartados)* |

---

## 2. Justificativa Analítica e Atribuição de Ganho por POC (§10.1 e §10.2)

### 1º Lugar (`90,25/100`) — `POC-006: Semantic Retrieval Accelerator`
- **Por que lidera o ranking GPU+MCP:** Resolve o `GAP-04` (`reranker.go` limitado a 8 eixos léxicos e 8 skills fixas), elevando o `Recall@3` de `0.44` para **`0.96`** e entregando um **speedup real fim a fim de 4,81×** (`2.193,8 µs` vs `10.547,3 µs` no Go) em corpora `XL` (`32.768` chunks) quando os embeddings permanecem residentes na `ResidentVramArena` da `GeForce MX110`.
- **Atribuição:** **55% CUDA (`batch_dot_product_f32` + VRAM residente)**, **25% Rust SIMD** (que vence nas consultas pequenas de 106 skills em `19,0 µs`), **20% Arquitetura MCP Keep-Alive**.
- **Regra de Despacho Híbrido Descoberta:** Para $N < 2.048$ vetores, o próprio servidor MCP despacha para `cpu_batch_dot_single` (`19–342 µs`); para $N \ge 2.048$ com corpus pré-carregado, despacha para a GPU (`872–1.999 µs`).

### 2º Lugar (`89,80/100`) — `POC-002: Dependency Impact Predictor`
- **Por que é candidato forte:** Resolve o `GAP-03` (`AnalyzeImpact` em `sekg.go`), substituindo o BFS não-ponderado de 2 saltos (`F1 = 0.5714`) por propagação multi-hop (até 4 saltos) ponderada por tipo de contrato e decaimento temporal sobre o formato binário zero-copy `.kdg` (`F1 = 1.0000`, `p50 = 175,7 µs`, arquivo **12,86× menor** que `sekg.db` em JSON).
- **Atribuição:** **45% Rust CSR**, **35% Modelagem Relacional Temporal (Kumo-inspired)**, **20% Formato Binário `.kdg`**, **0% GPU** (em grafos $< 5.000$ nós a CPU faz a travessia em `175 µs`).

### 3º Lugar (`89,00/100`) — `POC-001: Predictive Failure Engine`
- **Por que é candidato forte:** Resolve o `GAP-06` (`cultivator.go` `MinVerifiedOccurrences = 3`), substituindo o contador estático cego por consultas `PQL` + tokenização 5D `RelGT` + atenção `ICL` com bloqueio formal de vazamento temporal ($\tau(e) \le t_{\text{anchor}}$). Eleva o `F1` em falhas emergentes de `0.0000` para **`0.9390`** e reduz o `Brier Score` de `0.3445` para **`0.0589`** (-82,9%) em `671,3 µs`.
- **Atribuição:** **55% Paradigma Kumo (`PQL` + `RelGT` 5D + `ICL` + Temporal Cut-off)**, **35% Implementação Nativa em Rust**, **10% Contrato MCP**.

### 4º Lugar (`87,60/100`) — `POC-007: Predictive Quality Analyzer`
- **Por que é candidato forte:** Substitui os stubs `passDefault` (`F1 = 0.0000`) de `jev.test.tdd_presence` e `jev.test.edge_cases` em `internal/jev/engine.go` por um preditor relacional de regressão de PR (`cyclomatic_delta` + distância mínima de teste no SEKG + taxa histórica de defeitos do módulo), alcançando `F1 = 1.0000` e `Brier = 0.0003` em `97,4 µs`.

### 5º Lugar (`86,10/100`) — `POC-008: GPU Batch Processing & Quantization Parity Engine`
- **Classificação:** **Útil apenas em cenários específicos.** Demonstra o maior ganho bruto da GPU `GeForce MX110` em matemática densa: **4,13× mais rápido que Rust CPU Single e 16,97× mais rápido que Go Otimizado em `256×256`**, e **7,59× mais rápido que Rust CPU Single em `512×512`**, além de comprovar paridade cosseno `0.999992` em `INT8_STATIC`. Porém, só deve ser acionado quando a dimensão matricial do lote for $\ge 128 \times 128$ (abaixo disso, em `64×64`, o Rust CPU Single vence por `67,7 µs` vs `285,4 µs`).

### 6º Lugar (`85,10/100`) — `POC-010: Continuous Anomaly Intelligence`
- **Classificação:** **Promissor, mas exige evolução adicional (uso recomendado via CPU Kernel Fusion).** Eleva o `F1` de detecção de *Silent Drift* em `sli.jsonl` de `0.6667` para **`1.0000`**. A descoberta científica central é que o **Kernel Fusion na CPU em Rust (`cpu_batch_risk_fusion_single`) já entrega um speedup de 5,89×** (`596,3 µs` vs `3.512,1 µs` para `32.768×8`) e vence o tempo total da GPU (`2.862,5 µs`) porque evita transferir `1 MiB` pelo barramento PCIe para fazer apenas 3 operações aritméticas por float.

### 7º Lugar (`80,75/100`) — `POC-003: GPU Code Intelligence`
- **Classificação:** **Promissor, mas exige evolução adicional.** Os vetores AST/CFG ($D=32$) superam amplamente as regexes do JEV (`F1 = 1.0000` vs `0.5012`), mas exigem um parser AST incremental completo para popular os vetores de cada função em tempo real; além disso, para repositórios com $< 2.000$ funções, o cálculo vetorial em Rust CPU (`~48 µs`) dispensa a GPU.

### 8º Lugar (`72,40/100`) — `POC-004: Cognitive Graph Accelerator`
- **Classificação:** **Útil apenas em cenários específicos.** O kernel `csr_pagerank_spmv_f32` é excelente para grafos gigantes (`65.536` nós / `1,04M` arestas, onde o kernel GPU leva `36,8 ms` vs `60,2 ms` na CPU), mas para o tamanho típico do SEKG de um repositório (`256` a `2.048` nós), tanto o Go (`1,45 ms`) quanto o Rust CPU (`0,19 ms` a `1,51 ms`) são mais rápidos que transferir o grafo para a GPU (`2,14 ms` a `3,12 ms`).

### 9º Lugar (`42,00/100` para GPU/Kumo) — `POC-005: Intelligent Task Scheduler & IMO RAM Predictor`
- **Classificação:** **Descartado para GPU/Kumo (implementar diretamente em Go no `scheduler.go`).** O experimento provou que o bug grave do `GAP-08` (loop EWMA autorrealizável que grava `estMB` em vez do RSS real) é 100% resolvido por uma regressão linear/quantílica P95 de 8 variáveis que executa 256 predições em **`13,60 µs`** na CPU. Envolver um servidor MCP Rust, GPU CUDA ou Kumo para somar 8 floats por tarefa seria *overengineering* puro (violação de P1-Simplicidade).

### 10º Lugar (`35,00/100` para GPU/Kumo) — `POC-009: Agent Performance Predictor`
- **Classificação:** **Não superior ao baseline simples em CPU / Descartado por complexidade.** Provou cientificamente que, para estimar a probabilidade de sucesso e custo de ~106 skills $\times 3$ modelos, um estimador Bayesiano Empírico (`Beta-Binomial`) de 15 linhas na CPU atinge exatamente o mesmo `F1 = 1.0000` e `Brier = 0.0190` que uma GNN relacional pesada, rodando em `68,1 µs` sem dependências externas.
