# CLAUDE.md — contexto estável do projeto <PROJECT_NAME>

> Lido automaticamente por **Claude Code** e **Cowork** no início de cada sessão.
> Este arquivo **não** é dump de procedimentos — é só **contexto estável**
> (arquitetura, convenções, comandos). Procedimentos repetíveis vivem em
> [`.claude/commands/`](.claude/commands/); regras granulares em
> [`.claude/rules/`](.claude/rules/); agentes especializados em
> [`.claude/agents/`](.claude/agents/); automações determinísticas em
> [`.claude/hooks/`](.claude/hooks/).

---

## 1. Identidade do projeto

- **Nome**: `<PROJECT_NAME>` (`<GROUP_ID>:<PROJECT_NAME>`).
- **Pacote base**: `<BASE_PACKAGE>`.
- **Fase**: `<PHASE>`.
- **Arquitetura**: monólito modular com Spring Modulith 2.x — cada módulo é um
  futuro microsserviço `ms-<PROJECT_NAME>-<contexto>` na Fase 2.
  Ver [`<ADR_PRINCIPAL>`](<ADR_PRINCIPAL>).
- **Bounded Contexts**: <CONTEXTS>.
- **Stack fixa da squad**: Java 25 · Spring Boot 4.0 · Spring Framework 7 ·
  Hibernate 7 · Jackson 3 · PostgreSQL 16 (Aurora-compatible) · AWS SDK v2 ·
  Testcontainers 2.0.

---

## 2. Fonte da verdade do schema: DBML

Os arquivos em [`docs/dbml/`](docs/dbml/) descrevem **formalmente** o schema
relacional. **Qualquer** `@Entity`, migration Flyway, query ou DDL precisa
casar 1:1 com o DBML. Detalhes em
[`.claude/rules/01-dbml-source-of-truth.md`](.claude/rules/01-dbml-source-of-truth.md).

---

## 3. Convenções-chave (resumo; detalhe em rules/)

- **Padrão §1.1** — PK `codigo_identificacao_*`, 6 colunas de auditoria,
  `numero_versao_registro` (`@Version`), soft delete, `TIMESTAMPTZ` UTC.
  Ver [`rules/02-schema-conventions.md`](.claude/rules/02-schema-conventions.md).
- **Fronteiras Modulith** verificadas em build via
  `ApplicationModules.verify()`. Cross-module só via API pública (records) ou
  eventos. Ver [`rules/03-module-boundaries.md`](.claude/rules/03-module-boundaries.md).
- **Java 25 idiomático** — `record`, `sealed`, pattern matching, virtual
  threads, `StructuredTaskScope`, `ScopedValue`. Sem `ThreadLocal`, sem
  `synchronized` em hot paths, sem `CompletableFuture` chains a menos que
  explicitamente pedido. Ver [`rules/04-java25-idioms.md`](.claude/rules/04-java25-idioms.md).
- **Testes** — Testcontainers 2.0 + `@ServiceConnection`, `RestTestClient`,
  `@ApplicationModuleTest`. Ver [`rules/05-testing.md`](.claude/rules/05-testing.md).
- **Nomenclatura corporativa** — arquivos e recursos AWS em kebab
  (`<SQUAD_PREFIX>-<DB_KIND>-<contexto>`), schemas/DB em snake
  (`<SQUAD_PREFIX>_<DB_KIND>_<contexto>`).

---

## 4. Comandos essenciais

```bash
./mvnw verify                    # build + testes + ModulithArchitectureTest
docker compose up -d             # stack local (Postgres + LocalStack + app)
dbml2sql docs/dbml/<SQUAD_PREFIX>-<DB_KIND>-<ctx>.dbml --postgres
                                 # validar DDL esperado a partir do DBML
```

Workflows multi-passo reutilizáveis estão em
[`.claude/commands/`](.claude/commands/) — use `/project:<nome>` para invocar.

---

## 5. Quando o usuário pede algo recorrente

- **"Vou mudar o schema"** → use `/project:schema-change`.
- **"Revise este PR / este diff"** → use `/project:review-pr`.
- **"Estou com erro de fronteira de módulo"** → use `/project:debug-boundary`.
- **"Vou subir para produção"** → use `/project:deploy-checklist`.
- **"Crie uma nova feature em `<modulo>`"** → use `/project:new-feature`.

Se um prompt novo se repetir 3 vezes, **promova-o a command** em
`.claude/commands/` — é o hábito #3 da AI-First.

---

## 6. Ferramentas de IA suportadas neste repo

| Ferramenta | Lê automaticamente |
|---|---|
| Claude Code / Cowork | `CLAUDE.md` + `.claude/**` |
| ChatGPT Codex, Devin, agents genéricos | `AGENTS.md` |
| GitHub Copilot (VS Code, JetBrains, VS) | `.github/copilot-instructions.md` |
| Microsoft Copilot Enterprise (Business) | `.github/copilot-instructions.md` |
| Cursor | `.cursorrules` + `CLAUDE.md` (fallback) |

Todos apontam para a mesma fonte da verdade: `docs/dbml/` + `.claude/rules/`.

---

## 7. O que NÃO fazer sem aval explícito

- Não adicionar Kafka, Redis, Service Mesh, K8s operator — é escopo da Fase 2.
- Não criar schema compartilhado entre módulos — cross-module só via snapshot
  imutável em evento.
- Não introduzir colunas fora do padrão §1.1 sem atualizar o DBML antes.
- Não retornar `@Entity` em controller — sempre mapear para `record`.

---

## 8. Referências

- ADR vigente: [`<ADR_PRINCIPAL>`](<ADR_PRINCIPAL>).
- DBMLs: [`docs/dbml/`](docs/dbml/).
- Rules granulares: [`.claude/rules/`](.claude/rules/).
- Commands reutilizáveis: [`.claude/commands/`](.claude/commands/).
- Sub-agentes: [`.claude/agents/`](.claude/agents/).
- Hooks determinísticos: [`.claude/hooks/`](.claude/hooks/).
