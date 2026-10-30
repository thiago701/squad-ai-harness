# GitHub Copilot / Microsoft Copilot Enterprise — instruções do <PROJECT_NAME>

> Este arquivo é lido automaticamente por **GitHub Copilot** (VS Code,
> JetBrains, Visual Studio) e por **Microsoft Copilot for Enterprise / Business**
> quando ancorado ao repositório. Versões completas em
> [`../CLAUDE.md`](../CLAUDE.md), [`../AGENTS.md`](../AGENTS.md) e
> [`../.cursorrules`](../.cursorrules).

## Projeto

- **Nome**: `<PROJECT_NAME>` (`<GROUP_ID>:<PROJECT_NAME>`).
- **Fase**: `<PHASE>`.
- **Arquitetura**: monólito modular com **Spring Modulith 2.x**. Cada módulo
  Spring Modulith é um futuro microsserviço `ms-<PROJECT_NAME>-<contexto>`.
- **Bounded contexts**: <CONTEXTS>.
- **Stack**: Java 25, Spring Boot 4.0, Spring Framework 7, Hibernate 7,
  Jackson 3, PostgreSQL 16 (Aurora-compatible), AWS SDK v2, Testcontainers 2.0.

## Fonte da verdade do schema: DBML

Arquivos em [`../docs/dbml/`](../docs/dbml/) são a **fonte primária**. Antes de
sugerir `@Entity`, migration Flyway ou query, consulte o DBML correspondente.
Se o schema necessário não existir, sinalize que é preciso atualizar o DBML
primeiro.

## Convenções obrigatórias (padrão §1.1)

1. **PK**: `codigo_identificacao_<entidade>` UUID `gen_random_uuid()`.
2. **FKs**: `codigo_identificacao_<entidade_referenciada>` — nunca `fk_*` nem `id_*`.
3. **Seis colunas de auditoria** obrigatórias:
   - `usuario_criacao_registro` + `data_hora_criacao_registro`
   - `usuario_atualizacao_registro` + `data_hora_atualizacao_registro`
   - `data_hora_exclusao_registro` + `usuario_exclusao_registro`
4. **Soft delete** via `data_hora_exclusao_registro IS NULL`.
5. **Optimistic lock** via `numero_versao_registro BIGINT` (`@Version`).
6. **Timestamps** sempre `TIMESTAMPTZ` (UTC).
7. **Nomes** snake_case em português, substantivos completos.

## Fluxo de alteração de schema

1. Editar `docs/dbml/<contexto>.dbml`.
2. Validar: `dbml2sql docs/dbml/<SQUAD_PREFIX>-<DB_KIND>-<contexto>.dbml --postgres`.
3. Criar `V{N}__*.sql` em `src/main/resources/db/migration/<contexto>/`.
4. Ajustar `@Entity` JPA em `src/main/java/.../<contexto>/infra/persistence/`.
5. `./mvnw verify` — `spring.jpa.ddl-auto=validate` quebra se entity ≠ DB.

## Fronteiras de módulo (Spring Modulith)

- `allowedDependencies` em `package-info.java` de cada módulo.
- Cross-module **apenas** via:
  1. **API pública exportada** — interfaces + VOs `record`.
  2. **Eventos de domínio** — `@ApplicationModuleListener` + outbox
     `spring-modulith-events-jpa`.
- **Proibido** importar `.infra.*`, `.application.*` ou `.domain.*` de outro
  módulo. `ModulithArchitectureTest.verifyBoundaries()` falha o build.

## Nomenclatura corporativa

- **DBMLs e recursos AWS**: `<SQUAD_PREFIX>-<DB_KIND>-<contexto>` (kebab).
- **Database / project DBML interno**: `<SQUAD_PREFIX>_<DB_KIND>_<contexto>` (snake).
- **Microsserviços Fase 2**: `ms-<PROJECT_NAME>-<contexto>`.
- **Roles de banco Fase 1**: `<PROJECT_NAME>_<contexto>_app`.

## Estrutura interna de módulo (Clean Architecture)

```
<BASE_PACKAGE>.<modulo>
  (raiz)           → API pública: interfaces + events + VOs record exportados
  api              → @RestController + DTOs request/response
  application      → @Service @Transactional (casos de uso)
  domain           → Aggregates, VOs, sealed types
    spi            → ports (repositories, clients — interfaces)
  infra/persistence → @Entity + JpaRepository + adapters (impls dos ports)
  package-info.java → @ApplicationModule(displayName, allowedDependencies)
```

## Idiomas Java 25 — preferir

- `record` para DTOs, VOs, eventos.
- `sealed interface` + pattern matching exaustivo para estados finitos.
- Virtual Threads já ligadas (`spring.threads.virtual.enabled=true`).
  Escrever código bloqueante direto — não usar `Mono`/`Flux` nem
  `CompletableFuture` chains sem pedido explícito.
- `StructuredTaskScope` (JEP 505) para fan-out I/O paralelo.
- `ScopedValue` (JEP 506) em vez de `ThreadLocal`.
- `switch` com pattern matching em vez de cadeias `if/instanceof`.
- `@HttpExchange` declarativo para clientes HTTP (Spring 7).

## Idiomas Java — evitar

- `synchronized` em hot paths (pinning de virtual thread) — use `ReentrantLock`.
- `ThreadLocal` — use `ScopedValue`.
- `CompletableFuture.thenCompose` em cadeia — use `StructuredTaskScope`.
- Lombok — records cobrem 95% dos casos.
- Retornar `@Entity` em controllers — sempre mapear para record response.

## Testes

- **Testcontainers 2.0** + `@ServiceConnection` para PostgreSQL real.
- **`RestTestClient`** (Spring 7) para controller tests.
- **`@ApplicationModuleTest`** para teste de módulo isolado.

## O que NÃO sugerir sem pedido explícito

- Kafka, Redis, Service Mesh, K8s operator (Fase 2).
- Schemas compartilhados entre módulos (cross-module via snapshot em evento).
- Colunas fora do padrão §1.1 sem atualização do DBML antes.

## Checklist de qualidade

- [ ] Mudança começou no DBML (se envolve schema)?
- [ ] Tabela segue §1.1 completa?
- [ ] `@Entity` bate 1:1 com DBML?
- [ ] Fronteira de módulo respeitada?
- [ ] Cross-module via API pública / evento?
- [ ] Usa `record` para DTO/VO/event?
- [ ] Usa `sealed` para estado finito?
- [ ] Query respeita soft delete?
- [ ] Teste escrito?
