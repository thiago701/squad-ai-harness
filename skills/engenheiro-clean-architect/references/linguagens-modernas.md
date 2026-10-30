# Referência — Java 25 e Python 3.12+ — features que elevam o design

> Parte da skill `engenheiro-clean-architect`. Carregue sob demanda. Hub: `../SKILL.md`.
## Java 25 — Novidades que Elevam o Design

### Flexible Constructor Bodies (JEP 513) — Validação antes de `super()`

A partir do JDK 25, construtores podem executar lógica **antes** de `this(...)` ou `super(...)`,
permitindo validação de invariantes sem ginástica com fábricas estáticas.

```java
public class Pedido {
    private final PedidoId id;
    private final List<ItemPedido> itens;

    public Pedido(PedidoId id, List<ItemPedido> itens) {
        // Validação ANTES do super() — novidade JDK 25
        Objects.requireNonNull(id, "id obrigatório");
        if (itens == null || itens.isEmpty())
            throw new DomainException("Pedido sem itens");
        if (itens.size() > 100)
            throw new DomainException("Pedido com mais de 100 itens");

        super();       // inicialização padrão
        this.id = id;
        this.itens = List.copyOf(itens);
    }
}
```

### Module Import Declarations (JEP 511) — imports concisos

```java
// Importa TODO o módulo java.base em uma linha (JDK 25+)
import module java.base;
// Equivalente a: import java.util.*; import java.time.*; import java.io.*; ...
```

Prefira imports específicos em código de domínio (clareza). Use `import module` em
ferramentas, scripts JBang e aulas de ensino.

### Unnamed Variables `_` (JEP 456 — final em JDK 22+)

```java
try { /* ... */ }
catch (IOException _) {            // ignorar a exception mas tratar o fato
    log.warn("falha I/O transiente, aplicando fallback");
}

// Pattern matching com componente irrelevante
switch (evento) {
    case PedidoCriado(var id, _) -> handle(id);   // ignorar timestamp
}
```

### Records como Value Objects (Java 16+)
```java
// Antes: classe verbosa, mutável por acidente
public class PedidoId {
    private final Long valor;
    public PedidoId(Long valor) { this.valor = Objects.requireNonNull(valor); }
    public Long getValor() { return valor; }
    @Override public boolean equals(Object o) { ... } // 10+ linhas
    @Override public int hashCode() { ... }
}

// Agora: Record — imutável, equals/hashCode/toString automáticos
public record PedidoId(Long valor) {
    public PedidoId {  // compact constructor para validação
        Objects.requireNonNull(valor, "PedidoId não pode ser nulo");
        if (valor <= 0) throw new IllegalArgumentException("PedidoId deve ser positivo");
    }
}

// Value Objects do domínio como Records:
public record Email(String valor) {
    public Email {
        if (!valor.matches("^[\\w.-]+@[\\w.-]+\\.[a-z]{2,}$"))
            throw new EmailInvalidoException(valor);
    }
}

public record Dinheiro(BigDecimal valor, String moeda) {
    public Dinheiro somar(Dinheiro outro) {
        if (!moeda.equals(outro.moeda)) throw new MoedasIncompativeisException();
        return new Dinheiro(valor.add(outro.valor), moeda);
    }
}
```

### Sealed Classes como Domínio Rico (Java 17+)
```java
// Estados do domínio como tipos — impossível criar estado inválido
public sealed interface StatusPedido permits Pendente, Confirmado, Enviado, Cancelado {}
public record Pendente(LocalDateTime criadoEm) implements StatusPedido {}
public record Confirmado(LocalDateTime confirmadoEm, String operadorId) implements StatusPedido {}
public record Enviado(LocalDateTime enviadoEm, String codigoRastreio) implements StatusPedido {}
public record Cancelado(LocalDateTime canceladoEm, String motivo) implements StatusPedido {}

// Pattern Matching exaustivo em tempo de compilação (Java 25)
public String descricaoStatus(StatusPedido status) {
    return switch (status) {
        case Pendente p    -> "Aguardando confirmação desde " + p.criadoEm();
        case Confirmado c  -> "Confirmado por " + c.operadorId();
        case Enviado e     -> "Em trânsito: " + e.codigoRastreio();
        case Cancelado c   -> "Cancelado: " + c.motivo();
        // sem default — compilador garante exaustividade
    };
}
```

### Text Blocks para Queries e Templates (Java 15+)
```java
// SQL legível no domínio de repositório
private static final String BUSCAR_PEDIDOS_ATIVOS = """
        SELECT p.id, p.valor, p.status, c.nome AS cliente_nome
          FROM pedidos p
          JOIN clientes c ON c.id = p.cliente_id
         WHERE p.status NOT IN ('CANCELADO', 'DEVOLVIDO')
           AND p.criado_em >= :dataInicio
         ORDER BY p.criado_em DESC
        """;
```

### Virtual Threads — impacto no design (Java 25)
```java
// Com Virtual Threads (Spring Boot 3.2+), cada request tem sua própria thread
// Isso muda o design: código bloqueante simples volta a ser a escolha certa
// NÃO é necessário reactive/WebFlux para escalar I/O

// application.yml:
// spring.threads.virtual.enabled: true

// Design recomendado com Virtual Threads:
@Service
public class RelatorioService {
    public RelatorioCompleto gerarRelatorio(RelatorioId id) {
        // Bloqueante, mas escala porque Virtual Thread não prende OS thread
        var pedidos   = pedidoRepo.buscarParaRelatorio(id);    // I/O bloqueante OK
        var pagamentos = pagamentoRepo.buscarPorPedidos(pedidos); // I/O bloqueante OK
        return RelatorioAssembler.montar(pedidos, pagamentos);
    }
}
```

---

## Python 3.12+ — Features que Elevam o Design

### Type Hints completos como documentação viva
```python
from typing import TypeVar, Generic, Protocol, runtime_checkable
from dataclasses import dataclass, field

T = TypeVar("T")

@runtime_checkable
class Repository(Protocol[T]):
    def buscar_por_id(self, id: int) -> T | None: ...
    def salvar(self, entidade: T) -> None: ...
    def listar(self) -> list[T]: ...

# Value Objects com frozen dataclass
@dataclass(frozen=True)
class Email:
    valor: str

    def __post_init__(self) -> None:
        import re
        if not re.match(r"^[\w.-]+@[\w.-]+\.[a-z]{2,}$", self.valor):
            raise ValueError(f"Email inválido: {self.valor}")

@dataclass(frozen=True)
class Dinheiro:
    valor: Decimal
    moeda: str = "BRL"

    def __add__(self, outro: "Dinheiro") -> "Dinheiro":
        if self.moeda != outro.moeda:
            raise ValueError("Moedas incompatíveis")
        return Dinheiro(self.valor + outro.valor, self.moeda)
```

### match/case para domínio rico (Python 3.10+)
```python
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class Pendente:
    criado_em: datetime

@dataclass(frozen=True)
class Confirmado:
    confirmado_em: datetime
    operador_id: str

@dataclass(frozen=True)
class Cancelado:
    cancelado_em: datetime
    motivo: str

type StatusPedido = Pendente | Confirmado | Cancelado  # Python 3.12 type alias

def descricao_status(status: StatusPedido) -> str:
    match status:
        case Pendente(criado_em=dt):
            return f"Aguardando confirmação desde {dt}"
        case Confirmado(operador_id=op):
            return f"Confirmado por {op}"
        case Cancelado(motivo=m):
            return f"Cancelado: {m}"
```

---

