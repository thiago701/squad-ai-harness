# Funções

> "A primeira regra das funções é que elas devem ser pequenas. A segunda regra é que elas devem ser ainda menores."

Funções são o verbo do código. São onde o trabalho acontece e — não por coincidência — onde a maior parte da complexidade se esconde. Boas funções leem-se como prosa: você sabe o que cada uma faz pelo nome, e abrir uma confirma a expectativa.

## Pequenas, depois ainda menores

A pergunta certa não é "quantas linhas?" — é "quantas ideias?". Idealmente, **uma função expressa uma ideia**.

Como referência prática:
- 4 a 20 linhas é a faixa saudável para a maioria das funções.
- Mais de 30 linhas merece olhar crítico.
- Mais de 100 linhas é quase certamente problemática.

Mas o ponto não é o número — é que funções pequenas tendem a fazer uma coisa, são fáceis de testar, fáceis de nomear, e fáceis de reusar.

### Blocos e indentação

Blocos dentro de `if`, `else`, `while` devem ter **uma linha** — geralmente uma chamada de função. Isso dá ao bloco um nome documentador. Funções devem ter **no máximo dois níveis** de indentação. Mais que isso, extraia.

## Faça uma coisa só

> "Funções devem fazer uma coisa. Devem fazê-la bem. Devem fazê-la apenas."

Como saber se uma função faz mais de uma coisa? Tente extrair outra função com nome significativo dela. Se você consegue (e o nome novo não é uma reformulação do nome velho), a original fazia mais de uma coisa.

Outro teste: descreva a função em uma frase. Se a frase contiver "e" ou "ou" ou ";", ela faz mais de uma coisa.

Funções que fazem uma coisa **não têm seções** dentro delas — não há "declarações", "inicialização", "loop principal", "limpeza" como subseções comentadas. Se houver, são duas funções pelo menos.

## Um nível de abstração por função

Misturar níveis de abstração em uma função quebra a leitura. Compare:

```
// Misturado
function getHtml() {
    // detalhe alto: rendrizar HTML
    // detalhe médio: configurar cabeçalho
    // detalhe baixo: concatenar strings
}
```

Cada linha deveria estar no mesmo nível conceitual. Se você está pensando em "renderizar a página", não deveria estar pensando em manipulação de strings na mesma frase.

### Regra do step-down

Leia código como um livro: alto nível em cima, detalhes embaixo. Cada função chama outras **um nível abaixo**. Isso cria uma hierarquia natural:

```
public void renderPage() { ... }
   public void renderHeader() { ... }
      public String formatTitle(...) { ... }
   public void renderBody() { ... }
   public void renderFooter() { ... }
```

Quem lê de cima para baixo entende sem precisar pular para os detalhes.

## Switch statements

`switch` (e cadeias `if/else if`) são naturalmente longas e tendem a violar SRP (uma razão para mudar é cada `case`). A regra: **enterre o switch em um lugar só**, atrás de polimorfismo, e nunca o repita.

```
// Em vez de switch espalhado pela base
public Money calculatePay(Employee e) {
    switch (e.type) {
        case COMMISSIONED: return calculateCommissionedPay(e);
        case HOURLY:       return calculateHourlyPay(e);
        case SALARIED:     return calculateSalariedPay(e);
    }
}

// Use uma fábrica + polimorfismo
EmployeeFactory factory = new EmployeeFactoryImpl();
Employee e = factory.makeEmployee(record);
e.calculatePay(); // cada subclasse implementa
```

## Use nomes descritivos

> "Um nome longo e descritivo é melhor que um nome curto e enigmático. Um nome longo e descritivo é melhor que um comentário longo e descritivo."

Não tenha medo de nomes longos. `testableHtmlOnIncludeAndSetupAndTeardownPagesAreInherited` é hediondo, mas comunica. Junto com a regra de "fazer uma coisa", isso fica natural — uma função pequena tem um nome específico.

E **mantenha consistência** nos nomes do mesmo módulo: se você usa `include`, não use `add` em outras funções similares.

## Argumentos de função

A ordem ideal de argumentos: **nenhum (niládica) > um (monádica) > dois (diádica) > três (triádica) > parar**. Quatro ou mais (poliádica) precisa de justificativa muito boa.

Por quê? Cada argumento é uma coisa que o leitor precisa segurar mentalmente. Argumentos também complicam testes — você precisa cobrir combinações.

### Formas monádicas comuns

Funções com um argumento geralmente caem em:
- **Pergunta sobre o argumento**: `boolean fileExists("MyFile")`
- **Operação sobre o argumento que retorna algo**: `InputStream fileOpen("MyFile")`
- **Evento**: `void passwordAttemptFailedNtimes(int attempts)` — usa o argumento para alterar estado do sistema

### Argumentos flag

`render(true)` é horrível: o leitor não sabe o que `true` significa. Argumentos booleanos sinalizam que a função faz duas coisas — uma para `true`, outra para `false`. **Separe em duas funções**: `renderForSuite()` e `renderForSingleTest()`.

### Funções diádicas

Duas funções são significativamente mais difíceis de entender que uma. `writeField(name)` é mais fácil que `writeField(output, name)`. Quando a ordem dos dois argumentos importa (`assertEquals(expected, actual)`), erros são frequentes.

Triádicas são exponencialmente piores.

### Objetos de argumento

Quando uma função precisa de muitos argumentos, **alguns deles provavelmente formam um conceito** que merece sua própria classe.

```
// Ruim
Circle makeCircle(double x, double y, double radius);

// Bom
Circle makeCircle(Point center, double radius);
```

`Point` agrupa coordenadas relacionadas. Não é trapaça contar os argumentos — é descobrir um conceito que estava escondido.

### Listas de argumentos

Argumentos variádicos (`String.format("%s, %s", a, b)`) tratados como uma única lista contam como um argumento. Faz sentido quando todos têm o mesmo papel.

### Verbos e palavras-chave

Funções monádicas devem ter um par verbo-substantivo: `write(name)`. Melhor ainda, codifique o nome do argumento no nome da função: `writeField(name)`.

Para funções com múltiplos argumentos, "palavras-chave" no nome ajudam a lembrar a ordem: `assertExpectedEqualsActual(expected, actual)` em vez de `assertEquals(expected, actual)`.

## Sem efeitos colaterais

Uma função `checkPassword(user, pwd)` que **também** inicializa a sessão tem um efeito colateral oculto. O nome promete uma verificação; o código faz mais. O leitor que confia no nome será surpreendido — e os bugs aparecem em condições que ninguém previu.

Se a função precisa fazer ambos, dê-lhe um nome que diga: `checkPasswordAndInitializeSession`. Ou — melhor — separe.

### Argumentos de saída

Argumentos passados por referência para receber resultado (`appendFooter(report)` que modifica `report`) são pegadinhas. O leitor espera input, não output. Se a função precisa modificar algo, faça-o membro de classe e chame: `report.appendFooter()`.

## Separação de comando e consulta

Funções devem **fazer alguma coisa** ou **responder alguma coisa**, não ambas.

```
// Ruim — faz e responde
public boolean set(String attr, String value);
if (set("username", "unclebob")) { ... }
// Está perguntando se está setado, ou setando?

// Bom
if (attributeExists("username")) {
    setAttribute("username", "unclebob");
}
```

## Prefira exceções a códigos de retorno

Códigos de erro forçam o chamador a verificar e desviar imediatamente. Aninhamento explode. Exceções permitem código feliz fluir e tratamento de erro ser separado.

```
// Ruim — códigos de erro encadeados
if (deletePage(page) == E_OK) {
    if (registry.deleteReference(page.name) == E_OK) {
        if (configKeys.deleteKey(page.key) == E_OK) {
            logger.log("page deleted");
        } else {
            logger.log("configKey not deleted");
        }
    } ...
}

// Bom — try/catch separa caminho feliz do tratamento
try {
    deletePage(page);
    registry.deleteReference(page.name);
    configKeys.deleteKey(page.key);
} catch (Exception e) {
    logger.log(e.getMessage());
}
```

### Extraia blocos try/catch

Blocos try/catch são feios e misturam o normal com o excepcional. Extraia-os para suas próprias funções:

```
public void delete(Page page) {
    try {
        deletePageAndAllReferences(page);
    } catch (Exception e) {
        logError(e);
    }
}
```

A função principal agora só fala da estrutura de tratamento de erro. Os detalhes ficam separados. **Tratamento de erro é uma coisa** — então quem o faz não deveria fazer mais nada.

## Don't Repeat Yourself

Duplicação é a raiz de quase todos os males em software. Cada cópia que você esquece de atualizar é um bug. Cada conhecimento deveria ter **uma representação canônica** no sistema.

Mas atenção: duplicação de **forma sintática** sem duplicação de **intenção** não é o mesmo. Forçar abstração onde não há conceito comum cria acoplamento espúrio.

## Programação estruturada

Edsger Dijkstra defendia uma entrada e uma saída por função (sem `return` no meio, sem `break`, sem `continue`). Em funções pequenas, isso não importa — múltiplos `return` cedo (guard clauses) muitas vezes esclarecem. Em funções grandes, a regra de Dijkstra ajuda. **A solução real é manter as funções pequenas** — então o debate fica acadêmico.

## Como você escreve funções como essas?

Robert C. Martin é claro: **ele não as escreve assim na primeira tentativa**. A primeira versão é longa, complicada, com muito aninhamento. Mas:

1. Tem testes desde o início que cobrem o comportamento esperado.
2. Refina obsessivamente: nomes, decomposição, eliminação, reorganização.
3. Quando termina, as funções caem nas regras descritas aqui.

A primeira versão **funciona**. As versões seguintes são **artes**.

## Smells de função (Cap. 17)

### F1: Argumentos demais
Mais de três argumentos é suspeito. Procure conceitos que merecem virar classes.

### F2: Argumentos de saída
Argumentos modificados pela função são contraintuitivos. Se precisa modificar estado, modifique `this`.

### F3: Argumentos flag
Booleanos como argumento dizem em voz alta: "esta função faz mais de uma coisa". Separe.

### F4: Função morta
Função que ninguém chama. Apague — o sistema de controle de versão lembra.

## Conclusão

Funções são onde a linguagem de programação encontra a linguagem do domínio. Boas funções compõem uma narrativa — cada uma com um propósito, um nome que o anuncia, um corpo que o cumpre. **Mestres veem programação como contar uma história**, e funções como as frases.

Não escreva regras; conte uma história.
