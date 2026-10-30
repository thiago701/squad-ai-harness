# Referência — Modelagem Relacional + DBML-First (Propósito, Stack, DBML, Power Designer/MER, Performance, Referências)

> Parte da skill `especialista-banco`. Carregue sob demanda. Hub: `../SKILL.md`.
## 1. Propósito

Projetar, revisar e evoluir modelos de dados de ponta a ponta, dominando tanto o mundo **relacional** (OLTP/OLAP, ACID, SQL:2023) quanto o **não-relacional** (key-value, document, wide-column, graph, vector, search), sempre com **DBML (dbdiagram.io)** como fonte de verdade sincronizada com a implementação Java 25 + Spring Boot 4.

A skill entrega:

- **DBML canônico** (fonte de verdade versionada em `db/schema.dbml`)
- **Implementação Java avançada** gerada determinísticamente a partir do DBML (JPA entities, Domain entities, Mappers, Repositories, Flyway migrations, testes de coerência)
- **Refactorings de schema sem downtime** (expand-contract, blue-green, shadow tables)
- **Decisão fundamentada RDBMS ↔ NoSQL** por caso de uso (padrão de acesso, consistência, escala)
- **Read models e CQRS** (materialized views, projeções DynamoDB/OpenSearch, Redis)
- **Engenharia reversa** de DDL/Power Designer/imagens para DBML

---

## 3. Stack de Referência

| Camada | Tecnologia |
|--------|-----------|
| Fonte de verdade do schema | **DBML 2.x** ([dbdiagram.io](https://dbdiagram.io)) em `db/schema.dbml` |
| RDBMS primário (OLTP) | **PostgreSQL 16+** / Aurora PostgreSQL (PITR, logical replication, PGVector) |
| RDBMS alternativos | MySQL 8.4 LTS / Aurora MySQL, Oracle 23ai, SQL Server 2022 |
| NoSQL document | **MongoDB 7** / DocumentDB, **DynamoDB** (single-table + GSI) |
| NoSQL key-value / cache | **Redis 7.4** / ElastiCache / Valkey / DynamoDB DAX |
| NoSQL wide-column | Cassandra 5 / ScyllaDB / Keyspaces |
| NoSQL graph | Neo4j 5 / Neptune |
| Search engine | **OpenSearch 2.x** / Elasticsearch 8.x |
| Vector store | **PGVector** (PostgreSQL) / OpenSearch k-NN / DynamoDB + Bedrock Knowledge Bases |
| Migrations | **Flyway 10** (padrão) / Liquibase 4.x |
| CDC / Streaming | Debezium + Kafka / DynamoDB Streams + Lambda / PostgreSQL logical replication |
| ORM/Access | **JPA 3.2 / Hibernate 7.1**, Spring Data JDBC 4, jOOQ 3.20, Spring Data MongoDB 5, AWS SDK v2 Enhanced DynamoDB Client |
| Testes | Testcontainers 2.0 (Postgres, Mongo, Redis, LocalStack DynamoDB) |

---

## 4. DBML-First: Regras do Jogo

### 4.1 Fluxo Canônico de Mudança (imutável)

```
    1. Alterar db/schema.dbml         ← fonte de verdade
           ↓
    2. Gerar/revisar migration Flyway  ← V{N}__descricao.sql
           ↓
    3. Atualizar JPA Entity            ← espelha DBML fielmente
           ↓
    4. Atualizar Mapper                ← Domain ↔ JPA
           ↓
    5. Testes de coerência             ← DBML ↔ migration ↔ JPA
           ↓
    6. Code review P1.DB               ← tech-lead-review verifica
```

**Proibido**:

- `spring.jpa.hibernate.ddl-auto=update` em qualquer ambiente (usar `validate`)
- Alterar JPA Entity sem atualizar o DBML primeiro
- Criar migration Flyway sem o DBML refletir a mudança
- Expor JPA Entity fora do pacote `adapter/out/persistence/`

### 4.2 Estrutura DBML Canônica

```dbml
// =======================================================================
// schema.dbml — Fonte de verdade do modelo de dados
// Projeto: <nome>
// Versão:  2026.04.0
// Dialeto alvo: PostgreSQL 16
// =======================================================================

Project "circuito-palestras" {
  database_type: 'PostgreSQL'
  Note: '''
    Domínio: Gestão de circuitos de palestras.
    Convenções: snake_case, PK UUID v7, audit columns obrigatórias,
    soft delete via coluna `deleted_at`, timestamps com timezone.
  '''
}

// ---------- Domínios reutilizáveis (emulados via comentários) ----------
// DOMAIN uuid_pk        = uuid [pk, default: `gen_random_uuid()`]
// DOMAIN audit_at       = timestamptz [not null, default: `now()`]
// DOMAIN audit_user     = varchar(100) [not null, default: 'system']

Table coordenadorias {
  id          uuid          [pk, default: `gen_random_uuid()`, note: 'UUID v7 preferencial']
  nome        varchar(100)  [not null]
  regiao      varchar(50)   [not null]
  created_at  timestamptz   [not null, default: `now()`]
  updated_at  timestamptz   [not null, default: `now()`]
  deleted_at  timestamptz   [null, note: 'Soft delete']
  version     bigint        [not null, default: 0, note: 'Optimistic locking']

  indexes {
    (regiao)                       [name: 'idx_coordenadorias_regiao']
    (nome)                         [unique, name: 'uk_coordenadorias_nome']
    (deleted_at)                   [name: 'idx_coordenadorias_deleted_at', note: 'Filtro partial']
  }

  Note: 'Aggregate Root. Todos os acessos passam pelo CoordenadoriaRepository.'
}

Table instituicoes {
  id               uuid         [pk, default: `gen_random_uuid()`]
  coordenadoria_id uuid         [not null, ref: > coordenadorias.id]
  nome             varchar(100) [not null]
  status           varchar(20)  [not null, default: 'ATIVA', note: 'Enum: ATIVA|INATIVA|SUSPENSA|CANCELADA']
  created_at       timestamptz  [not null, default: `now()`]
  updated_at       timestamptz  [not null, default: `now()`]
  version          bigint       [not null, default: 0]

  indexes {
    (coordenadoria_id)           [name: 'idx_instituicoes_coordenadoria_id']
    (nome)                       [unique, name: 'uk_instituicoes_nome']
    (status, created_at)         [name: 'idx_instituicoes_status_created_at', note: 'Cobertura para listagem paginada']
  }
}

Ref fk_instituicoes_coordenadoria: instituicoes.coordenadoria_id > coordenadorias.id [delete: restrict, update: cascade]

// ---------- Enum documental (hoje VARCHAR + CHECK; migração para enum nativo em V37) ----------
Enum status_instituicao {
  ATIVA
  INATIVA
  SUSPENSA
  CANCELADA
}

TableGroup aggregate_coordenadoria {
  coordenadorias
  instituicoes
}
```

### 4.3 Convenções Obrigatórias no DBML

| Convenção | Regra |
|-----------|-------|
| Nomes de tabelas | `snake_case`, plural em português (consistente com domínio) |
| PK | Sempre `id uuid [pk]` com `gen_random_uuid()` (preferência por UUID v7 quando suportado) |
| Audit columns | `created_at`, `updated_at` (timestamptz), opcional `created_by`, `updated_by` |
| Soft delete | Coluna `deleted_at timestamptz [null]` + índice parcial |
| Optimistic lock | Coluna `version bigint not null default 0` |
| FK | Sempre declarar com `ref: >` e definir `[delete]` / `[update]` explicitamente |
| Índices | FKs sempre indexadas, nomes com prefixo `idx_`/`uk_`/`pk_` |
| Enums | Declarar `Enum` mas persistir como `varchar` + `CHECK` (portabilidade) |
| TableGroup | Agrupar tabelas que formam um [[Aggregate Root]] |
| Notas | `Note` em tabelas/colunas críticas para preservar contexto de negócio |

---

## 8. Interpretação Legada: SAP Power Designer + Diagramas MER

(Absorvido de `power-designer-mer` — capacidade preservada.)

### 8.1 Formatos suportados

| Formato | Extensão | Propósito |
|---------|----------|-----------|
| CDM | `.cdm` | Modelo Conceitual |
| LDM | `.ldm` | Modelo Lógico |
| PDM | `.pdm` | Modelo Físico (tabelas, índices, FKs) |

Power Designer serializa em **XML**. Parsing extrai `Table`, `Column`, `Key`, `Relationship`, `Index`.

### 8.2 Pipeline: Power Designer / Imagem → DBML → Java

```
.pdm (XML) ─┐
.cdm (XML) ─┼─► Parser ─► AST normalizada ─► db/schema.dbml (output canônico)
screenshot ─┘                                     │
DDL SQL    ─┘                                     ▼
                                          Seções 4 e 5: JPA/Flyway/Testes
```

### 8.3 Notações Visuais Reconhecidas

- **Information Engineering (Crow's Foot)**: `├──` um, `├─<` muitos, `o──` opcional
- **IDEF1X**: PK→FK, linhas sólidas/tracejadas por dependência identificadora
- **Chen**: losangos para relacionamentos, elipses para atributos
- **Barker**: barras e círculos nas extremidades
- **UML Class Diagram**: `1`, `0..1`, `0..*`, `1..*`

### 8.4 Checklist de Validação de Normalização

- [ ] **1NF**: sem atributos multivalorados (nada como `telefones VARCHAR = "11...,12..."`)
- [ ] **2NF**: todos os atributos não-chave dependem da PK inteira
- [ ] **3NF**: sem dependências transitivas (se `A → B` e `B → C`, extrair `B`)
- [ ] **BCNF**: todo determinante é chave candidata
- [ ] Toda tabela tem PK
- [ ] Toda FK aponta para PK existente
- [ ] Sem ciclos de FK
- [ ] Índices em FKs e colunas UNIQUE
- [ ] Tipos apropriados (UUID vs BIGINT, VARCHAR com tamanho real, TIMESTAMPTZ em vez de TIMESTAMP)

---

## 12. Performance

- **Índices**: sempre para FKs, colunas de `WHERE` frequentes, `ORDER BY`, `JOIN`. Evitar > 5 índices por tabela em OLTP write-heavy
- **Índices parciais** (Postgres): `CREATE INDEX ... WHERE deleted_at IS NULL`
- **Covering indexes** (Postgres 11+): `INCLUDE (col1, col2)` para evitar heap lookup
- **Partitioning**: por `range(created_at)` para tabelas > 100M linhas ou time-series
- **Vacuum**: `autovacuum_vacuum_scale_factor=0.1` para tabelas grandes
- **Connection pool**: HikariCP pequeno com Virtual Threads (ver [[Virtual Threads vs HikariCP]])
- **Read replicas** para queries analíticas; write sempre no primary
- **Prepared statements**: `reWriteBatchedInserts=true` no JDBC Postgres

---

## 16. Referências e Recursos

### DBML
- DBML Spec: https://dbml.dbdiagram.io/docs/
- dbdiagram.io online editor
- `@dbml/core` CLI para export DBML → SQL

### SQL Standard e Dialetos
- PostgreSQL 16 docs, MySQL 8.4 LTS, Oracle 23ai, SQL Server 2022
- SQL:2023 features: PROPERTY_GRAPH, JSON path

### NoSQL
- AWS DynamoDB Developer Guide (single-table design by Rick Houlihan)
- MongoDB 7 schema design patterns
- Redis University: Data Structures

### Java/Spring Persistence
- Hibernate 7.1 User Guide
- Spring Data JDBC 4 reference
- Spring Data MongoDB 5
- AWS SDK v2 Enhanced DynamoDB Client

### Refactoring e Patterns
- "Refactoring Databases" — Ambler & Sadalage
- "Designing Data-Intensive Applications" — Kleppmann
- Microservices Patterns — Chris Richardson (Outbox, Saga, CQRS)

---

