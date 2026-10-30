# Referência — Workflows da Skill + Checklist P1.DB (DBML novo, evolução, engenharia reversa, decisão RDBMS↔NoSQL)

> Parte da skill `especialista-banco`. Carregue sob demanda. Hub: `../SKILL.md`.
## 13. Workflows da Skill

### 13.1 Workflow A — DBML novo a partir de requisitos

```
Input:  Descrição do domínio + user stories
Passos:
  1. Identificar agregados ([[Aggregate Root]]) — um por `TableGroup`
  2. Listar atributos obrigatórios e opcionais
  3. Definir relacionamentos + cardinalidade
  4. Rascunhar DBML em `db/schema.dbml`
  5. Validar normalização (1NF → 3NF mínimo)
  6. Inserir convenções canônicas (audit, version, soft delete)
  7. Gerar migration Flyway V1
  8. Gerar JPA entities + Domain entities + Mappers
  9. Gerar testes de coerência
  10. Abrir PR com checklist P1.DB
Output: db/schema.dbml + src/main/resources/db/migration/V1__init.sql + entities + mappers + testes
```

### 13.2 Workflow B — Evolução do DBML (rename/add/split)

```
Input:  DBML atual + requisição de mudança
Passos:
  1. Classificar: Additive / Renomeio / Split / Drop
  2. Escolher estratégia:
     - Additive       → V{N} simples
     - Renomeio       → Expand-Contract (2 PRs)
     - Split          → Expand-Migrate-Contract (3 PRs)
     - Drop           → Deprecation period + V{N+k}
  3. Atualizar db/schema.dbml (comentar campos deprecados, nunca deletar abruptamente)
  4. Gerar migration(s) Flyway
  5. Atualizar JPA + Mapper + Domain
  6. Atualizar testes
  7. Documentar no ADR (tech-lead-review)
Output: DBML atualizado + migrations + código + ADR
```

### 13.3 Workflow C — Engenharia Reversa DDL/Power Designer → DBML

```
Input:  DDL SQL, .pdm XML, screenshot
Passos:
  1. Parse (XML para Power Designer; regex/antlr para DDL; OCR+heurísticas para imagem)
  2. Normalizar para AST
  3. Emitir db/schema.dbml canônico (com convenções da squad)
  4. Alertar anomalias (tabelas sem PK, 3NF violada, FKs sem índice)
  5. Sugerir refactorings (ver seção 7)
Output: db/schema.dbml + relatório de anomalias
```

### 13.4 Workflow D — Decisão RDBMS ↔ NoSQL

```
Input:  Caso de uso (access patterns, SLA, escala, consistência)
Passos:
  1. Preencher matriz da seção 6.1
  2. Calcular custo aproximado (RCU/WCU DynamoDB vs RDS t4g; storage vs IOPS)
  3. Verificar com [[arquiteto-minimalista]] (anti-overengineering)
  4. Validar com [[arquiteto-cloud-aws]] (FinOps)
  5. Produzir ADR com decisão + justificativa
  6. Se NoSQL: modelar em DBML-extension com Notes (seção 6.2)
Output: ADR + schema (DBML ou notação NoSQL)
```

---

## 14. Checklist P1.DB (para tech-lead-review)

Ao revisar qualquer PR que mexe em persistência:

- [ ] `db/schema.dbml` foi atualizado primeiro (git log mostra a ordem)?
- [ ] Migration Flyway tem nome sequencial, descritivo e idempotente quando possível?
- [ ] JPA Entity reflete o DBML coluna-por-coluna?
- [ ] Domain Entity **não** tem anotações JPA?
- [ ] Mapper Domain↔JPA existe e é testado round-trip?
- [ ] FKs têm índice?
- [ ] UNIQUE constraints refletidos em `@UniqueConstraint`?
- [ ] Audit columns (`created_at`, `updated_at`) e `version` presentes?
- [ ] Soft delete coerente (coluna + `@SQLRestriction`)?
- [ ] `spring.jpa.hibernate.ddl-auto=validate` no properties?
- [ ] Teste de coerência em `CoerenciaSchemaTest` passa?
- [ ] Sem `SELECT *` fora de projeções explícitas?
- [ ] Paginação em listagens (evitar OOM)?
- [ ] Queries críticas têm índice sustentando (EXPLAIN anexado no PR)?
- [ ] Refactoring não-aditivo segue expand-contract (sem downtime)?
- [ ] PII com `@Sensitive` + redação em logs?

---

