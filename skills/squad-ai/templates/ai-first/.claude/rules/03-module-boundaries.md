# Rule 03 — Fronteiras de módulo (Spring Modulith)

Aplica-se a: todo código sob `src/main/java/<BASE_PACKAGE>/**`.

## Regra

Cada módulo declara suas dependências permitidas em `package-info.java`:

```java
@org.springframework.modulith.ApplicationModule(
    displayName = "<Nome do Módulo>",
    allowedDependencies = { "<outro_modulo>", "shared" }
)
package <BASE_PACKAGE>.<modulo>;
```

Cross-module **apenas** via:

1. **API pública exportada** — interfaces no pacote raiz do módulo
   (ex.: `FornecedorLookup`) e **VOs imutáveis** (`record`).
2. **Eventos de domínio** — publicados pelo módulo dono via
   `@ApplicationModuleListener` + outbox `spring-modulith-events-jpa`.
   Use `@Externalized` para eventos que terão equivalente em SNS/SQS na Fase 2.

## Estrutura interna obrigatória

```
<BASE_PACKAGE>.<modulo>
├── (raiz)                    ← API pública (interfaces + events + VOs record)
├── api                       ← @RestController + DTOs request/response
├── application               ← @Service @Transactional (casos de uso)
├── domain                    ← Aggregates, VOs, sealed types
│   └── spi                   ← ports (repositories, clients — interfaces)
├── infra                     ← adapters
│   └── persistence           ← @Entity + JpaRepository + adapters (impls)
└── package-info.java         ← @ApplicationModule(displayName, allowedDependencies)
```

## Proibições (build quebra)

- Importar `<BASE_PACKAGE>.<outro>.infra.*` de outro módulo.
- Importar `<BASE_PACKAGE>.<outro>.application.*` de outro módulo.
- Importar `<BASE_PACKAGE>.<outro>.domain.*` de outro módulo.
- Retornar `@Entity` ou classes do `domain.*` em API pública cross-module —
  use sempre **snapshots record imutáveis**.

## Verificação automática

O teste `ModulithArchitectureTest.verifyBoundaries()` roda em todo build e
**falha imediatamente** se qualquer regra acima for violada. Também gera
documentação viva em `target/spring-modulith-docs/` (C4 + PlantUML).

## CQRS in-process

Se precisar separar leitura de escrita num módulo, crie dois **ports SPI**
(ex.: `FornecedorReadRepository` + `FornecedorWriteRepository`) e dois
adapters sobre o **mesmo** store. **Nunca** crie banco separado para
read-model sem ADR explícito — é escopo da Fase 2.
