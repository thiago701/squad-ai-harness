# RestAssured Professional — Reference Implementation

Prova **executável** da reference [`../../references/rest-assured-api-testing.md`](../../references/rest-assured-api-testing.md)
da skill `especialista-qualidade`. Um projeto Maven que roda offline (após baixar dependências) e
demonstra, com testes verdes, os padrões profissionais de teste de API REST com **RestAssured**.

## O que este projeto prova

- **Specs reutilizáveis** (`RequestSpecBuilder` / `ResponseSpecBuilder`) — DRY de base URI, headers, auth e SLA.
- **Validação por JSON Schema** (`matchesJsonSchemaInClasspath`, draft-04).
- **Serialização tipada** — resposta desserializada em POJO, dinheiro em `BigDecimal`.
- **Autenticação OAuth2/Bearer** (`.auth().oauth2(...)`) + cenário negativo 401.
- **Data-driven** com JUnit 5 `@ParameterizedTest` + `@MethodSource`.
- **Os 8 eixos** de cenário: happy path, input validation, auth, not found, state conflict.
- **API sob teste = WireMock in-process** — sem Docker, sem servidor externo, 100% determinístico.

## Como rodar

```bash
mvn test                 # GREEN — 10/10 testes passam
RED_PHASE=1 mvn test     # RED   — 10/10 falham (contrato NÃO implementado)
```

O flag `RED_PHASE=1` desliga os stubs do WireMock (a "implementação"), simulando a fase RED do TDD: os
testes existem mas a API ainda não cumpre o contrato. Remover o flag = fase GREEN.

## Resultado verificado (Java 11, RestAssured 5.5.6)

| Fase | Comando | Resultado |
|---|---|---|
| GREEN | `mvn test` | `Tests run: 10, Failures: 0, Errors: 0` — **BUILD SUCCESS** |
| RED | `RED_PHASE=1 mvn test` | `Tests run: 10, Failures: 10` — **BUILD FAILURE** (esperado) |

## Estrutura

```
src/test/java/com/squadai/qa/restassured/
  support/ApiSpecs.java              # specs reutilizáveis (o coração do framework)
  support/WireMockApiTest.java       # base: sobe WireMock e stuba o contrato (RED/GREEN)
  model/ConfirmarPedidoResponse.java # POJO de desserialização
  ConfirmarPedidoApiTest.java        # suíte funcional dos 8 eixos
  PedidoValidacaoDataDrivenTest.java # validação data-driven
src/test/resources/
  schemas/confirmar-pedido-response.schema.json   # contrato (JSON Schema draft-04)
```

## Compatibilidade de versões

Este exemplo compila em **Java 11** e usa **RestAssured 5.5.6** por restrição do ambiente de execução
(sandbox com JDK 11). Em **produção**, a Squad AI usa **Java 25 + Spring Boot 4 / Jackson 3**, cujo alvo
é **RestAssured 6.0.0** (baseline Java 17+, Groovy 5, suporte a Spring 7 + Jackson 3). Para migrar:

1. `maven.compiler.release` → `25`
2. `rest-assured.version` → `6.0.0`
3. Trocar o POJO por `record` (Java 25) e `String confirmadoEm` por `OffsetDateTime`.

A API do DSL (`given/when/then`, specs, schema validation, `oauth2`) é idêntica entre 5.5.x e 6.0.0.

## Detalhe técnico: JSON Schema draft-04

O módulo `json-schema-validator` usa a lib `fge/java-json-tools`, que valida contra **draft-04**. Por
isso `valorTotal` usa `"minimum": 0, "exclusiveMinimum": true` (forma booleana do draft-04), e não a
forma numérica do draft-07 — que geraria `InvalidSchemaException`. Esse erro foi reproduzido e corrigido
durante a construção deste exemplo (ver reference §4).
