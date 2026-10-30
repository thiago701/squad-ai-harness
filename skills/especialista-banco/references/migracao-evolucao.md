# Referência — Migração e Evolução de Schema (refactorings sem downtime, Outbox, Temporal, CQRS, CDC)

> Parte da skill `especialista-banco`. Carregue sob demanda. Hub: `../SKILL.md`.
## 7. Refactorings de Schema Sem Downtime

### 7.1 Expand-Contract (Renome de Coluna)

```
FASE 1 — EXPAND (V10)
  ALTER TABLE x ADD COLUMN novo_nome VARCHAR(100);
  UPDATE x SET novo_nome = nome_antigo;          -- backfill em lotes
  CREATE TRIGGER sync_x ON x ...                 -- dual-write transparente
  -- App lê ambas, escreve ambas

FASE 2 — MIGRAÇÃO APP (V10.b, deploy)
  App passa a ler/escrever só `novo_nome`

FASE 3 — CONTRACT (V11, após rollout 100%)
  DROP TRIGGER sync_x;
  ALTER TABLE x DROP COLUMN nome_antigo;
```

### 7.2 Blue-Green Schema Migration

- V{N}: adiciona nova tabela com schema alvo
- App dual-write (escreve em ambas via `@Transactional`)
- Backfill em background (Spring Batch ou jobs)
- Cutover de leitura com feature flag
- V{N+k}: dropa tabela antiga

### 7.3 Splits de Normalização

Detectar anomalia no DBML atual e propor o split antes do PR:

```
❌ Antes (viola 3NF — dependência transitiva):
  usuarios(id, email, departamento_id, departamento_nome)

✅ Depois (3NF):
  usuarios(id, email, departamento_id)
  departamentos(id, nome UNIQUE)
```

Migration segura:

```sql
-- V12__split_departamentos.sql
CREATE TABLE departamentos AS
  SELECT DISTINCT departamento_id AS id, departamento_nome AS nome FROM usuarios;
ALTER TABLE departamentos ADD PRIMARY KEY (id);
ALTER TABLE usuarios ADD CONSTRAINT fk_usuarios_dept
  FOREIGN KEY (departamento_id) REFERENCES departamentos(id);
-- V12.1 (após deploy) drop da coluna redundante
```

---

## 9. Padrões Avançados

### 9.1 Outbox Pattern (commit atômico entidade + evento)

Ver [[Outbox Pattern]]. DBML:

```dbml
Table outbox_events {
  id            uuid        [pk, default: `gen_random_uuid()`]
  aggregate_id  uuid        [not null]
  aggregate_type varchar(50)[not null]
  event_type    varchar(100)[not null]
  payload       jsonb       [not null]
  created_at    timestamptz [not null, default: `now()`]
  processed_at  timestamptz [null]

  indexes {
    (processed_at) [name: 'idx_outbox_pending', note: 'WHERE processed_at IS NULL']
    (aggregate_id, created_at)
  }
}
```

### 9.2 Temporal Tables (histórico de mudanças)

Opção A — coluna de período (PostgreSQL + range types):

```sql
CREATE TABLE coordenadorias_history (
    id UUID, nome VARCHAR(100), regiao VARCHAR(50),
    valid_period TSTZRANGE NOT NULL,
    EXCLUDE USING gist (id WITH =, valid_period WITH &&)
);
```

Opção B — tabela paralela `_audit` populada por trigger AFTER UPDATE.

### 9.3 CQRS Read Model

DBML do write side permanece normalizado. Read model é view materializada ou projeção em OpenSearch/Redis:

```sql
CREATE MATERIALIZED VIEW circuito_summary AS
SELECT c.id, c.nome, COUNT(p.id) AS total_palestras, MAX(p.data) AS proxima
FROM circuitos c LEFT JOIN palestras p ON p.circuito_id = c.id
GROUP BY c.id, c.nome;

CREATE UNIQUE INDEX ON circuito_summary (id);
REFRESH MATERIALIZED VIEW CONCURRENTLY circuito_summary;
```

### 9.4 Change Data Capture (CDC)

- **PostgreSQL logical replication** → Debezium → Kafka/Kinesis → consumidores
- **DynamoDB Streams** → Lambda → projeções
- **MongoDB Change Streams** → consumidores Reactive

---

