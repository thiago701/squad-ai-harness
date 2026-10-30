# Nomes Significativos

> "Você deve nomear uma variável com o mesmo cuidado com que nomeia um filho primogênito."

Nomes estão em todo lugar: variáveis, funções, argumentos, classes, pacotes, arquivos. São a interface humana com o código. Bem feitos, eles **revelam intenção**, **eliminam comentários**, **guiam a estrutura**. Mal feitos, fazem o leitor decifrar o que poderia simplesmente ler.

## Regras fundamentais

### 1. Use nomes que revelam intenção

Se um nome precisa de comentário para ser entendido, ele falhou. O nome deve responder: **o que isso é? por que existe? como é usado?**

```
// Ruim
int d; // tempo decorrido em dias

// Bom
int elapsedTimeInDays;
int daysSinceCreation;
int daysSinceModification;
int fileAgeInDays;
```

A pergunta-chave: pode o leitor entender o propósito olhando só o nome?

### 2. Evite desinformação

Não dê pistas falsas. Cuidado com:

- Palavras com significado técnico estabelecido usadas para outra coisa. `accountList` deve ser uma `List`. Se for um `Set` ou um `Map`, chame de `accounts` ou `accountGroup`.
- Nomes que se diferenciam por pequenas variações: `XYZControllerForEfficientHandlingOfStrings` vs `XYZControllerForEfficientStorageOfStrings`. O leitor não vai notar a diferença.
- Letra maiúscula `O` ou `l` minúsculo (parecem `0` e `1`).

### 3. Faça distinções significativas

Trocar palavras só para satisfazer o compilador (ou um padrão arbitrário) é "noise". `Product`, `ProductInfo`, `ProductData` são o mesmo conceito com ruído. `a1, a2, a3` não distingue nada.

```
// Ruim — qual é qual?
public static void copyChars(char a1[], char a2[]) {
    for (int i = 0; i < a1.length; i++) {
        a2[i] = a1[i];
    }
}

// Bom
public static void copyChars(char source[], char destination[]) { ... }
```

### 4. Use nomes pronunciáveis

Você vai falar sobre o código. `genymdhms` é doloroso de pronunciar; `generationTimestamp` flui. Times conversam melhor sobre nomes pronunciáveis.

### 5. Use nomes pesquisáveis

Constantes literais (`7`, `5`) e nomes de uma letra (`e`) são impossíveis de buscar com grep. Quanto maior o escopo, mais longo deve ser o nome. Variável de loop pode ser `i`; campo de classe não pode.

```
// Ruim
for (int j=0; j<34; j++) { s += (t[j]*4)/5; }

// Bom
int realDaysPerIdealDay = 4;
const int WORK_DAYS_PER_WEEK = 5;
int sum = 0;
for (int j = 0; j < NUMBER_OF_TASKS; j++) {
    int realTaskDays = taskEstimate[j] * realDaysPerIdealDay;
    int realTaskWeeks = realTaskDays / WORK_DAYS_PER_WEEK;
    sum += realTaskWeeks;
}
```

### 6. Evite codificações

- **Notação húngara** (prefixos como `m_`, `str`, `i_`) é ruído em linguagens modernas com tipos. IDEs já mostram tipo.
- **Prefixos de membros** (`m_dsc`) viraram lixo em IDEs com syntax highlighting.
- **Interfaces e implementações**: prefira deixar a interface "limpa" (`Account`) e codificar a implementação (`AccountImpl`, `CppAccount`) — o cliente nunca deveria saber que está falando com uma interface.

### 7. Evite mapeamento mental

Um nome que força o leitor a traduzir mentalmente para outro nome conhecido é ruim. `r` para "URL minúscula sem o host e o esquema" é cruel. Profissionais escrevem código que outros profissionais leem.

### 8. Nomes de classe

Substantivos ou frases nominais: `Customer`, `WikiPage`, `Account`, `AddressParser`. **Não** verbos. Evite palavras como `Manager`, `Processor`, `Data`, `Info` — diluem o significado.

### 9. Nomes de método

Verbos ou frases verbais: `postPayment`, `deletePage`, `save`. Acessadores, mutadores e predicados convencionalmente: `getName`, `setName`, `isPosted`.

Para construtores sobrecarregados, prefira **factory methods estáticos** com nome descritivo:

```
// Em vez de
Complex fulcrumPoint = new Complex(23.0);

// Prefira
Complex fulcrumPoint = Complex.fromRealNumber(23.0);
```

### 10. Não seja "fofinho"

`HolyHandGrenade` em vez de `DeleteItems` faz piada — mas o próximo desenvolvedor não vai rir. `whack()` em vez de `kill()` confunde. Diga o que faz, com clareza, sem trocadilhos.

### 11. Uma palavra por conceito

Escolha uma palavra para cada conceito abstrato e mantenha. Misturar `fetch`, `retrieve`, e `get` para a mesma operação em classes diferentes obriga o leitor a verificar se há diferença. Não há — só inconsistência.

### 12. Não faça trocadilhos

O oposto da regra anterior: não use a mesma palavra para conceitos diferentes. Se em uma classe `add` cria a soma, em outra ele não pode adicionar a uma coleção. Use `insert` ou `append`.

### 13. Use nomes do domínio da solução

Para conceitos técnicos (estruturas de dados, padrões), use vocabulário técnico: `AccountVisitor` (para um Visitor), `JobQueue`. Programadores entendem.

### 14. Use nomes do domínio do problema

Quando não há termo técnico, use o vocabulário do domínio do problema. `OrderLineItem` é mais útil que `Record` para alguém que conhece o negócio.

### 15. Adicione contexto significativo

Variáveis isoladas como `state`, `street`, `zipcode` formam um endereço. Se aparecem soltas em uma função, prefixe (`addrState`, `addrStreet`) ou — melhor — encapsule em uma classe `Address`. O contexto vira parte do nome estrutural.

### 16. Não adicione contexto desnecessário

Se a aplicação se chama "Gas Station Deluxe", prefixar **toda** classe com `GSD` é ruído. Nomes mais curtos são melhores quando o contexto já está claro pelo pacote ou módulo.

## Smells de nome (Cap. 17)

### N1: Escolha nomes descritivos
Nomes em software têm 90% do significado. Não escolha rapidamente — refine. Nomes pobres são tão difíceis de mudar quanto módulos pobres.

### N2: Nomes no nível certo de abstração
Não exponha detalhes de implementação no nome. `getActivePage()` em uma interface não deveria virar `getActiveAccount()` se o conceito é "Page".

### N3: Use nomenclatura padrão onde possível
Se o time usa "Visitor" para o padrão Visitor, use também. Convenções compartilhadas reduzem fricção.

### N4: Nomes não-ambíguos
`doRename` em uma classe que tem só um candidato a renomear é ambíguo se há duas operações de renomeação. Diga **o que** está sendo renomeado.

### N5: Nomes longos para escopos longos
Variável dentro de um loop curto: `i` está bem. Variável que vive por uma classe inteira: precisa de nome completo.

### N6: Evite codificações
Já dito acima. Notação húngara, prefixos `m_`, `I` em interfaces — tudo lixo legado.

### N7: Nomes devem descrever efeitos colaterais
`createOrReturnOos` é melhor que `getOos` se a função pode criar quando não existe. Não esconda atividade.

## Resumo

Escolher bons nomes é difícil — exige boa habilidade descritiva e contexto cultural compartilhado. É uma habilidade de **ensinar**, não só de **codificar**. Pessoas que conhecem o domínio + escrevem bem produzem o melhor código.

E quando você se der conta de que um nome poderia ser melhor, **mude-o**. Modernas IDEs tornam isso barato. A próxima pessoa que ler — talvez você mesmo — vai agradecer.
