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

O **SquadAI Harness (`squad-ai-harness`)** é uma plataforma de engenharia de software autônoma e *gated* (**"autônoma na execução, gated na decisão"**) projetada para desenvolvedores e empresas.

Na versão **v0.8.0**, toda a infraestrutura de orquestração, validação, memória de grafo e governança foi consolidada em um **binário estático único em Go 1.24.3 (`CGO_ENABLED=0`)**, com **zero dependências externas** no `go.mod`, coordenando:

- **106 Skills Especializadas Auditáveis** (`skills/*/SKILL.md`) cobrindo arquitetura, AWS Serverless, Go, Java 25, Python 3.13+, Rust, .NET, TypeScript/Angular, bancos de dados, qualidade/TDD, segurança/OWASP e observabilidade.
- **Camada 0 `CognitiveHarness` (< 25 ms)**: 10 estágios determinísticos de preflight, roteamento híbrido BM25 + Vetorial 384-d e compressão cirúrgica de contexto antes de acionar qualquer LLM remoto.
- **Software Engineering Knowledge Graph (`SEKG` + `GraphRAG`)**: Grafo em memória representado em *Compressed Sparse Row* (`CSR`) com detecção determinística de comunidades de Leiden e três modos de busca (`LocalSearch`, `GlobalSearch` e `DRIFTSearch` em microssegundos).
- **Tribunal JEV de 25 Especialistas (`< 1 ms`)**: Avaliação concorrente determinística (custo US$ 0) com *Critic/Judge* anti-regressão sob a função de arbitragem imutável:
  $$\text{Segurança (inegociável)} \gg \text{P1 Simplicidade} > \text{P2 Performance} > \text{P3 Custo Baixo}$$
- **Cognitive Compute Router Multi-Estação (`C0` / `C1` / `C2`)**: Adapta-se automaticamente ao hardware de cada máquina (PC corporativo somente CPU, notebook com NPU Intel AI Boost, estação com iGPU Arc ou servidor com GPU NVIDIA RTX).
- **Catálogo Interativo Web & Monitor de Recursos (`.\squad-harness.exe ui`)**: Interface gráfica web 100% nativa (`net/http` + `embed`, tema Dark + Azul Celeste Claro) com busca via `HybridRouter`, filtros dinâmicos por tecnologia, telemetria em tempo real (`Heap`, `GOMEMLIMIT`, `RAM Livre Host`, `Skills`, `Nós SEKG`), botão **`📂 Abrir skill`** no Windows Explorer e **Validador de Sincronização** integrado.
- **Instalador e Sincronizador Multi-Alvo 100% Go Nativo (`.\squad-harness.exe install`)**: Substitui o antigo instalador Python por sincronização concorrente em Go com porta de segurança *fail-closed* e manifesto `SHA-256` em `~/.claude/skills`, `~/.gemini/config/skills`, `~/.dsh/skills` e `~/.resolveai/skills`.

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
    CLI["squad-harness CLI / MCP / UI"] --> DAG["DAG Engine (Goroutines)"]
    CLI --> COG["Camada 0 CognitiveHarness"]
    CLI --> COMP["Compute Router (C0 / C1 / C2)"]
    CLI --> INST["Installer Go Nativo (Multi-Target)"]
    CLI --> WEB["Web UI Nativa (127.0.0.1:9090)"]

    DAG --> CAT["Catalog Loader (106 Skills)"]
    DAG --> JEV["JEV Tribunal (25 Specialists)"]
    DAG --> SEKG["SEKG (CSR + Leiden GraphRAG)"]
    DAG --> GATES["DecidirEntrega (4 Delivery Gates)"]

    GATES --> SEC["SecretScan (14 Classes) + ASL/VTL Lint"]
```

---

## 🧠 Arquitetura de Alto Nível do Cérebro Cognitivo (`Cognitive Brain`)

O diagrama abaixo ilustra como o **Cérebro Cognitivo** do `squad-ai-harness` processa qualquer pedido antes de consumir tokens de um LLM remoto — combinando **percepção de impacto**, **busca em grafo (`SEKG + GraphRAG`)**, **memória em 4 camadas (`M0–M3`)**, **julgamento determinístico (`Tribunal JEV`)** e **roteamento adaptativo de hardware (`C0 / C1 / C2`)**:

```mermaid
flowchart TB
    subgraph L1["1. PERCEPCAO E ENTRADA (Dev, Diff Git ou Agente via MCP)"]
        IN["Prompt / Tarefa / Git Diff — Ex.: Squad ai, prepare a equipe"]
        TRIG{"Gatilho Executivo? (gere relatorio de uso)"}
        IN --> TRIG
    end

    subgraph L2["2. CAMADA 0 — COGNITIVE HARNESS (10 Estagios em Go · < 10 ms · US$ 0)"]
        S1["(1) TASK & (2) CONTEXT — Raio de Impacto + Orcamento CTX-1 (2k) | CTX-2 (6k) | CTX-3 (12k)"]
        S3["(3) RETRIEVAL HIBRIDO — HybridRouter BM25 + Vetorial 384-d (Top-K entre 106 Skills)"]
        S4["(4) PLAN -> (5) EXECUTION -> (6) TEST — Trava N0/N1 ate GATE 1 + Oraculos de Teste"]
        S8["(8) REFLECTION -> (9) MEMORY -> (10) NEXT_ACTION — Pacote Cirurgico de Contexto"]
        S1 --> S3
        S3 --> S4
    end

    subgraph L3["3. GRAFO DE CONHECIMENTO — SEKG & GRAPHRAG (CSR em RAM + Comunidades de Leiden)"]
        CSR["Grafo CSR (< 12 MB RAM) — Modulos, Contratos, Testes, ADRs e Skills (Leiden C0 / C1 / C2)"]
        LOCAL["LocalSearch (< 1 ms) — Vizinhanca 1-hop e 2-hop (Quem chama? Qual teste cobre?)"]
        GLOBAL["GlobalSearch (< 1 ms) — Visao Holistica de Arquitetura (Community Reports)"]
        DRIFT["DRIFTSearch (< 1 ms) — Raciocinio Dinamico Macro + Micro (Causa Raiz)"]
        CSR --> LOCAL
        CSR --> GLOBAL
        CSR --> DRIFT
    end

    subgraph L4["4. MEMORIA MULTICAMADA (M0 a M3) & GUARDRAILS EPISTEMICOS"]
        M0["M0 Working Memory — Contexto ativo da sessao com teto rigido de tokens"]
        M1["M1 Episodic Memory — Historico de execucoes, falhas e indice de surpresa"]
        M2["M2 Semantic Memory — Quarentena (HYPOTHESIS, TTL 7d) vs. Provado (VERIFIED)"]
        M3["M3 Procedural Memory — 106 Skills Auditaveis + Regras Always-On + Instintos"]
        M0 --> M1
        M1 --> M2
        M2 --> M3
    end

    subgraph L5["5. TRIBUNAL DETERMINISTICO JEV (25 Especialistas + Critic/Judge · ~518 us · US$ 0)"]
        JEV25["Fan-Out Paralelo de 25 Especialistas JEV (Seguranca, Arquitetura, Banco, Cloud, Clean Code)"]
        ARB["Juiz Anti-Regressao — Seguranca (Bloqueante) >> P1 Simplicidade > P2 Performance > P3 Custo"]
        JEV25 --> ARB
    end

    subgraph L6["6. ROTEADOR COMPUTACIONAL (C0 / C1 / C2) & TELEMETRIA QUANTICA (QUID)"]
        C0["Rota C0 (Go Nativo CPU) — Decisoes Deterministicas · 0 Tokens · US$ 0"]
        C1["Rota C1 (Neural Assist Local) — ONNX / NPU / iGPU / GPU Local · US$ 0"]
        C2["Rota C2 (LLM Remoto Cirurgico) — Haiku (Exploracao) | Sonnet (Codigo) | Opus (Arquitetura)"]
        QUID["Ledger Assincrono (< 15 us) + ID Quantico (QUID-SQ8-...) — Relatorio ASCII 3 Meses (US$ e R$)"]
    end

    TRIG -->|"Sim (100% Offline)"| QUID
    TRIG -->|"Nao (Fluxo de Engenharia)"| S1
    S3 <-->|"Travessia em Microssegundos"| CSR
    S4 --> JEV25
    ARB --> S8
    S8 <-->|"Leitura / Escrita Auditada"| M0
    S8 --> C0
    S8 --> C1
    S8 --> C2
    C0 --> QUID
    C1 --> QUID
    C2 --> QUID
```

### 📖 Legendas Didáticas — Como o Cérebro Cognitivo Funciona na Prática

Para facilitar o entendimento técnico e executivo, cada bloco numerado no diagrama acima cumpre um papel específico inspirado na cognição humana e na engenharia de sistemas de baixa latência:

| Bloco do Diagrama | O que é (Explicação Didática) | Como funciona por dentro (`Go 1.24.3`) | Ganho Prático (Velocidade & Economia) |
| :--- | :--- | :--- | :--- |
| **1. Percepção e Entrada** | É a **"porta sensorial"** da Squad. Recebe tanto pedidos de engenharia (`"implemente API em Go"`, `"revise este PR"`) quanto gatilhos executivos (`"Squad ai, gere relatorio de uso"`). | Intercepta a intenção via CLI, hook (`PreToolUse`) ou servidor MCP local (`stdio`). Se for uma consulta de relatório ou `QUID`, responde instantaneamente sem acionar o restante da pipeline. | Evita chamadas desnecessárias à nuvem e funciona **100% offline** dentro da rede corporativa. |
| **2. Camada 0 (`CognitiveHarness`)** | É o **"pré-frontal de triagem rápida"**. Antes de perguntar qualquer coisa a um LLM caro, executa **10 estágios determinísticos** (`TASK` → `NEXT_ACTION`) em menos de `10 ms`. | Mede o *Blast Radius* (raio de impacto dos arquivos alterados), classifica o tamanho da tarefa (`trivial`, `small`, `standard`, `large`), trava o orçamento de tokens (`CTX-1` a `CTX-3`) e seleciona apenas as skills relevantes via `HybridRouter` (BM25 + Vetor `384-d`). | Reduz de **60% a 75% o consumo de tokens**, pois o LLM nunca recebe o repositório inteiro nem todas as 106 skills de uma vez — apenas o recorte cirúrgico. |
| **3. Grafo `SEKG` & `GraphRAG`** | É o **"mapa relacional vivo"** do sistema. Enquanto um RAG comum lê trechos soltos de texto (e falha ao responder *"o que quebra se eu mudar esta tabela?"*), o `SEKG` conhece quem chama quem, qual teste valida qual módulo e qual ADR governa cada pacote. | Mantém o grafo em memória no formato compacto **CSR (*Compressed Sparse Row*)** com agrupamento hierárquico pelo algoritmo de **Leiden** (`C0` domínio, `C1` subsistema, `C2` pacote), oferecendo 3 buscas em `< 1 ms`: **`LocalSearch`** (vizinhança 1–2 saltos), **`GlobalSearch`** (visão macro por comunidades) e **`DRIFTSearch`** (investigação combinada macro + micro). | Elimina "alucinações de acoplamento" e responde perguntas de impacto arquitetural em **`~526 µs`** a **custo US$ 0 de LLM**. |
| **4. Memória Multicamada (`M0–M3`) & Guardrails** | É o **"sistema de memória com imunidade anti-alucinação"**. Divide o conhecimento em 4 horizontes de tempo e impede que suposições não provadas contaminem decisões futuras. | **`M0` (Trabalho)**: contexto enxuto da sessão atual.<br/>**`M1` (Episódica)**: histórico de execuções e falhas.<br/>**`M2` (Semântica)**: separa hipóteses em **Quarentena (`HYPOTHESIS`, expira em 7 dias)** de fatos **Verificados (`VERIFIED`)** — uma hipótese só vira fato se passar por teste automatizado + gate verde.<br/>**`M3` (Procedural)**: as **106 Skills** e regras versionadas no Git. | Garante que o agente aprenda entre sessões sem sofrer *memory poisoning* (envenenamento de memória por respostas antigas incorretas). |
| **5. Tribunal Determinístico `JEV`** | É o **"conselho de 25 juízes especialistas"** que audita arquitetura, segurança, banco de dados e código limpo paralelamente em meio milissegundo (`~518 µs`). | Executa 25 avaliadores determinísticos em goroutines e consolida os votos no *Critic/Judge* sob a regra pétrea:<br/>$$\text{Segurança} \gg \text{P1 Simplicidade} > \text{P2 Performance} > \text{P3 Custo}$$<br/>Qualquer violação crítica de segurança ou tentativa de quebrar a trava Go-Exclusive barra a operação na hora (`BLOCKED`). | Substitui dezenas de chamadas repetitivas de code review em LLM por verificações exatas a **US$ 0** e latência sub-milissegundo. |
| **6. Roteador `C0/C1/C2` & Telemetria `QUID`** | É o **"despachante inteligente de custos e auditoria executiva"**. Decide qual motor computacional usar e registra cada segundo e dólar economizado. | - **`C0` (Go Nativo)**: resolve localmente tudo o que é determinístico (`US$ 0`).<br/>- **`C1` (Neural Local)**: usa CPU/NPU/iGPU/GPU local quando disponível (`US$ 0`).<br/>- **`C2` (LLM Cloud)**: roteia para `Haiku` (exploração), `Sonnet` (implementação) ou `Opus` (arquitetura/segurança) já com o contexto comprimido.<br/>- **`QUID`**: grava em *ring-buffer* assíncrono (`< 15 µs`) as horas trabalhadas, horas otimizadas e tokens poupados (`US$` e `R$`) sob o ID Quântico do repositório. | Dá visibilidade executiva imediata em ASCII para o gestor (`.\squad-harness.exe report`) sem qualquer impacto na velocidade de resposta do desenvolvedor. |

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

# 8. Gerar o Relatório Executivo ASCII de Uso, Horas e Economia de Tokens (US$ / R$ · Últimos 3 Meses · QUID)
.\squad-harness.exe report

# 9. Iniciar o Control Center Web Nativo embutido (http://127.0.0.1:9090)
.\squad-harness.exe ui
```

### 3. Distribuir as 106 Skills para seus Agentes Locais (100% Go Nativo — Claude Code, Antigravity, DeepSeek, Resolve AI)

```powershell
# 1. Detectar os ambientes agênticos instalados na máquina (~/.claude, ~/.gemini/config, ~/.dsh, ~/.resolveai)
.\squad-harness.exe install detect

# 2. Instalar/sincronizar concorrentemente as 106 skills (com porta de segurança e manifesto SHA-256)
.\squad-harness.exe install

# 3. Verificar integridade byte-a-byte (LF normalizado) de todas as skills instaladas
.\squad-harness.exe install verify
```

### 4. Catálogo Interativo de Skills & Monitor de Recursos (`.\squad-harness.exe ui`)

O binário `squad-harness.exe` incorpora uma GUI Web zero-dependência (`net/http` + `//go:embed`, tema Dark `#060b14` com Azul Celeste Claro `#7dd3fc`) acessível em `http://127.0.0.1:9090`:

- **Monitor de Recursos 100% Dinâmico**: lê em tempo real `runtime.ReadMemStats` (`Heap`), `debug.SetMemoryLimit(-1)` (`GOMEMLIMIT`), sensores de memória física do SO (`RAM Livre Host`), contagem de skills carregadas do disco e nós do grafo `SEKG`.
- **Pesquisa via `HybridRouter` + Filtros Dinâmicos por Tecnologia**: filtra por stack tecnológica (`Java / Spring / Quarkus`, `AWS / Cloud / IaC`, `Go & Rust`, `Python`, `Angular / TS / Web`, `.NET / C#`, `Banco / Dados`, `IA & Agentes`, `Segurança, QA & Obs`) com contadores calculados dinamicamente.
- **Aviso Validador de Sincronização**: verifica automaticamente se as skills estão instaladas e atualizadas em `~/.claude/skills`, `~/.gemini/config/skills` e `~/.dsh/skills`, oferecendo o botão **`⚡ Sincronizar Skills (Go Nativo)`** em 1 clique.
- **Botão `📂 Abrir skill`**: abre o Windows Explorer (`explorer.exe` / `open` / `xdg-open`) diretamente na pasta `skills/<nome-da-skill>/`.

### 5. Relatório Executivo de Uso, Horas Economizadas & Economia de Tokens (`.\squad-harness.exe report` / `QUID`)

A Squad possui um módulo interno ultra-leve em Go ([`internal/telemetry/`](internal/telemetry/)) com impacto zero de latência (`< 15 µs` assíncrono em *ring-buffer*) que consolida os **ganhos × tempo de uso** nos últimos 3 meses:

- **Gatilhos de Linguagem Natural**:
  - `"Squad ai, gere relatorio de uso"` / `"Squad ai. me mostre seu relatorio"`
- **Métricas Consolidadas em ASCII (Últimos 3 Meses — Agrupado por Mês e por Dia)**:
  - **Total de Horas Trabalhadas** utilizando a Squad AI (`Horas de Uso Ativo`).
  - **Total de Horas Economizadas / Otimizadas** e multiplicador de velocidade medido (`~7.0x`).
  - **Economia Total de Tokens** (Camada 0 + 25 Especialistas JEV + SEKG GraphRAG) convertida em **Dólar (`US$`)** e **Real (`R$`)**.
- **ID Quântico Universal (`QUID-SQ8-...`) & Consulta Pública 100% Offline (Sem Bloqueio de Firewall)**:
  - Cada repositório clonado gera um identificador único pós-quântico (`QUID-SQ8-XXXX-XXXX-XXXX-XXXX`, esponja iterativa `HMAC-SHA512` de 12 rodadas com sal CSPRNG de 256 bits) assinado criptograficamente.
  - O gestor ou qualquer ferramenta agêntica/LLM na máquina ou rede local pode consultar o relatório ASCII pelo `QUID` **100% offline**:
    ```powershell
    # Consulta direta via CLI pelo ID Quântico Universal do repositório
    .\squad-harness.exe report --quid QUID-SQ8-...

    # Ou via gatilho natural no preflight
    .\squad-harness.exe preflight "Squad ai, me mostre seu relatorio"
    ```
  - Exposto nativamente via **MCP Offline** (`squad_usage_report`, `squad_resolve_quid` e resource `squad://telemetry/ascii`) e via **HTTP Local/LAN** (`http://127.0.0.1:9090/api/telemetry/ascii?quid=QUID-SQ8-...`).

---

## 📂 Estrutura do Repositório

```text
squad-ai-harness/
├── assets/                     # Logomarca e identidade visual oficial (JPG + SVG)
├── cmd/squad-harness/          # CLI unificado (version, gate, preflight, sekg, sync, jev, compute, hook, mcp, bench, install, ui)
├── internal/
│   ├── aws/                    # Linter determinístico de AWS Step Functions (ASL) e API Gateway (VTL)
│   ├── catalog/                # Loader concorrente e validador UTF-8/Frontmatter/Defesa das 106 skills
│   ├── cognitive/              # Camada 0 CognitiveHarness, SEKG (CSR + Leiden), GraphRAG, Router e Memory
│   ├── compute/                # Cognitive Compute Router (C0 Go Nativo / C1 Neural Assist / C2 LLM) + Circuit Breaker
│   ├── dag/                    # Motor concorrente de execução em Grafo Acíclico Dirigido (goroutines)
│   ├── gates/                  # Função canônica DecidirEntrega (env-infra, db-schema, config-compat, interop)
│   ├── git/                    # Planejador determinístico de sincronização Git (JEV)
│   ├── hooks/                  # Hooks PreToolUse, PostToolUse e Stop (< 1ms)
│   ├── installer/              # Instalador e sincronizador multi-alvo 100% Go nativo (~/.claude, ~/.gemini, ~/.dsh)
│   ├── jev/                    # Tribunal determinístico com 25 especialistas + Critic/Judge
│   ├── mcp/                    # Servidor MCP JSON-RPC 2.0 nativo via stdio
│   ├── runtime/                # Coletor Git concorrente e sensores de memória física do SO
│   ├── scheduler/              # Agendador inteligente 8D + IMO
│   ├── security/               # SecretScan (14 classes de segredos) + FSGuard
│   ├── sonar/                  # Analisador estático Sonar-First (complexidade cognitiva e calistenia)
│   ├── telemetry/              # Ledger assíncrono (<15µs), ID Quântico Universal (QUID), Relatório ASCII 3 meses (US$/R$)
│   └── ui/                     # Control Center Web Nativo embutido via //go:embed (127.0.0.1:9090)
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

## 🔒 Trava Exclusiva Go (`Go-Exclusive Source Lock`) & Segurança

- **Fonte do Harness 100% Exclusivo em Go (`Go 1.24.3+`, `CGO_ENABLED=0`)**: O estágio `stage1.go_exclusive_lock` ([`internal/gates/gopurity.go`](internal/gates/gopurity.go)) e os hooks em tempo real (`PreToolUse` / `PostToolUse`) **bloqueiam automaticamente (`Exit Code 2 / GateBlocked`)** qualquer tentativa de misturar código ou manifestos de outras linguagens (Python `.py`, Node/JS/TS `.js/.ts`, Java `.java`, Rust `.rs`, C# `.cs`, scripts `.ps1/.sh/.bat` ou `package.json`/`pyproject.toml`/`requirements.txt`) no fonte do harness.
- **Zero Dependências Externas (`go.mod` limpo)**: superfície de supply chain reduzida a zero no runtime compilado.
- **Linha de Defesa de Prompt Obrigatória**: validada em 100% das 106 skills a cada execução do `squad-harness gate`.
- **Varredura Pré-Commit Nativa (`secretscan`)**: bloqueia chaves privadas, credenciais AWS (`AKIA`), tokens de API (`sk-`, `ghp_`), strings de conexão e arquivos `.env`/`.tfstate`.
- Consulte [`SECURITY.md`](SECURITY.md), [`CONTRIBUTING.md`](CONTRIBUTING.md) e [`security/RELATORIO-AUDITORIA-SEGURANCA-V080.md`](security/RELATORIO-AUDITORIA-SEGURANCA-V080.md).

---

## 📄 Licença

Distribuído sob a licença **Apache 2.0** ([`LICENSE`](LICENSE)) · `30/10/2026` · [Thiago Gonçalo](https://www.linkedin.com/in/thiago-gon%C3%A7alo)
