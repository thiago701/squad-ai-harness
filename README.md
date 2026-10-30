<div align="center">
  <img src="assets/logo-squad-ai-harness.jpg" alt="SquadAI Harness Banner" width="100%" />

  # SquadAI Harness (`squad-ai-harness`) · v0.8.0

  **Gated Autonomous Software Engineering · Runtime Nativo em Go 1.24.3 (`CGO_ENABLED=0`)**

  [![Go Version](https://img.shields.io/badge/Go-1.24.3-00ADD8?style=flat-square&logo=go)](go.mod)
  [![Dependencies](https://img.shields.io/badge/Dependencies-Zero%20External-success?style=flat-square)](go.mod)
  [![Canonical Skills](https://img.shields.io/badge/Skills-106%20Canonical-0EA5E9?style=flat-square)](governance/registry/registry.json)
  [![JEV Tribunal](https://img.shields.io/badge/JEV%20Specialists-25%20Deterministic-8B5CF6?style=flat-square)](internal/jev/)
  [![Security Policy](https://img.shields.io/badge/Security-Prompt%20Defense%20Verified-10B981?style=flat-square)](SECURITY.md)
  [![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)
</div>

---

## 🎯 Visão Geral

O **SquadAI Harness (`squad-ai-harness`)** é uma plataforma de engenharia de software autônoma e *gated* (**"autônoma na execução, gated na decisão"**) projetada para desenvolvedores e empresas.

Na versão **v0.8.0**, toda a infraestrutura de orquestração, validação, memória de grafo e governança foi consolidada em um **binário estático único em Go 1.24.3 (`CGO_ENABLED=0`)**, com **zero dependências externas** no `go.mod`, coordenando:

- **106 Skills Especializadas Auditáveis** (`skills/*/SKILL.md`) cobrindo arquitetura, AWS Serverless, Go, Java 25, Python 3.13+, Rust, .NET, TypeScript/Angular, bancos de dados, qualidade/TDD, segurança/OWASP e observabilidade.
- **Camada 0 `CognitiveHarness` (< 25 ms)**: 10 estágios determinísticos de preflight, roteamento híbrido BM25 + Vetorial 384-d e compressão cirúrgica de contexto antes de acionar qualquer LLM remoto.
- **Software Engineering Knowledge Graph (`SEKG` + `GraphRAG`)**: Grafo em memória representado em *Compressed Sparse Row* (`CSR`) com detecção determinística de comunidades de Leiden e três modos de busca (`LocalSearch`, `GlobalSearch` e `DRIFTSearch` em microssegundos).
- **Tribunal JEV de 25 Especialistas (`< 1 ms`)**: Avaliação concorrente determinística (custo US$ 0) com *Critic/Judge* anti-regressão sob a função de arbitragem imutável:
  $$\text{Segurança (inegociável)} \gg \text{P1 Simplicidade} > \text{P2 Performance} > \text{P3 Custo Baixo}$$
- **Cognitive Compute Router Multi-Estação (`C0` / `C1` / `C2`)**: Adapta-se automaticamente ao hardware de cada máquina (PC corporativo somente CPU, notebook com NPU Intel AI Boost, estação com iGPU Arc ou servidor com GPU NVIDIA RTX).

---

## 📊 Resultados Científicos Medidos (Baseline Legado vs. `squad-ai-harness` v0.8.0)

Medições empíricas auditáveis ([`docs/BENCHMARKS-V080.md`](docs/BENCHMARKS-V080.md) e [`docs/RELATORIO-CIENTIFICO-V080.md`](docs/RELATORIO-CIENTIFICO-V080.md)):

| Dimensão / Operação Medida | Baseline Anterior (Python 3.13) | SquadAI Harness v0.8.0 (Go 1.24.3) | Ganho Científico Medido |
| :--- | :---: | :---: | :---: |
| **Unified Quality Gate (`gate` completo)** | `21.960,00 ms` *(~22,0 s)* | **`288,12 ms`** *(5 nós DAG)* | **76,2× mais rápido** (`-98,7%` latência) |
| **Preflight Cognitivo Camada 0 (10 estágios)** | `1.391,00 ms` | **`9,46 ms`** | **147,0× mais rápido** (`-99,3%` latência) |
| **Carregamento + Validação das 106 Skills** | `640,00 ms` | **`9,46 ms`** | **67,6× mais rápido** |
| **Tribunal JEV (25 Especialistas + Critic/Judge)** | `485,00 ms` | **`0,518 ms` (`518 µs`)** | **936,3× mais rápido** |
| **Hot-Path Hook (`PreToolUse` Security Guard)** | `185,00 ms` | **`0,524 ms` (`524 µs`)** | **353,1× mais rápido** |
| **GraphRAG `LocalSearch` / `GlobalSearch` / `DRIFT`** | `312,00 ms` | **`526 µs` / `0 µs` / `526 µs`** | **> 590× mais rápido** |
| **Consumo de Memória RAM (Heap Ativo)** | `~421,80 MiB` *(6 processos)* | **`3,20 MiB`** *(`HeapSys: 11,59 MiB`)* | **131,8× menos RAM** (`-99,2%` memória) |

---

## 🏗️ Arquitetura do Runtime Go (`squad-ai-harness`)

```mermaid
flowchart LR
    CLI["squad-harness CLI / MCP"] --> DAG["DAG Engine (Goroutines)"]
    CLI --> COG["Camada 0 CognitiveHarness"]
    CLI --> COMP["Compute Router (C0 / C1 / C2)"]

    DAG --> CAT["Catalog Loader (106 Skills)"]
    DAG --> JEV["JEV Tribunal (25 Specialists)"]
    DAG --> SEKG["SEKG (CSR + Leiden GraphRAG)"]
    DAG --> GATES["DecidirEntrega (4 Delivery Gates)"]

    GATES --> SEC["SecretScan (14 Classes) + ASL/VTL Lint"]
```

---

## 🚀 Guia Rápido de Instalação e Uso

### 1. Compilar o Binário Nativo (`Go 1.24.3+`)

```powershell
# Windows (PowerShell)
$env:CGO_ENABLED="0"
go build -trimpath -ldflags="-s -w" -o squad-harness.exe ./cmd/squad-harness

# Linux / macOS
CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o squad-harness ./cmd/squad-harness
```

### 2. Comandos Principais do `squad-harness`

```powershell
# 1. Identidade, versão v0.8.0, arquitetura e memória RAM disponível no host
.\squad-harness.exe version

# 2. Detectar hardware da estação (CPU, iGPU, NPU, dGPU) e rotas C0 / C1 / C2
.\squad-harness.exe compute

# 3. Executar a pipeline unificada de qualidade em DAG concorrente (5 estágios)
.\squad-harness.exe gate

# 4. Executar o Preflight Cognitivo de 10 estágios + roteamento híbrido BM25 + SEKG
.\squad-harness.exe preflight "arquitetura aws serverless step functions golang seguranca"

# 5. Operar o Software Engineering Knowledge Graph (status | index | query | impact)
.\squad-harness.exe sekg status
.\squad-harness.exe sekg query "engenheiro-seguranca" local

# 6. Executar o Tribunal JEV de 25 especialistas determinísticos
.\squad-harness.exe jev "func Handler() error { return nil }"

# 7. Executar a suíte de benchmarks ao vivo na estação atual
.\squad-harness.exe bench
```

### 3. Distribuir as 106 Skills para seus Agentes Locais (Claude Code, Antigravity, Codex, Cursor)

```powershell
python install-squad-ai.py detectar
python install-squad-ai.py instalar-todos
python install-squad-ai.py verify
```

---

## 📂 Estrutura do Repositório

```text
squad-ai-harness/
├── assets/                     # Logomarca e identidade visual oficial (JPG + SVG)
├── cmd/squad-harness/          # CLI unificado (version, gate, preflight, sekg, sync, jev, compute, hook, mcp, bench)
├── internal/
│   ├── aws/                    # Linter determinístico de AWS Step Functions (ASL) e API Gateway (VTL)
│   ├── catalog/                # Loader concorrente e validador UTF-8/Frontmatter/Defesa das 106 skills
│   ├── cognitive/              # Camada 0 CognitiveHarness, SEKG (CSR + Leiden), GraphRAG, Router e Memory
│   ├── compute/                # Cognitive Compute Router (C0 Go Nativo / C1 Neural Assist / C2 LLM) + Circuit Breaker
│   ├── dag/                    # Motor concorrente de execução em Grafo Acíclico Dirigido (goroutines)
│   ├── gates/                  # Função canônica DecidirEntrega (env-infra, db-schema, config-compat, interop)
│   ├── git/                    # Planejador determinístico de sincronização Git (JEV)
│   ├── hooks/                  # Hooks PreToolUse, PostToolUse e Stop (< 1ms)
│   ├── jev/                    # Tribunal determinístico com 25 especialistas + Critic/Judge
│   ├── mcp/                    # Servidor MCP JSON-RPC 2.0 nativo via stdio
│   ├── runtime/                # Coletor Git concorrente e sensores de memória física do SO
│   ├── scheduler/              # Agendador inteligente 8D + IMO
│   ├── security/               # SecretScan (14 classes de segredos) + FSGuard
│   └── sonar/                  # Analisador estático Sonar-First (complexidade cognitiva e calistenia)
├── pkg/contracts/              # Contratos tipados imutáveis (GateState, ProvenanceTag, Identidade v0.8.0)
├── skills/                     # Catálogo canônico de 106 skills especializadas auditáveis
├── governance/                 # Políticas de autonomia (N0-N3), padrão de skill, gates e registry gerado
├── security/                   # Política de segurança, checklist pré-commit, Linha de Defesa e Relatório de Auditoria
├── rules/                      # Regras always-on enxutas por domínio e linguagem
├── contracts/                  # JSON Schemas formais da plataforma
├── templates/                  # Templates de engenharia (PRD, ARCHITECTURE, ADR, PLAN, TEST_PLAN, SECURITY_REVIEW)
└── docs/                       # Benchmarks científicos medidos e relatórios de validação v0.8.0
```

---

## 🛡️ Segurança, Governança e Conformidade

- **Zero Dependências Externas (`go.mod` limpo)**: superfície de supply chain reduzida a zero no runtime compilado.
- **Linha de Defesa de Prompt Obrigatória**: validada em 100% das 106 skills a cada execução do `squad-harness gate`.
- **Varredura Pré-Commit Nativa (`secretscan`)**: bloqueia chaves privadas, credenciais AWS (`AKIA`), tokens de API (`sk-`, `ghp_`), strings de conexão e arquivos `.env`/`.tfstate`.
- Consulte [`SECURITY.md`](SECURITY.md), [`CONTRIBUTING.md`](CONTRIBUTING.md) e [`security/RELATORIO-AUDITORIA-SEGURANCA-V080.md`](security/RELATORIO-AUDITORIA-SEGURANCA-V080.md).

---

## 📄 Licença

Distribuído sob a licença **MIT**. Veja [`LICENSE`](LICENSE) para detalhes.
