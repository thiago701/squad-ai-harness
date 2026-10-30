# Rule 01 — DBML é a fonte da verdade do schema

Aplica-se a: qualquer arquivo sob `src/main/resources/db/migration/**`,
`src/main/java/**/infra/persistence/**` e qualquer query/DDL em código.

## Regra

Os arquivos em [`docs/dbml/`](../../docs/dbml/) descrevem **formalmente** o schema
relacional dos Bounded Contexts. Qualquer `@Entity` JPA, migration Flyway,
query nativa ou DDL precisa **casar 1:1 com o DBML correspondente**.

Bounded contexts do projeto: <CONTEXTS>.
Convenção de arquivos: `<SQUAD_PREFIX>-<DB_KIND>-<contexto>.dbml`.

## Comportamento obrigatório

1. **Antes de gerar** qualquer código que toque schema, leia o DBML
   correspondente em `docs/dbml/`.
2. **Se o schema necessário não existir** no DBML, pare e peça decisão
   explícita — não improvise.
3. **Se a mudança envolve schema**, siga o fluxo do command
   `/project:schema-change` em `.claude/commands/schema-change.md`.

## Sinal de violação

- `@Entity` com coluna que não está no DBML.
- Migration Flyway criando tabela sem atualização correspondente no DBML.
- Query referenciando coluna inexistente no DBML.
- Type mapping divergente (ex.: entity `String` onde DBML declara `varchar(40)`).

Qualquer uma dessas situações exige parar e consertar o DBML **primeiro**.

## Comandos úteis

```bash
# Gerar DDL Postgres a partir do DBML (conferência)
dbml2sql docs/dbml/<SQUAD_PREFIX>-<DB_KIND>-<contexto>.dbml --postgres

# Engenharia reversa (inferir DBML de banco existente)
db2dbml postgres "postgresql://localhost/<PROJECT_NAME>" -o /tmp/inferido.dbml
```
