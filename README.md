<div align="center">
  <img src="assets/logo-squad-ai-harness.jpg" alt="SquadAI Harness Banner" width="100%" />

  # SquadAI Harness (`squad-ai-harness`) · v0.8.0

  **Gated Autonomous Software Engineering · Runtime Nativo em Go 1.24.3 (`CGO_ENABLED=0`)**

  [![Go Version](https://img.shields.io/badge/Go-1.24.3%20Exclusive-00ADD8?style=flat-square&logo=go)](go.mod)
  [![Dependencies](https://img.shields.io/badge/Dependencies-Zero%20External-success?style=flat-square)](go.mod)
  [![Canonical Skills](https://img.shields.io/badge/Skills-106%20Canonical-0EA5E9?style=flat-square)](governance/registry/registry.json)
  [![JEV Tribunal](https://img.shields.io/badge/JEV%20Specialists-25%20Deterministic-8B5CF6?style=flat-square)](internal/jev/)
  [![License](https://img.shields.io/badge/License-Apache%202.0-blue?style=flat-square)](LICENSE)
</div>

---

## 🎯 Visão Geral

O **SquadAI Harness (`squad-ai-harness`)** é um **orquestrador de engenharia de software autônomo**, regido pela regra **"autônomo na execução, *gated* na decisão"**: investiga, planeja, escreve código, roda testes e revisa sozinho, mas **exige aprovação humana nos marcos críticos (`GATE 1` e `GATE 2`)**.

Todo o motor cognitivo, grafo de conhecimento, tribunal de revisão, instalador multi-agente, servidor MCP, telemetria e interface web vivem em **um único binário estático em Go 1.24.3 (`CGO_ENABLED=0`)**, com **zero dependências externas** no `go.mod`:

| Pilar | Como Funciona | Ganho Direto |
| :--- | :--- | :--- |
| **106 Skills Auditáveis** | Especialistas em `skills/*/SKILL.md` (Arquitetura, AWS, Go, Java 25, Python, Rust, .NET, Angular, Bancos, QA e Segurança). | Time virtual sob medida acionado sob demanda. |
| **Cérebro Cognitivo (`< 10 ms`)** | Preflight de 10 estágios + `HybridRouter` (BM25 + Vetorial) + Grafo `SEKG` (`CSR` + Comunidades de Leiden). | **Reduz 60%–75% dos tokens** enviados ao LLM. |
| **Tribunal JEV (`~518 µs`)** | 25 especialistas determinísticos em paralelo + *Critic/Judge* sob $\text{Segurança} \gg \text{P1 Simplicidade} > \text{P2 Performance} > \text{P3 Custo}$. | Revisão instantânea a **`$ 0.00`** antes do commit. |
| **Multi-Estação & Offline** | Roteador `C0` (Go CPU) / `C1` (NPU/iGPU/GPU local) / `C2` (LLM) + Telemetria Executiva `QUID` em dólar (`$`). | Opera 100% offline sem bloqueio de firewall. |

---

## 📊 Performance Medida (Legado Python vs. Runtime Go v0.8.0)

Medições auditáveis ([`docs/BENCHMARKS-V080.md`](docs/BENCHMARKS-V080.md) · [`docs/RELATORIO-CIENTIFICO-V080.md`](docs/RELATORIO-CIENTIFICO-V080.md)):

| Operação | Legado (Python 3.13) | Go Nativo (`v0.8.0`) | Ganho |
| :--- | :---: | :---: | :---: |
| **Unified Quality Gate (`gate`)** | `21.960,00 ms` | **`288,12 ms`** | **76,2× mais rápido** (`-98,7%`) |
| **Preflight Cognitivo Camada 0 (10 estágios)** | `1.391,00 ms` | **`9,46 ms`** | **147,0× mais rápido** (`-99,3%`) |
| **Tribunal JEV (25 Especialistas + Juiz)** | `485,00 ms` | **`0,518 ms` (`518 µs`)** | **936,3× mais rápido** |
| **Hot-Path Hook (`PreToolUse` Security Guard)** | `185,00 ms` | **`0,524 ms` (`524 µs`)** | **353,1× mais rápido** |
| **GraphRAG (`Local` / `Global` / `DRIFT`)** | `312,00 ms` | **`526 µs`** | **> 590× mais rápido** |
| **Consumo de Memória RAM (Heap Ativo)** | `~421,80 MiB` | **`3,20 MiB`** | **131,8× menos RAM** (`-99,2%`) |

---

## 🧠 Arquitetura do Cérebro Cognitivo (`Cognitive Brain`)

<div align="center">
  <img src="assets/diagram-cognitive-brain.svg" alt="Arquitetura de Alto Nível do Cérebro Cognitivo — SquadAI Harness v0.8.0" width="100%" />
</div>

### 📖 Legendas Didáticas do Cérebro Cognitivo

| Bloco | Papel Didático | Como Opera (`Go 1.24.3`) | Benefício |
| :--- | :--- | :--- | :--- |
| **1. Percepção** | **Porta Sensorial** | Recebe tarefas de engenharia ou gatilhos executivos (`"gere relatorio de uso"`) via CLI, Hook ou MCP. | Resposta imediata e **100% offline**. |
| **2. Camada 0** | **Triagem Pré-Frontal** | Roda 10 estágios em `< 10 ms`: mede o raio de impacto, trava o orçamento (`CTX-1..3`) e filtra as Top-K skills. | **Economiza 60%–75% dos tokens** de LLM. |
| **3. Grafo `SEKG`** | **Mapa Relacional Vivo** | Mapeia em RAM (`CSR` + Leiden) *quem chama quem* e *qual teste cobre qual módulo* (`Local`, `Global`, `DRIFT`). | Zero alucinação de acoplamento em **`~526 µs`** (`$ 0`). |
| **4. Memória `M0–M3`** | **Imunidade Anti-Alucinação** | Separa suposições em **Quarentena (`HYPOTHESIS`, 7d)** de fatos **Verificados (`VERIFIED` por teste + gate)**. | Aprende entre sessões sem contaminar a memória. |
| **5. Tribunal `JEV`** | **Conselho de 25 Juízes** | Avalia segurança, arquitetura, banco e código limpo em paralelo sob $\text{Segurança} \gg \text{P1} > \text{P2} > \text{P3}$. | Revisão determinística em `~518 µs` a **`$ 0`**. |
| **6. Rotas & `QUID`** | **Despachante & Auditor** | Prioriza `C0` (CPU Go) e `C1` (NPU/GPU local) antes de `C2` (LLM), gravando horas e economia em `$` sob o `QUID`. | Visibilidade executiva em ASCII com zero overhead. |

---

## 🔄 Pipeline Gated (`GATE 1` / `GATE 2`) & Governança (`DecidirEntrega`)

<div align="center">
  <img src="assets/diagram-pipeline-gated.svg" alt="Pipeline Gated End-to-End (N0-N3), Governança DecidirEntrega e Resiliência em 3 Camadas" width="100%" />
</div>

| Tamanho (*Blast Radius*) | Escopo Detectado | Cerimônia Acionada | Autonomia |
| :--- | :--- | :--- | :--- |
| **`trivial`** (`CTX-1 · 2k tok`) | 1 arquivo, sem nova dependência | **1 especialista direto**, sem pipeline completo. | `N0` → `N2` |
| **`small`** (`CTX-2 · 6k tok`) | Poucos arquivos no mesmo pacote | **1–2 especialistas** + validação de testes. | `N0/N1` → `N2` → `N3` |
| **`standard`** (`CTX-3 · 12k tok`) | Múltiplos pacotes ou contratos | **Pipeline completo** com paradas no `GATE 1` e `GATE 2`. | Trava em `N1` até aprovar `GATE 1` |
| **`large`** (`CTX-3 · 12k tok`) | Nova arquitetura, schema ou dependência | **Comissão de Arquitetos (3 rodadas)** + Spec + **4 Gates de Entrega** (`env-infra`, `db-schema`, `config-compat`, `interop`). | Exige `GATE 1` + `GATE 2` (`PASS`) |

---

## 🗺️ Mapa das 106 Skills por Domínio ([`governance/registry/registry.json`](governance/registry/registry.json))

| Domínio | Skills de Referência (`skills/*/SKILL.md`) | Modelo (`P3`) | Escopo Principal |
| :--- | :--- | :---: | :--- |
| **1. Orquestração** | `squad-ai`, `squad-pipeline`, `comissao-arquitetos`, `repo-ai-first-multiagente`, `batman` | `opus` | Sistemas completos, refino em 3 rodadas e automação noturna. |
| **2. Especificação & DDD** | `engenheiro-especificacao`, `diagramador`, `sandeco-loop`, `spec-code-drift-detector` | `sonnet` | Requisitos BDD/Gherkin, EventStorming, diagramas C4/Mermaid e drift. |
| **3. Arquitetura & SLA** | `arquiteto-minimalista`, `engenheiro-clean-architect`, `arquiteto-performance`, `sonar-first-engineering` | `opus` | Combate a overengineering, Clean Architecture, SLA p95/p99 e Sonar. |
| **4. Cloud AWS** | `arquiteto-cloud-aws`, `aws-serverless-eda`, `orquestracao-step-functions`, `api-gateway-integracoes`, `analise-producao-aws` | `opus` | AWS Serverless/Enterprise, FinOps, ASL Step Functions e VTL. |
| **5. Backend & Runtimes** | `golang-pro`, `aws-lambda-go`, `java25-spring-boot`, `quarkus-java-aot`, `python-pro`, `rust-pro`, `dotnet-csharp-pro`, `nodejs-pro` | `sonnet` | Código idiomático, concorrência, GraalVM/AOT e memória RAM. |
| **6. Frontend & UI/UX** | `especialista-frontend`, `typescript-pro`, `angular-error-investigator`, `ui-ux-pro-max`, `validador-navegador` | `sonnet` | Angular 21+ Signals, TypeScript 7, design systems e browser E2E. |
| **7. Bancos & Streaming** | `especialista-banco`, `arquiteto-dados-streaming`, `localstack-dev` | `sonnet` | Modelagem DBML-first, SQL/NoSQL, *Expand-Contract*, Kafka/Kinesis. |
| **8. IA, GraphRAG & MCP** | `arquiteto-ia`, `ai-evaluation`, `mcp-builder`, `graphify`, `headroom`, `roteamento-modelo-adaptativo`, `resiliencia-agente` | `opus` | Agentes LLM, RAG, servidores MCP, LLMOps e Circuit Breaker 3 camadas. |
| **9. Qualidade & Caos** | `especialista-qualidade`, `estrategia-testes-aws`, `contrato-reverso`, `testes-carga-desempenho-aws`, `testes-resiliencia-caos-aws` | `sonnet` | TDD/BDD, Testcontainers, contrato reverso (CDC), k6 e caos (AWS FIS). |
| **10. Segurança & Obs** | `engenheiro-seguranca`, `auditoria-skill-externa`, `engenheiro-iac`, `logs-observabilidade`, `dd-apm`, `trace2local` | `opus` | **Automático** em diffs de auth/input/queries/secrets; Terraform e APM. |

---

## 🚀 Guia Rápido de Instalação e Uso

### 1. Compilar e Sincronizar as 106 Skills (100% Go Nativo)

```powershell
# Compilar o binário estático (Windows PowerShell)
$env:CGO_ENABLED="0"; go build -trimpath -ldflags="-s -w" -o squad-harness.exe ./cmd/squad-harness

# Detectar agentes locais (~/.claude, ~/.gemini/config, ~/.codex, ~/.dsh), sincronizar e verificar SHA-256
.\squad-harness.exe install detect
.\squad-harness.exe install
.\squad-harness.exe install verify
```

### 2. Comandos Principais

```powershell
.\squad-harness.exe version                                          # Identidade v0.8.0, Go 1.24.3 e RAM livre
.\squad-harness.exe compute                                          # Hardware da estação e rotas C0 / C1 / C2
.\squad-harness.exe gate                                             # Quality Gate completo em DAG concorrente
.\squad-harness.exe preflight "arquitetura aws step functions go"    # Preflight 10 estágios + HybridRouter + SEKG
.\squad-harness.exe sekg query "engenheiro-seguranca" local          # Busca no grafo SEKG (local | global | drift)
.\squad-harness.exe jev "func Handler() error { return nil }"        # Avalia código no Tribunal JEV (25 especialistas)
.\squad-harness.exe ui                                               # Abre o Control Center Web (http://127.0.0.1:9090)
.\squad-harness.exe report                                           # Relatório Executivo ASCII (Horas e Economia em $)
```

### 3. Como Gerar o Relatório Executivo de Uso (`report` / Gatilho Natural / `QUID` Offline)

O módulo [`internal/telemetry/`](internal/telemetry/) (`< 15 µs` de overhead) consolida os **últimos 3 meses** por mês e dia (**Horas Usando IA**, **Horas Economizadas `~7.1x`** e **Economia de Tokens em `$`**), com **Rodapé Consolidador (`Mês Atual × Total Acumulado`)** e **ID Quântico Universal (`QUID-SQ8-...`)** 100% offline:

```powershell
# 1. Via CLI direto
.\squad-harness.exe report

# 2. Via gatilho em linguagem natural
.\squad-harness.exe preflight "Squad ai, gere relatorio de uso"
.\squad-harness.exe preflight "Squad ai. me mostre seu relatorio"

# 3. Consulta pelo Gestor via ID Quântico Universal do repositório clonado (100% Offline, sem firewall)
.\squad-harness.exe report --quid QUID-SQ8-8552-C841-B36A-2F0F

# 4. Exportar em JSON ou listar todos os QUIDs registrados na estação
.\squad-harness.exe report --json
.\squad-harness.exe report --list-quids
```

- **Consulta via MCP (`stdio`) e HTTP Local/LAN**: tools `squad_usage_report` / `squad_resolve_quid` (resource `squad://telemetry/ascii`) e endpoint `http://127.0.0.1:9090/api/telemetry/ascii?quid=QUID-SQ8-...`.

```text
╠════════════════════════════════════════════════════════════════════════════════════════════════════╣
║ [5] RODAPÉ CONSOLIDADOR EM DESTAQUE — MÊS ATUAL (OUT/2026) X TOTAL ACUMULADO (3 MESES)             ║
╟────────────────────────────────────────────────────────────────────────────────────────────────────╢
║  ┌──────────────────────────────────────────────────────────────────────────────────────────────┐  ║
║  │ ★ HORAS USANDO IA (MÊS X TOTAL)    : 12.68h (12h40m) no mês  x  24.15h (24h09m) total (52.5%)│  ║
║  │ ★ HORAS ECONOMIZADAS (MÊS X TOTAL) : 76.27h (76h16m) no mês  x  146.65h (146h39m) total (7.1x│  ║
║  │ ★ TOKENS ECONOMIZADOS (MÊS X TOTAL): 5.674.100 tok no mês  x  10.995.800 tok total (51.6%)   │  ║
║  │ ★ ECONOMIA EM DÓLAR $ (MÊS X TOTAL): $ 85.11 no mês  x  $ 164.94 total acumulado (51.6%)     │  ║
║  └──────────────────────────────────────────────────────────────────────────────────────────────┘  ║
╚════════════════════════════════════════════════════════════════════════════════════════════════════╝
```

---

## 📂 Estrutura do Repositório & Segurança (`Go-Exclusive Lock`)

```text
squad-ai-harness/
├── assets/             # Identidade visual oficial (JPG + SVG)
├── cmd/squad-harness/  # CLI unificado (gate, preflight, sekg, jev, compute, install, report, ui, mcp, sync)
├── internal/           # Core Go: cognitive (harness/sekg/graphrag), jev, gates, compute, dag, installer, telemetry, ui
├── pkg/contracts/      # Contratos imutáveis (GateState, ProvenanceTag, ContextTier, Identidade v0.8.0)
├── skills/             # Catálogo canônico das 106 skills especializadas (SKILL.md)
├── governance/         # Políticas de autonomia (N0-N3), gates de entrega e registry gerado
└── security/           # Política de segurança, Linha de Defesa de Prompt e auditoria v0.8.0
```

- **Trava Exclusiva Go (`stage1.go_exclusive_lock`)**: bloqueia automaticamente (`Exit Code 2`) qualquer código ou manifesto de outra tecnologia (`.py`, `.js`, `.ts`, `.java`, `.rs`, `.cs`, `.ps1`, `.sh`, `package.json`, `pyproject.toml`) no fonte do harness ([`internal/gates/gopurity.go`](internal/gates/gopurity.go)).
- **Defesa em Profundidade**: zero dependências externas no `go.mod`, Linha de Defesa de Prompt validada nas 106 skills e `secretscan` nativo (14 classes de segredos). Consulte [`SECURITY.md`](SECURITY.md) e [`CONTRIBUTING.md`](CONTRIBUTING.md).

---

## 📄 Licença

Distribuído sob a licença **Apache 2.0** ([`LICENSE`](LICENSE)) · `30/10/2026` · [Thiago Gonçalo](https://www.linkedin.com/in/thiago-gon%C3%A7alo)
