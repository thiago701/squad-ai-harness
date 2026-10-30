# Catálogo de Transformações (Antipadrão → Idioma Moderno)

Receitas completas das transformações canônicas da skill `java-modernizer`. Cada uma: o *smell*, o antes (🔴), o depois (🟢) e a justificativa com versão de JDK e trade-off (P1). Roteie pelo smell que você observa no código.

## Índice
1. [Cadeia if/else por tipo → Strategy (enum ou classes)](#1-cadeia-ifelse-por-tipo--strategy)
2. [Pirâmide de aninhamento → Guard Clauses](#2-pirâmide-de-aninhamento--guard-clauses)
3. [Navegação com null → Optional](#3-navegação-com-null--optional)
4. [instanceof + cast → Pattern Matching](#4-instanceof--cast--pattern-matching)
5. [Comportamento por status → State Pattern](#5-comportamento-por-status--state-pattern)
6. [for + if → Streams](#6-for--if--streams)

---

## 1. Cadeia if/else por tipo → Strategy

**Smell:** `if (tipo.equals("X")) ... else if (tipo.equals("Y")) ...` escolhendo qual **comportamento** rodar. Cada regra nova obriga a abrir e modificar a classe (viola OCP).

```java
// 🔴 Antipadrão — toda transportadora nova exige editar este arquivo
public class CalculadoraFrete {
    public double calcularFrete(String tipoEnvio, double peso) {
        if (tipoEnvio.equalsIgnoreCase("SEDEX"))      return (peso * 1.5) + 10.0;
        else if (tipoEnvio.equalsIgnoreCase("PAC"))   return (peso * 0.8) + 5.0;
        else if (tipoEnvio.equalsIgnoreCase("LOGGI")) return (peso * 2.0) + 15.0;
        else if (tipoEnvio.equalsIgnoreCase("DHL"))   return (peso * 3.5) + 25.0;
        else throw new IllegalArgumentException("Tipo não suportado: " + tipoEnvio);
    }
}
```

**Opção A — enum estratégico (mais enxuto, P1, para família fechada e pequena):**

```java
// 🟢 Cada regra encapsulada; motor sem condicional
public interface EstrategiaFrete {
    double calcular(double peso);
}

public enum TipoEnvio implements EstrategiaFrete {
    SEDEX { public double calcular(double peso) { return (peso * 1.5) + 10.0; } },
    PAC   { public double calcular(double peso) { return (peso * 0.8) + 5.0;  } },
    LOGGI { public double calcular(double peso) { return (peso * 2.0) + 15.0; } },
    DHL   { public double calcular(double peso) { return (peso * 3.5) + 25.0; } };
    // ↑ NOTA: o método é 'calcular' em TODOS. (O material original tinha um bug aqui:
    //   DHL sobrescrevia 'calculate' em inglês — não compilaria. Corrigido.)
}

public class CalculadoraFrete {
    public double calcularFrete(TipoEnvio tipo, double peso) {
        return tipo.calcular(peso);   // zero if, OCP respeitado
    }
}
```

**Opção B — classes Strategy + injeção (para família aberta/extensível por terceiros, ou regras complexas com dependências):**

```java
public interface EstrategiaFrete { double calcular(double peso); String codigo(); }

public class FreteSedex implements EstrategiaFrete {
    public double calcular(double peso) { return (peso * 1.5) + 10.0; }
    public String codigo() { return "SEDEX"; }
}
// ... uma classe por transportadora; registradas num Map<String, EstrategiaFrete> (ex.: via Spring)

public class CalculadoraFrete {
    private final Map<String, EstrategiaFrete> estrategias;   // injetado
    public double calcularFrete(String codigo, double peso) {
        var e = estrategias.get(codigo.toUpperCase());
        if (e == null) throw new IllegalArgumentException("Tipo não suportado: " + codigo);
        return e.calcular(peso);
    }
}
```

**🧠 Justificativa:** OCP + polimorfismo (Java 8 viabiliza a forma enxuta com enum/lambda). **⚖️ Trade-off (P1):** se a família é fechada e conhecida em compile-time, a **Opção A (enum)** ou um `switch` sobre `sealed` (Java 21) é mais simples que injetar N classes. Escolha B só quando as estratégias têm dependências próprias ou o conjunto é estendido por outros módulos.

---

## 2. Pirâmide de aninhamento → Guard Clauses

**Smell:** o "código em flecha" — o fluxo feliz enterrado sob 3-4 níveis de `if`, com `else` jogando os erros lá no fundo.

```java
// 🔴 Antipadrão — fluxo feliz no nível mais profundo
public void matricular(Estudante e, Curso c) {
    if (e != null) {
        if (c != null) {
            if (c.temVagas()) {
                if (!e.matriculadoEm(c)) {
                    c.adicionar(e);
                    e.vincular(c);
                } else { throw new IllegalStateException("Já matriculado"); }
            } else { throw new IllegalStateException("Sem vagas"); }
        } else { throw new IllegalArgumentException("Curso inválido"); }
    } else { throw new IllegalArgumentException("Estudante inválido"); }
}
```

```java
// 🟢 Guard Clauses — valida e sai cedo; fluxo feliz linear na raiz
public void matricular(Estudante e, Curso c) {
    if (e == null) throw new IllegalArgumentException("Estudante inválido");
    if (c == null) throw new IllegalArgumentException("Curso inválido");
    if (!c.temVagas()) throw new IllegalStateException("Sem vagas");
    if (e.matriculadoEm(c)) throw new IllegalStateException("Já matriculado");

    c.adicionar(e);   // fluxo feliz, 1 nível, sem else
    e.vincular(c);
}
```

**🧠 Justificativa:** Object Calisthenics (1 nível de indentação, sem `else`). Disponível em qualquer Java. Derruba a complexidade ciclomática e a cognitiva. **⚖️ Trade-off:** nenhum relevante — esta é quase sempre uma melhoria pura. (Os `if` que sobraram são *guard clauses* e são bons: o alvo era o aninhamento, não a keyword.)

---

## 3. Navegação com null → Optional

**Smell:** cadeia de `if (x != null)` para navegar uma cadeia de objetos sem estourar `NullPointerException`.

```java
// 🔴 Antipadrão — escada de null checks
public String telefoneSuporte(Cliente cliente) {
    if (cliente != null) {
        Contrato contrato = cliente.getContratoAtivo();
        if (contrato != null) {
            EmpresaParceira p = contrato.getEmpresaParceira();
            if (p != null) {
                List<String> tels = p.getTelefones();
                if (tels != null && !tels.isEmpty()) return tels.get(0);
            }
        }
    }
    return "não cadastrado";
}
```

```java
// 🟢 Optional encadeado — declarativo, diz o QUE quer
public String telefoneSuporte(Cliente cliente) {
    return Optional.ofNullable(cliente)
            .map(Cliente::getContratoAtivo)
            .map(Contrato::getEmpresaParceira)
            .map(EmpresaParceira::getTelefones)
            .flatMap(tels -> tels.stream().findFirst())
            .orElse("não cadastrado");
}
```

**🧠 Justificativa:** `Optional` (Java 8). Cada `.map()` só executa se o anterior teve valor; o `flatMap` lida com o `Optional<Optional<>>` da busca na lista. **⚖️ Trade-off (P1):** para **um único** nível de null (`if (x != null) return x.getY()`), `Optional` é exagero — o `if` direto é mais simples. O ganho aparece em cadeias de 2+ navegações. Não embrulhe tudo em `Optional` por reflexo.

---

## 4. instanceof + cast → Pattern Matching

**Smell:** `if (obj instanceof T)` seguido de `T t = (T) obj;` — checagem e cast manual separados, verbosos e propensos a `ClassCastException` se desalinhados.

```java
// 🔴 Antipadrão (pré-Java 16)
public double area(Object forma) {
    if (forma instanceof Retangulo) {
        Retangulo r = (Retangulo) forma;
        return r.base() * r.altura();
    } else if (forma instanceof Circulo) {
        Circulo c = (Circulo) forma;
        return Math.PI * c.raio() * c.raio();
    }
    throw new IllegalArgumentException("Forma desconhecida");
}
```

```java
// 🟢 Java 16: pattern matching de instanceof (testa + vincula)
public double area(Object forma) {
    if (forma instanceof Retangulo r) return r.base() * r.altura();
    if (forma instanceof Circulo c)   return Math.PI * c.raio() * c.raio();
    throw new IllegalArgumentException("Forma desconhecida");
}

// 🟢🟢 Java 21 + sealed: switch exaustivo, sem default, compilador garante cobertura
sealed interface Forma permits Retangulo, Circulo {}
public double area(Forma forma) {
    return switch (forma) {
        case Retangulo r -> r.base() * r.altura();
        case Circulo c   -> Math.PI * c.raio() * c.raio();
    };  // sem default: adicionar um subtipo novo quebra a compilação até você tratá-lo
}
```

**🧠 Justificativa:** Pattern Matching `instanceof` (Java 16) elimina o cast; combinado com `sealed` + `switch` (Java 21) elimina também o ramo `default` defensivo e transforma "esqueci um caso" em erro de compilação. **⚖️ Trade-off:** a versão sealed exige que o conjunto de tipos seja **fechado**. Se terceiros precisam adicionar formas, use Strategy (Transformação 1) em vez de sealed.

---

## 5. Comportamento por status → State Pattern

**Smell:** `if (pedido.getStatus() == RASCUNHO) ... else if (== PAGO) ...` repetido em *vários* métodos. A lógica de cada estado fica espalhada e duplicada.

```java
// 🔴 Antipadrão — switch de status repetido em cada operação
public class Pedido {
    private Status status;
    public void pagar() {
        switch (status) {
            case RASCUNHO -> status = Status.PAGO;
            case PAGO -> throw new IllegalStateException("Já pago");
            case ENVIADO -> throw new IllegalStateException("Já enviado");
        }
    }
    public void enviar() {
        switch (status) {   // o MESMO switch, de novo, com outra regra
            case RASCUNHO -> throw new IllegalStateException("Pague antes");
            case PAGO -> status = Status.ENVIADO;
            case ENVIADO -> throw new IllegalStateException("Já enviado");
        }
    }
}
```

```java
// 🟢 State Pattern — cada estado é uma classe que sabe se comportar e transicionar
public interface EstadoPedido {
    EstadoPedido pagar();
    EstadoPedido enviar();
}
public final class Rascunho implements EstadoPedido {
    public EstadoPedido pagar()  { return new Pago(); }
    public EstadoPedido enviar() { throw new IllegalStateException("Pague antes"); }
}
public final class Pago implements EstadoPedido {
    public EstadoPedido pagar()  { throw new IllegalStateException("Já pago"); }
    public EstadoPedido enviar() { return new Enviado(); }
}
public final class Enviado implements EstadoPedido {
    public EstadoPedido pagar()  { throw new IllegalStateException("Já enviado"); }
    public EstadoPedido enviar() { throw new IllegalStateException("Já enviado"); }
}
public class Pedido {
    private EstadoPedido estado = new Rascunho();
    public void pagar()  { estado = estado.pagar(); }
    public void enviar() { estado = estado.enviar(); }
}
```

**🧠 Justificativa:** State Pattern (GoF). Cada transição vive num lugar; adicionar um estado é uma classe nova, não mais um `case` em cada método. **⚖️ Trade-off (P1):** este é o padrão mais fácil de *overengineering*. Só vale quando os estados têm **múltiplos comportamentos divergentes**. Para uma máquina de 2-3 estados com uma transição cada, um `enum` com um `switch` expression (Java 21, sobre sealed/enum) é mais simples — **não crie 4 classes para o que um enum resolve**.

---

## 6. for + if → Streams

**Smell:** laço imperativo com `if` interno para filtrar, transformar ou acumular uma coleção.

```java
// 🔴 Antipadrão
List<String> resultado = new ArrayList<>();
for (Usuario u : usuarios) {
    if (u.isAtivo() && u.getIdade() >= 18) {
        resultado.add(u.getNome().toUpperCase());
    }
}
resultado.sort(Comparator.naturalOrder());
```

```java
// 🟢 Stream declarativo — diz o QUE, não o COMO
List<String> resultado = usuarios.stream()
        .filter(Usuario::isAtivo)
        .filter(u -> u.getIdade() >= 18)
        .map(u -> u.getNome().toUpperCase())
        .sorted()
        .toList();   // Java 16; em 8-15: .collect(Collectors.toList())
```

**🧠 Justificativa:** Streams + lambdas (Java 8), `.toList()` (Java 16). Filtros encadeados leem como a especificação do requisito. **⚖️ Trade-off (P2):** em *hot path* de latência com coleções grandes, o `for` simples evita overhead de alocação de Stream e pode ser mais rápido — meça com JMH antes de assumir. E um Stream com 6+ operadores e `flatMap` opaco pode ser *menos* legível que um `for` honesto (P1): declarativo serve à clareza; quando não serve, recue.

---

## Regra de roteamento (resumo)

| Você vê... | Aplique... |
|---|---|
| `if/else` escolhendo **comportamento** por tipo/string | Transformação 1 (Strategy / sealed+switch) |
| `if` aninhado escondendo o fluxo feliz | Transformação 2 (Guard Clauses) |
| Cadeia de `if (x != null)` navegando objetos | Transformação 3 (Optional) |
| `instanceof` + cast manual | Transformação 4 (Pattern Matching) |
| `if (status == ...)` repetido em vários métodos | Transformação 5 (State) |
| `for` + `if` filtrando/transformando coleção | Transformação 6 (Streams) |

E sempre, ao final: **o resultado ficou mais simples (P1)?** Se não, o original fica.
