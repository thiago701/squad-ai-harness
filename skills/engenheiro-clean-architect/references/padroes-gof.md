# Referência — Padrões GoF, Code Smells (Fowler) e Base Canônica de Conhecimento

> Parte da skill `engenheiro-clean-architect`. Carregue sob demanda. Hub: `../SKILL.md`.
## Base de Conhecimento Canônica

Você domina profundamente e cita quando relevante:

### Livros Fundamentais
| Livro | Autor | Contribuição Central |
|---|---|---|
| **Clean Code** | Robert C. Martin | Nomes, funções, comentários, formatação, objetos vs estruturas |
| **Clean Architecture** | Robert C. Martin | Regra da dependência, camadas, use cases, entities |
| **The Pragmatic Programmer** | Hunt & Thomas | DRY, ortogonalidade, contratos, automação |
| **Refactoring** | Martin Fowler | Catálogo de code smells e refatorações seguras |
| **Design Patterns (GoF)** | Gang of Four | 23 padrões criacionais, estruturais e comportamentais |
| **Domain-Driven Design** | Eric Evans | Ubiquitous language, bounded contexts, aggregates, domain events |
| **Implementing DDD** | Vaughn Vernon | Aplicação prática de DDD em sistemas reais |
| **A Philosophy of Software Design** | John Ousterhout | Deep modules, complexidade, information hiding |
| **Working Effectively with Legacy Code** | Michael Feathers | Seams, characterization tests, técnicas de quebra de dependência |
| **Patterns of Enterprise Application Architecture** | Martin Fowler | Repository, Unit of Work, Service Layer, Data Mapper |
| **Software Architecture: The Hard Parts** | Ford, Richards, Sadalage, Dehghani | Trade-offs em arquiteturas distribuídas modernas |
| **Accelerate** | Forsgren, Humble, Kim | DORA metrics, entrega contínua e qualidade como vantagem competitiva |

---

## Catálogo de Code Smells (Fowler) — Diagnóstico Rápido

| Code Smell | Sintoma | Refatoração |
|---|---|---|
| **Long Method** | > 20 linhas, múltiplos níveis de abstração | Extract Method |
| **Large Class** | > 300 linhas, > 5 dependências injetadas | Extract Class, Extract Interface |
| **Long Parameter List** | > 3 parâmetros | Introduce Parameter Object (Record/dataclass) |
| **Divergent Change** | Classe muda por múltiplas razões não relacionadas | Extract Class (SRP) |
| **Shotgun Surgery** | Uma mudança exige tocar muitos arquivos | Move Method/Field, consolidar |
| **Feature Envy** | Método usa mais dados de outra classe que da sua | Move Method |
| **Data Clumps** | Mesmos grupos de variáveis aparecem juntos sempre | Extract Class (Value Object) |
| **Primitive Obsession** | String para CPF, int para dinheiro, etc. | Replace Primitive with Object |
| **Switch Statements** | switch/if-else que cresce a cada feature | Replace Conditional with Polymorphism |
| **Parallel Inheritance Hierarchies** | Adicionar subclasse exige subclasse em outra hierarquia | Collapse Hierarchy |
| **Lazy Class** | Classe que não faz nada útil | Inline Class |
| **Speculative Generality** | Abstração criada "para o futuro" | Collapse Hierarchy, Inline |
| **Temporary Field** | Campo da classe só usado em alguns métodos | Extract Class |
| **Message Chains** | `a.getB().getC().getD()` | Hide Delegate (Lei de Demeter) |
| **Middle Man** | Classe que só delega para outra | Remove Middle Man |
| **Inappropriate Intimacy** | Classe conhece detalhes internos de outra | Move Method, Extract Interface |
| **Data Class** | Classe só com getters/setters, sem comportamento | Move Method para ela (Tell Don't Ask) |
| **Refused Bequest** | Subclasse herda mas não usa métodos do pai | Replace Inheritance with Delegation |
| **Comments** | Comentário explica código confuso | Rename, Extract Method |

---

## Padrões GoF — Quando Aplicar

### Criacionais
```java
// Factory Method — quando a criação requer lógica de domínio
public sealed interface Notificacao permits EmailNotificacao, SmsNotificacao, PushNotificacao {}

public class NotificacaoFactory {
    public static Notificacao criar(TipoNotificacao tipo, String destinatario) {
        return switch (tipo) {
            case EMAIL -> new EmailNotificacao(new Email(destinatario));
            case SMS   -> new SmsNotificacao(new Telefone(destinatario));
            case PUSH  -> new PushNotificacao(new DeviceToken(destinatario));
        };
    }
}

// Builder — quando objeto tem muitos parâmetros opcionais
var pedido = Pedido.builder()
    .cliente(cliente)
    .item(produto1, Quantidade.de(2))
    .item(produto2, Quantidade.de(1))
    .enderecoEntrega(endereco)
    .build();  // validação no build(), não no construtor
```

### Persistência — DBML como Fonte de Verdade

O modelo de dados do projeto é definido em DBML (DSL do dbdiagram.io). Toda entity, repository
e migration DEVE ser coerente com o arquivo `.dbml`.

```
REGRA DE OURO — SEPARAÇÃO DE CAMADAS DE PERSISTÊNCIA:
  ┌─────────────────────────────────────────────────────┐
  │  domain/model/Pedido.java          ← Record/classe  │
  │  (comportamento + regras de negócio, SEM JPA)       │
  ├─────────────────────────────────────────────────────┤
  │  adapter/out/persistence/                            │
  │  ├── PedidoJpaEntity.java          ← @Entity JPA   │
  │  ├── PedidoJpaMapper.java          ← converte ↔    │
  │  ├── PedidoJpaDao.java             ← Spring Data   │
  │  └── PedidoJpaAdapter.java         ← implementa    │
  │       port PedidoRepository                          │
  └─────────────────────────────────────────────────────┘

FLUXO DE MUDANÇA NO ESQUEMA:
  1. Alterar .dbml → 2. Gerar migration Flyway → 3. Atualizar JPA Entity
  → 4. Atualizar Mapper → 5. Atualizar Domain Entity (se necessário) → 6. Testes

PROIBIDO:
  ✗ Expor JPA Entity fora do adapter
  ✗ Usar JPA Entity como parâmetro de Use Case
  ✗ spring.jpa.hibernate.ddl-auto=update em produção
  ✗ Alterar esquema sem atualizar o .dbml primeiro

RESOLUÇÃO DE CONFLITOS NO .dbml:
  Quando dois desenvolvedores alteram o .dbml simultaneamente:

  1. SEMPRE resolver via merge — nunca usar "accept mine/theirs" cegamente
  2. O .dbml é a fonte de verdade: o MERGE deve resultar em um .dbml válido
  3. Após resolver o conflito no .dbml:
     a. Validar sintaxe: executar `dbml-renderer` ou importar no dbdiagram.io
     b. Re-gerar migration Flyway a partir do .dbml atualizado
     c. Atualizar JPA Entities e Mappers para refletir o merge
     d. Rodar todos os testes de integração (round-trip mapper, constraints)
  4. Se ambas branches adicionaram migrations com mesmo número:
     → Renumerar a migration da branch mais recente (V{N+1})
  5. NUNCA editar migrations já aplicadas em ambientes compartilhados
  6. Em caso de dúvida sobre a semântica do merge:
     → Pair review com o outro dev + arquiteto antes de commitar

  PREVENÇÃO:
  - Comunicar no stand-up quando for alterar o .dbml
  - Manter PRs pequenos que tocam o .dbml (merge rápido)
  - Usar lock advisory no .dbml para times grandes (CODEOWNERS)
```

```java
// Mapeamento correto DBML → JPA → Domain (exemplo com Aggregate Root)

// DBML define:
// Table pedidos { id bigint [pk, increment]; status varchar(20); ... }
// Table itens_pedido { pedido_id bigint [ref: > pedidos.id]; ... }

// JPA Entity — reflete fielmente o DBML
@Entity @Table(name = "pedidos")
public class PedidoJpaEntity {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @OneToMany(mappedBy = "pedido", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<ItemPedidoJpaEntity> itens = new ArrayList<>();

    @Version  // optimistic locking para Aggregate Root
    private Long version;
    // ... demais campos conforme DBML
}

// Domain Entity — comportamento rico, sem JPA
public record Pedido(PedidoId id, StatusPedido status, List<ItemPedido> itens, Dinheiro total) {
    public Pedido confirmar() { /* regra de negócio */ }
    public Pedido adicionarItem(ItemPedido item) { /* regra de negócio */ }
}

// Mapper — converte sem perda de dados
public final class PedidoJpaMapper {
    public static Pedido toDomain(PedidoJpaEntity e) { /* ... */ }
    public static PedidoJpaEntity toJpa(Pedido d) { /* ... */ }
}
```

### Estruturais
```java
// Adapter — conectar infraestrutura ao domínio sem contaminá-lo
public class PedidoJpaAdapter implements PedidoRepository {
    private final PedidoJpaDao dao;
    public Optional<Pedido> buscarPorId(PedidoId id) {
        return dao.findById(id.valor()).map(PedidoJpaMapper::toDomain);
    }
}

// Decorator — adicionar comportamento sem herança
public class PedidoRepositorioComCache implements PedidoRepository {
    private final PedidoRepository delegate;
    private final Cache<PedidoId, Pedido> cache;
    
    public Optional<Pedido> buscarPorId(PedidoId id) {
        return Optional.ofNullable(cache.getIfPresent(id))
            .or(() -> {
                var resultado = delegate.buscarPorId(id);
                resultado.ifPresent(p -> cache.put(id, p));
                return resultado;
            });
    }
}
```

### Comportamentais
```java
// Strategy — algoritmos intercambiáveis (OCP)
// Strategy — ver seção SOLID/OCP acima (TipoCliente)

// Observer / Domain Events
public class Pedido {
    private final List<DomainEvent> eventos = new ArrayList<>();
    
    public void confirmar() {
        // lógica de negócio...
        eventos.add(new PedidoConfirmadoEvent(this.id, LocalDateTime.now()));
    }
    
    public List<DomainEvent> pullEventos() {
        var copia = List.copyOf(eventos);
        eventos.clear();
        return copia;
    }
}

// Command — encapsular intenção de negócio
public record ConfirmarPedidoCommand(PedidoId pedidoId, OperadorId operadorId) {}
```

---

