# Step 3 — Build (Scaffold + TDD)

## Fase 3 — BUILD

### Objetivo

Implementar o sistema **via TDD rigoroso** em Java 25 + Spring Boot 4, materializando o modelo DDD da Discovery e a arquitetura da Fase 2.

### 1. Ativar Engenheiros

- `engenheiro-clean-architect` — lidera, implementa GREEN/REFACTOR
- `especialista-qualidade` — pair TDD, escreve RED
- `java25-spring-boot` — garante uso correto das APIs modernas
- `engenheiro-devops` — pipeline, Docker, compose
- `especialista-banco` — Flyway migrations a partir do DBML
- `arquiteto-ia` — se aplicável

---

### 2. Gerar o Esqueleto do Projeto

Antes de qualquer TDD, o `engenheiro-clean-architect` gera o scaffold:

```bash
python .agent/skills/squad-ai/scripts/generate_project.py \
  --name <artifact-id-do-projeto> \
  --group-id <groupId-maven> \
  --base-package <pacote-raiz-java> \
  --contexts "<ctx1>,<ctx2>" \
  --output ./
```

O gerador produz o scaffold `java25-cqrs-clean` (gerado em tempo de execução, não a partir de pasta versionada):

```
✓ POMs agregador + 4 módulos (domain, application, infrastructure, bootstrap)
✓ Java 25 configurado (source/target=25, preview features onde necessário)
✓ Spring Boot 4.x BOM importado
✓ Domain skeleton: 1 Value Object validado exemplo, 1 Aggregate Root exemplo,
  1 Domain Event, 1 DomainException
✓ Application skeleton: 1 Command + Handler, 1 Query + Handler, ports
✓ Infrastructure skeleton: JPA Entity + Mapper, Outbox table entity,
  Outbox relay (poller Spring @Scheduled), REST controller, GlobalExceptionHandler
✓ Flyway: V1__init_schema.sql (gerado do DBML quando fornecido),
  V2__outbox.sql (tabela outbox_events)
✓ Bootstrap: Application.java, application.yml (profiles dev/prod),
  logback-spring.xml JSON
✓ Testes:
   - domain: teste unitário do VO + Aggregate (JUnit 5 + AssertJ)
   - application: teste de use case com mock em port
   - infrastructure: teste de repositório com Testcontainers Postgres 16
   - arch: ArchUnit validando dependências Clean Architecture
✓ Dockerfile multi-stage (build JDK 25 → runtime JRE slim)
✓ docker-compose.yml (app + postgres:16)
✓ .github/workflows/ci.yml (build, test, ArchUnit, jacoco)
✓ README.md com runbook
```

**Importante:** o scaffold é o **ponto de partida**, não a entrega final. Toda feature de negócio entra depois via TDD.

---

### 3. Ordem de Implementação por User Story

Para cada US da Discovery:

```
1. TESTE DE ACEITAÇÃO (Gherkin → BDD automatizado) → DEVE FALHAR

2. LOOP por invariante/comportamento do aggregate:
   ├─ RED      → Qualidade escreve teste unitário (domain) → FALHA
   ├─ GREEN    → Clean Code escreve código MÍNIMO → PASSA
   ├─ REFACTOR → Ambos limpam → testes VERDES
   └─ COMMIT   → Mensagem descritiva do ciclo

3. DONE
   └─ Teste de aceitação PASSA sem modificá-lo
```

**Camada por camada, de dentro para fora:**

```
ORDEM DENTRO DE CADA US:
  0. Flyway migration incremental (se esquema mudou)
  1. Domain: Value Objects → Aggregate → Domain Events → Domain Services
     (tudo em domain/, ZERO imports de Spring/Jakarta/Hibernate)
  2. Application: Command/Query + Handler + Port
  3. Infrastructure: JPA Entity + Mapper + Repository + Outbox integration
  4. Infrastructure: REST Controller + DTO + validação Jakarta
  5. Bootstrap: wiring se novo bean global
```

---

### 4. Padrões Java 25 — Obrigatórios

Código deve usar **sempre**:

- **Records** para Value Objects e DTOs imutáveis
- **Sealed interfaces** para estados de domínio (`sealed interface PedidoStatus permits Rascunho, Confirmado, Cancelado`)
- **Pattern Matching** em switch expressions
- **Virtual Threads** — `spring.threads.virtual.enabled=true` (Tomcat/Servlet)
- **Structured Concurrency** (`StructuredTaskScope`) para fan-out de chamadas externas
- **Scoped Values** em vez de ThreadLocal (tenant, correlation-id, user)
- **`@HttpExchange`** (HTTP Service Clients declarativos) para clientes HTTP internos

**Proibidos:**
- `ThreadLocal` (substituir por `ScopedValue`)
- `synchronized` em código com Virtual Threads (usar `ReentrantLock`)
- Setters públicos em Aggregate/Entity de domínio
- `String` ou `BigDecimal` solto representando conceito de negócio (usar VO)
- Imports de `jakarta.*`, `org.springframework.*`, `org.hibernate.*` em `domain/`

---

### 5. Padrões DDD — Obrigatórios

Detalhes em `references/ddd-guide.md`. Resumo executável:

**Value Object:**
```java
public record Email(String value) {
    public Email {
        Objects.requireNonNull(value, "email não pode ser nulo");
        if (!value.matches("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$")) {
            throw new DomainException("email inválido: " + value);
        }
    }
}
```

**Aggregate Root (com invariantes protegidas):**
```java
public final class Pedido {
    private final PedidoId id;
    private final ClienteId clienteId;
    private final List<ItemPedido> itens = new ArrayList<>();
    private PedidoStatus status;
    private final List<DomainEvent> eventos = new ArrayList<>();

    public static Pedido criar(ClienteId clienteId) { /* valida, emite PedidoCriado */ }

    public void adicionarItem(ProdutoId p, Quantidade q, Money preco) {
        if (!(status instanceof PedidoStatus.Rascunho)) {
            throw new DomainException("só rascunho aceita itens");
        }
        // ... invariantes
        eventos.add(new ItemAdicionado(id, p, q, preco));
    }

    public void confirmar() {
        if (itens.isEmpty()) throw new DomainException("pedido vazio");
        this.status = new PedidoStatus.Confirmado(Instant.now());
        eventos.add(new PedidoConfirmado(id));
    }
    // ... getters imutáveis, sem setters
}
```

**Domain Event:**
```java
public sealed interface PedidoEvent extends DomainEvent
    permits PedidoCriado, ItemAdicionado, PedidoConfirmado, PedidoCancelado {}

public record PedidoConfirmado(PedidoId pedidoId, Instant em) implements PedidoEvent {}
```

Toda mudança de estado relevante emite evento. Eventos pendentes são consumidos pelo Application Service ao persistir e gravados no Outbox.

---

### 6. CQRS + Outbox — Regras

Detalhes em `references/cqrs-outbox.md`. Resumo:

**Command Handler (transação única):**
```java
@Transactional
public PedidoId handle(ConfirmarPedidoCommand cmd) {
    Pedido pedido = repo.findById(cmd.pedidoId()).orElseThrow();
    pedido.confirmar();
    repo.save(pedido);
    outbox.enqueue(pedido.pullEvents());  // MESMA transação
    return pedido.id();
}
```

**Query Handler (leitura direta, sem aggregate):**
```java
public List<PedidoResumoView> handle(ListarPedidosPorClienteQuery q) {
    return viewRepo.buscarPorCliente(q.clienteId(), q.limit());
}
```

**Outbox table (Flyway V2__outbox.sql):**
```sql
CREATE TABLE outbox_events (
    id UUID PRIMARY KEY,
    aggregate_type VARCHAR(100) NOT NULL,
    aggregate_id VARCHAR(100) NOT NULL,
    event_type VARCHAR(200) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    attempts INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_outbox_unprocessed ON outbox_events (created_at) WHERE processed_at IS NULL;
```

Relay: poller Spring `@Scheduled` (intervalo configurável) ou Debezium (CDC) — escolha via ADR.

---

### 7. Entregas Obrigatórias

`artefatos/fase-3-build/`:

```
├── codigo-implementado.md     → Inventário de aggregates, VOs, use cases, controllers
├── scaffold-log.md            → Log do gerador, decisões de customização
├── testes-unitarios.md        → Lista de testes unitários por aggregate
├── testes-integracao.md       → Testcontainers: repositórios, outbox, rest
├── archunit-report.md         → Regras ativas e resultado
├── pipeline-ci.md             → Configuração do CI
├── docker-config.md           → Dockerfile + compose
└── cobertura-testes.md        → JaCoCo; meta ≥ 80% domínio, ≥ 60% geral
```

### 8. Gatekeeping Build → Test

```
CHECKLIST
  □ Projeto compila (mvn -T 1C clean verify) sem warnings bloqueantes
  □ Todos os testes unitários verdes
  □ Todos os testes de integração verdes (Testcontainers sobe Postgres)
  □ ArchUnit: domain ∉ {spring, jakarta, hibernate} ✓
  □ ArchUnit: application depende apenas de domain ✓
  □ ArchUnit: bootstrap e infrastructure podem depender de application ✓
  □ Cobertura ≥ 80% domínio, ≥ 60% geral
  □ Zero setters públicos em aggregates/entities de domínio
  □ Zero uso de ThreadLocal (ScopedValue ou equivalente)
  □ Zero synchronized em Virtual Thread paths (ReentrantLock)
  □ Flyway migrations executam limpas no compose
  □ docker-compose up sobe app + Postgres e health check responde 200
  □ Outbox table criada, relay configurado, teste de integração com outbox passando
  □ Pipeline CI green
  □ Histórico git reflete ciclos RED-GREEN-REFACTOR
  □ tdd_compliance.json sem violações
```

### 9. Próximo Step

`./step-04-test.md`
