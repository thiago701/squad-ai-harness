# Step 2 — Discovery e Design

## Fase 1 — DISCOVERY (DDD + BDD)

### Objetivo

Transformar o problema de negócio em **modelo de domínio rico** (DDD tático) + **user stories executáveis** (BDD) + **DBML coerente**.

### 1. Ativar Engenheiro de Especificação

```
Instruções para engenheiro-especificacao:
  - Leia SKILL.md da própria skill e references/ddd-guide.md da squad
  - Aplique o Protocolo de Levantamento de Requisitos
  - Modele em DDD:
      □ Identifique Bounded Contexts (um por linha de negócio)
      □ Identifique Aggregates e seus Roots em cada contexto
      □ Identifique Value Objects candidatos (todo conceito com identidade
        por valor: Email, Money, CPF, DocumentNumber, Address, Quantity…)
      □ Liste invariantes que cada Aggregate deve proteger
      □ Identifique Domain Events (mudanças de estado relevantes)
      □ Produza a Linguagem Ubíqua (glossário) antes de qualquer código
  - Salve em artefatos/fase-1-discovery/
```

### 2. Entregas Obrigatórias

`artefatos/fase-1-discovery/`:

```
├── user-stories.md              → INVEST + BDD Given-When-Then (3+ cenários por story)
├── bounded-contexts.md          → Contextos, suas linguagens, context map
├── modelo-dominio.md            → Aggregates, Value Objects, Entities, Events
├── invariantes.md               → Lista de invariantes por aggregate (rastreáveis)
├── modelo-dados.dbml            → DER em DBML — fonte de verdade do esquema
├── regras-negocio.md            → Classificadas (RN-restrição, RN-derivação, RN-ação, RN-permissão)
├── diagrama-c4-contexto.md      → C4 Nível 1
├── requisitos-nao-funcionais.md → SLAs, volumetria, disponibilidade, segurança (com números)
└── glossario.md                 → Linguagem ubíqua completa
```

### 3. Template de Aggregate (obrigatório em modelo-dominio.md)

Para cada aggregate identificado:

```
AGGREGATE: Pedido (Bounded Context: pedidos)
  Root:          Pedido
  Identidade:    PedidoId (Value Object)
  Entities:      [ItemPedido]
  Value Objects: [Money, Quantidade, PedidoStatus]
  Invariantes:
    I1: Pedido não pode ter status CONFIRMADO sem pelo menos 1 item
    I2: Valor total = Σ (item.preco × item.quantidade) sempre
    I3: Uma vez CONFIRMADO, itens não podem ser removidos
    I4: Cliente ativo é obrigatório para criação
  Comandos:      [CriarPedido, AdicionarItem, ConfirmarPedido, Cancelar]
  Eventos:       [PedidoCriado, ItemAdicionado, PedidoConfirmado, PedidoCancelado]
  Regras:        RN-012, RN-013, RN-014
```

### 4. Gatekeeping Discovery → Design

```
CHECKLIST
  □ User stories atendem Definition of Ready (DoR)
  □ ≥ 3 cenários BDD por story (happy + sad + edge)
  □ Bounded contexts identificados e justificados
  □ Todo aggregate tem invariantes listadas (≥ 1)
  □ Todo Value Object candidato tem regra de validação explícita
  □ Domain Events cobrem mudanças de estado relevantes
  □ DBML coerente com o modelo DDD (tabelas refletem agregados)
  □ Linguagem ubíqua completa e consistente
  □ NFRs com números (não "rápido", "seguro" — use "p95 < 200ms", "OWASP Top 10")
  □ Tech Lead validou viabilidade técnica
```

Se algum item falhar: notificar Especificador, estado `EM_REVISÃO`, aguardar correção.

```bash
python .agent/skills/squad-ai/scripts/squad_manager.py comunicado_geral \
  "squad-ai" "Discovery concluída. Iniciando Design."
```

---

## Fase 2 — DESIGN (Arquitetos)

### Objetivo

Decidir a arquitetura mínima viável que materializa o modelo DDD da Fase 1 com CQRS+Outbox e Clean Architecture.

### 1. Ativar Arquitetos

**Sempre:** `arquiteto-minimalista` (lidera), `especialista-banco`.
**Conforme contexto:** `arquiteto-cloud-aws`, `arquiteto-performance`, `arquiteto-ia`.

Instruções:
```
  - Leiam artefatos de fase-1-discovery/
  - Leiam references/clean-architecture-java25.md, cqrs-outbox.md, cloud-native-aws.md
  - Proponham solução P1 > P2 > P3
  - Submetam plano de ação ao Condutor antes de entregar
  - Registrem decisões como ADRs em decisoes/
```

### 2. Consenso em 3 Rodadas (se múltiplos arquitetos)

```
Rodada 1 — Posicionamento:
  Cada arquiteto registra proposta + justificativa P1>P2>P3.

Rodada 2 — Refinamento:
  Condutor envia perguntas específicas aos divergentes.
  Respostas com evidências: benchmarks, custos, complexidade.

Rodada 3 — Decisão:
  Tech Lead arbitra conforme prioridades. ADR documenta decisão
  (consenso ou unilateral).
```

### 3. Entregas Obrigatórias

`artefatos/fase-2-design/`:

```
├── arquitetura-c4-container.md  → C4 Nível 2
├── stack-tecnologica.md         → Confirmação/justificativa da stack
├── estrutura-pacotes.md         → Layout Maven multi-module + Clean Arch
├── cqrs-outbox-design.md        → Commands, Queries, tabela outbox, relay
├── estrategia-persistencia.md   → DBML → JPA, Flyway, Aurora config
├── diagramas-sequencia.md       → Fluxos críticos (comando → aggregate → outbox → consumer)
├── slas-definidos.md            → SLAs por endpoint com números
├── estimativa-custo.md          → FinOps Aurora + compute (se aplicável)
└── testabilidade.md             → Como a arquitetura facilita TDD e ArchUnit
```

### 4. ADRs Obrigatórios

```
decisoes/
├── ADR-001-stack-java25-spring-boot4.md
├── ADR-002-clean-architecture-maven-multimodule.md
├── ADR-003-cqrs-inprocess-outbox.md
├── ADR-004-persistencia-aurora-flyway.md
├── ADR-005-ddd-tatico-aggregates-vos.md
└── ADR-006-testes-testcontainers-archunit.md
```

Cada ADR segue template: Contexto / Decisão / Alternativas Consideradas / Consequências / Métrica de Sucesso.

### 5. Estrutura de Pacotes Canônica (já decidida, apenas materializar no design)

```
<artifactId>/
├── pom.xml (agregador, packaging=pom)
├── domain/
│   └── src/main/java/<pkg>/domain/
│       ├── <context>/model/         → Aggregate Roots, Entities
│       ├── <context>/vo/            → Value Objects validados
│       ├── <context>/event/         → Domain Events
│       └── common/                  → DomainException, base classes
├── application/
│   └── src/main/java/<pkg>/application/
│       ├── <context>/command/       → Commands + Handlers
│       ├── <context>/query/         → Queries + Handlers
│       └── <context>/port/          → Ports (interfaces) para adapters
├── infrastructure/
│   └── src/main/java/<pkg>/infrastructure/
│       ├── persistence/             → JPA Entities, Repositories, Mappers
│       ├── outbox/                  → OutboxEntity, Relay
│       ├── rest/                    → Controllers, DTOs, ExceptionHandler
│       ├── messaging/               → Consumers de eventos
│       └── config/                  → @Configuration adapters
└── bootstrap/
    └── src/main/java/<pkg>/
        ├── Application.java         → @SpringBootApplication
        └── config/                  → wiring, beans globais
```

### 6. Gatekeeping Design → Build

```
CHECKLIST
  □ Arquitetura mínima viável (arquiteto-minimalista assinou)
  □ Stack confirmada por ADR
  □ C4 Container completo
  □ Design CQRS+Outbox: tabela outbox_events definida, relay escolhido
  □ Estrutura de pacotes materializando Clean Architecture
  □ Domínio demonstravelmente testável sem Spring/JPA (ArchUnit rules prontas)
  □ DBML compatível com estratégia JPA/Flyway
  □ SLAs definidos com números (p95, p99, RPS)
  □ Estimativa de custo (se aplicável)
  □ Consenso entre arquitetos ou decisão do Tech Lead registrada
  □ Zero decisões não-documentadas
```

### 7. Guias complementares (progressive disclosure)

- `../references/system-design-guide.md` — **framework de 5 passos** (Requirements com números, High-Level em uma tela, Deep Dive em 2-3 partes críticas, Scale & Reliability com load estimation + failure modes, Trade-offs com Opção C obrigatória). Use quando a feature cria novo Bounded Context ou redesign de módulo existente.
- `../references/minimalist-toolkit.md` — aplicar **4 perguntas do Advogado do Diabo** antes de aceitar arquitetura complexa. Nomear antipadrões quando identificados (Distributed Monolith, Abstração Prematura, Integração por Banco, etc.).
- `../references/testing-strategy.md` — checklist de test plan por feature nova (unit/component/integration/contract/chaos). Decidir **antes** do build quais tipos de teste a feature demanda.
- `../references/adr-guide.md` — formalizar as decisões do design via ADR com gatilhos + Opção C = status quo obrigatória.

### 8. Próximo Step

`./step-03-build.md`
