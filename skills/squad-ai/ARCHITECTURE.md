# Squad AI v2 — Arquitetura da Squad Multi-Agente

## Visão Geral

A Squad AI v2 é uma squad completa de agentes seniores para construir sistemas modernos em **Java 25 + Spring Boot 4 / Spring Framework 7**, com **DDD forte**, **CQRS in-process + Outbox**, **Clean Architecture**, **Cloud Native AWS (Aurora PostgreSQL default)** e **testes robustos (unitários + Testcontainers)**. A squad entrega do Discovery ao Deliver com gatekeeping por evidência e ADRs rastreáveis.

---

## Princípios Fundamentais

1. **Especialização real** — cada agente tem skill dedicada; não há sobreposição de papéis.
2. **Fases do SDLC explícitas** — Discovery → Design → Build → Test → Review → Deliver, com critérios de entrada e saída mensuráveis.
3. **Gatekeeping orientado a evidências** — checklists por fase com métricas objetivas (cobertura, ArchUnit, OWASP, SLAs, aderência DDD).
4. **Colaboração formalizada** — pares naturais de agentes, handoffs via `artefatos/`, consenso técnico estruturado.
5. **Rastreabilidade** — ADRs padronizados, artefatos por fase, métricas de TDD e DDD registradas automaticamente.
6. **DDD é arquitetura, não decoração** — Value Objects validam, Aggregates protegem invariantes, Bounded Contexts explícitos.
7. **TDD é método, não documentação** — RED → GREEN → REFACTOR com rastreio de violações.

---

## Stack Alvo (padrão fixo da squad)

| Camada | Tecnologia |
|---|---|
| Linguagem | Java 25 (Virtual Threads, Structured Concurrency JEP 505, Scoped Values JEP 506, Pattern Matching, Sealed/Records) |
| Framework | Spring Boot 4.x, Spring Framework 7, Spring Security 7, Spring Data 2025.1 |
| Persistência | **Aurora PostgreSQL** + Hibernate 7.1 + Flyway |
| Build | Apache Maven 4 (model 4.1.0, mvnd, Build Cache Extension, Consumer POM) |
| Mensageria | Transactional Outbox (tabela `outbox_events`) + relay (poller Spring ou Debezium) |
| Testes | JUnit 5.11+, AssertJ, Mockito, Testcontainers 2.0, ArchUnit |
| Observabilidade | OpenTelemetry (OTLP) + Micrometer + JSON structured logging |
| Container | Docker multi-stage (ZGC Generational); IaC neutro (Terraform/CDK a critério do time) |

Qualquer desvio exige ADR justificado sob P1 > P2 > P3.

---

## Arquitetura da Squad

```
┌───────────────────────────────────────────────────────────────────────────┐
│                         SQUAD AI v2 (Condutor)                            │
│  Orquestra fases, gatekeeping, métricas DDD/TDD, mensageria, ADRs         │
└───┬──────────┬───────────┬──────────┬──────────┬──────────┬──────────────┘
    │          │           │          │          │          │
    ▼          ▼           ▼          ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌──────────┐ ┌──────┐ ┌────────┐ ┌───────────┐
│DISCOVERY│ │ DESIGN │ │  BUILD   │ │ TEST │ │ REVIEW │ │  DELIVER  │
│        │ │        │ │          │ │      │ │        │ │           │
│ Espec. │ │Arq.Min.│ │Java25/SB4│ │Qual. │ │TechLead│ │DevOps     │
│        │ │Arq.AWS │ │Clean Arch│ │Seg.  │ │        │ │LocalStack │
│ DDD    │ │Arq.Perf│ │DBA       │ │Perf. │ │        │ │           │
│ BDD    │ │Arq.IA  │ │DevOps    │ │      │ │        │ │           │
└────────┘ └────────┘ └──────────┘ └──────┘ └────────┘ └───────────┘
```

### Os 14 Agentes

| # | Agente | Fase Principal | Especialidade |
|---|---|---|---|
| 1 | **squad-ai** | Todas | Orquestração, gatekeeping, métricas, relatórios |
| 2 | **engenheiro-especificacao** | Discovery | Requisitos, user stories BDD, modelagem DDD, linguagem ubíqua, bounded contexts |
| 3 | **arquiteto-minimalista** | Design | Arquitetura mínima viável, combate à complexidade acidental |
| 4 | **arquiteto-cloud-aws** | Design | AWS Aurora-first, FinOps, custo otimizado |
| 5 | **arquiteto-ia** | Design + Build | Agentes de IA, LLMs, RAG, guardrails (quando aplicável) |
| 6 | **arquiteto-performance** | Design + Test | Latência, throughput, SLAs, profiling com JFR |
| 7 | **java25-spring-boot** | Build | Java 25, Spring Boot 4, Virtual Threads, Structured Concurrency, Scoped Values, JdbcClient, @HttpExchange |
| 8 | **engenheiro-clean-architect** | Build | SOLID, Clean Architecture, implementação do GREEN/REFACTOR no TDD |
| 9 | **engenheiro-devops** | Build + Deliver | CI/CD, Docker, observabilidade, deploy |
| 10 | **engenheiro-seguranca** | Test | OWASP Top 10, autenticação, auditoria, AI safety |
| 11 | **especialista-qualidade** | Test | RED do TDD, Testcontainers, mutation testing, pirâmide |
| 12 | **tech-lead-review** | Review | Code review 🔴🟡🔵⚪, validação DDD e TDD, consenso, ADRs |
| 13 | **especialista-banco** | Build + Test | DBML-first, JPA, Outbox, CQRS read model, CDC, migrações sem downtime |
| 14 | **localstack-dev** | Deliver | AWS 100% local com Docker Compose + Spring `@Profile` dev/prod |

### Pares Naturais de Colaboração

```
engenheiro-especificacao   ↔  tech-lead-review          (refinamento de requisitos + DDD)
arquiteto-minimalista      ↔  arquiteto-cloud-aws        (stack + custo)
arquiteto-performance      ↔  especialista-qualidade     (SLAs + testes de carga)
java25-spring-boot         ↔  engenheiro-clean-architect (Virtual Threads + Clean Arch)
engenheiro-clean-architect ↔  especialista-qualidade     (pair TDD)
engenheiro-devops          ↔  engenheiro-seguranca       (pipeline seguro)
arquiteto-ia               ↔  engenheiro-seguranca       (guardrails + AI safety)
especialista-banco         ↔  arquiteto-cloud-aws        (Aurora + CDC + Outbox)
especialista-banco         ↔  especialista-qualidade     (Testcontainers + migrations)
localstack-dev             ↔  engenheiro-devops          (paridade dev/prod)
```

---

## Os 5 Pilares Arquiteturais (+ TDD como método)

### Pilar 1 — DDD Forte

- Value Objects que **validam no construtor** (compact constructor em records).
- Aggregate Roots que **protegem invariantes** e são a única porta de mutação.
- Domain Events como records em `sealed interface`.
- Bounded Contexts com pacotes separados e (idealmente) schemas lógicos distintos.
- Linguagem ubíqua no código — nomes ecoam o glossário de negócio.

Referência: `references/ddd-guide.md`.

### Pilar 2 — Clean Architecture

Maven multi-module com dependências apontando para dentro:

```
bootstrap → infrastructure → application → domain
```

- `domain/` não importa `jakarta.*`, `org.springframework.*`, `org.hibernate.*`, `software.amazon.*`.
- Validado em CI via **ArchUnit** (`layeredArchitecture`).

Referência: `references/clean-architecture-java25.md`.

### Pilar 3 — CQRS in-process + Outbox

- Commands mudam estado e emitem Domain Events persistidos na **mesma transação** em `outbox_events`.
- Queries lêem do read model via `JdbcClient` (sem reidratar aggregate).
- Relay (poller Spring ou Debezium) publica eventos para consumers externos.
- Consumers são **idempotentes** (chave = `event_id`).

Referência: `references/cqrs-outbox.md`.

### Pilar 4 — Cloud Native + AWS

- 12-factor em cada config (env, logs JSON em stdout, stateless).
- Aurora PostgreSQL (Serverless v2 quando carga é irregular; IAM auth quando possível).
- Dockerfile multi-stage (JDK 25 → JRE slim) ou GraalVM Native quando cold start é crítico.
- OpenTelemetry, health probes separados (liveness ≠ readiness), graceful shutdown.
- IaC neutro — ECS Fargate / App Runner / Lambda / EKS a critério do time via ADR.

Referência: `references/cloud-native-aws.md`.

### Pilar 5 — Testes Robustos

Pirâmide 60/20/15/5:

| Nível | % | Ferramenta |
|---|---|---|
| Unit (domínio puro + application com mocks) | 60% | JUnit 5, AssertJ, Mockito |
| Integration (Postgres real + Outbox + REST) | 20% | Testcontainers 2.0 + `@ServiceConnection` |
| BDD / Acceptance | 15% | Cucumber ou JUnit + AssertJ |
| E2E (opcional) | 5% | RestAssured / Karate |

Obrigatórios no gate: unit + integration + ArchUnit. Extensões via ADR: PIT, jqwik, Pact, k6/Gatling.

Referência: `references/testing-guide.md`.

### Método — TDD

Nenhuma linha de código de produção sem teste vermelho primeiro. Violações são rastreadas em `metricas/tdd_compliance.json` nos tipos `CODIGO_SEM_TESTE_PREVIO`, `TESTE_NAO_FALHOU`, `REFACTOR_COM_TESTE_VERMELHO`, `COMMIT_GRANDE`.

---

## As 6 Fases do SDLC

### Fase 1 — Discovery
**Líder:** engenheiro-especificacao
**Entregas:** User stories BDD, modelo DDD (aggregates, VOs, eventos, invariantes), bounded contexts, linguagem ubíqua, C4 contexto, NFRs com números, DBML coerente.
**Gate:** DoR atendido; ≥ 3 cenários BDD por story; aggregates identificados; invariantes listadas.

### Fase 2 — Design
**Líder:** arquiteto-minimalista (com consenso dos demais arquitetos)
**Entregas:** C4 Container, estrutura de pacotes Clean Architecture, estratégia CQRS+Outbox, persistência Aurora+Flyway, SLAs por endpoint, ADRs.
**Gate:** Consenso, ADRs aprovados, P1>P2>P3 respeitado, domínio demonstravelmente testável sem infraestrutura.

### Fase 3 — Build
**Líder:** engenheiro-clean-architect (em pair TDD com especialista-qualidade)
**Entregas:** Projeto Maven multi-module gerado via `scripts/generate_project.py`, domínio rico, use cases, infraestrutura, Flyway migrations, Dockerfile, compose, CI.
**Gate:** Compila; testes unitários verdes; cobertura ≥ 80% no domínio; ArchUnit verde; pipeline green; tdd_compliance.json sem violações.

### Fase 4 — Test
**Líder:** especialista-qualidade (com segurança e performance)
**Entregas:** Integração Testcontainers cobrindo repos/outbox/controllers/migrations; auditoria OWASP; SLAs p95/p99 validados.
**Gate:** Pirâmide respeitada; zero vulnerabilidades críticas; Testcontainers estável no CI (< 2% flakiness).

### Fase 5 — Review
**Líder:** tech-lead-review
**Entregas:** Review 🔴🟡🔵⚪, verificação P1/P2/P3 + DDD + TDD, consenso, tech debt.
**Gate:** Zero 🔴; zero 🟡 abertos; DoD completo; aderência DDD e TDD confirmada.

### Fase 6 — Deliver
**Líder:** engenheiro-devops
**Entregas:** Deploy configurado, observabilidade, runbook, rollback plan, relatório final com métricas DDD/TDD.
**Gate:** Sistema pronto para produção; probes verdes; rollback testado.

---

## Infraestrutura de Comunicação

```
.agent/skills/squad-ai/.antigravity/equipe/
├── registro_atividades.json    → Atividades com fase, estado, deps, notas
├── caixa_entrada/              → Mensagens diretas 1-a-1 (.msg)
├── aviso_geral.msg             → Broadcast do Condutor
├── travas/                     → Semáforos (.lock) para edição concorrente
├── decisoes/                   → ADRs (preservados entre projetos)
├── artefatos/                  → Entregas por fase
│   ├── fase-1-discovery/
│   ├── fase-2-design/
│   ├── fase-3-build/
│   ├── fase-4-test/
│   ├── fase-5-review/
│   └── fase-6-deliver/
└── metricas/
    ├── tdd_compliance.json     → Violações de TDD
    └── ddd_compliance.json     → Violações de DDD (VO não validado, setter em aggregate, etc.)
```

---

## Squad Manager — Comandos

| Comando | Descrição |
|---|---|
| `iniciar` | Prepara toda a infraestrutura |
| `limpar` | Limpa para novo projeto (preserva ADRs) |
| `criar_atividade` | Registra atividade com fase e dependências |
| `atualizar_estado` | Atualiza estado (8 estados possíveis) |
| `listar [fase]` | Lista atividades com filtro |
| `avancar_fase` | Avança se critérios da fase atual estão OK |
| `status_fase` | Mostra progresso da fase atual |
| `comunicado_geral` | Broadcast para toda a squad |
| `mensagem_direta` | Mensagem 1-a-1 entre agentes |
| `ler_mensagens` | Lê caixa de entrada |
| `validar_skills` | Verifica existência das skills |
| `registrar_metricas` | Registra indicadores |
| `relatorio` | Gera relatório completo |
| `travar` / `destravar` | Gerencia semáforos |

---

## Scaffold Generator

Para acelerar a Fase 3, a squad inclui `scripts/generate_project.py`:

```bash
python .agent/skills/squad-ai/scripts/generate_project.py \
    --name pedidos-api \
    --group-id com.example \
    --base-package com.example.pedidos \
    --contexts "pedidos,pagamentos" \
    --output ./
```

Entrega completa: Maven 4 multi-module, domínio DDD exemplar (Aggregate + VO + Event), CQRS handlers, Outbox table + relay + adapter, Flyway V1+V2, Dockerfile multi-stage, docker-compose, CI (`.github/workflows/ci.yml`), Testcontainers integration + ArchUnit. Detalhes em `references/project-generator.md`.

---

## Três Prioridades Imutáveis

```
P1 — SIMPLICIDADE NO CÓDIGO
    Legível em < 10 min por qualquer engenheiro do time.

P2 — PERFORMANCE
    SLAs cumpridos sob carga real.
    Dev environment leve: startup rápido, build incremental em segundos.
    Otimize apenas onde há evidência.

P3 — BAIXO CUSTO CLOUD
    Cada real de infraestrutura com retorno mensurável.
    Rightsizing antes de escalar.

REGRA DE DESEMPATE: P1 > P2 > P3 (sempre)
```

---

## Como Usar

### Projeto novo do zero
```
"Squad AI, prepare a equipe para o projeto [NOME].
Escopo: [API REST / worker / job] com [contextos].
Requisito de negócio: [descrição].
Modo: sequencial."
```

### Intervenção pontual
```
"Squad AI, execute apenas a fase [FASE] com [AGENTES]."
```

### Auditoria
```
"Squad AI, execute auditoria DDD + segurança + qualidade."
```

---

## Adoção Corporativa

A Squad AI é **agnóstica de empresa e domínio**. Basta clonar `squad-ai-harness/`, configurar IDE/agente e invocar `iniciar`. Não há dependência de serviços internos, naming proprietário ou conhecimento tácito — tudo está documentado em skills versionáveis e referências técnicas profundas carregadas por disclosure progressivo.

> Frase de invocacao: o orquestrador e acionado por 'Squad AI, prepare a equipe' (id squad-ai).
