# clean-code-craftsman · Síntese dos princípios por área

> Reference da skill `clean-code-craftsman` (movida da SKILL.md em 11/10/2026 — hub + references, I3). Carregue só quando a tarefa pedir este tema.

## Síntese dos princípios por área

Cada área tem um arquivo de referência. Leia o arquivo relevante quando a tarefa cair nele — não tente carregar tudo de uma vez.

### Nomes (`references/naming.md`)

Nomes são a interface humana do código. **Revele intenção** (`elapsedTimeInDays` > `d`), **evite desinformação** (não chame de `accountList` o que não é uma lista), **faça distinções significativas** (`a1`, `a2` não distinguem nada), **use nomes pronunciáveis e pesquisáveis**, **escolha uma palavra por conceito** (não misture `fetch`, `retrieve`, `get`).

### Funções (`references/functions.md`)

**Pequenas. Muito pequenas.** Idealmente 4-20 linhas. **Fazem uma coisa só** — se você consegue extrair outra função com nome significativo, ela fazia mais de uma. **Um nível de abstração por função** (regra do step-down: cada função chama outras um nível abaixo). **Poucos argumentos** (zero é ideal, três é o limite, mais que isso vira objeto). **Sem efeitos colaterais escondidos**. **Comando ou consulta, nunca os dois**.

### Comentários (`references/comments.md`)

**Comentários são, no melhor caso, um mal necessário.** Eles sempre falham em manter-se atualizados com o código. Se você sente vontade de escrever um comentário, primeiro tente: renomear, extrair função, criar variável explicativa. Comentários bons existem (legais, intenção, aviso de consequência, amplificação, TODO marcado), mas a maioria do que parece bom é redundante, obsoleto, ou ruído.

### Formatação (`references/formatting.md`)

Formatação é comunicação. **Metáfora do jornal**: o topo do arquivo dá o panorama, descendo aumenta o detalhe. **Densidade vertical**: linhas relacionadas próximas; conceitos diferentes separados por espaço. **Distância vertical**: variáveis perto de seu uso, funções relacionadas próximas. **Largura horizontal modesta** (80-120 colunas). **Indentação consistente**. Equipe deve concordar e ferramentas devem aplicar.

### Objetos e Estruturas de Dados (`references/objects-and-data.md`)

**Objetos escondem dados, expõem comportamento. Estruturas de dados expõem dados, não têm comportamento significativo.** Não misture. **Lei de Deméter**: um método deve falar apenas com amigos próximos — `objA.getB().getC().fazAlgo()` (train wreck) viola. **DTOs** (Data Transfer Objects) são puras estruturas, sem regras de negócio.

### Tratamento de erros (`references/error-handling.md`)

**Use exceções, não códigos de retorno**. **Escreva o try/catch primeiro** (delimite o escopo do erro antes da lógica feliz). **Forneça contexto** com mensagens informativas. **Defina classes de exceção pelas necessidades de quem chama**, não pela origem técnica. **Não retorne null** (devolva coleção vazia, Optional, ou Special Case Object). **Não passe null** como argumento.

### Testes (`references/tests.md`)

**Testes são de primeira classe** — merecem o mesmo cuidado que o código de produção. **F.I.R.S.T.**: Fast, Independent, Repeatable, Self-validating, Timely. **Um conceito por teste**. **Linguagem de domínio do teste** (BUILD-OPERATE-CHECK). As **três leis do TDD**: (1) não escreva código de produção sem um teste falhando, (2) não escreva mais teste do que o suficiente para falhar, (3) não escreva mais código de produção do que o suficiente para passar.

**Cobertura proativa**: quando uma classe nova nasce, seu teste nasce junto — no mesmo PR. Cobertura ≥ 90% no projeto (gate ≥ 97% em camadas críticas como `domain/` e `api/`) configurado para falhar o build, não advisory. **Estrutura padrão moderna** (JUnit 5 + AssertJ + Mockito): `@Nested` agrupando por cenário (`Validacao` / `HappyPath` / `MapError`), `@DisplayName` em pt-BR descrevendo a regra (não a implementação), `@ParameterizedTest` + `@CsvSource` para colapsar variações, `@NullAndEmptySource` para inputs vazios, AAA explícito, fixtures privadas estáticas no fim do arquivo. **Asserte comportamento, não texto rígido de erro** — `assertThat(resp.getStatusCode()).isEqualTo(400)` é estável; `.contains("invalido")` quebra quando alguém melhora a mensagem.

### Classes (`references/classes.md`)

**Classes pequenas**. Métrica: número de **responsabilidades**, não de linhas. **SRP**: uma única razão para mudar. **Coesão alta**: instâncias compartilham muitas variáveis com muitos métodos; baixa coesão sinaliza que a classe quer ser várias. **Organização para mudança**: dependa de abstrações, isole o que muda do que não muda (OCP).

### Catálogo de smells (`references/smells-catalog.md`)

Referência rápida do Capítulo 17. Use quando precisar de **vocabulário preciso** para um problema que está vendo: Comments (C1-C5), Environment (E1-E2), Functions (F1-F4), General (G1-G36), Names (N1-N7), Tests (T1-T9). Cada smell tem nome, sintoma e correção.

### Coordenação com outras skills (`references/coordination.md`)

Como decidir quando esta skill deve atuar sozinha, ceder espaço, ou colaborar. Regras práticas para combinar com **arquiteto-minimalista**, **java25-spring-boot**, **java-modernizer** (as 9 regras da Calistenia de Objetos × Java 25, com antes/depois e JEPs), **review**, e **ui-ux-pro-max**.

### Java / Spring — review e clean code (`references/java-clean-code-review.md`)

Aplicação dos princípios ao **review de Java/Spring**: taxonomia de severidade de PR em 6 rótulos (incl. `learning`/`praise`), review em 4 fases (contexto → alto nível → linha-a-linha → decisão) e checklist de clean code Java/JPA (Records, sealed, injeção por construtor, N+1, `equals`/`hashCode` em entidade). Padrões absorvidos de fontes externas — ver `docs/ATTRIBUTIONS.md`.
