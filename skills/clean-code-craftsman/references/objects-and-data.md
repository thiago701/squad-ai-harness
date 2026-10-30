# Objetos e Estruturas de Dados

> "Objetos escondem seus dados atrás de abstrações e expõem funções que operam sobre esses dados. Estruturas de dados expõem seus dados e não têm funções significativas."

Esses dois conceitos parecem opostos — e são. Cada um tem seu lugar. Misturá-los é um dos erros mais comuns no design de classes.

## Abstração de dados

A diferença não é apenas "métodos públicos" ou "atributos públicos". É sobre **o que é exposto**:

```
// Estrutura de dados concreta — expõe coordenadas cartesianas
public class Point {
    public double x;
    public double y;
}

// Abstração — esconde a representação interna
public interface Point {
    double getX();
    double getY();
    void setCartesian(double x, double y);
    double getR();
    double getTheta();
    void setPolar(double r, double theta);
}
```

A primeira diz **como** os dados estão guardados (cartesiana). A segunda esconde a representação — pode ser cartesiana, polar, qualquer coisa. Ela expõe **o que** você pode fazer.

> "Você quer expressar seus dados em termos abstratos. Não basta colocar uma camada de funções entre as variáveis. As classes devem forçar você a operar sobre dados sem precisar conhecer a forma deles."

## Antissimetria objeto/dado

A escolha entre objetos e estruturas de dados depende do que você quer **flexibilizar**:

| Você quer adicionar... | Use |
|---|---|
| Novos **tipos** de coisas (sem mudar funções) | **Objetos** (polimorfismo) |
| Novas **funções** (sem mudar tipos existentes) | **Estruturas de dados** (lógica externa) |

### Exemplo: forma geométrica

```
// Estilo "estrutura de dados + funções externas"
public class Square { public Point topLeft; public double side; }
public class Circle { public Point center; public double radius; }

public class Geometry {
    public double area(Object shape) {
        if (shape instanceof Square)  return ...;
        if (shape instanceof Circle)  return ...;
    }
    public double perimeter(Object shape) { ... }
}
```

**Adicionar `perimeter()` é fácil** — escreve-se mais uma função.
**Adicionar uma nova forma é difícil** — precisa abrir todas as funções e adicionar um caso.

```
// Estilo "objeto polimórfico"
public class Square implements Shape {
    private Point topLeft;
    private double side;
    public double area() { ... }
}
public class Circle implements Shape { ... public double area() { ... } }
```

**Adicionar uma nova forma é fácil** — implementa-se a interface.
**Adicionar uma nova função é difícil** — abre todas as classes.

> "OO faz código novo de tipos fácil sem mudar funções. Procedural faz código novo de funções fácil sem mudar estruturas de dados. Os pontos fortes de um são as fraquezas do outro."

Bons designers escolhem conscientemente. Sistemas maduros frequentemente têm ambos.

## A Lei de Demeter

> "Um módulo não deveria conhecer as entranhas dos objetos que manipula."

Mais especificamente: um método `f` de uma classe `C` deveria chamar apenas métodos de:

1. A própria `C`.
2. Objetos criados por `f`.
3. Objetos passados como argumento para `f`.
4. Objetos guardados em variáveis de instância de `C`.

**Não** deveria chamar métodos em objetos retornados por **outras** chamadas.

### Train wrecks

```
final String outputDir = ctxt.getOptions().getScratchDir().getAbsolutePath();
```

Isso é um **train wreck** (acidente de trem). Cada `.getX()` revela mais sobre as entranhas do sistema. Para o leitor:
- O contexto tem opções.
- As opções têm um diretório de scratch.
- O diretório tem um caminho absoluto.

Para mudar qualquer um desses detalhes, todos os chamadores quebram. Cada chamada é uma dependência.

Quebre:

```
Options opts = ctxt.getOptions();
File scratchDir = opts.getScratchDir();
final String outputDir = scratchDir.getAbsolutePath();
```

Visualmente melhora, mas não corrige a violação. A correção real é perguntar: **por que o caller precisa do absolute path?**

```
// Aposta: ele quer criar um arquivo lá
BufferedOutputStream bos = ctxt.createScratchFileStream(classFileName);
```

Agora o caller diz **o que quer** ao contexto, e o contexto faz o trabalho. Não há mais cadeia de getters.

### Híbridos

Quando uma classe é parte objeto, parte estrutura de dados, ela é o pior dos mundos:
- Tem métodos significativos (parece objeto).
- Tem getters e setters expondo a forma interna (parece estrutura de dados).

Híbridos são difíceis de adicionar funções **e** difíceis de adicionar tipos. Evite — escolha um lado.

### Esconder estrutura

Se uma classe expõe sua estrutura interna via cadeia de getters, viola Demeter mesmo que tecnicamente respeite as regras (cada `.getX()` é um nível diferente, mas todos pertencem ao mesmo objeto raiz).

A pergunta não é apenas "quem chamei?" — é "**estou expondo coisas que deveriam estar escondidas?**".

## Data Transfer Objects (DTOs)

A forma mais pura de estrutura de dados: classe com campos públicos (ou getters/setters triviais), sem comportamento. Comum na fronteira do sistema:
- Ler de banco de dados.
- Receber de uma API REST.
- Persistir em fila/Kafka/etc.

```
public class Address {
    public String street;
    public String streetExtra;
    public String city;
    public String state;
    public String zip;
}
```

DTOs **devem ser DTOs** — não acumule lógica de negócio neles. Quando lógica precisa rodar, crie outra classe que opera sobre o DTO.

### Active Record

DTOs com métodos `save()` e `find()`. Carregam-se de banco e se persistem. **Convenientes**, mas tendem a virar híbridos quando lógica de negócio começa a ser injetada. Mantenha Active Records como estruturas de dados; bote a lógica de negócio em **outra classe** que tem o Active Record como variável.

## Conclusão

> "Bons programadores fazem distinções claras. Um design profissional é livre de híbridos."

Em qualquer parte do código, pergunte-se: **isso é um objeto, ou uma estrutura de dados?**

- Se é objeto: esconda dados, exponha comportamento, respeite Demeter.
- Se é estrutura: exponha dados, mantenha-se sem comportamento, sem fingir ser outra coisa.

Pratique a distinção ativamente. Times que sabem distinguir produzem sistemas mais maleáveis a longo prazo.
