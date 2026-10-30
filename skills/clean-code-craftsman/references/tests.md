# Testes Limpos

> "Código de teste é tão importante quanto código de produção. Não é cidadão de segunda classe — requer pensamento, design e cuidado. Tem que ser mantido tão limpo quanto código de produção."

Testes são a rede de proteção que permite refatorar com segurança. Se eles são frágeis, a rede tem buracos. Se são ilegíveis, ninguém os atualiza. Se são lentos, ninguém os roda. **Testes ruins são piores que ausência de testes** — eles dão falsa sensação de segurança e bloqueiam mudanças.

## As três leis do TDD

> "Robert C. Martin pratica TDD com três regras simples:"

1. **Você não pode escrever código de produção até ter escrito um teste de unidade falhando.**
2. **Você não pode escrever mais teste de unidade do que o suficiente para falhar — e não compilar é falhar.**
3. **Você não pode escrever mais código de produção do que o suficiente para fazer o teste passar.**

Isso obriga você a:
- Sempre ter cobertura de teste para tudo que escreveu.
- Pensar **o que** o código deve fazer antes de **como** fazer.
- Manter ciclos curtos (segundos) — escreva teste → fail → produção → pass → refatore.

Aplicado disciplinadamente, o resultado é dezenas (ou centenas) de testes por dia, e código que **sempre passa**.

> Nota: TDD não é dogma. Mas a pressão para "ter testes depois" raramente cumpre o que promete. Testes escritos depois testam o que o código faz, não o que ele deveria fazer. Testes escritos antes testam contrato.

## Mantenha os testes limpos

Testes sujos são piores que testes ausentes. Por quê?

- **Sujos não recebem manutenção.** Quando o código muda, os testes quebram. Se são confusos, é mais fácil deletar do que entender.
- **Sujos prendem-se a detalhes de implementação.** Refatorar quebra dezenas de testes. Em pouco tempo, ninguém ousa mexer no código.
- **Resultado**: o time fica com a opção "testar com cuidado" ou "produzir velocidade". Acaba escolhendo velocidade. Os testes morrem.

O efeito de testes limpos: **eles te dão liberdade**. Você pode refatorar agressivamente porque a rede prende. Sem testes (ou com testes ruins), cada mudança é arriscada.

> "Quanto mais sujos seus testes, mais sujo seu código de produção fica eventualmente."

## Testes habilitam as -ilities

- **Flexibilidade** — você pode mudar o código sem medo.
- **Manutenibilidade** — quem chega depois pode entender e mudar com segurança.
- **Reutilização** — código testado é mais confiável de extrair e reusar.

Sem testes, cada mudança degrada o código (porque você teme refatorar). Com testes limpos, cada mudança o melhora.

## O que faz um teste limpo?

> "Três coisas. Legibilidade. Legibilidade. Legibilidade."

Para ler bem:
- **Clareza**.
- **Simplicidade**.
- **Densidade de expressão** — diga o que precisa em poucas palavras, sem ruído.

Compare:

```
// Sujo — você precisa decifrar o que está sendo testado
public void testGetPageHieratchyAsXml() throws Exception {
    crawler.addPage(root, PathParser.parse("PageOne"));
    crawler.addPage(root, PathParser.parse("PageOne.ChildOne"));
    crawler.addPage(root, PathParser.parse("PageTwo"));

    request.setResource("root");
    request.addInput("type", "pages");
    Responder responder = new SerializedPageResponder();
    SimpleResponse response =
        (SimpleResponse) responder.makeResponse(
            new FitNesseContext(root), request);
    String xml = response.getContent();

    assertEquals("text/xml", response.getContentType());
    assertSubString("<name>PageOne</name>", xml);
    assertSubString("<name>PageTwo</name>", xml);
    assertSubString("<name>ChildOne</name>", xml);
}

// Limpo — três fases claras: BUILD, OPERATE, CHECK
public void testGetPageHieratchyAsXml() throws Exception {
    makePages("PageOne", "PageOne.ChildOne", "PageTwo");

    submitRequest("root", "type:pages");

    assertResponseIsXML();
    assertResponseContains("<name>PageOne</name>", "<name>PageTwo</name>", "<name>ChildOne</name>");
}
```

A segunda versão expressa **o que o teste verifica** sem o ruído mecânico.

## BUILD-OPERATE-CHECK

Cada teste é dividido em três partes claras:

1. **BUILD** — monte os dados do teste.
2. **OPERATE** — execute o que está sendo testado.
3. **CHECK** — verifique o resultado.

Linhas em branco separam visualmente. Em outras tradições, isso é **Given-When-Then** ou **Arrange-Act-Assert**. Mesma ideia: três fases, um conceito por fase.

## Linguagem de domínio do teste

Crie funções utilitárias que falam a linguagem do **domínio do teste**:

```
// Em vez de chamar APIs do sistema diretamente em todo teste...
makePages("PageOne", "PageTwo");
submitRequest("root", "type:pages");
assertResponseIsXML();
assertResponseContains("<name>PageOne</name>");
```

`makePages`, `submitRequest`, `assertResponseIsXML` são vocabulário do **time de teste** — não da implementação. Esse vocabulário evolui com o sistema. Testes ficam fáceis de escrever e de ler porque expressam intenção em alto nível.

## Padrão duplo

Testes podem violar regras que você **não** violaria em produção, **se** isso melhorar a clareza:
- Strings hardcoded.
- Variáveis com nomes mais curtos.
- Estruturas mais imediatas (sem abstração para reuso futuro).

O critério é: **o teste continua claro?** Se sim, OK. Se a violação vira hábito que confunde, recue.

Performance de testes: você pode (e deve) usar mocks/fakes em testes de unidade quando os de integração seriam lentos. Não otimize prematuramente em produção; em testes, otimize por velocidade desde o início — porque testes lentos não rodam.

## Um assert por teste? (controverso)

A regra "**um assert por teste**" é pedagogicamente útil — força você a focar. Mas dogmaticamente aplicada produz fragmentação artificial.

Refinamento: **um conceito por teste**. Pode ter vários `assert`s se todos verificam **o mesmo conceito**.

```
public void testAddMonths() {
    SerialDate d1 = SerialDate.createInstance(31, 5, 2004);
    SerialDate d2 = SerialDate.addMonths(1, d1);
    assertEquals(30, d2.getDayOfMonth());
    assertEquals(6, d2.getMonth());
    assertEquals(2004, d2.getYYYY());

    SerialDate d3 = SerialDate.addMonths(2, d1);
    assertEquals(31, d3.getDayOfMonth());
    assertEquals(7, d3.getMonth());
    assertEquals(2004, d3.getYYYY());
}
```

Isso testa um **conceito** (adicionar meses preserva semântica de dia/mês/ano apropriadamente). Os `assert`s são a verificação multi-dimensional do mesmo conceito. Ok.

## F.I.R.S.T.

Cinco regras para testes limpos:

### Fast (Rápido)

Testes têm que ser rápidos. Lentos não são executados frequentemente. Não executados frequentemente não pegam problemas cedo. Resultado: ninguém roda.

### Independent (Independente)

Testes não devem depender uns dos outros. Cada teste configura o que precisa, executa, e limpa. Você deve poder rodar em qualquer ordem, isoladamente, e tudo passa.

### Repeatable (Repetível)

Em qualquer ambiente. No seu laptop, no laptop do colega, no CI, sem rede. Se um teste depende de "estar conectado ao banco" ou "rodar terça antes do meio-dia", ele é frágil.

### Self-Validating (Auto-validáveis)

Resultado: passou ou falhou. Booleano. **Não** "verifique o log para ver se está OK". Isso é trabalho manual e some quando ninguém olha.

### Timely (Oportuno)

Escreva os testes na hora certa: **antes** do código de produção (TDD) ou junto com (na mesma sprint, no mesmo PR). Testes escritos meses depois geralmente são escritos para o código que **existe**, não para o código que **deveria existir**.

## Smells de teste (Cap. 17)

### T1: Testes insuficientes
"Insuficientes" não é uma métrica simples. Pergunte: cada caso especial, cada borda, cada ramo, está coberto?

### T2: Use uma ferramenta de cobertura
Cobertura mostra os ramos não testados. Não é meta — é diagnóstico. 100% pode ser alcançado escrevendo lixo; 70% bem feito é melhor que 100% trapaceado.

### T3: Não pule testes triviais
Testes triviais valem o esforço. Eles documentam comportamento esperado.

### T4: Um teste ignorado é uma pergunta sobre uma ambiguidade
Se você não sabe se um requisito vale, escreva o teste e marque como `@Ignore` com um comentário explicando a ambiguidade. Isso vira documentação ativa.

### T5: Teste condições de fronteira
A maior parte dos bugs vive nas bordas. Empty list, null, off-by-one, primeira/última iteração. Teste explicitamente.

### T6: Teste exaustivamente perto de bugs
Encontrou um bug? Não pare no teste que o reproduz. Teste vizinhança — geralmente há mais bugs lá.

### T7: Padrões de falha são reveladores
Se um conjunto de falhas tem um padrão comum, esse padrão diz onde está a causa raiz.

### T8: Padrões de cobertura são reveladores
O que **não** está coberto também conta. Linhas/ramos sem cobertura são sintomas.

### T9: Testes devem ser rápidos
Se o teste é lento, ele não é executado. Se não é executado, ele é inútil. Otimize ou mocke.

## Conclusão

> "Testes preservam e enaltecem a flexibilidade, manutenibilidade, e reutilização do código de produção. Mantenha-os limpos. Trabalhe-os para serem expressivos e sucintos. Invente APIs para testes que sirvam como linguagem de domínio que ajude você a escrever os testes."

Sem testes limpos, você perde a capacidade de melhorar o sistema. Com eles, refatorar é um prazer.
