# Classes

> "Classes pequenas." Métrica não é número de linhas, é número de responsabilidades.

Funções podem ser pequenas; classes também. A diferença: o critério para classes é mais sutil.

## Organização da classe

Convenção (de Java, mas amplamente aplicável):

1. Lista de variáveis (constantes públicas → constantes privadas → instâncias privadas → instâncias públicas — raras).
2. Métodos públicos.
3. Métodos privados, **logo abaixo** do público que os utiliza.

Isso preserva a regra do step-down ao nível da classe: leitor de cima vê alto nível; descendo encontra detalhes.

## Encapsulamento

Quanto **menos** público, melhor. Variáveis privadas são preferidas; expostas só com motivo. Mas há exceções pragmáticas:
- Em testes, métodos `protected` ou `package-private` permitem testar internals sem expor publicamente.
- Loosen encapsulation when needed for testing **é aceitável** como último recurso; mas tente primeiro testar via interface pública.

## Classes devem ser pequenas

Conte responsabilidades, não linhas. Como descobrir as responsabilidades?

> "Você deveria ser capaz de descrever uma classe em cerca de 25 palavras, sem usar 'se', 'e', 'ou', ou 'mas'."

Se você precisa dessas conjunções, a classe faz mais de uma coisa.

```
// Classe muito grande (52 métodos públicos), faz tudo
public class SuperDashboard extends JFrame implements MetaDataUser {
    public Component getLastFocusedComponent()
    public void setLastFocused(Component lastFocused)
    public int getMajorVersionNumber()
    public int getMinorVersionNumber()
    public int getBuildNumber()
    // ...mais 47 métodos
}
```

Você pode até reduzir para 5 métodos. Mas se ainda fizesse coisas distintas (versionamento, foco, exibição), continuaria sendo um problema.

## Single Responsibility Principle (SRP)

> "Uma classe ou módulo deve ter uma — e apenas uma — razão para mudar."

Pergunta-teste: **se eu mudar o sistema, quantas classes precisarão mudar?** Idealmente, uma para cada eixo de mudança.

```
// Quantas razões SuperDashboard mudaria?
//   - Mudar a UI principal
//   - Mudar como o foco funciona
//   - Mudar a versionamento
// → 3 responsabilidades em 1 classe
```

Separe em três classes, cada uma com uma razão de mudar.

> "Software bem projetado consiste em muitas classes pequenas. Cada classe encapsula uma responsabilidade, tem uma única razão para mudar, e colabora com algumas outras para alcançar o comportamento desejado do sistema."

### O medo de ter muitas classes pequenas

"Não é mais difícil entender 50 classes do que 5 grandes?" — pergunta comum.

Resposta: **não, se cada classe tem nome e responsabilidade claros**. Você não precisa entender todas para trabalhar com uma. Em sistemas com classes grandes, você é forçado a entender muito de cada uma — e ver acoplamentos espalhados em todo lugar.

Pequenas classes são como caixas etiquetadas em uma despensa. Grandes são uma pilha amorfa.

## Coesão

> "Classes devem ter um pequeno número de variáveis de instância. Cada um dos métodos da classe deve manipular uma ou mais dessas variáveis."

**Alta coesão**: muitos métodos usam muitas das variáveis. **Baixa coesão**: alguns métodos usam algumas variáveis; outros, outras. Coesão baixa indica que a classe contém **duas ou mais classes escondidas** que querem nascer.

```
public class Stack {
    private int topOfStack = 0;
    private List<Integer> elements = new LinkedList<>();

    public void push(int element) { topOfStack++; elements.add(element); }
    public int pop() throws PoppedWhenEmpty {
        if (topOfStack == 0) throw new PoppedWhenEmpty();
        int element = elements.get(--topOfStack);
        elements.remove(topOfStack);
        return element;
    }
    public int size() { return topOfStack; }
}
```

Os três métodos usam ambas as variáveis. **Altíssima coesão**.

### Manter alta coesão

Quando você quebra uma função grande em várias menores, frequentemente **as variáveis locais viram instância**. Algumas funções usam algumas variáveis; outras, outras. Quando isso acontece, você está diante de **uma classe escondida**.

> "Quando classes perdem coesão, divida-as!"

Frequentemente, dividir não significa dois pedaços; significa **descobrir três ou quatro classes** que estavam embutidas.

## Organizando para mudança

Sistemas em produção evoluem. **Classes deveriam estar abertas para extensão e fechadas para modificação** — Open/Closed Principle (OCP).

```
// Toda nova consulta SQL exige modificar Sql
public class Sql {
    public Sql(String table, Column[] columns)
    public String create()
    public String insert(Object[] fields)
    public String selectAll()
    public String findByKey(String keyColumn, String keyValue)
    // ...
    private String columnList(Column[] columns)
    private String valuesList(Object[] fields, final Column[] columns)
    // ...
}
```

Adicionar `update` significa abrir esta classe e adicionar dois métodos novos. Cada caller existente — em risco. Refatorando:

```
abstract public class Sql {
    public Sql(String table, Column[] columns)
    abstract public String generate();
}

public class CreateSql extends Sql { public String generate() {...} }
public class SelectSql extends Sql { public String generate() {...} }
public class InsertSql extends Sql { public String generate() {...} }
public class FindByKeySql extends Sql { public String generate() {...} }
```

Adicionar `UpdateSql` é **criar uma nova classe**. Nada existente é tocado. **Aberto para extensão, fechado para modificação**.

### Isolando do que muda

Detalhes vão mudar — APIs externas, formatos de armazenamento, frameworks. Suas regras de negócio não deveriam.

> "Dependa de abstrações, não de detalhes." (Dependency Inversion Principle, DIP)

```
// Ruim — Portfolio depende diretamente de TokyoStockExchange
public class Portfolio {
    private TokyoStockExchange exchange;
    public Portfolio() { exchange = new TokyoStockExchange(); }
    public Money getValue() { ... }
}

// Bom — Portfolio depende de StockExchange (abstração)
public interface StockExchange { Money currentPrice(String symbol); }

public class Portfolio {
    private StockExchange exchange;
    public Portfolio(StockExchange exchange) { this.exchange = exchange; }
}
```

Agora você pode injetar uma `FixedStockExchangeStub` em testes, ou trocar o provedor real, sem mudar `Portfolio`. Ele depende da **interface**, não do **detalhe**.

## Conclusão

Classes limpas:
- **Pequenas** — uma frase descreve, sem "e/ou".
- **Coesas** — métodos compartilham variáveis; nada está espalhado.
- **Únicas** — uma razão para mudar (SRP).
- **Estáveis** — abertas para extensão, fechadas para modificação (OCP).
- **Isoladas** — dependem de abstrações (DIP).

Esses princípios não são "regras de design avançado" — são as fundações para que o código sobreviva à evolução.
