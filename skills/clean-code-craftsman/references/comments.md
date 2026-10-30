# Comentários

> "Não comente código ruim — reescreva-o." — Brian Kernighan & P. J. Plauger

Comentários são, no melhor caso, um **mal necessário**. Quando precisamos deles é porque falhamos em expressar a intenção no código. Eles não são intrinsecamente bons — são uma desculpa.

## A premissa

Por que ser cético com comentários?

1. **Comentários mentem.** Não maliciosamente — mas o código muda, e os comentários não acompanham. Quanto mais antigo o código, mais distantes os comentários ficam da verdade.
2. **Comentários compensam más decisões.** "Eu não consegui dar nome a isso, então comentei" é o sintoma. A cura é nomear melhor.
3. **Comentários adicionam ruído visual.** Eles ocupam espaço, distraem, e pioram a relação sinal/ruído.

A pergunta correta antes de escrever um comentário é: **eu posso transmitir essa informação no próprio código?** Quase sempre, sim:

```
// Ruim
// Verifica se o funcionário tem direito a benefícios
if ((employee.flags & HOURLY_FLAG) && (employee.age > 65))

// Bom — o código fala por si
if (employee.isEligibleForFullBenefits())
```

Renomear, extrair função, criar variável explicativa. Essas são as primeiras escolhas. Comentário é a última.

## Comentários compensam código ruim

> "Comentários claros e expressivos são reaproveitados a cada release; código sujo precisa de uma reescrita a cada bug."

Se você se pega comentando uma função porque ela é confusa, não escreva o comentário — limpe a função. **Código limpo e expressivo com poucos comentários é superior** a código sujo cheio de comentários.

## Explique-se no código

Você consegue criar uma função explicativa para quase qualquer caso onde pensaria em comentar.

```
// Ruim
// Verifica se ovo está pronto
if (timer >= 360 && temperature >= 200) { ... }

// Bom
if (eggIsReady(timer, temperature)) { ... }
```

## Comentários bons (existem!)

Há casos onde comentários são genuinamente úteis. Mesmo nesses, escrutínio é saudável.

### 1. Comentários legais

Notas de copyright, licença, etc. — exigidos por contrato ou convenção corporativa. Não há como evitá-los.

```
// Copyright (C) 2008 by Object Mentor, Inc. All rights reserved.
// Released under the terms of the GNU General Public License version 2 or later.
```

### 2. Comentários informativos

Quando o comentário fornece informação básica útil que não cabe no nome:

```
// formato kk:mm:ss EEE, MMM dd, yyyy
Pattern timeMatcher = Pattern.compile("\\d*:\\d*:\\d* \\w*, \\w* \\d*, \\d*");
```

Ainda assim — esse padrão poderia virar uma classe `TimePattern` com nome auto-explicativo.

### 3. Explicação de intenção

Quando o comentário explica **por que** uma decisão foi tomada — algo que o código não consegue expressar:

```
// Estamos forçando que este teste falhe deliberadamente
// para validar que o framework de detecção de timeout funciona.
```

A intenção raramente cabe no código. Esse é o tipo de comentário que envelhece bem.

### 4. Esclarecimento

Quando você não controla o código (uma biblioteca de terceiros, por exemplo) e precisa traduzir um valor obscuro:

```
assertEquals(0, a.compareTo(a)); // a == a
assertEquals(-1, a.compareTo(b)); // a < b
```

### 5. Aviso de consequências

Avisos importantes que o código não consegue gritar:

```
// Não execute a menos que você tenha algumas horas livres.
public void _testWithReallyBigFile() { ... }

// SimpleDateFormat não é thread-safe; cada thread cria a sua.
```

### 6. Comentários TODO

Razoáveis quando devidamente acompanhados (e devidamente removidos quando feitos). Use-os como marcadores temporários, não como cemitério de boas intenções.

```
// TODO: refatorar para usar a nova API quando ela estiver estável (ticket #1234)
```

Se um TODO viveu mais de uma sprint sem ser endereçado, **ele é uma mentira**. Apague ou faça.

### 7. Amplificação

Quando você precisa enfatizar a importância de algo aparentemente trivial:

```
String listItemContent = match.group(3).trim();
// O trim é REAL importante. Remove espaços de início que poderiam
// fazer o item ser interpretado como continuação da lista anterior.
```

### 8. Javadocs em APIs públicas

APIs públicas merecem boa documentação — esse é seu contrato com o mundo. Mas Javadocs ruins são piores que ausentes (veja smells abaixo).

## Comentários ruins (a maioria)

A vasta maioria dos comentários cai aqui. Identifique e elimine.

### Resmungos

Comentários escritos por obrigação, sem cuidado, deixam o leitor mais confuso:

```
catch (IOException e) {
    // ler erro de carregamento
    // que tal um valor padrão?
    // talvez falhar?
}
```

O que esse comentário diz? Não está claro. Se a única audiência é você mesmo, escreva o suficiente para você lembrar **o que fazer**, não para você divagar.

### Comentários redundantes

Repetem o que o código já diz:

```
// Utility method that returns when this.closed is true.
// Throws an exception if the timeout is reached.
public synchronized void waitForClose(final long timeoutMillis) throws Exception
```

O Javadoc diz exatamente o que a assinatura já mostra. **Comentários devem dizer o que o código não consegue.** Se o comentário só repete a assinatura, ele é ruído.

```
i++; // increment i
```

Crime sem desculpa.

### Comentários enganosos

Pior que redundante: o que está sutilmente errado. Geralmente acontece quando o código mudou e o comentário não. Leitores que confiam no comentário entram em armadilhas.

### Comentários mandatórios

Regra que diz "toda função deve ter Javadoc" produz exatamente o lixo abaixo, em massa:

```
/**
 * @param title The title of the CD
 * @param author The author of the CD
 * @param tracks The number of tracks on the CD
 * @param durationInMinutes The duration of the CD in minutes
 */
public void addCD(String title, String author, int tracks, int durationInMinutes)
```

Substitui zero conhecimento por seis linhas. Aboliam.

### Comentários de jornal

```
// Changes (from 11-Oct-2001)
// --------------------------
// 11-Oct-2001 : Re-organised the class and moved it to new package
// 05-Nov-2001 : Added a getDescription() method
// ...
```

Para isso existe **controle de versão**. Apague.

### Comentários de ruído

Repetem o óbvio sem adicionar nada:

```
/** O dia do mês. */
private int dayOfMonth;
```

Apague.

### Marcadores de posição

```
// Actions //////////////////////////////////
```

Se você precisa de marcadores assim, sua classe é grande demais. Quebre.

### Comentários de chave de fechamento

```
} // while
} // for
} // try
```

Se você precisa marcar qual chave fecha o quê, sua função é grande demais. Quebre.

### Atribuições e bylines

```
/* Added by Bob */
```

Quem adicionou é o que o controle de versão sabe. Apague.

### Código comentado

```
// InputStreamResponse response = new InputStreamResponse();
// response.setBody(formatter.getResultStream(), formatter.getByteCount());
```

Quem o escreveu pensa que ainda pode ser útil. Quem chega depois não sabe se é importante e tem medo de apagar. **Resultado**: código morto que apodrece.

**Apague código comentado**. Se precisar voltar, está no controle de versão.

### Comentários HTML

HTML em comentários de código fonte — porque "vai aparecer no Javadoc" — torna o código fonte ilegível. Se o comentário precisa virar HTML, é trabalho da ferramenta de geração de documentação, não do humano que escreve.

### Informação não-local

Comentário que descreve coisas além do contexto imediato. Não comente em uma função coisas que se referem a outra:

```
public void setFitnessePort(int fitnessePort) {
    /**
     * Porta no qual o fitnesse roda. Default 8082.
     */
    this.fitnessePort = fitnessePort;
}
```

O comentário descreve o que vai aparecer em outro lugar. Migre o comentário (ou — melhor — apague e dê nomes melhores).

### Informação demais

Não despeje conhecimento de domínio histórico no comentário. Mantenha o suficiente para entender o código.

### Conexão não-óbvia

Se o comentário precisa do **próprio** comentário para ser entendido, ele é ruim:

```
/*
 * iniciar com um array que é grande o suficiente para conter todos os
 * pixels (mais filtros), e mais 200 bytes para informação de cabeçalho.
 */
this.pngBytes = new byte[((this.width + 1) * this.height * 3) + 200];
```

O que é "filtros"? Por que `+1` na largura? Comentário deveria iluminar; este escurece.

### Cabeçalhos de função

Funções pequenas com nomes bem escolhidos não precisam de cabeçalho. Funções grandes que precisam de cabeçalho deveriam ser quebradas.

### Javadocs em código não público

API pública pode justificar Javadoc. Código interno raramente — adiciona cerimônia sem adicionar comunicação.

## Smells de comentário (Cap. 17)

### C1: Informação inadequada
Comentários não devem conter histórico de mudanças, números de SPR, autores. Isso vive no controle de versão. Comentário é para nota técnica sobre código e design.

### C2: Comentário obsoleto
Comentário que envelheceu, ficou irrelevante, e agora mente. Atualize ou — preferencialmente — apague.

### C3: Comentário redundante
Diz o que o código já diz. Sempre apagar.

### C4: Comentário mal escrito
Se vai escrever, escreva bem. Gramática, escolha de palavras, brevidade. Comentários ruins são piores que ausentes.

### C5: Código comentado
Apague. Sempre. Sem exceção. Controle de versão lembra.

## Conclusão

Comentários não são tóxicos por natureza, mas são frequentemente sintomas. Antes de escrever um, pergunte: **posso fazer o código falar por si?** A resposta é "sim" muito mais vezes do que parece.

Quando o comentário sobreviver a essa pergunta — escreva-o bem. Comentário curto, preciso, focado em **o porquê**, vivendo perto do código que descreve. Mantenha-o atualizado ou apague-o.

A meta não é zero comentários. A meta é **honestidade**: cada comentário tem que ter razão de ser, e essa razão tem que ser maior que o que o código sozinho já diz.
