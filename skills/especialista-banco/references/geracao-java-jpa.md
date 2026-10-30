# Referência — Geração Java 25 / Spring Boot a partir do DBML (JPA, Domain, Mapper, Repositories, Recursos modernos)

> Parte da skill `especialista-banco`. Carregue sob demanda. Hub: `../SKILL.md`.
## 5. Geração Avançada de Java/Spring Boot a partir do DBML

### 5.1 Mapeamento Canônico DBML → JPA → Domain

| DBML | PostgreSQL | JPA (adapter) | Domain (puro) |
|------|-----------|---------------|---------------|
| `uuid [pk]` | `UUID` | `@Id UUID id` | `UUID id` |
| `varchar(n) [not null]` | `VARCHAR(n) NOT NULL` | `@Column(nullable=false, length=n)` | `String` com validação no construtor |
| `varchar [not null, default: 'X']` | `VARCHAR DEFAULT 'X'` | `@Column(nullable=false) @ColumnDefault("'X'")` | Enum no Domain |
| `timestamptz [not null]` | `TIMESTAMP WITH TIME ZONE` | `@Column(nullable=false) OffsetDateTime` | `Instant` ou `OffsetDateTime` |
| `int` / `bigint` | `INTEGER` / `BIGINT` | `Integer` / `Long` | `int` / `long` (primitivos no domínio) |
| `numeric(p,s)` | `NUMERIC(p,s)` | `BigDecimal` + `@Column(precision=p, scale=s)` | `Money` (VO) ou `BigDecimal` |
| `jsonb` | `JSONB` | `@JdbcTypeCode(SqlTypes.JSON)` | Record/Map tipado |
| `ref: > tabela.id` | `FK` | `@ManyToOne(fetch=LAZY) @JoinColumn` | Apenas `UUID xxxId` (evita coupling) |
| `indexes { (a, b) }` | `CREATE INDEX` | `@Table(indexes=@Index(columnList="a,b"))` | — |
| `[unique]` | `UNIQUE` | `@Column(unique=true)` ou `uniqueConstraints` | Invariante de agregado |
| `deleted_at` | `TIMESTAMP NULL` | `@SQLRestriction("deleted_at IS NULL")` (Hibernate 6+) | Método `isDeleted()` |
| `version bigint` | `BIGINT NOT NULL` | `@Version Long version` | Não exposto |

### 5.2 Exemplo Completo: DBML → JPA + Domain + Mapper

**DBML** (trecho de `schema.dbml`):

```dbml
Table coordenadorias {
  id         uuid         [pk, default: `gen_random_uuid()`]
  nome       varchar(100) [not null]
  regiao     varchar(50)  [not null]
  created_at timestamptz  [not null, default: `now()`]
  updated_at timestamptz  [not null, default: `now()`]
  deleted_at timestamptz  [null]
  version    bigint       [not null, default: 0]

  indexes {
    (regiao)             [name: 'idx_coordenadorias_regiao']
    (nome)               [unique, name: 'uk_coordenadorias_nome']
  }
}
```

**JPA Entity** (`adapter/out/persistence/jpa/CoordenadoriaJpaEntity.java`):

```java
package com.app.circuito.adapter.out.persistence.jpa;

import jakarta.persistence.*;
import org.hibernate.annotations.SQLRestriction;
import java.time.OffsetDateTime;
import java.util.UUID;

@Entity
@Table(
    name = "coordenadorias",
    uniqueConstraints = @UniqueConstraint(name = "uk_coordenadorias_nome", columnNames = "nome"),
    indexes = {
        @Index(name = "idx_coordenadorias_regiao", columnList = "regiao"),
        @Index(name = "idx_coordenadorias_deleted_at", columnList = "deleted_at")
    }
)
@SQLRestriction("deleted_at IS NULL")
public class CoordenadoriaJpaEntity {

    @Id
    @Column(name = "id", nullable = false, updatable = false)
    private UUID id;

    @Column(name = "nome", nullable = false, length = 100)
    private String nome;

    @Column(name = "regiao", nullable = false, length = 50)
    private String regiao;

    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private OffsetDateTime updatedAt;

    @Column(name = "deleted_at")
    private OffsetDateTime deletedAt;

    @Version
    @Column(name = "version", nullable = false)
    private Long version;

    protected CoordenadoriaJpaEntity() { /* JPA */ }

    // getters/setters (Lombok @Data opcional; preferir acesso restrito no adapter)
}
```

**Domain Entity** (`domain/model/Coordenadoria.java`) — sem JPA, sem Lombok, invariantes no construtor:

```java
package com.app.circuito.domain.model;

import java.time.OffsetDateTime;
import java.util.Objects;
import java.util.UUID;

public final class Coordenadoria {

    private final UUID id;
    private String nome;
    private String regiao;
    private final OffsetDateTime criadoEm;
    private OffsetDateTime atualizadoEm;

    public Coordenadoria(UUID id, String nome, String regiao,
                          OffsetDateTime criadoEm, OffsetDateTime atualizadoEm) {
        this.id = Objects.requireNonNull(id, "id");
        this.nome = requireNomeValido(nome);
        this.regiao = Objects.requireNonNull(regiao, "regiao");
        this.criadoEm = Objects.requireNonNull(criadoEm, "criadoEm");
        this.atualizadoEm = Objects.requireNonNull(atualizadoEm, "atualizadoEm");
    }

    public static Coordenadoria novo(String nome, String regiao) {
        var agora = OffsetDateTime.now();
        return new Coordenadoria(UUID.randomUUID(), nome, regiao, agora, agora);
    }

    public void renomear(String novoNome) {
        this.nome = requireNomeValido(novoNome);
        this.atualizadoEm = OffsetDateTime.now();
    }

    private static String requireNomeValido(String n) {
        if (n == null || n.isBlank() || n.length() > 100)
            throw new IllegalArgumentException("nome inválido");
        return n;
    }

    // getters (sem setters — mutação só por métodos de negócio)
    public UUID id() { return id; }
    public String nome() { return nome; }
    public String regiao() { return regiao; }
    public OffsetDateTime criadoEm() { return criadoEm; }
    public OffsetDateTime atualizadoEm() { return atualizadoEm; }
}
```

**Mapper** (`adapter/out/persistence/CoordenadoriaMapper.java`):

```java
package com.app.circuito.adapter.out.persistence;

import com.app.circuito.adapter.out.persistence.jpa.CoordenadoriaJpaEntity;
import com.app.circuito.domain.model.Coordenadoria;

final class CoordenadoriaMapper {

    static Coordenadoria toDomain(CoordenadoriaJpaEntity e) {
        return new Coordenadoria(
            e.getId(), e.getNome(), e.getRegiao(),
            e.getCreatedAt(), e.getUpdatedAt()
        );
    }

    static CoordenadoriaJpaEntity toJpa(Coordenadoria c) {
        var e = new CoordenadoriaJpaEntity();
        e.setId(c.id());
        e.setNome(c.nome());
        e.setRegiao(c.regiao());
        e.setCreatedAt(c.criadoEm());
        e.setUpdatedAt(c.atualizadoEm());
        return e;
    }

    private CoordenadoriaMapper() {}
}
```

**Flyway Migration** (`db/migration/V1__create_coordenadorias.sql`) gerada a partir do DBML:

```sql
-- V1__create_coordenadorias.sql
-- Origem: db/schema.dbml (tag 2026.04.0)
CREATE TABLE coordenadorias (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome       VARCHAR(100) NOT NULL,
    regiao     VARCHAR(50)  NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    deleted_at TIMESTAMP WITH TIME ZONE,
    version    BIGINT       NOT NULL DEFAULT 0,
    CONSTRAINT uk_coordenadorias_nome UNIQUE (nome)
);

CREATE INDEX idx_coordenadorias_regiao     ON coordenadorias (regiao);
CREATE INDEX idx_coordenadorias_deleted_at ON coordenadorias (deleted_at)
  WHERE deleted_at IS NOT NULL;

COMMENT ON TABLE coordenadorias IS 'Aggregate Root — gerenciado via CoordenadoriaRepository';
```

**Teste de coerência** (`CoerenciaSchemaTest.java`):

```java
@SpringBootTest
@Testcontainers
class CoerenciaSchemaTest {

    @Container
    static PostgreSQLContainer<?> db = new PostgreSQLContainer<>("postgres:16-alpine").withReuse(true);

    @Autowired DataSource dataSource;

    @Test
    @DisplayName("JPA entity reflete todas as colunas não-deprecadas do DBML")
    void schemaSincronizado() throws SQLException {
        try (var conn = dataSource.getConnection()) {
            var cols = new HashSet<String>();
            try (var rs = conn.getMetaData().getColumns(null, "public", "coordenadorias", null)) {
                while (rs.next()) cols.add(rs.getString("COLUMN_NAME"));
            }
            assertThat(cols).containsExactlyInAnyOrder(
                "id","nome","regiao","created_at","updated_at","deleted_at","version"
            );
        }
    }

    @Test
    @DisplayName("Mapper round-trip preserva identidade")
    void roundTrip() {
        var original = Coordenadoria.novo("Palmeiras", "Sudeste");
        var jpa = CoordenadoriaMapper.toJpa(original);
        var reconstruido = CoordenadoriaMapper.toDomain(jpa);
        assertThat(reconstruido.id()).isEqualTo(original.id());
        assertThat(reconstruido.nome()).isEqualTo(original.nome());
    }
}
```

### 5.3 Repository Patterns

**Spring Data JPA** (default relacional):

```java
public interface CoordenadoriaJpaRepository extends JpaRepository<CoordenadoriaJpaEntity, UUID> {
    @Query("select c from CoordenadoriaJpaEntity c where c.regiao = :regiao")
    List<CoordenadoriaJpaEntity> porRegiao(String regiao);

    @Modifying
    @Query("update CoordenadoriaJpaEntity c set c.deletedAt = :agora where c.id = :id")
    int softDelete(UUID id, OffsetDateTime agora);
}
```

**Spring Data JDBC** (alternativa minimalista, sem lazy loading, ideal para agregados pequenos):

```java
public interface CoordenadoriaJdbcRepository extends CrudRepository<Coordenadoria, UUID> {
    @Query("SELECT * FROM coordenadorias WHERE regiao = :regiao AND deleted_at IS NULL")
    List<Coordenadoria> porRegiao(String regiao);
}
```

### 5.4 Uso de Recursos Modernos Java 25

- **Records** como projeções read-only de queries (`@Query` + `interface` ou `record` DTO)
- **Pattern Matching** em `switch` sobre enums persistidos (com `sealed` hierarchies no Domain)
- **Virtual Threads** habilitados em [[Virtual Threads vs HikariCP]]: `spring.threads.virtual.enabled=true` + `hikari.maximum-pool-size=N` onde N é o nº de CPUs × 2 (pool pequeno, VTs bloqueiam sem pinning graças ao JDBC NIO do PostgreSQL 16)
- **Structured Concurrency** para fan-out em consultas read-only paralelas
- **Scoped Values** propagando `tenantId` / `correlationId` até queries (usar com [[Correlation ID Middleware]])
- **Sealed interfaces** para hierarquias de eventos ([[Outbox Pattern]], Event Sourcing)

---

