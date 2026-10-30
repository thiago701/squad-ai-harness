# AGENTS.md — contexto para agentes (ChatGPT Codex, Devin, OpenAI Swarm, etc.)

> Este arquivo é lido automaticamente por agentes que seguem o padrão
> `AGENTS.md` (ChatGPT Codex, Devin, Cline, Aider em modo agent, etc.). É uma
> versão compacta de [`CLAUDE.md`](CLAUDE.md) focada no essencial para agentes
> que não têm acesso a estrutura de pastas de configuração.

---

## Projeto

- **Nome**: `<PROJECT_NAME>` (`<GROUP_ID>:<PROJECT_NAME>`).
- **Pacote base**: `<BASE_PACKAGE>`.
- **Fase**: `<PHASE>`.
- **Arquitetura**: monólito modular com Spring Modulith 2.x. Cada módulo é um
  futuro microsserviço `ms-<PROJECT_NAME>-<contexto>` (Fase 2).
- **Bounded contexts**: <CONTEXTS>.
- **Stack**: Java 25, Spring Boot 4.0, Spring Framework 7, Hibernate 7,
  Jackson 3, PostgreSQL 16 Aurora-compatible, AWS SDK v2, Testcontainers 2.0.

## Fonte da verdade do schema

- Os DBMLs em `docs/dbml/` são a **fonte primária da verdade** do schema.
- **Qualquer** mudança de schema começa no DBML. Nunca gere `@Entity`,
  migration Flyway ou DDL sem antes ler o DBML correspondente.
- Se a tabela necessária não existe no DBML, pare e peça decisão explícita.

## Convenções obrigatórias (padrão §1.1)

1. **PK**: `codigo_identificacao_<entidade>` UUID `gen_random_uuid()`.
2. **FKs**: `codigo_identificacao_<entidade_referenciada>` — nunca `fk_*` nem `id_*`.
3. **6 colunas de auditoria** obrigatórias:
   - `usuario_criacao_registro` + `data_hora_criacao_registro`
   - `usuario_atualizacao_registro` + `data_hora_atualizacao_registro`
   - `data_hora_exclusao_registro` + `usuario_exclusao_registro`
4. **Soft delete** via `data_hora_exclusao_registro IS NULL`.
5. **Optimistic lock** via `numero_versao_registro BIGINT` (`@Version`).
6. **Timestamps** sempre `TIMESTAMPTZ` (UTC).
7. **Nomes** snake_case em português, substantivos completos.

## Fluxo obrigatório quando o schema muda

1. Editar `docs/dbml/<contexto>.dbml`.
2. Validar: `dbml2sql docs/dbml/<SQUAD_PREFIX>-<DB_KIND>-<contexto>.dbml --postgres`.
3. Criar `V{N}__*.sql` em `src/main/resources/db/migration/<contexto>/`.
4. Ajustar `@Entity` JPA em `src/main/java/.../<contexto>/infra/persistence/`.
5. `./mvnw verify` — `spring.jpa.ddl-auto=validate` falha se entity ≠ DB.

## Fronteiras de módulo (Spring Modulith)

- Declaradas em `package-info.java` via `@ApplicationModule(allowedDependencies=...)`.
- **Cross-module** somente via:
  1. **API pública exportada** (interfaces no pacote raiz do módulo + VOs `record`).
  2. **Eventos de domínio** com outbox (`spring-modulith-events-jpa`).
- **Proibido** importar `.infra.*`, `.application.*` ou `.domain.*` de outro módulo.
- `ModulithArchitectureTest.verifyBoundaries()` **falha o build** se violado.

## Idiomas Java 25 — preferir

- `record` para DTOs, VOs e eventos.
- `sealed interface` + pattern matching exaustivo para estados finitos.
- Virtual threads já ligadas — código bloqueante direto (sem `Mono`/`Flux`
  nem `CompletableFuture` chains sem pedido).
- `StructuredTaskScope` (JEP 505) para fan-out I/O paralelo.
- `ScopedValue` (JEP 506) em vez de `ThreadLocal`.
- `switch` com pattern matching em vez de `if/instanceof`.
- `@HttpExchange` declarativo para clients HTTP (Spring 7).

## Idiomas Java — evitar

- `synchronized` em hot paths (pinning de virtual thread) — usar `ReentrantLock`.
- `ThreadLocal` — usar `ScopedValue`.
- `CompletableFuture.thenCompose` chains — usar `StructuredTaskScope`.
- Lombok — `record` cobre 95% dos casos.
- Retornar `@Entity` em controller — sempre mapear para `record` response.

## Nomenclatura corporativa

- **DBMLs e recursos AWS**: `<SQUAD_PREFIX>-<DB_KIND>-<contexto>` (kebab).
- **Database / project DBML interno**: `<SQUAD_PREFIX>_<DB_KIND>_<contexto>` (snake).
- **Microsserviços Fase 2**: `ms-<PROJECT_NAME>-<contexto>`.
- **Roles de banco Fase 1**: `<PROJECT_NAME>_<contexto>_app`.

## Comandos essenciais

```bash
./mvnw verify                                          # build + testes + boundaries
docker compose up -d                                   # stack local
dbml2sql docs/dbml/<SQUAD_PREFIX>-<DB_KIND>-<ctx>.dbml --postgres
```

## Checklist antes de aceitar código gerado

- [ ] Mudança de schema começou pelo DBML?
- [ ] §1.1 completo (PK, 6 auditoria, `@Version`, TIMESTAMPTZ, soft delete)?
- [ ] `@Entity` bate 1:1 com DBML?
- [ ] Fronteira de módulo respeitada (`ModulithArchitectureTest` passa)?
- [ ] Cross-module via API pública ou evento — não por importação direta?
- [ ] `record` para DTO/VO/event?
- [ ] `sealed` para estados finitos?
- [ ] Query respeita soft delete (`data_hora_exclusao_registro IS NULL`)?
- [ ] Teste escrito?

## Proibido sem aval explícito

- Kafka, Redis, Service Mesh, K8s operator (Fase 2).
- Schema compartilhado entre módulos (cruzar via evento + snapshot imutável).
- Colunas fora do padrão §1.1.
- Retornar `@Entity` em controller.
