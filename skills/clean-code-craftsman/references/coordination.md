# Coordenação com Outras Skills

Esta skill atua no **nível micro** (linhas, funções, classes, módulos). Outras skills cobrem outros níveis. Saber quando ceder espaço, quando colaborar, e quando atuar sozinho é parte do ofício.

## Mapa do território

```
        +------------------------------------+
        |    arquiteto-minimalista            |  ← MACRO
        |    (sistemas, stacks, contextos)   |
        +-----------------+------------------+
                          |
                          | passa para
                          v
        +------------------------------------+
        |    clean-code-craftsman (ESTA)     |  ← MICRO
        |    (linhas, funções, classes)      |
        +--------+--------------------+------+
                 |                    |
        complementa                   complementa
                 |                    |
         +-------v------+    +--------v---------+
         |java25-spring-|    |    review        |
         |  boot        |    |  (audita skills) |
         +--------------+    +------------------+

         +-----------------+
         | ui-ux-pro-max   |  ← micro de UI/Frontend
         +-----------------+
```

## Regras de fronteira

### Quando **clean-code-craftsman** atua sozinho

- "Refatore esta função para ficar mais clara"
- "Estes nomes estão bons?"
- "Vale a pena este comentário?"
- "Como devo tratar este erro?"
- "Este teste cobre o suficiente?"
- "Esta classe tem mais de uma responsabilidade?"
- "Identifique smells aqui"
- Qualquer pedido focado em **um arquivo, função ou classe específica**

### Quando ceder para `arquiteto-minimalista`

A discussão muda quando o problema é **estrutural** ou **inter-componente**:

- "Devo quebrar isso em microsserviços?"
- "Preciso de um event bus aqui?"
- "Como modelar este domínio?"
- "Devo usar Kafka ou SQS?"
- "Como decompor este monólito?"

Aja: ofereça transição explicitamente.

> "Esta pergunta passou para o nível arquitetural — sai do meu escopo (qualidade de código). A arquiteto-minimalista skill é melhor para discutir essa decisão. Quer que eu chame ela?"

### Quando colaborar com `java25-spring-boot`

Quando a refatoração ou escrita envolve **sintaxe Java moderna** ou **Spring específico**:

- "Refatore para usar virtual threads"
- "Aplique Pattern Matching aqui"
- "Esta dependência Spring está injetada da forma certa?"
- "Como usar `@Component` em vez de `new`?"

Aja: aplique princípios de Clean Code (nomes, funções, separação) **junto com** a sintaxe Java 21+. Os dois andam de mãos dadas — Clean Code dá os princípios, java25-spring-boot dá a expressividade da linguagem moderna.

> "Vou aplicar os princípios de Clean Code aqui. Para sintaxe Java específica (records, sealed types, virtual threads), também vou aproveitar a java25-spring-boot. Você verá os dois juntos no resultado."

### Quando complementar `review`

`review` audita o **conjunto** das 12 squad-ai skills do Thiago. `clean-code-craftsman` audita o **código**. Eles têm escopos diferentes:

| review | clean-code-craftsman |
|---|---|
| Audita SKILL.md files | Audita código de produção |
| Verifica se skills estão atualizadas com Java 25 + AWS | Verifica se código segue princípios de qualidade |
| Foco: governança das skills | Foco: qualidade do código |

Caso de colaboração:
- Se o conteúdo de uma SKILL.md tem **exemplos de código**, esses exemplos podem ser auditados pela clean-code-craftsman.
- Se você revisa código que foi gerado **por** uma skill auditada pelo review, há um ciclo virtuoso: review garante a skill é boa; clean-code-craftsman garante o código que ela gera é bom.

### Quando colaborar com `ui-ux-pro-max`

ui-ux-pro-max cobre design, padrões visuais, frameworks UI. Tem seu próprio "micro" de UI.

- Se o pedido é "como organizar este componente React?", ui-ux-pro-max lidera.
- Se o pedido é "este componente React tem nomes ruins / função grande demais / lógica duplicada", clean-code-craftsman lidera (princípios são universais).
- Em design tokens, espaçamento, paleta — ui-ux-pro-max sempre.

## Quando duas skills conflitam

Princípios de Clean Code são fortes mas não absolutos. Se java25-spring-boot recomenda um padrão idiomático que viola algo do Clean Code (raro, mas acontece), discuta o trade-off:

**Exemplo**: `record` em Java tem todos os campos públicos (via accessors). Estritamente, isso parece violar encapsulamento. Mas:
- Records são **DTOs**. Cap. 6 do Clean Code aceita estruturas de dados expostas.
- Esses são casos onde **idiomas modernos da linguagem** evoluíram com novas formas — Clean Code de 2008 não previu, mas o **espírito** (clareza, intenção, separação) é preservado.

Quando isso acontece, **explicite** o trade-off e a escolha.

## Fluxos típicos

### "Refatore esta função" (clean-code-craftsman puro)

1. Leio a função.
2. Aplico smells (G5, G30, F1, N1).
3. Proponho refatoração com justificativa por mudança.
4. Não menciono outras skills.

### "Refatore esta função para Java 25" (combinação)

1. Aplico Clean Code (G5, G30, etc.) **primeiro**.
2. Aplico modernização Java (records, virtual threads, pattern matching) **depois**.
3. Justifico cada decisão atribuindo à fonte (Clean Code ou java25-spring-boot).

### "Como organizar este sistema?" (passar adiante)

1. Identifico que é nível arquitetural.
2. Não tento resolver com Clean Code (insuficiente).
3. Sugiro chamar arquiteto-minimalista.
4. Se fizermos juntos, foco apenas na qualidade do código que sair, não na decomposição.

### "Este código que vou auditar tem problemas — me ajude a relatar" (revisão formal)

1. Aplico modo Revisão.
2. Reporto smells com código (`G5: duplicação`).
3. Mostro o impacto de cada (não pedante; impacto real).
4. Termino com priorização.

## Princípio geral

**Não invada o que outras skills fazem melhor; não recue do que esta skill faz bem.**

Quando em dúvida sobre quem deveria liderar:
- Pergunta é sobre **um pedaço específico de código**? → clean-code-craftsman
- Pergunta é sobre **sistema, stack, decomposição**? → arquiteto-minimalista
- Pergunta é sobre **sintaxe Java moderna**? → java25-spring-boot lidera, esta skill complementa
- Pergunta é sobre **UI/visual/design**? → ui-ux-pro-max lidera, esta skill complementa
- Pergunta é sobre **as próprias skills**? → review

Combinar é a regra; competir é a exceção.
