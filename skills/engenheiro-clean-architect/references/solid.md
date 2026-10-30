# Referência — SOLID (aplicação rigorosa + testes de arquitetura ArchUnit/Pytest)

> Parte da skill `engenheiro-clean-architect`. Carregue sob demanda. Hub: `../SKILL.md`.
## Princípios SOLID — Aplicação Rigorosa

### S — Single Responsibility Principle
> *"Uma classe deve ter um, e somente um, motivo para mudar."* — Robert C. Martin

```java
// VIOLAÇÃO — Java 25
// Esta classe muda por 3 razões: regra de negócio, persistência e notificação
public class PedidoService {
    public void confirmar(Pedido pedido) {
        if (pedido.getValor().compareTo(BigDecimal.TEN) < 0)
            throw new ValorMinimoPedidoException();          // regra de negócio
        jdbcTemplate.update("UPDATE pedidos SET status=.."); // persistência
        emailClient.enviar(pedido.getCliente().getEmail());  // notificação
    }
}

// CORRETO — responsabilidades separadas com Records Java 25
public class ConfirmarPedidoUseCase {
    private final PedidoRepository repository;         // porta
    private final NotificadorPedido notificador;        // porta

    public PedidoConfirmado executar(PedidoId pedidoId) {
        var pedido = repository.buscarPorId(pedidoId)
            .orElseThrow(() -> new PedidoNaoEncontradoException(pedidoId));
        pedido.confirmar();                             // regra no domínio
        repository.salvar(pedido);
        notificador.pedidoConfirmado(pedido);
        return new PedidoConfirmado(pedido.getId(), pedido.getStatus()); // Record
    }
}
```

```python
# CORRETO — Python 3.12+
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class PedidoConfirmado:
    pedido_id: int
    status: str

class ConfirmarPedidoUseCase:
    def __init__(
        self,
        repository: PedidoRepository,   # Protocol — porta
        notificador: NotificadorPedido,  # Protocol — porta
    ) -> None:
        self._repository = repository
        self._notificador = notificador

    def executar(self, pedido_id: int) -> PedidoConfirmado:
        pedido = self._repository.buscar_por_id(pedido_id)
        pedido.confirmar()                  # regra no domínio
        self._repository.salvar(pedido)
        self._notificador.pedido_confirmado(pedido)
        return PedidoConfirmado(pedido.id, pedido.status.value)
```

---

### O — Open/Closed Principle
> *"Aberto para extensão, fechado para modificação."* — Bertrand Meyer

```java
// VIOLAÇÃO — adicionar tipo exige modificar a classe
public class CalculadorDesconto {
    public BigDecimal calcular(String tipoCliente, BigDecimal valor) {
        return switch (tipoCliente) {           // cresce para sempre
            case "VIP"     -> valor.multiply(new BigDecimal("0.20"));
            case "REGULAR" -> valor.multiply(new BigDecimal("0.05"));
            default        -> BigDecimal.ZERO;
        };
    }
}

// CORRETO — Sealed interface + Pattern Matching Java 25
public sealed interface TipoCliente permits ClienteVip, ClienteRegular, ClienteNovo {
    BigDecimal calcularDesconto(BigDecimal valor);
}

public record ClienteVip() implements TipoCliente {
    public BigDecimal calcularDesconto(BigDecimal valor) {
        return valor.multiply(new BigDecimal("0.20"));
    }
}

public record ClienteRegular() implements TipoCliente {
    public BigDecimal calcularDesconto(BigDecimal valor) {
        return valor.multiply(new BigDecimal("0.05"));
    }
}

// Uso com Pattern Matching — exaustivo em tempo de compilação
BigDecimal desconto = switch (cliente) {
    case ClienteVip v      -> v.calcularDesconto(valor);
    case ClienteRegular r  -> r.calcularDesconto(valor);
    case ClienteNovo n     -> BigDecimal.ZERO;
};
```

```python
# CORRETO — Python 3.12+ com Protocol e match/case
from typing import Protocol
from decimal import Decimal

class TipoCliente(Protocol):
    def calcular_desconto(self, valor: Decimal) -> Decimal: ...

@dataclass(frozen=True)
class ClienteVip:
    def calcular_desconto(self, valor: Decimal) -> Decimal:
        return valor * Decimal("0.20")

@dataclass(frozen=True)
class ClienteRegular:
    def calcular_desconto(self, valor: Decimal) -> Decimal:
        return valor * Decimal("0.05")

def aplicar_desconto(cliente: TipoCliente, valor: Decimal) -> Decimal:
    return cliente.calcular_desconto(valor)  # extensível sem modificação
```

---

### L — Liskov Substitution Principle
> *"Subtipos devem ser substituíveis por seus tipos base."* — Barbara Liskov

```java
// VIOLAÇÃO — Quadrado quebra o contrato de Retângulo
public class Retangulo {
    protected int largura, altura;
    public void setLargura(int l) { largura = l; }
    public void setAltura(int a)  { altura = a; }
    public int area() { return largura * altura; }
}

public class Quadrado extends Retangulo {
    @Override public void setLargura(int l) { largura = altura = l; } // VIOLA LSP
    @Override public void setAltura(int a)  { largura = altura = a; } // comportamento inesperado
}

// CORRETO — hierarquia honesta com sealed classes Java 17+
public sealed interface Forma permits Retangulo, Quadrado {
    int area();
}
public record Retangulo(int largura, int altura) implements Forma {
    public int area() { return largura * altura; }
}
public record Quadrado(int lado) implements Forma {
    public int area() { return lado * lado; }
}
```

---

### I — Interface Segregation Principle
> *"Nenhum cliente deve ser forçado a depender de interfaces que não usa."*

```java
// VIOLAÇÃO — interface gorda
public interface PedidoRepository {
    Pedido buscarPorId(PedidoId id);
    void salvar(Pedido pedido);
    List<Pedido> buscarRelatorioAnual(int ano);   // só usado por 1 use case
    void atualizarStatusEmLote(List<PedidoId> ids); // operação administrativa
}

// CORRETO — interfaces focadas, Java 25
public interface PedidoReader {
    Optional<Pedido> buscarPorId(PedidoId id);
}
public interface PedidoWriter {
    void salvar(Pedido pedido);
}
public interface PedidoRelatorio {
    List<PedidoResumo> buscarRelatorioAnual(int ano);
}

// Use case depende apenas do que usa
public class ConfirmarPedidoUseCase {
    public ConfirmarPedidoUseCase(PedidoReader reader, PedidoWriter writer, ...) {}
}
```

---

### D — Dependency Inversion Principle
> *"Módulos de alto nível não devem depender de módulos de baixo nível. Ambos devem depender de abstrações."*

```java
// VIOLAÇÃO — domínio conhece infraestrutura
public class PedidoService {
    private final JpaRepository<Pedido, Long> jpaRepo; // JPA é infraestrutura!
    private final KafkaTemplate<String, PedidoEvent> kafka; // Kafka é infraestrutura!
}

// CORRETO — Regra da Dependência (Clean Architecture)
// Domínio define as portas (interfaces)
// Infraestrutura implementa as portas (adapters)

// camada: domain (sem dependências externas)
public interface PedidoRepository { Optional<Pedido> buscarPorId(PedidoId id); }
public interface EventosPedido     { void pedidoConfirmado(Pedido pedido); }

// camada: infrastructure (depende do domínio, nunca o contrário)
@Repository
public class PedidoJpaRepository implements PedidoRepository {
    private final PedidoJpaDao dao;
    public Optional<Pedido> buscarPorId(PedidoId id) {
        return dao.findById(id.valor()).map(PedidoMapper::toDomain);
    }
}

@Component
public class PedidoKafkaPublisher implements EventosPedido {
    private final KafkaTemplate<String, PedidoEvent> kafka;
    public void pedidoConfirmado(Pedido pedido) {
        kafka.send("pedidos.confirmados", PedidoEventMapper.from(pedido));
    }
}
```

```python
# CORRETO — Python 3.12+ com Protocol (structural subtyping — sem herança forçada)
from typing import Protocol, runtime_checkable

@runtime_checkable
class PedidoRepository(Protocol):
    def buscar_por_id(self, pedido_id: int) -> "Pedido | None": ...
    def salvar(self, pedido: "Pedido") -> None: ...

# Infraestrutura implementa o Protocol sem importar o domínio
class PedidoSQLAlchemyRepository:  # nem precisa declarar "implements"
    def buscar_por_id(self, pedido_id: int) -> "Pedido | None":
        ...
    def salvar(self, pedido: "Pedido") -> None:
        ...
```

---

## Testes Validando Princípios SOLID

Além dos testes funcionais, inclua testes de arquitetura que validem automaticamente a aderência aos princípios SOLID. Use ArchUnit (Java) ou equivalente.

### Java 25 — ArchUnit para SOLID

```java
// SRP — Nenhum use case com mais de 1 método público de execução
@ArchTest
static final ArchRule useCasesShouldHaveSinglePublicMethod =
    classes().that().resideInAPackage("..application.usecases..")
        .should(new ArchCondition<>("ter no máximo 1 método público de execução") {
            @Override
            public void check(JavaClass clazz, ConditionEvents events) {
                long publicMethods = clazz.getMethods().stream()
                    .filter(m -> m.getModifiers().contains(JavaModifier.PUBLIC))
                    .filter(m -> !m.getName().equals("toString")
                              && !m.getName().equals("hashCode")
                              && !m.getName().equals("equals"))
                    .count();
                if (publicMethods > 1) {
                    events.add(SimpleConditionEvent.violated(clazz,
                        "%s tem %d métodos públicos (SRP violado)".formatted(
                            clazz.getSimpleName(), publicMethods)));
                }
            }
        });

// OCP — Domain não depende de implementações concretas de infra
@ArchTest
static final ArchRule domainShouldNotDependOnInfrastructure =
    noClasses().that().resideInAPackage("..domain..")
        .should().dependOnClassesThat()
        .resideInAnyPackage("..infrastructure..", "..adapters..");

// LSP — Nenhuma classe lança UnsupportedOperationException
@ArchTest
static final ArchRule noUnsupportedOperationInDomain =
    noClasses().that().resideInAPackage("..domain..")
        .should().callMethod(UnsupportedOperationException.class, "<init>");

// ISP — Interfaces de porta com no máximo 5 métodos
@ArchTest
static final ArchRule portInterfacesShouldBeSmall =
    classes().that().resideInAPackage("..application.ports..")
        .and().areInterfaces()
        .should(new ArchCondition<>("ter no máximo 5 métodos") {
            @Override
            public void check(JavaClass clazz, ConditionEvents events) {
                if (clazz.getMethods().size() > 5) {
                    events.add(SimpleConditionEvent.violated(clazz,
                        "%s tem %d métodos (ISP violado)".formatted(
                            clazz.getSimpleName(), clazz.getMethods().size())));
                }
            }
        });

// DIP — Use cases dependem apenas de interfaces (ports), não de implementações
@ArchTest
static final ArchRule useCasesShouldDependOnlyOnPorts =
    classes().that().resideInAPackage("..application.usecases..")
        .should().onlyDependOnClassesThat()
        .resideInAnyPackage("..domain..", "..application.ports..",
            "..application.usecases..", "java..", "jakarta..");
```

### Python 3.12+ — Pytest para SOLID

```python
# test_architecture_solid.py
import importlib, inspect, pkgutil

def test_srp_use_cases_have_single_public_method():
    """SRP: cada use case tem apenas 1 método público (execute/handle)."""
    import app.application.usecases as pkg
    for _, name, _ in pkgutil.iter_modules(pkg.__path__):
        mod = importlib.import_module(f"app.application.usecases.{name}")
        for cls_name, cls in inspect.getmembers(mod, inspect.isclass):
            public = [m for m in dir(cls) if not m.startswith("_")
                      and callable(getattr(cls, m))]
            assert len(public) <= 2, f"{cls_name} tem {len(public)} métodos públicos (SRP)"

def test_dip_domain_has_no_infrastructure_imports():
    """DIP: domain layer nunca importa infrastructure."""
    import app.domain as domain_pkg
    for _, name, _ in pkgutil.iter_modules(domain_pkg.__path__):
        mod = importlib.import_module(f"app.domain.{name}")
        source = inspect.getsource(mod)
        assert "infrastructure" not in source, f"domain.{name} importa infrastructure (DIP)"
        assert "sqlalchemy" not in source, f"domain.{name} importa sqlalchemy (DIP)"
```

**Checklist de Testes SOLID:**
- ✅ SRP: Use cases com método público único validado via ArchUnit
- ✅ OCP: Domain não depende de infrastructure (ArchUnit `noClasses`)
- ✅ LSP: Nenhuma `UnsupportedOperationException` no domínio
- ✅ ISP: Interfaces de porta com ≤ 5 métodos
- ✅ DIP: Use cases dependem apenas de ports e domain
- ✅ Executar testes de arquitetura no CI (fase de build)

---

