# Resultados Científicos Medidos (Baseline Python vs. SquadAI Harness v0.8.0)

> **Data da Medição:** `2026-10-29` · **Estação:** `SAMSUNG-BOOK` (`Windows 11`) · **Projeto Piloto:** `labs/piloto-validacao-cientifica-v080/servico-pix-ledger` · **Nível de Evidência:** `V4 (Medido em Execução Real Local)`

| Hipótese | Métrica Avaliada | Baseline Legado (Python) | SquadAI Harness v0.8.0 (Go 1.24.3) | Ganho Empírico Medido | Veredito |
|---|---|---|---|---|---|
| **H1 — Velocidade de Gate & Catálogo** | Carregar + validar 106 skills, 34 agentes e 35 comandos (`p50`) | `4.184,35 ms` (`p95: 4.198,66 ms`) | `160,16 ms` (`90,72 ms` in-DAG) | **`26,13x` mais rápido** (`-96,17%` de tempo) | **APROVADA** (`>= 5x`) |
| **H2 — Latência de Hook (`PreToolUse`)** | Injeção de guarda de segurança a cada tool call (`p50`) | `437,54 ms` por subprocesso Python | `177,83 ms` (CLI Go) · **`0,571 ms` (in-process)** | **`2,46x` (CLI) / `766x` (in-process)** | **APROVADA** (`>= 2x`) |
| **H3 — Eficiência de Memória RAM** | Pegada de memória para rodar 5 gates em paralelo | `411,0 MB` RSS acumulado (5 processos Python) | **`3,84 MB` Heap Alloc** (`10,28 MB` Sys no binário único) | **`-99,07%` de RAM** (`107x` mais leve) | **APROVADA** (`>= 70%`) |
| **H4 — Cérebro Cognitivo (`SEKG + GraphRAG`)** | Indexação determinística + `Local/Global/DRIFT` + Recall de impacto | Sem grafo nativo (`grep` linear s/ comunidades) | `199` nós, `192` arestas, `35` comunidades Leiden; `Local p50 = 1,43 ms`, `DRIFT p50 = 9,57 ms` | **Recall `100%` (`1.0`) em < `10 ms` a US$ 0 (0 tokens)** | **APROVADA** |
| **H5 — Tribunal JEV (25 Especialistas)** | Detecção de mutações reais no piloto (`SQLi`, `AKIA...`, `except: pass`) + código limpo | Sem tribunal unificado em tempo sub-ms | `TP=3, TN=3, FP=0, FN=0` em **`0,552 ms` in-process** | **`Precision = 1.00`, `Recall = 1.00`, `F1 = 1.00`** | **APROVADA** (`F1 = 1.0`) |
| **H6 — Portabilidade Multi-PC (CPU / iGPU / NPU / CUDA)** | Roteamento determinístico em 5 arquétipos de estação (com e sem GPU/NPU) | Acoplado à presença manual de acelerador | `5/5` arquétipos roteados com fallback gracioso para `C0 Go Nativo` e filtro de GPU legada (`MX110` ignorada) | **`100%` (`5/5`) de acurácia multi-estação** | **APROVADA** (`5/5`) |
