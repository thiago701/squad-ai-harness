# Catálogo de Smells e Heurísticas (Cap. 17)

> "Esta lista é para ser lida de cima a baixo e também usada como referência."

Este capítulo é o **dicionário** do livro. Quando você precisa de vocabulário preciso para um problema que está vendo, procure aqui. Cada item tem código, sintoma e correção.

Use os códigos quando reportando achados — `G5: duplicação` é mais rápido e rastreável que "tem código repetido".

## Comentários (C)

| Código | Smell | Sintoma | Ação |
|---|---|---|---|
| **C1** | Informação Inadequada | Histórico de mudanças, autor, número de bug em comentário | Mover para sistema de versionamento ou rastreamento de issues |
| **C2** | Comentário Obsoleto | Comentário não bate com o código atual | Atualizar ou apagar |
| **C3** | Comentário Redundante | Diz o que o código já diz (`i++ // increment i`) | Apagar |
| **C4** | Comentário Mal Escrito | Gramática ruim, divagações, óbvio | Reescrever ou apagar |
| **C5** | Código Comentado | Bloco de código entre `//` ou `/* */` | **Apagar sempre** — controle de versão lembra |

## Ambiente (E)

| Código | Smell | Ação |
|---|---|---|
| **E1** | Build requer mais de um passo | Devia ser `mvn install`, ou um script. Não múltiplos comandos manuais. |
| **E2** | Testes requerem mais de um passo | Um botão / um comando. Senão, não rodam. |

## Funções (F)

| Código | Smell | Ação |
|---|---|---|
| **F1** | Argumentos Demais | 0 > 1 > 2 > 3. Mais que isso, busque conceitos que merecem virar classes. |
| **F2** | Argumentos de Saída | Argumento modificado pela função confunde. Modifique `this`. |
| **F3** | Argumentos Flag | Booleano como argumento sinaliza que faz duas coisas. Separe. |
| **F4** | Função Morta | Sem chamadas. Apague. |

## Geral (G)

Esta é a maior categoria. Trinta e seis itens.

### G1: Múltiplas linguagens em um arquivo
Java + HTML + SQL + JavaScript + XML. Cada um com regras próprias. Confusão. Esforce-se para um por arquivo.

### G2: Comportamento óbvio não implementado
Princípio do mínimo de surpresa. Se uma função se chama `daysInMonth`, **funciona** com qualquer mês. Se quebra em casos óbvios (mês 13, ano negativo), o leitor perde confiança em todo o módulo.

### G3: Comportamento incorreto nas fronteiras
Bordas são onde bugs vivem. Não confie na sua intuição: **escreva testes** para fronteiras (vazio, único, máximo, off-by-one).

### G4: Proteções derrubadas
"Apenas vou desligar este teste para que o build passe" — caminho para o desastre. `@Ignore` permanente, asserções comentadas, exceções engolidas. **Não desligue proteções; conserte o que está protegendo.**

### G5: Duplicação
> "Não Repita Você Mesmo (DRY) ou Princípio Único do Sistema."

Cada vez que algo é duplicado, é uma oportunidade perdida de abstração. Tipos de duplicação:
- **Idêntica** — exatamente o mesmo código duas vezes. Extraia.
- **Similar** — `switch/case` espalhado. Polimorfismo.
- **Modular** — algoritmos similares com pequenas variações. Template Method ou Strategy.

### G6: Código no nível errado de abstração
Detalhe baixo (manipulação de string, cast) numa função de alto nível (regra de negócio). Ou abstração alta (interface, conceito) numa função de baixo nível. Cada nível em seu lugar.

```
// Ruim — mistura abstrações
public interface Stack {
    Object pop();
    void push(Object o);
    double percentFull(); // ← detalhe de implementação
    int getCapacity();    // ← detalhe de implementação
}
```

`percentFull()` faz sentido para algumas implementações (array). Para outras (linked list), não. Está vazando.

### G7: Classes base dependendo de seus derivados
Geralmente sinal que a base sabe demais sobre os filhos. Idealmente, base não conhece filhos — herança é polimórfica de cima para baixo.

### G8: Informação demais
Bons módulos expõem **pouco**. Quanto menor a interface, menor o acoplamento. Métodos públicos demais, classes auxiliares expostas, variáveis acessíveis — tudo isso aumenta a área de superfície.

### G9: Código morto
Funções que nunca rodam. Branches `if (false)`. Catches vazios. Apague.

### G10: Separação vertical
Variáveis e funções devem ser definidas perto de onde são usadas. Decimais entre declaração e uso forçam o leitor a rolar.

### G11: Inconsistência
Se você decide fazer algo de um jeito, faça **sempre** desse jeito. `response.setContentLength(...)` em um lugar, `setContentLength(response, ...)` em outro: leitor sofre.

### G12: Bagunça
Variáveis não usadas. Funções nunca chamadas. Comentários sem propósito. Construtores vazios. Tudo isso é entulho. **Limpe.**

### G13: Acoplamento artificial
Coisas que não dependem umas das outras não devem ser acopladas. `enum` definida dentro de uma classe específica, mas usada por outras. Tire para um lugar neutro.

### G14: Inveja de feature (Feature Envy)
Método de uma classe se interessa demais por dados de outra:

```
public class HourlyPayCalculator {
    public Money calculateWeeklyPay(HourlyEmployee e) {
        int tenthRate = e.getTenthRate().getPennies();
        int tenthsWorked = e.getTenthsWorked();
        // ... operações em campos de e
    }
}
```

`HourlyPayCalculator` parece mais interessado em `HourlyEmployee` que em si próprio. **Mova o método** para `HourlyEmployee`.

### G15: Argumentos seletores
Booleano (ou enum, ou flag) que escolhe comportamento. Sinaliza múltiplas responsabilidades.

```
public int calculateWeeklyPay(boolean overtime) {
    int tenthRate = getTenthRate();
    int tenthsWorked = getTenthsWorked();
    int straightTime = Math.min(400, tenthsWorked);
    int overTime = Math.max(0, tenthsWorked - straightTime);
    int straightPay = straightTime * tenthRate;
    double overtimeRate = overtime ? 1.5 : 1.0 * tenthRate;
    int overtimePay = (int) Math.round(overTime * overtimeRate);
    return straightPay + overtimePay;
}
```

`overtime` argumento sinaliza duas funções. Quebre.

### G16: Intenção obscurecida
Código que esconde o que está fazendo atrás de cálculos compactados, expressões cripticas, ou notação econômica:

```
public int m_otCalc() {
    return iThsWkd * iThsRte +
        (int) Math.round(0.5 * iThsRte *
            Math.max(0, iThsWkd - 400));
}
```

Compacto, mas críptico. Variáveis explicativas, nomes melhores, e — frequentemente — separação em duas funções resolveriam.

### G17: Responsabilidade fora do lugar
Onde **deveria** estar este código? Algum princípio de localidade?

Por exemplo: cálculo de cobertura está em `PI` ou em `OverTimePay`? Provavelmente o segundo é mais natural. Coloque no lugar onde quem lê **espera** encontrar.

### G18: Static inadequado
Métodos estáticos servem para operações que **não** se referem a um objeto particular. `Math.max(a, b)` é um clássico legítimo. Mas se há **qualquer** chance de querer um comportamento específico-de-objeto (subclasse, mock), prefira um método de instância.

### G19: Use variáveis explicativas
Quebre cálculos complexos em variáveis com bons nomes:

```
// Ruim
Matcher match = headerPattern.matcher(line);
if (match.find()) {
    String key = match.group(1);
    String value = match.group(2);
    headers.put(key.toLowerCase(), value);
}

// Bom — variáveis nomeiam intenção
Matcher match = headerPattern.matcher(line);
if (match.find()) {
    String key = match.group(1);
    String value = match.group(2);
    headers.put(key.toLowerCase(), value);
}
```

### G20: Nomes de função devem dizer o que fazem
Se você precisa olhar a implementação para saber o que ela faz, o nome falha:

```
Date newDate = date.add(5);
```

Adiciona 5 dias? 5 horas? 5 milissegundos? O nome **deve** ser explícito: `addDays(5)`, `daysLater(5)`.

### G21: Entenda o algoritmo
Não escreva uma função até saber **como ela funciona**. Refatorar até funcionar **e** ficar claro é diferente de "arrumar até passar". Se você tem um teste passando mas não consegue explicar o algoritmo, refatore-o até conseguir.

### G22: Faça dependências lógicas físicas
Se um módulo A depende de um valor que B fornece, A não deveria **inferir** esse valor — deveria **perguntar** a B.

```
// Ruim — A presume saber o tamanho da página
private void printPageBreak() {
    if (rowsPerPage > 0 && rowCount % rowsPerPage == 0) {
        // imprime quebra
    }
}

// Bom — pergunte ao componente que sabe
if (reportFormat.shouldHavePageBreak(rowCount)) { ... }
```

### G23: Prefira polimorfismo a if/else ou switch/case
Já discutido em Funções. `switch` que repete o mesmo conjunto de casos em vários lugares é o caso clássico para polimorfismo.

### G24: Siga convenções padrão
Convenções do time, da linguagem, do framework. Se o time usa `camelCase`, **não** decida fazer `snake_case` na sua classe. Convenções são cimento social.

### G25: Substitua números mágicos por constantes nomeadas
`return value * 0.85;` — o que é 0.85? Margem? Imposto? Desconto?

```
final double DISCOUNT_RATE = 0.85;
return value * DISCOUNT_RATE;
```

### G26: Seja preciso
Decisões devem ser deliberadas, não acidentais. Se você usa `int` e não `long`, **escolha**. Se você usa `null` em vez de `Optional`, **justifique**. Imprecisão é raiz de bugs.

### G27: Estrutura sobre convenção
Decisões impostas pela estrutura ganham. Decisões impostas por convenção exigem disciplina contínua. Quando puder, faça a estrutura forçar a regra.

### G28: Encapsule condicionais
Condicional booleana complexa? Mude para função:

```
// Ruim
if (timer.hasExpired() && !timer.isRecurrent()) {

// Bom
if (shouldBeDeleted(timer)) {
```

### G29: Evite condicionais negativas
`if (!buffer.shouldNotCompact())` — duas negações. Reescreva afirmativamente: `if (buffer.shouldCompact())`.

### G30: Funções devem fazer uma coisa
Já dito. Vale repetir.

### G31: Acoplamentos temporais escondidos
Se a função A precisa rodar antes de B, **a estrutura deve dizer isso**:

```
// Ruim — chamadas independentes que precisam de ordem específica
public void dive(String reason) {
    saturateGradient();
    reticulateSplines();
    diveForMoog(reason);
}

// Bom — saída de uma é input da próxima, forçando a ordem
public void dive(String reason) {
    Gradient gradient = saturateGradient();
    List<Spline> splines = reticulateSplines(gradient);
    diveForMoog(splines, reason);
}
```

### G32: Não seja arbitrário
Decisões em código devem ter razão. "Eu fiz assim porque sim" gera padrões inconsistentes que outros vão imitar sem entender.

### G33: Encapsule condições de fronteira
"Mais um", "menos um", "menor que" — se aparecem em vários lugares, encapsule:

```
// Ruim — espalhado
if (level + 1 < tags.length) { ... }
// e em outro lugar
String parts[] = "abc".split(",");
String firstPart = parts.length > 0 ? parts[0] : "";

// Bom — encapsulado
int nextLevel = level + 1;
if (nextLevel < tags.length) { ... }
```

### G34: Funções devem descer apenas um nível de abstração
Se uma função tem partes em três níveis diferentes, ela está desorganizada. Cada função em **um** nível.

### G35: Mantenha dados configuráveis em alto nível
Constantes de configuração não deveriam estar enterradas em código baixo nível. Eleve-as para o alto — facilita ajustar.

### G36: Evite navegação transitiva
Lei de Demeter de novo. `a.getB().getC().getD()` é frágil — qualquer mudança intermediária quebra todo o caminho.

## Java (J)

| Código | Smell | Ação |
|---|---|---|
| **J1** | Listas de import longas | Use wildcards (`import java.util.*;`) |
| **J2** | Não herde constantes | Usar interface só para constantes é abuso. Prefira `import static` |
| **J3** | Constantes vs Enums | Enums têm métodos, são type-safe. Use enums em vez de `int` constants |

## Nomes (N)

| Código | Smell | Ação |
|---|---|---|
| **N1** | Escolha nomes descritivos | Refine — nomes ruins são tão difíceis de mudar quanto módulos ruins |
| **N2** | Nomes no nível certo de abstração | Não exponha implementação no nome da interface |
| **N3** | Use nomenclatura padrão | Se o time usa "Visitor", use também. Convenções compartilhadas |
| **N4** | Nomes não-ambíguos | Diga **o que** é — não deixe duas operações similares sem distinção |
| **N5** | Nomes longos para escopos longos | `i` em loop é ok; `i` como campo de classe não |
| **N6** | Evite codificações | Notação húngara, prefixos `m_`, `I` em interfaces — todos lixo |
| **N7** | Nomes devem descrever efeitos colaterais | `createOrReturnOos` é melhor que `getOos` se cria quando não existe |

## Testes (T)

| Código | Smell | Ação |
|---|---|---|
| **T1** | Testes insuficientes | Cada caso especial, cada borda — está coberto? |
| **T2** | Use ferramenta de cobertura | Mostra os ramos não testados. Diagnóstico, não meta. |
| **T3** | Não pule testes triviais | Eles documentam comportamento esperado. |
| **T4** | Teste ignorado é uma pergunta sobre ambiguidade | `@Ignore` marca uma decisão pendente, vira documentação |
| **T5** | Teste condições de fronteira | Vazio, null, off-by-one, primeiro/último |
| **T6** | Teste exaustivamente perto de bugs | Bug encontrado? Vizinhança provavelmente tem mais |
| **T7** | Padrões de falha são reveladores | Falhas semelhantes apontam causa raiz comum |
| **T8** | Padrões de cobertura são reveladores | O que não está coberto também conta |
| **T9** | Testes devem ser rápidos | Lentos não rodam, e o que não roda é inútil |

## Como usar este catálogo

- Em **modo Revisão**: aponte com código (`G5`, `N1`) para dar rastreabilidade.
- Em **modo Refatoração**: ataque os mais impactantes primeiro (geralmente `G5` duplicação, `G30` faz mais de uma coisa, `N1` nomes).
- Em **modo Escrita**: use mentalmente como filtro antes de entregar.

Não é necessário decorar. Use como referência. Os mais frequentes (G5, G30, F1, N1, N7, C5, T1) aparecem em quase toda revisão — esses, sim, vale internalizar.
