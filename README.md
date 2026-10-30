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

## 🔄 Pipeline Gated End-to-End (`GATE 1` / `GATE 2`), Blast Radius e Níveis de Autonomia (`N0–N3`)

O princípio central da Squad é **"Gated, Not Autonomous"** (*autônoma na execução, gated na decisão*). A cerimônia de engenharia se adapta automaticamente ao **raio de impacto (*Blast Radius*)** da mudança, exigindo aprovação humana explícita apenas nos marcos irreversíveis:

```mermaid
flowchart LR
    subgraph FASE_N0_N1["Fase N0 / N1 — Leitura, Pesquisa e Planejamento (Zero Escrita em Producao)"]
        S0["0. Intake & Blast Radius — Classifica: trivial | small | standard | large"]
        S1["1. Research & SEKG — Mapeia acoplamentos, contratos e reuso no grafo"]
        S2["2. Plan — Gera .prd.md + .plan.md + ADRs"]
        S0 --> S1
        S1 --> S2
    end

    G1{"GATE 1 — Humano Aprova o Plano?"}

    subgraph FASE_N2["Fase N2 — Execucao Autonoma Reversivel (TDD + Especialistas)"]
        S3["3. Scaffold & Contratos — OpenAPI, DBML, ASL e Interfaces"]
        S4["4. Ciclo TDD — Red -> Green -> Refactor com Oraculos Executaveis"]
        S5["5. Review & Tribunal JEV — 25 Especialistas + Tech Lead + Seguranca"]
        S3 --> S4
        S4 --> S5
    end

    G2{"GATE 2 — Diff Aprovado + Gates PASS?"}

    subgraph FASE_N3["Fase N3 — Entrega Auditada & Memoria"]
        S6["6. Commit & Remember — Conventional Commit PT-BR + Atualizacao SEKG + QUID"]
    end

    S2 --> G1
    G1 -->|"Aprovado"| S3
    G1 -->|"Ajustar"| S2
    S5 --> G2
    G2 -->|"PASS + Zero Critico"| S6
    G2 -->|"Bloqueado / Corrigir"| S4
```

### 1. Matriz de Dimensionamento por *Blast Radius* (Anti-"Agent Soup")

Para evitar o desperdício de acionar dezenas de agentes em tarefas simples (*anti-padrão "agent soup"*), o `SEKG Impact Analyzer` classifica cada pedido no **Passo 0**:

| Tamanho (*Size Class*) | Sinal Detectado pelo `SEKG` | Resposta da Squad | Orçamento de Contexto |
| :--- | :--- | :--- | :---: |
| **`trivial`** | 1 arquivo, sem nova dependência, sem ambiguidade | **1 especialista direto**; sem burocracia de pipeline completo. | `CTX-1` (`2.000 tokens`) |
| **`small`** | Poucos arquivos em um único pacote, escopo claro | **1 a 2 especialistas**; pipeline enxuto com validação de testes. | `CTX-2` (`6.000 tokens`) |
| **`standard`** | Múltiplos pacotes/contratos, decisão de design local | **Pipeline completo** com `GATE 1` (plano) e `GATE 2` (diff). | `CTX-3` (`12.000 tokens`) |
| **`large`** | Nova capacidade, novas dependências, mudança de schema/arquitetura | **Comissão de Arquitetos + Spec aprovada obrigatória** antes de codar; squad completa. | `CTX-3` (`12.000 tokens`) |

### 2. Os 4 Níveis de Autonomia (`N0` a `N3` — [`governance/autonomy-policy.md`](governance/autonomy-policy.md))

| Nível | Nome | O que o Agente Pode Fazer Sozinho | Onde Precisa de Humano |
| :---: | :--- | :--- | :--- |
| **`N0`** | **Observação Pura** | Ler arquivos, consultar o grafo `SEKG`, rodar diagnósticos *read-only* e produzir relatórios. | Nenhuma permissão necessária (100% seguro). |
| **`N1`** | **Proposta & Planejamento** | Escrever artefatos de especificação (`.prd.md`, `.plan.md`, ADRs) em área de rascunho. | Não pode tocar em código de produção até a aprovação do **`GATE 1`**. |
| **`N2`** | **Execução Reversível** | Criar/editar código e testes dentro do workspace, rodar compilador, linter e suíte de testes locais. | Barrado automaticamente por `hooks` se tentar tocar segredos ou violar a trava `Go-Exclusive`. |
| **`N3`** | **Operação Irreversível / Externa** | `git commit`, `git push`, migração destrutiva de banco, `terraform apply` ou alteração de segurança. | Exige **`GATE 2` aprovado (`PASS`)** + confirmação explícita do desenvolvedor. |

---

## ⚖️ Core de Decisão: Tribunal JEV (25 Especialistas), Função `DecidirEntrega` e Arbitragem `P1 > P2 > P3`

Em vez de depender de opiniões subjetivas de um LLM a cada revisão de código, o core do `squad-ai-harness` possui um **motor jurídico-técnico determinístico** em Go ([`internal/jev/`](internal/jev/) e [`internal/gates/`](internal/gates/)) que roda em **`~518 µs`**:

```mermaid
flowchart TB
    DIFF["Alteracao de Codigo / Contrato / Infra (Git Diff + AST)"]

    subgraph TRIBUNAL["Tribunal Deterministico JEV (25 Especialistas em Goroutines · US$ 0)"]
        DOM_SEC["Esquadrao Seguranca — SecretScan (14 classes), Auth/JWT, OWASP, Prompt Defense"]
        DOM_ARC["Esquadrao Arquitetura — Clean Arch, Acoplamento, Go-Exclusive Lock, Drift Spec x Codigo"]
        DOM_DB["Esquadrao Dados & Cloud — Schema DBML, Migracoes Expand-Contract, ASL Step Functions, VTL"]
        DOM_QA["Esquadrao Qualidade & Performance — Sonar-First (Complexidade Cognitiva), Oraculos TDD, Memoria"]
    end

    JUDGE["Critic / Judge — Funcao de Arbitragem Imutavel: Seguranca >> P1 Simplicidade > P2 Performance > P3 Custo"]

    subgraph GATES4["Funcao Canonica DecidirEntrega (4 Gates de Entrega)"]
        G_ENV["1. environment-infrastructure-gate (Runtime, Limites, IaC, Config)"]
        G_DB["2. database-schema-gate (Compatibilidade de Schema e Migracoes)"]
        G_CFG["3. config-compatibility-gate (Manifestos, Contratos e Flags)"]
        G_INT["4. interop-contract-gate (OpenAPI, MCP, Eventos e Consumidores)"]
    end

    VERDICT{"Veredito Unico Auditavel"}
    PASS["PASS — Pronto para o GATE 2 / Commit"]
    BLOCKED["BLOCKED — Bloqueio Imediato (Exit Code 2)"]
    INCONC["INCONCLUSIVE / STALE — Exige Evidencia Adicional"]

    DIFF --> DOM_SEC
    DIFF --> DOM_ARC
    DIFF --> DOM_DB
    DIFF --> DOM_QA
    DOM_SEC --> JUDGE
    DOM_ARC --> JUDGE
    DOM_DB --> JUDGE
    DOM_QA --> JUDGE
    JUDGE --> G_ENV
    JUDGE --> G_DB
    JUDGE --> G_CFG
    JUDGE --> G_INT
    G_ENV --> VERDICT
    G_DB --> VERDICT
    G_CFG --> VERDICT
    G_INT --> VERDICT
    VERDICT -->|"100% Conforme"| PASS
    VERDICT -->|"Violacao P1/Seguranca"| BLOCKED
    VERDICT -->|"Sem Oraculo Fresco"| INCONC
```

### Como o Core Resolve Conflitos Técnicos (Regra de Desempate)

Quando dois especialistas apontam direções opostas (por exemplo, `arquiteto-minimalista` sugere monólito modular com SQLite/Postgres enquanto outro caminho sugere microsserviços com Kafka), o **Juiz JEV (`Critic/Judge`)** aplica a cláusula pétrea da Squad:

1. **Segurança é Inegociável (`🔴 BLOQUEANTE`)**: qualquer achado crítico de segurança (segredo exposto, injeção, quebra de autenticação, ausência da Linha de Defesa de Prompt) veta imediatamente a entrega, prevalecendo sobre qualquer ganho de simplicidade, performance ou custo.
2. **`P1 Simplicidade` vence `P2 Performance`**: soluções mais simples e fáceis de manter vencem otimizações prematuras — a menos que exista um **SLA/SLO explícito** documentado pelo `arquiteto-performance` exigindo o contrário.
3. **`P2 Performance` vence `P3 Custo Baixo`**: dentro dos limites de simplicidade, a arquitetura prioriza baixa latência e eficiência de memória antes de micro-otimizações de custo.

---

## ⚡ Compute Router Multi-Estação (`C0` / `C1` / `C2`) & Resiliência em 3 Camadas

O `squad-ai-harness` foi projetado para rodar com desempenho máximo em **qualquer máquina** — desde um notebook corporativo bloqueado (somente CPU) até uma workstation com NPU dedicada ou servidor com GPU NVIDIA RTX — combinando roteamento adaptativo ([`internal/compute/`](internal/compute/)) e isolamento de falhas em 3 camadas:

```mermaid
flowchart LR
    subgraph HW["1. Sensor de Hardware da Estacao (squad-harness compute)"]
        PROBE["Probe Nativo (CPU Cores, AVX2, RAM Livre, iGPU, NPU AI Boost, dGPU CUDA)"]
    end

    subgraph ROUTER["2. Cognitive Compute Router (Menor Custo que Cumpre a Missao)"]
        R_C0["Camada C0 — Go Nativo (CPU Pura) · 100% Deterministico · < 10 ms · US$ 0"]
        R_C1["Camada C1 — Neural Assist Local (ONNX / NPU / iGPU / dGPU) · Embeddings e Rerank · US$ 0"]
        R_C2["Camada C2 — LLM Cloud Roteado por Complexidade (Haiku -> Sonnet -> Opus)"]
    end

    subgraph RESIL["3. Resiliencia em 3 Camadas (Circuit Breaker Anti-Travamento)"]
        CB1["Camada 1 — Disjuntor por Especialista (Isola skill com falha repetida)"]
        CB2["Camada 2 — Cooldown por Tentativa (Backoff Exponencial + Jitter)"]
        CB3["Camada 3 — Lockout e Fallback de Modelo (429 / Timeout: Opus -> Sonnet -> Haiku -> C0)"]
        CB1 --> CB2
        CB2 --> CB3
    end

    PROBE --> R_C0
    PROBE --> R_C1
    PROBE --> R_C2
    R_C2 --> CB1
```

| Camada Computacional | Onde Roda | O que Executa | Latência & Custo | Comportamento Offline / Firewall |
| :--- | :--- | :--- | :---: | :--- |
| **`C0` — Go Nativo** | Qualquer CPU (`amd64` / `arm64`, sem GPU/NPU) | Preflight 10 estágios, `SEKG` CSR + Leiden, `HybridRouter` BM25, Tribunal JEV (25 especialistas), Gates, Linter ASL/VTL, SecretScan e Relatório `QUID`. | **`< 10 ms` · `US$ 0`** | **100% Offline** (zero rede). |
| **`C1` — Neural Local** | CPU AVX2, Intel/AMD NPU, iGPU ou GPU RTX local | Reranking semântico denso (`384-d`), classificação auxiliar local e embeddings sem sair da máquina. | **`< 25 ms` · `US$ 0`** | **100% Offline** (pesos locais em `~/.squad-ai/models`). |
| **`C2` — LLM Cloud** | Provedor configurado no agente (Anthropic, Google, OpenAI, Bedrock) | Geração criativa de código, modelagem de domínio complexa e arbitragem arquitetural profunda (`Haiku` / `Sonnet` / `Opus`). | Sob demanda (contexto reduzido em até 75%) | Protegido por **Circuit Breaker de 3 camadas** com fallback gracioso para `C0`. |

---

## 🗺️ Ecossistema das 106 Skills: Mapa por Domínio e Composição Dinâmica de Equipe

Toda capacidade da Squad nasce como uma **Skill auditável** (`skills/<nome>/SKILL.md`), seguindo o princípio **Agent-First / Skills-First**. O `HybridRouter` seleciona dinamicamente apenas os especialistas necessários para cada etapa do ciclo de engenharia:

```mermaid
flowchart LR
    D1["1. Especificacao & DDD (engenheiro-especificacao, comissao-arquitetos)"]
    D2["2. Arquitetura & Cloud AWS (arquiteto-minimalista, arquiteto-cloud-aws, step-functions)"]
    D3["3. Backend & Runtimes (golang-pro, java25-spring-boot, python-pro, rust-pro, dotnet-csharp-pro)"]
    D4["4. Frontend & UI/UX (especialista-frontend, angular-error-investigator, ui-ux-pro-max)"]
    D5["5. Bancos & Streaming (especialista-banco, arquiteto-dados-streaming, localstack-dev)"]
    D6["6. Qualidade, Caos & Contratos (especialista-qualidade, contrato-reverso, testes-resiliencia-caos-aws)"]
    D7["7. Seguranca & Supply Chain (engenheiro-seguranca, auditoria-skill-externa, validacao-veracode)"]
    D8["8. Observabilidade, DevOps & IaC (engenheiro-iac, logs-observabilidade, dd-apm, trace2local)"]

    D1 --> D2
    D2 --> D3
    D2 --> D4
    D2 --> D5
    D3 --> D6
    D4 --> D6
    D5 --> D6
    D6 --> D7
    D7 --> D8
```

### Catálogo Resumido por Domínio de Engenharia ([`governance/registry/registry.json`](governance/registry/registry.json))

| Domínio do Core | Especialistas de Referência (`skills/*/SKILL.md`) | Modelo Alvo (`P3`) | Quando o `HybridRouter` Aciona Automaticamente |
| :--- | :--- | :---: | :--- |
| **1. Orquestração & Planejamento** | `squad-ai`, `squad-pipeline`, `comissao-arquitetos`, `repo-ai-first-multiagente`, `batman` | `opus` | Pedidos de novos sistemas, refino arquitetural em 3 rodadas, coordenação multi-agente e melhoria contínua noturna. |
| **2. Especificação, Produto & DDD** | `engenheiro-especificacao`, `diagramador`, `sandeco-loop`, `traceability-matrix-builder`, `spec-code-drift-detector` | `sonnet` / `opus` | Levantamento de requisitos, user stories BDD/Gherkin, EventStorming, diagramas C4/Mermaid e detecção de drift entre spec e código. |
| **3. Arquitetura de Software & Performance** | `arquiteto-minimalista`, `engenheiro-clean-architect`, `arquiteto-performance`, `sonar-first-engineering` | `opus` | Desenho de sistemas, combate a overengineering, SOLID/Clean Architecture, análise de latência p95/p99 e complexidade cognitiva. |
| **4. Cloud AWS, Serverless & Eventos** | `arquiteto-cloud-aws`, `aws-serverless-eda`, `orquestracao-step-functions`, `api-gateway-integracoes`, `tempo-real-aws`, `analise-producao-aws` | `opus` | Arquitetura AWS (Padrão/Enterprise), FinOps, workflows ASL Step Functions, API Gateway/VTL, WebSocket/IoT Core e diagnóstico *read-only* de produção. |
| **5. Engenharia Go, Rust, Java 25, Python, .NET & Node** | `golang-pro`, `go-cloud-services`, `aws-lambda-go`, `rust-pro`, `java25-spring-boot`, `quarkus-java-aot`, `aws-lambda-java25-aot`, `python-pro`, `python-memoria`, `dotnet-csharp-pro`, `nodejs-pro` | `sonnet` | Implementação idiomática, concorrência segura, GraalVM/Native AOT, Lambdas de cold-start sub-100ms e otimização de memória RAM. |
| **6. Frontend, Web & UI/UX** | `especialista-frontend`, `typescript-pro`, `angular-error-investigator`, `ui-ux-pro-max`, `validador-navegador` | `sonnet` | Aplicações Angular 21+ Signals, TypeScript 7, design systems acessíveis e validação E2E real via navegador. |
| **7. Bancos de Dados & Streaming** | `especialista-banco`, `arquiteto-dados-streaming`, `localstack-dev` | `sonnet` / `opus` | Modelagem DBML-first, SQL (Postgres/Aurora) e NoSQL (DynamoDB single-table), migrações *Expand-Contract*, Outbox, Kafka/Kinesis e LocalStack. |
| **8. IA, Agentes, GraphRAG & MCP** | `arquiteto-ia`, `ai-evaluation`, `mcp-builder`, `graphify`, `headroom`, `roteamento-modelo-adaptativo`, `resiliencia-agente` | `opus` | Arquitetura de agentes LLM, RAG, servidores MCP enxutos (`<= 10 servers`), avaliação A/B (LLMOps) e compressão de contexto. |
| **9. Qualidade, Testes, Contratos & Caos** | `especialista-qualidade`, `estrategia-testes-aws`, `contrato-reverso`, `testes-carga-desempenho-aws`, `testes-resiliencia-caos-aws`, `testes-infra-iac-aws` | `sonnet` | Pirâmide TDD/BDD, Testcontainers, testes reversos dirigidos pelo consumidor (CDC), k6/Locust e engenharia de caos com AWS FIS. |
| **10. Segurança, DevOps & Observabilidade** | `engenheiro-seguranca`, `testes-seguranca-aws`, `auditoria-skill-externa`, `validacao-veracode`, `engenheiro-iac`, `logs-observabilidade`, `dd-apm`, `dd-logs`, `dd-monitors`, `trace2local` | `opus` / `sonnet` | Acionado **automaticamente** em qualquer diff de auth/input/queries/cripto/secrets; Terraform gated, logs estruturados sem vazamento de PII e APM Datadog/Local. |

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
