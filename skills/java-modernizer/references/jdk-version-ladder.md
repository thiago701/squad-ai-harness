# Catálogo de Recursos por Versão de JDK (25 → 21 → 17 → 14/11/8)

Referência completa da **escada de versões** da skill `java-modernizer`. Cada recurso traz: status (final/preview), a versão exata que o introduziu, o **condicional/antipadrão que ele elimina** e um par antes/depois.

**Regra de ouro:** nunca proponha um recurso acima da versão-alvo do projeto. Se for *preview* na versão-alvo, sinalize que exige `--enable-preview` e carrega risco de mudança.

## Índice
- [Java 25 (prioridade máxima)](#java-25-prioridade-máxima)
- [Java 21 (LTS — o coração da eliminação de condicionais)](#java-21-lts)
- [Java 17 (LTS — as fundações)](#java-17-lts)
- [Java 14 / 11 / 8 (apenas os melhores)](#java-14--11--8)
- [Tabela de "introduzido em" (anti-confusão)](#tabela-de-introduzido-em)

---

## Java 25 (prioridade máxima)
GA em 16/09/2025. Primeira LTS depois do 21. 18 JEPs; 7 finalizados. Abaixo, os que importam para refatoração de condicionais.

### 🟢 FINAL — seguros para produção

#### Flexible Constructor Bodies (JEP 513) ⭐
**Mata:** validação tortuosa em construtor. Antes, `super()`/`this()` tinha que ser a primeira instrução, forçando *helper* estático para validar argumentos. Agora o guard clause vive naturalmente no topo do construtor.

```java
// 🔴 Antes — validação empurrada para método estático, ou aninhada
class PremiumUser extends User {
    private final double desconto;
    public PremiumUser(String nome, int idade, double desconto) {
        super(nome, validarIdade(idade));      // super precisa vir primeiro
        if (desconto < 0 || desconto > 1.0)    // validação só DEPOIS do super
            throw new IllegalArgumentException("Desconto inválido");
        this.desconto = desconto;
    }
    private static int validarIdade(int i) { /* helper só pra contornar a regra */ return i; }
}

// 🟢 Depois — guard clause antes do super(), sem helper
class PremiumUser extends User {
    private final double desconto;
    public PremiumUser(String nome, int idade, double desconto) {
        if (desconto < 0 || desconto > 1.0)
            throw new IllegalArgumentException("Desconto deve estar entre 0 e 1");
        if (idade < 18)
            throw new IllegalArgumentException("Idade mínima 18");
        super(nome, idade);                    // agora pode vir depois da validação
        this.desconto = desconto;
    }
}
```

#### Module Import Declarations (JEP 511)
**Mata:** muro de `import` (cerimônia — P1). Importa todos os pacotes exportados por um módulo numa linha.

```java
// 🔴 Antes
import java.util.List;
import java.util.Map;
import java.util.ArrayList;
import java.util.HashMap;

// 🟢 Depois
import module java.base;   // List, Map, ArrayList, HashMap, ...
// ⚠️ atenção a ambiguidade: importar java.base e java.sql juntos torna 'Date' ambíguo
```

#### Scoped Values (JEP 506)
**Mata:** `ThreadLocal` + lógica defensiva de `.remove()`/null em concorrência, e o antipadrão de arrastar contexto por toda assinatura de método. Imutável, propaga para subtasks. (Detalhe fino de Virtual Threads/Structured Concurrency é território de `java25-spring-boot`.)

```java
// 🔴 Antes — ThreadLocal com risco de leak e null defensivo
static final ThreadLocal<String> CTX = new ThreadLocal<>();
void handle(String userId) {
    CTX.set(userId);
    try { processar(); } finally { CTX.remove(); }   // esquecer o remove() = leak
}
void processar() {
    String u = CTX.get();
    if (u == null) u = "anonimo";                     // checagem defensiva
}

// 🟢 Depois — imutável, escopo lexical, sem remove(), sem null
static final ScopedValue<String> CTX = ScopedValue.newInstance();
void handle(String userId) {
    ScopedValue.where(CTX, userId).run(this::processar);
}
void processar() {
    String u = CTX.get();   // garantidamente presente dentro do escopo
}
```

#### Compact Object Headers (JEP 519) — produto, mas **não-default**
**Mata:** parte do custo de heap que penalizava a **Regra 3 da Calistenia** (envolver primitivos em Value Objects). Funde *mark word* + *class pointer* num único cabeçalho: de **12 → 8 bytes**, ~**22% menos heap** e ~15% menos GC em cargas típicas — sem reescrever uma linha de aplicação.

```text
# Habilitar (NÃO é default no JDK 25):
java -XX:+UseCompactObjectHeaders -jar app.jar
```

⚠️ **Restrições reais (verifique antes de prometer o ganho):** não está ligado por default; **incompatível com ZGC** (use G1/Parallel); e heaps **> 32 GB** não podem usar (dependem de *compressed class pointers*). É o que viabiliza a Regra 3 sem culpa de memória — enquanto Value Classes (Valhalla/JEP 401) **não chegam antes do JDK 28**.

### ⚠️ PREVIEW — exigem `--enable-preview`, NÃO use em produção sem decisão consciente

#### Primitive Types in Patterns, instanceof, switch (JEP 507 — 3º preview)
**Mata:** cadeias de range-check em primitivos. Estende pattern matching para `int`, `long`, etc.

```java
// 🔴 Antes — cadeia de range em primitivo
String classificar(int status) {
    if (status == 200) return "OK";
    else if (status >= 400 && status < 500) return "erro cliente";
    else if (status >= 500) return "erro servidor";
    else return "desconhecido";
}

// 🟢 Depois (PREVIEW) — guarded primitive patterns
String classificar(int status) {
    return switch (status) {
        case 200 -> "OK";
        case int i when i >= 400 && i < 500 -> "erro cliente";
        case int i when i >= 500           -> "erro servidor";
        default -> "desconhecido";
    };
}
// ⚠️ Preview no JDK 25. Em produção sem flag, mantenha o if/else ou um switch tradicional.
```

#### Stable Values (JEP 502 — preview)
**Mata:** lazy-init `if (x == null) x = ...` e double-checked locking. Constante para a JVM, mas atribuível depois da construção.

```java
// 🔴 Antes — lazy init com checagem de null (e risco em concorrência)
private Logger logger;
Logger getLogger() {
    if (logger == null) logger = Logger.create(OrderController.class);
    return logger;
}

// 🟢 Depois (PREVIEW) — sem null, otimizado como final
private final StableValue<Logger> logger = StableValue.of();
Logger getLogger() {
    return logger.orElseSet(() -> Logger.create(OrderController.class));
}
// ⚠️ Preview no JDK 25.
```

---

## Java 21 (LTS)
GA em 09/2023. **O coração da eliminação de condicionais.** Tudo abaixo é **final**.

#### Pattern Matching for switch + Guarded Patterns (JEP 441) ⭐⭐
**Mata:** cadeias `if/else-if/instanceof` de dispatch por tipo. O recurso mais importante desta skill. Inclui `case null` e guardas com `when`.

```java
// 🔴 Antes — if/instanceof + cast
public void enviar(Object canal, String msg) {
    if (canal instanceof EmailCanal) {
        ((EmailCanal) canal).enviarEmail(msg);
    } else if (canal instanceof SmsCanal) {
        ((SmsCanal) canal).enviarSms(msg);
    } else if (canal instanceof PushCanal) {
        ((PushCanal) canal).dispararPush(msg);
    }
}

// 🟢 Depois — switch com type patterns, sem cast
public void enviar(Object canal, String msg) {
    switch (canal) {
        case EmailCanal e -> e.enviarEmail(msg);
        case SmsCanal s   -> s.enviarSms(msg);
        case PushCanal p  -> p.dispararPush(msg);
        case null, default -> throw new IllegalArgumentException("Canal inválido");
    }
}
```

#### Record Patterns (JEP 440)
**Mata:** getters aninhados + null checks (`a.getB().getC()`). Desconstrói records em profundidade dentro de `switch`/`instanceof`.

```java
record Endereco(String cidade, String pais) {}
record Cliente(String nome, Endereco endereco) {}
record Pedido(Long id, Cliente cliente, List<Item> itens) {}

// 🟢 Desconstrução profunda — um teste, todas as variáveis tipadas
if (obj instanceof Pedido(var id, Cliente(var nome, Endereco(_, var pais)), _)) {
    log.info("Pedido {} de {} no país {}", id, nome, pais);
}
```

#### Sealed + Switch Exaustivo (sealed=17, exaustividade plena=21)
**Mata:** ramo `default` defensivo e o bug do "esqueci um caso". O compilador exige que todos os subtipos sejam cobertos.

```java
sealed interface ResultadoPagamento permits Aprovado, Recusado, EmAnalise {}
record Aprovado(String txId) implements ResultadoPagamento {}
record Recusado(String motivo) implements ResultadoPagamento {}
record EmAnalise(Duration estimativa) implements ResultadoPagamento {}

// 🟢 Sem default — compilador garante exaustividade; adicionar um subtipo novo QUEBRA a compilação (de propósito)
String mensagem = switch (resultado) {
    case Aprovado(var tx)        -> "Aprovado: " + tx;
    case Recusado(var motivo)    -> "Recusado: " + motivo;
    case EmAnalise(var tempo)    -> "Em análise (~" + tempo.toMinutes() + " min)";
};
```

#### Sequenced Collections (JEP 431)
**Mata:** `list.get(list.size()-1)` e checagens de borda. Adiciona `getFirst()`, `getLast()`, `addFirst/Last`, `reversed()`.

```java
// 🔴 Antes
if (!lista.isEmpty()) {
    var ultimo = lista.get(lista.size() - 1);
}
// 🟢 Depois
var ultimo = lista.getLast();       // lança se vazio — explícito
var aoContrario = lista.reversed(); // sem Collections.reverse() mutando
```

#### Virtual Threads (JEP 444)
**Mata:** inferno de callbacks/async condicional. Código que lê como sequencial e escala como assíncrono. *Detalhamento (pinning, sizing de pool, Structured Concurrency) pertence a `java25-spring-boot` — não duplique aqui.*

---

## Java 17 (LTS)
GA em 09/2021. As fundações do pattern matching moderno. Tudo abaixo é **final** (alguns finalizados em 16, disponíveis no 17).

#### Sealed Classes (JEP 409)
**Mata:** hierarquia aberta que força ramo `default` defensivo. Restringe quem pode implementar/estender, habilitando matching exaustivo.

```java
public sealed interface Forma permits Circulo, Retangulo, Triangulo {}
public record Circulo(double raio) implements Forma {}
public record Retangulo(double base, double altura) implements Forma {}
public record Triangulo(double base, double altura) implements Forma {}
```

#### Pattern Matching for instanceof (JEP 394, final no 16)
**Mata:** `instanceof` seguido de cast manual verboso.

```java
// 🔴 Antes
if (forma instanceof Retangulo) {
    Retangulo r = (Retangulo) forma;
    return r.base() * r.altura();
}
// 🟢 Depois — testa e vincula a variável tipada na mesma linha
if (forma instanceof Retangulo r) {
    return r.base() * r.altura();
}
```

#### Records (JEP 395, final no 16)
**Mata:** boilerplate de DTO (getters/equals/hashCode/toString) e dados mutáveis. Portador de dados imutável.

```java
// 🔴 Antes — ~40 linhas de getter/setter/equals/hashCode/toString
public class PontoDTO { private int x; private int y; /* ... */ }

// 🟢 Depois
public record Ponto(int x, int y) {}   // imutável, equals/hashCode/toString prontos
```

#### Switch Expressions (JEP 361, final no 14)
**Mata:** `switch`-statement com `break`, fall-through acidental e o `if/else` que só atribui um valor a uma variável. Retorna valor; usa `->` e `yield`.

```java
// 🔴 Antes — statement com break, propenso a fall-through
int dias;
switch (mes) {
    case JAN: case MAR: dias = 31; break;
    case FEV: dias = 28; break;
    default: dias = 30;
}
// 🟢 Depois — expressão que retorna valor, sem break, sem fall-through
int dias = switch (mes) {
    case JAN, MAR -> 31;
    case FEV      -> 28;
    default       -> 30;
};
```

#### Text Blocks (JEP 378, final no 15)
**Mata:** escada de concatenação de String com `\n` e `+`. Tangencial a condicionais, mas idioma moderno essencial.

```java
String json = """
    { "nome": "%s", "ativo": %b }
    """.formatted(nome, ativo);
```

---

## Java 14 / 11 / 8
Apenas os melhores recursos — a base sobre a qual tudo acima foi construído.

### Java 14 (GA 03/2020)
- **Switch Expressions (final aqui)** — ver acima; primeira versão estável.
- **Helpful NullPointerExceptions** — a mensagem aponta *qual* variável era null (`Cannot invoke "...getCidade()" because the return value of "...getEndereco()" is null`). Reduz drasticamente o tempo de depuração de condicionais relacionados a null.

### Java 11 (LTS, GA 09/2018)
- **String API:** `isBlank()`, `strip()`, `lines()`, `repeat(n)`.
  ```java
  // 🔴 if (s != null && s.trim().isEmpty())   // "branco" mal definido
  // 🟢 if (s.isBlank())                        // intenção explícita
  ```
- **`var` em parâmetros de lambda** (JEP 323) — permite anotações em params de lambda.
- **`Files.readString` / `Files.writeString`** — mata boilerplate de I/O com BufferedReader.
- **`Predicate.not()`** — `.filter(not(String::isBlank))` lê melhor que negação manual.

### Java 8 (GA 03/2014) ⭐ — a fundação
- **Optional** — mata `if (x != null)`, o antipadrão mais comum.
  ```java
  // 🔴 Antes
  if (usuario != null) {
      Endereco e = usuario.getEndereco();
      if (e != null) return e.getCidade();
  }
  return "não informado";
  // 🟢 Depois
  return Optional.ofNullable(usuario)
          .map(Usuario::getEndereco)
          .map(Endereco::getCidade)
          .orElse("não informado");
  ```
- **Streams API** — mata `for` + `if` de filtro/map/redução.
  ```java
  // 🔴 for + if acumulando em lista
  // 🟢 lista.stream().filter(n -> n.startsWith("T")).map(String::toUpperCase).toList();
  //    (.toList() é Java 16; em 8-15 use .collect(Collectors.toList()))
  ```
- **Lambdas + Functional Interfaces** — comportamento como parâmetro; viabilizam Strategy sem anonymous-class verbosa.
- **Method References** — `Usuario::getPerfil` no lugar de `u -> u.getPerfil()`.
- **Default Methods** — evolução de interface sem quebrar implementadores existentes.
- **`java.time`** — datas imutáveis; mata bugs de mutação de `Calendar`/`Date`.
- **`CompletableFuture`** — async composável (hoje, em Java 21+, frequentemente substituído por Virtual Threads para I/O — ver Java 21).

---

## Tabela de "introduzido em" (anti-confusão)
A fonte de erro mais comum é citar a versão errada. O compilador da equipe decide o baseline por estes números — acerte-os.

| Recurso | Preview em | **Final em** |
|---|---|---|
| Lambdas, Streams, Optional | — | **8** |
| `var` (local) | — | **10** |
| `var` em lambda params | — | **11** |
| Switch Expressions | 12, 13 | **14** |
| Text Blocks | 13, 14 | **15** |
| Records | 14, 15 | **16** |
| Pattern Matching `instanceof` | 14, 15 | **16** |
| `Stream.toList()` | — | **16** |
| Sealed Classes | 15, 16 | **17** |
| Pattern Matching `switch` | 17, 18, 19, 20 | **21** |
| Record Patterns | 19, 20 | **21** |
| Virtual Threads | 19, 20 | **21** |
| Sequenced Collections | — | **21** |
| Stream Gatherers | 22, 23 | **24** |
| Scoped Values | 20–24 | **25** |
| Module Import Declarations | 23, 24 | **25** |
| Flexible Constructor Bodies | 22, 23, 24 | **25** |
| Compact Source Files / `void main()` | 21–24 | **25** |
| Compact Object Headers (JEP 519) | exp. 24 | **25** (produto, opt-in, sem ZGC) |
| Primitive Type Patterns | 23, 24, **25** | — (preview) |
| Stable Values | **25** | — (preview) |

> Lembrete operacional: "Pattern matching de `switch` é Java **21**" e "Records são Java **16**". Não diga "Java 17" para esses — é a confusão que mais aparece em material de blog.
