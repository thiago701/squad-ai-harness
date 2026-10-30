# Calistenia de Objetos × Java 25 — As 9 Regras com Suporte Idiomático

Referência canônica da `java-modernizer` para as **9 regras de Object Calisthenics** (Jeff Bay, 2008) mapeadas ao que o **JDK 25** (GA 16/09/2025) realmente entrega. O que antes era disciplina imposta com boilerplate e custo de runtime virou, em boa parte, **idioma nativo** — mas só onde os fatos sustentam. Esta página separa o que é **final**, o que é **preview** e o que **ainda não chegou**.

**Regra de ouro da skill (P1 > P2 > P3):** a calistenia é heurística a serviço da *simplicidade*, não dogma a serviço da contagem. Toda regra abaixo carrega um **Gate P1** dizendo quando NÃO aplicá-la. Se a regra adiciona mais complexidade do que remove, o original vence.

---

## ⚠️ Correções de fato (o que blogs/IA erram sobre o Java 25)

Antes das regras, três correções que protegem a squad de propor código que não compila em produção:

| Recurso citado como "Java 25" | Realidade verificada (jun/2026) | Consequência para a calistenia |
|---|---|---|
| **Value Classes / Valhalla (JEP 401)** | **NÃO está no JDK 25.** Alvo **JDK 28** (preview), hoje só em *early-access builds*. Provavelmente ainda preview no próximo LTS. | A Regra 3 (envolver primitivos) **não** pode contar com *flattening* de value class hoje. Use `record` + Compact Object Headers. |
| **Derived Record Creation / `with` (JEP 468 — "withers")** | Foi **preview no JDK 23**; **não** consta como recurso do JDK 25. Não há keyword `with` estável. | A Regra 9 usa `record` + métodos `withX()` **explícitos**, não a sintaxe `with` da linguagem. |
| **Compact Object Headers (JEP 519)** | **Final/produto no JDK 25**, porém **NÃO ligado por default** (`-XX:+UseCompactObjectHeaders`), **incompatível com ZGC** e com heaps **> 32 GB** (depende de compressed class pointers). | Mitiga o custo de heap da Regra 3 — mas só sob G1/Parallel e com a flag. Não prometa o ganho sob ZGC. |

> Fonte: OpenJDK JEPs 401/468/519 + notas de release do JDK 25. A escada completa de versões está em `jdk-version-ladder.md`.

---

## Regra 1 — Apenas um nível de indentação por método

**Ataca:** `for` aninhado, `if` dentro de `if` dentro de loop — a complexidade ciclomática que esconde o fluxo feliz.

**Idioma Java 25:** extração de método (qualquer Java) + **Streams** (8) e, para operações intermediárias que antes exigiam laço imperativo (janelas deslizantes, lotes, acumulação histórica), **Stream Gatherers (JEP 485 — final no JDK 24, disponível no 25)**: `windowFixed`, `windowSliding`, `fold`, `mapConcurrent`.

```java
// 🔴 Dois níveis: laço externo + condicional interna acumulando lote
List<List<Pedido>> lotes = new ArrayList<>();
List<Pedido> atual = new ArrayList<>();
for (Pedido p : pedidos) {
    atual.add(p);
    if (atual.size() == 100) { lotes.add(atual); atual = new ArrayList<>(); }
}
if (!atual.isEmpty()) lotes.add(atual);

// 🟢 Um nível, declarativo — o agrupamento vira um Gatherer (JEP 485)
List<List<Pedido>> lotes = pedidos.stream()
        .gather(Gatherers.windowFixed(100))
        .toList();
```

**⚖️ Gate P1:** um `stream()` com 6+ operadores e `flatMap` opaco pode ser *menos* legível que um `for` honesto. E em *hot path* de latência o laço evita overhead de alocação (P2 — meça com JMH). O alvo é o aninhamento, não a existência de um único laço.

---

## Regra 2 — Não use a palavra-chave `else`

**Ataca:** ramificação dupla na cabeça do leitor e o `else` que mascara polimorfismo faltante.

**Idioma Java 25:** **Guard Clauses** (early return/throw) para o caminho de erro; **Pattern Matching for switch (JEP 441 — final no 21)** sobre **Sealed (JEP 409 — final no 17)** para dispatch exaustivo *sem* `default` defensivo. O compilador vira a rede de segurança: esquecer um caso **quebra a build**.

```java
// 🔴 else encadeado mascarando dispatch por tipo
String texto;
if (r instanceof Aprovado a)      texto = "ok: " + a.txId();
else if (r instanceof Recusado x) texto = "nao: " + x.motivo();
else                              texto = "?";

// 🟢 switch exaustivo sobre sealed — sem else, sem default
sealed interface Resultado permits Aprovado, Recusado {}
String texto = switch (r) {
    case Aprovado a -> "ok: " + a.txId();
    case Recusado x -> "nao: " + x.motivo();
};  // novo subtipo sem case => erro de compilação (de propósito)
```

**⚖️ Gate P1:** quando um `if/else` simétrico e curto (duas linhas, dois ramos equivalentes) é mais legível que dois early returns, a legibilidade ganha. A meta é complexidade, não a contagem de keywords.

---

## Regra 3 — Envolva todos os primitivos e Strings

**Ataca:** *Primitive Obsession* — `double`/`String` cru circulando sem semântica nem validação (`int idade`, `String cpf`, `double valor`).

**Idioma Java 25:** **`record` (final no 16)** como Value Object de domínio, com invariante validada no **compact constructor** ou, quando a checagem precisa rodar antes de `super()`/`this()`, nos **Flexible Constructor Bodies (JEP 513 — final no 25)**. O custo histórico (cada wrapper = 12–16 bytes de cabeçalho no heap) é amortizado pelos **Compact Object Headers (JEP 519 — final no 25)**: header de 12→8 bytes, ~22% menos heap em cargas típicas.

```java
// 🔴 Primitivo cru: nada impede idade negativa ou CPF malformado
void cadastrar(String cpf, int idade) { ... }

// 🟢 Wrapper de domínio com invariante no compact constructor
public record Idade(int valor) {
    public Idade {                                  // valida na construção
        if (valor < 0 || valor > 150)
            throw new IllegalArgumentException("Idade fora da faixa: " + valor);
    }
}
public record Cpf(String valor) {
    public Cpf {
        if (!valor.matches("\\d{11}"))
            throw new IllegalArgumentException("CPF inválido");
    }
}
void cadastrar(Cpf cpf, Idade idade) { ... }        // assinatura auto-documentada
```

**⚖️ Gate P1:** **não** está no JDK 25 o *flattening* de Value Classes (Valhalla/JEP 401 → JDK 28). Então o ganho de memória vem dos Compact Object Headers (flag, sem ZGC), não de Valhalla. E não embrulhe um `int` trivial *sem invariante real* só para cumprir a regra — wrapper sem comportamento nem validação é cerimônia (viola P1).

---

## Regra 4 — Coleções de primeira classe

**Ataca:** `List`/`Map`/`Set` cru exposto, com a lógica de agregação vazando para os clientes em vez de viver num tipo de domínio.

**Idioma Java 25:** uma classe/record de domínio que **encapsula a coleção** (delegação por composição) e expõe verbos de negócio, nunca a estrutura. Coleções **imodificáveis** com `List.copyOf(...)` na borda. Para inicialização preguiçosa thread-safe da coleção *sem* double-checked locking, **Stable Values (JEP 502 — preview no 25, exige `--enable-preview`)**.

```java
// 🔴 Coleção crua exposta; clientes filtram/somam por conta própria
public class Carrinho { public List<Item> itens = new ArrayList<>(); }
double total = carrinho.itens.stream().mapToDouble(Item::preco).sum(); // lógica vazada

// 🟢 Coleção de primeira classe: o tipo dono concentra o comportamento
public final class Carrinho {
    private final List<Item> itens;
    public Carrinho(List<Item> itens) { this.itens = List.copyOf(itens); } // imutável
    public Dinheiro total()        { return itens.stream().map(Item::preco).reduce(Dinheiro.ZERO, Dinheiro::mais); }
    public int quantidade()        { return itens.size(); }
    public boolean vazio()         { return itens.isEmpty(); }
}
```

**⚖️ Gate P1:** se o "wrapper" só repassa `get`/`size` sem nenhum comportamento de domínio, ele não está pagando seu custo — uma coleção imodificável direta basta. O wrapper vale quando concentra regras (total, validação, invariantes do conjunto).

---

## Regra 5 — Apenas um ponto por linha (Lei de Demeter)

**Ataca:** `a.getB().getC().getD()` — navegação profunda que acopla o chamador à topologia interna de objetos alheios.

**Idioma Java 25:** **Record Patterns (JEP 440 — final no 21)** desconstroem a estrutura num único golpe declarativo, em vez de encadear getters; combinados com `switch`/`instanceof` extraem o que importa sem expor o caminho.

```java
// 🔴 Trem de getters: acopla à árvore Pedido→Cliente→Endereco
String pais = pedido.getCliente().getEndereco().getPais();

// 🟢 Desconstrução por Record Pattern — um teste, variáveis tipadas, zero getter encadeado
if (pedido instanceof Pedido(_, Cliente(var nome, Endereco(_, var pais)), _)) {
    log.info("{} compra do país {}", nome, pais);
}
```

**⚖️ Gate P1:** a regra mira *navegação entre objetos distintos*. Cadeias *fluentes* sobre o **mesmo** objeto (builders, `stream().filter().map().toList()`, `Optional.map(...)`) são exceção legítima — são uma expressão, não uma violação de Demeter.

---

## Regra 6 — Não abrevie

**Ataca:** `ord`, `cust`, `calc`, `tmp` — nomes crípticos que economizam teclas e custam entendimento.

**Idioma Java 25:** nomes completos sempre. A justificativa histórica para abreviar ("o nome fica longo demais com pacote + import") cai com **Module Import Declarations (JEP 511 — final no 25)** e **Compact Source Files (JEP 512 — final no 25)**, que removem a cerimônia ao redor do nome. `var` (10) infere o tipo **sem** encurtar a semântica do identificador.

```java
// 🔴 Cerimônia + abreviação
import java.util.List; import java.util.Map; import java.util.ArrayList;
Map<String,Integer> qtdProdMap = new HashMap<>();   // "qtd", "Prod"

// 🟢 Import de módulo + nome íntegro; var sem perder intenção
import module java.base;
var quantidadePorProduto = new HashMap<String, Integer>();
```

**⚖️ Gate P1:** siglas universais de domínio (CPF, HTTP, ID, URL, SQL) **não** são abreviações a evitar — são o nome canônico. Não "desabrevie" `id` para `identificador` por esporte.

---

## Regra 7 — Mantenha todas as entidades pequenas

**Ataca:** *God class* e arquivos massivos que aglomeram responsabilidades (heurística: classe ≤ ~50 linhas, método ≤ 20).

**Idioma Java 25:** **`record`** elimina dezenas de linhas de getter/equals/hashCode/toString; **Compact Source Files + Instance Main Methods (JEP 512 — final no 25)** removem o invólucro `public class ... { public static void main(String[] args) }` de programas pequenos, deixando a unidade enxuta e focada. Separe dados (records) de comportamento (serviços coesos).

```java
// 🔴 ~40 linhas de boilerplate mutável
public class PontoDTO { private int x; private int y; /* get/set/equals/hashCode/toString */ }

// 🟢 Uma linha, imutável, contrato completo
public record Ponto(int x, int y) {}
```

**⚖️ Gate P1:** "pequeno" é heurística, não meta cega. Quebrar uma classe coesa de 60 linhas em quatro de 15 só para passar no número **piora** a navegabilidade. Divida por *responsabilidade*, não por contador de linhas.

---

## Regra 8 — Máximo de duas variáveis de instância

**Ataca:** construtores gigantes e estado interligado difícil de manter invariante.

**Idioma Java 25:** **Data-Oriented Programming** — agrupe campos coesos em **records aninhados/modulares** (Value Objects), de modo que uma entidade carregue 1–2 sub-objetos ricos em vez de 8 primitivos soltos.

```java
// 🔴 Cinco variáveis soltas — coesão fraca, construtor massivo
class Cliente { String rua, cidade, cep; String nome, email; }

// 🟢 Agrupamento em VOs: duas variáveis de instância, cada uma coesa
record Endereco(String rua, String cidade, Cep cep) {}
record Contato(Nome nome, Email email) {}
class Cliente {
    private final Contato contato;     // 1
    private final Endereco endereco;   // 2
}
```

**⚖️ Gate P1:** esta é a regra mais agressiva de Bay e a mais "exercício de kata". O **valor real** é a pressão por coesão e a descoberta de VOs implícitos — não o número 2 literal. Um record de configuração com 6 campos verdadeiramente independentes é legítimo; não o fragmente artificialmente.

---

## Regra 9 — Sem getters/setters/properties

**Ataca:** exposição de estado para decisão externa (*Ask*) em vez de pedir o comportamento ao objeto (**Tell, Don't Ask**); e o setter mutável, fonte de *race conditions*.

**Idioma Java 25:** comportamento mora no objeto; estado é **imutável** via `record`. Para "evoluir" um imutável sem setter, o idioma do 25 é **`record` + métodos `withX()` explícitos** (a sintaxe `with`/JEP 468 **não** está no JDK 25). Os *accessors* de record (`pedido.total()`) são aceitáveis na **borda** (serialização, DTO); o antipadrão é o **setter** e o getter que vaza estado para terceiros decidirem regra de negócio.

```java
// 🔴 Ask + setter mutável: o cliente lê o estado e decide a regra; estado mutável
if (conta.getSaldo() >= valor) { conta.setSaldo(conta.getSaldo() - valor); }

// 🟢 Tell + imutável: o objeto decide e devolve nova instância (wither explícito)
public record Conta(Dinheiro saldo) {
    public Conta sacar(Dinheiro valor) {
        if (saldo.menorQue(valor)) throw new SaldoInsuficiente(saldo, valor);
        return withSaldo(saldo.menos(valor));          // sem setter, sem mutação
    }
    public Conta withSaldo(Dinheiro novo) { return new Conta(novo); }  // wither manual
}
```

**⚖️ Gate P1:** DTOs de transporte na borda (request/response, evento serializado) legitimamente expõem componentes — record é feito para isso. A regra ataca o estado de domínio mutável vazado, não todo método de leitura. Imutabilidade casa com **Virtual Threads (21)**: sem estado compartilhado mutável, sem corrida.

---

## Mapa de bolso — Regra → Recurso → Status no JDK 25

| # | Regra | Recurso idiomático | Status no 25 |
|---|---|---|---|
| 1 | Um nível de indentação | Streams (8), **Stream Gatherers (JEP 485)** | final (485 final no 24) |
| 2 | Sem `else` | Guard Clauses; **Pattern Matching switch (441)** + **Sealed (409)** | final (21 / 17) |
| 3 | Envolver primitivos | **Records (16)** + compact ctor / **Flexible Ctor Bodies (513)**; **Compact Object Headers (519)** | final · 519 não-default, sem ZGC · **Valhalla 401 NÃO (→28)** |
| 4 | Coleções de 1ª classe | Encapsular + `List.copyOf`; **Stable Values (502)** p/ lazy | composição final · **502 preview** |
| 5 | Um ponto por linha | **Record Patterns (440)** | final (21) |
| 6 | Não abreviar | Nomes íntegros; **Module Imports (511)** + **Compact Source (512)**; `var` | final (25) |
| 7 | Entidades pequenas | **Records**; **Compact Source + `void main` (512)** | final (25) |
| 8 | ≤ 2 variáveis de instância | DOP, records aninhados (VOs) | final (idioma) |
| 9 | Sem getters/setters | Tell-Don't-Ask; `record` + `withX()` explícito | final · **withers/468 NÃO no 25** |

> Sempre fechar com o **Gate P1**: a aplicação da regra deixou o código *mais simples de ler e manter*? Se a resposta hesita, o original pode ser a escolha certa. Calistenia serve à simplicidade — não o contrário.
