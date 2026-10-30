# Formatação

> "Formatação de código é sobre comunicação, e comunicação é o primeiro dever do desenvolvedor profissional."

Você pode pensar que "fazer funcionar" é a primeira responsabilidade. Não é. A funcionalidade que você cria hoje provavelmente vai mudar amanhã — mas a **legibilidade** do código vai influenciar todas as mudanças que virão.

## O propósito da formatação

Ferramentas (formatters) lidam com a maior parte do trabalho mecânico. Mas decisões mais profundas — densidade vertical, ordem das funções, separação visual de conceitos — ficam com o desenvolvedor.

A meta: comunicar a estrutura ao leitor antes mesmo dele ler as palavras.

## Formatação vertical

### Metáfora do jornal

Um jornal é lido de cima para baixo. Manchete em cima diz do que se trata. Os primeiros parágrafos resumem. Os detalhes vão se acumulando.

Aplique ao arquivo de código:
- O **topo** deve dizer ao leitor de que se trata o módulo. Os primeiros nomes, conceitos, e funções devem ser de **alto nível**.
- Conforme **descemos**, vão aparecendo os detalhes.

Você não deveria precisar pular para o final do arquivo para entender o que ele faz.

### Tamanho do arquivo

Estatística do livro: arquivos do JUnit tinham mediana de ~70 linhas; FitNesse, ~100; Tomcat e Ant, mais. Conclusão: arquivos pequenos (200-500 linhas máximo) são tipicamente mais legíveis e são possíveis na maioria dos sistemas.

Arquivos grandes raramente justificam-se. Quase sempre escondem múltiplas responsabilidades.

### Abertura vertical entre conceitos

Linhas em branco separam pensamentos. Cada bloco de código deve estar visualmente separado de blocos com propósito diferente:

```
package fitnesse.wikitext.widgets;

import java.util.regex.*;

public class BoldWidget extends ParentWidget {
    public static final String REGEXP = "'''.+?'''";
    private static final Pattern pattern = Pattern.compile("'''(.+?)'''",
        Pattern.MULTILINE + Pattern.DOTALL);

    public BoldWidget(ParentWidget parent, String text) throws Exception {
        super(parent);
        Matcher match = pattern.matcher(text);
        match.find();
        addChildWidgets(match.group(1));
    }
}
```

A linha em branco entre o `package`, os `import`s, a classe, as constantes, e o construtor segmenta visualmente. Tirar essas linhas:

```
package fitnesse.wikitext.widgets;
import java.util.regex.*;
public class BoldWidget extends ParentWidget {
    public static final String REGEXP = "'''.+?'''";
    private static final Pattern pattern = Pattern.compile("'''(.+?)'''",
        Pattern.MULTILINE + Pattern.DOTALL);
    public BoldWidget(ParentWidget parent, String text) throws Exception {
        super(parent);
        ...
```

...torna tudo um borrão. Mesmo conteúdo, comunicação muito pior.

### Densidade vertical

O oposto também é verdadeiro: linhas que pertencem ao mesmo pensamento devem estar **juntas**.

```
// Ruim — linhas em branco quebram o agrupamento
public class ReporterConfig {

    /**
     * O nome da classe do reporter
     */
    private String m_className;

    /**
     * As propriedades do reporter
     */
    private List<Property> m_properties = new ArrayList<Property>();
}

// Bom — duas declarações relacionadas, sem comentários ruidosos
public class ReporterConfig {
    private String className;
    private List<Property> properties = new ArrayList<Property>();
}
```

Densidade visual = densidade conceitual.

### Distância vertical

Conceitos relacionados devem estar **verticalmente próximos**. O leitor não deveria precisar caçar uma definição em outro arquivo (ou em outra parte distante do mesmo arquivo).

#### Declaração de variável

Variáveis devem ser declaradas **o mais próximo possível de seu uso**. Em funções pequenas, no topo da função. Em loops, dentro do for. Nunca à dúzia de linhas de distância.

#### Variáveis de instância

No topo da classe, agrupadas. Não espalhe pelo meio. Quem lê a classe espera encontrar suas variáveis em um único lugar conhecido.

#### Funções dependentes

Se a função A chama a função B, A deve estar **acima** de B. E elas devem estar próximas. Quem lê A vê o nome de B e — ao continuar descendo — encontra B logo em seguida.

#### Afinidade conceitual

Funções com nomes parecidos, ou que fazem variações da mesma coisa, ou que cooperam para um propósito, devem ficar próximas. O leitor associa proximidade física a parentesco lógico.

### Ordem vertical

Em geral, **alto nível em cima, baixo nível embaixo**. A primeira coisa que o leitor encontra é o conceito mais geral. Conforme desce, encontra a implementação mais detalhada. Esta é a regra do step-down de funções aplicada ao arquivo inteiro.

## Formatação horizontal

### Quão larga uma linha?

Linhas curtas vencem. **80 colunas** era a regra antiga; hoje, monitores grandes permitem 100-120 sem desconforto. Mas mais que 120 começa a indicar que há muito acontecendo em uma linha.

### Abertura horizontal e densidade

Use espaços para acentuar relacionamentos:

```
// Operadores binários têm espaços ao redor
total = price * quantity;

// Argumentos de função: vírgula seguida de espaço
sum(a, b, c);

// Chamadas de função: sem espaço entre nome e parêntese
print(name);

// Não há espaços entre fatores de multiplicação se você quer enfatizar precedência
return b*b - 4*a*c;
```

A última é estilo: `b*b - 4*a*c` lê-se mais como uma fórmula matemática que `b * b - 4 * a * c`. É contestado.

### Alinhamento horizontal

Alinhamento artificial entre declarações:

```
// Ruim
public class FitNesseExpediter implements ResponseSender {
    private    Socket          socket;
    private    InputStream     input;
    private    OutputStream    output;
    private    Request         request;
    private    Response        response;
    private    FitNesseContext context;
    protected  long            requestParsingTimeLimit;
}
```

Parece bonito, mas:
1. Faz o leitor olhar para a coluna alinhada (tipo) em vez do nome (que é o importante).
2. Quebra horrivelmente em diffs quando algo muda.
3. Indica que a classe tem campos demais.

Prefira:

```
public class FitNesseExpediter implements ResponseSender {
    private Socket socket;
    private InputStream input;
    private OutputStream output;
    private Request request;
    private Response response;
    private FitNesseContext context;
    protected long requestParsingTimeLimit;
}
```

### Indentação

Indentação mostra a hierarquia do código. **Sempre indente**, mesmo em blocos de uma linha:

```
// Ruim — viola a estrutura
if (condition) doSomething();

// Bom — indentação preserva a hierarquia
if (condition)
    doSomething();
```

### Escopos vazios

Loops `while` com corpo vazio (raros mas existentes):

```
while (dis.read(buf, 0, readBufferSize) != -1)
;
```

O `;` numa linha própria deixa o vazio explícito.

## Regras de equipe

> "Times de desenvolvedores devem concordar em um único estilo, e então cada membro do time deve usar esse estilo."

Você pode preferir colchetes na mesma linha. Eu posso preferir na próxima. Não importa — **importa que escolhamos um e mantenhamos**. Inconsistência interna é pior que qualquer escolha de estilo.

Códigos automatizados de formatação (Prettier, Spotless, Black, gofmt) eliminam a discussão. Configure no início do projeto, integre ao CI, e ninguém perde tempo discutindo.

## Conclusão

Boa formatação é tão invisível que você nem nota — só percebe quando ela falta e o código começa a parecer caótico. É a base sobre a qual tudo o mais (nomes, funções, classes) precisa funcionar.

A maior parte do trabalho de formatação está em **deixar a ferramenta fazer**. O que sobra para o humano é a **organização macro**: ordem das funções, agrupamento de campos, separação visual de conceitos. Isso, ferramentas não fazem por você.
