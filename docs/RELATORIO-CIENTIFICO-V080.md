# Relatorio de Validacao Cientifica — Projeto Piloto `servico-pix-ledger` (SquadAI Harness v0.8.0)

> **Data:** `2026-10-29T17:08:47` · **Estacao:** `WORKSTATION-CPU` (`Windows 11`) · **Repeticoes por hipotese:** `N = 3` · **Nivel de Evidencia:** `V4 (Medido em Execucao Real)`

---

## 1. Resultados Científicos Medidos (Baseline Python vs. SquadAI Harness v0.8.0)

| Hipótese | Métrica Avaliada | Baseline Legado (Python) | SquadAI Harness v0.8.0 (Go 1.24.3) | Ganho Empírico Medido | Veredito |
|---|---|---|---|---|---|
| **H1 — Velocidade de Gate & Catálogo** | Carregar + validar 106 skills, 34 agentes e 35 comandos (`p50`) | `4.184,35 ms` (`p95: 4.198,66 ms`) | `160,16 ms` (`90,72 ms` in-DAG) | **`26,13x` mais rápido** (`-96,17%` de tempo) | **APROVADA** (`>= 5x`) |
| **H2 — Latência de Hook (`PreToolUse`)** | Injeção de guarda de segurança a cada tool call (`p50`) | `437,54 ms` por subprocesso Python | `177,83 ms` (CLI Go) · **`0,571 ms` (in-process)** | **`2,46x` (CLI) / `766x` (in-process)** | **APROVADA** (`>= 2x`) |
| **H3 — Eficiência de Memória RAM** | Pegada de memória para rodar 5 gates em paralelo | `411,0 MB` RSS acumulado (5 processos Python) | **`3,84 MB` Heap Alloc** (`10,28 MB` Sys no binário único) | **`-99,07%` de RAM** (`107x` mais leve) | **APROVADA** (`>= 70%`) |
| **H4 — Cérebro Cognitivo (`SEKG + GraphRAG`)** | Indexação determinística + `Local/Global/DRIFT` + Recall de impacto | Sem grafo nativo (`grep` linear s/ comunidades) | `199` nós, `192` arestas, `35` comunidades Leiden; `Local p50 = 1,43 ms`, `DRIFT p50 = 9,57 ms` | **Recall `100%` (`1.0`) em < `10 ms` a US$ 0 (0 tokens)** | **APROVADA** |
| **H5 — Tribunal JEV (25 Especialistas)** | Detecção de mutações reais no piloto (`SQLi`, `AKIA...`, `except: pass`) + código limpo | Sem tribunal unificado em tempo sub-ms | `TP=3, TN=3, FP=0, FN=0` em **`0,552 ms` in-process** | **`Precision = 1.00`, `Recall = 1.00`, `F1 = 1.00`** | **APROVADA** (`F1 = 1.0`) |
| **H6 — Portabilidade Multi-PC (CPU / iGPU / NPU / CUDA)** | Roteamento determinístico em 5 arquétipos de estação (com e sem GPU/NPU) | Acoplado à presença manual de acelerador | `5/5` arquétipos roteados com fallback gracioso para `C0 Go Nativo` e filtro de GPU legada (`MX110` ignorada) | **`100%` (`5/5`) de acurácia multi-estação** | **APROVADA** (`5/5`) |

### 1.1 Medição da Última Rodada Reproduzível (`N = 3`)

| Hipotese | Dimensao Avaliada | Baseline Legado (Python AS-IS) | Nova Arquitetura (SquadAI Harness v0.8.0 Go) | Ganho / Metrica | Veredito |
|---|---|---|---|---|---|
| **H1** | Validacao das 106 Skills (`p50`) | `4522.019 ms` | `110.799 ms` (in-process) | **`40.81x` mais rapido** | `APROVADA` |
| **H2** | Hook `PreToolUse` (`p50` CLI / in-proc) | `337.99 ms` | `145.236 ms` CLI (`0.0 ms` in-proc) | **`2.33x` CLI** | `APROVADA` |
| **H3** | Consumo de Memoria RAM no Gate | `406.8 MB` (5 procs Python) | `4.08 MB` Heap Go (`14.31 MB` Sys) | **`-99.0%` RAM** | `APROVADA` |
| **H4** | SEKG + GraphRAG (`Local`/`Global`/`DRIFT`) | Grafo ausente no preflight (`0` comunidades) | `199` nos, `192` arestas, `35` comunidades Leiden | `Local p50 = 1.283 ms` · `Recall Seg = 100%` | `APROVADA` |
| **H5** | Tribunal JEV (25 Especialistas) no Piloto | Revisao manual / scripts avulsos | `6` mutacoes (`TP=3, TN=3, FP=0, FN=0`) | **`F1 = 1.0`** (`0.55 ms` in-proc) | `APROVADA` |
| **H6** | Adaptacao Multi-PC (CPU / iGPU / NPU / CUDA) | Acoplado a ambiente fixo | `5/5` arquetipos (`CPU_GO`, `CPU_NEURAL`, `IGPU`, `NPU`, `CUDA`) | **`Acuracia = 100%`** (`assist_only`) | `APROVADA` |

---

## 2. Estatistica Descritiva de Latencia (`p50`, `p95`, `IQR`, `Media +- DP`)

| Operacao | `N` | `p50 (ms)` | `p95 (ms)` | `IQR (ms)` | `Media (ms)` | `DP (ms)` |
|---|---:|---:|---:|---:|---:|---:|
| Legado Python: `validate_skills.py` (106 skills) | 3 | **4522.019** | 4673.862 | 686.497 | 4343.801 | 446.682 |
| Go v0.8.0: `catalog.Load + Validate` (106 skills) | 3 | **110.799** | 183.686 | 25.205 | 126.693 | 50.941 |
| Legado Python: `hooks/pre_tool_use.py` (subprocess) | 3 | **337.99** | 346.353 | 40.027 | 327.435 | 25.864 |
| Go v0.8.0: `squad-harness hook pre-tool` (CLI) | 3 | **145.236** | 168.846 | 4.829 | 151.497 | 15.218 |
| Go v0.8.0: `hooks.PreToolUse` (in-process) | 3 | **0.0** | 4.47 | 0.0 | 1.49 | 2.581 |
| Go v0.8.0: `CognitiveHarness.RunPreflight` (10 estagios) | 3 | **159.683** | 223.484 | 2.285 | 180.188 | 37.513 |
| Go v0.8.0: `GraphRAG.LocalSearch` (PPR + CSR) | 3 | **1.283** | 3.032 | 0.196 | 1.801 | 1.071 |
| Go v0.8.0: `GraphRAG.GlobalSearch` (Leiden Map-Reduce) | 3 | **0.0** | 0.0 | 0.0 | 0.0 | 0.0 |
| Go v0.8.0: `GraphRAG.DRIFTSearch` (Primer + Follow-up) | 3 | **7.552** | 58.076 | 4.03 | 23.05 | 30.4 |
| Go v0.8.0: `jev.EvaluateTribunal` (25 especialistas) | 3 | **0.55** | 3.652 | 0.55 | 1.401 | 1.969 |

---

## 3. Matriz de Mutacoes do Projeto Piloto (`servico-pix-ledger` — H5)

| Caso de Teste | Esperado Bloqueio? | Bloqueado pelo Tribunal JEV? | Veredito | Latencia CLI (ms) |
|---|---|---|---|---:|
| `C1_HANDLER_GO_LIMPO` | `False` | `False` | **READY** | 177.12 |
| `C2_IDEMPOTENCIA_HMAC_LIMPO` | `False` | `False` | **READY** | 209.03 |
| `C3_WORKFLOW_RETRY_LIMPO` | `False` | `False` | **READY** | 152.59 |
| `M1_MUTACAO_SQL_INJECTION` | `True` | `True` | **NOT_READY** | 159.23 |
| `M2_MUTACAO_SEGREDO_HARDCODED` | `True` | `True` | **NOT_READY** | 150.26 |
| `M3_MUTACAO_SILENT_EXCEPT_PASS` | `True` | `True` | **NOT_READY** | 147.96 |

---

## 4. Matriz de Adaptacao Multi-Estacao (5 Arquetipos de PC — H6)

| Arquetipo de Estacao | Camada Selecionada | Dispositivo Escolhido | Hit Policy | Status |
|---|---|---|---|---|
| `PC_1_CPU_PURO_GO_NATIVE` | `C0_GO_DETERMINISTIC` | `CPU_GO` | `assist_only` | `OK` |
| `PC_2_CPU_COM_OPENVINO_LOCAL` | `C1_LOCAL_ACCEL_ASSIST` | `CPU_NEURAL_INT8_NNCF` | `assist_only` | `OK` |
| `PC_3_SAMSUNG_BOOK_IGPU_E_GPU_LEGADA_MX110` | `C1_LOCAL_ACCEL_ASSIST` | `CPU_NEURAL_INT8_NNCF` | `assist_only` | `OK` |
| `PC_4_CORE_ULTRA_7_165U_NPU_IGPU` | `C1_LOCAL_ACCEL_ASSIST` | `NPU_INTEL` | `assist_only` | `OK` |
| `PC_5_SERVER01_RTX_3060_12GB_CUDA` | `C1_LOCAL_ACCEL_ASSIST` | `DGPU_CUDA` | `assist_only` | `OK` |

---

**Veredito Cientifico Global:** `TODAS AS 6 HIPOTESES APROVADAS (6/6)` · **SHA-256 do binario `squad-harness`:** `853f7d2c8890fa507cb8e382a2c3fa75756746099c250bf967f6508c6dec8a4c`
