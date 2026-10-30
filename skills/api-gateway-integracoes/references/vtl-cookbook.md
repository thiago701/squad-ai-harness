# Cookbook VTL (API Gateway REST/WebSocket) — padrões testados

> Parte da skill `api-gateway-integracoes`. Hub: `../SKILL.md`. Cada padrão abaixo está exercitado em
> `labs/aws-referencia-ordens/java/src/test/java/exemplo/ordens/vtl/VtlTemplatesTest.java`
> (Apache Velocity 2.4.1 real; `$input/$util/$context` emulados pela referência oficial — V3-emulado).

## 1. As 6 funções `$util` (e só elas)

`escapeJavaScript`, `parseJson`, `urlEncode`, `urlDecode`, `base64Encode`, `base64Decode`. Não existe
`$util.toJson` (lint `VTL-006`). Para serializar um campo do corpo, use `$input.json('$.campo')`.

## 2. Escape — as três situações

| Onde o valor vai | Fonte | Forma correta |
|---|---|---|
| String JSON simples | claim, parâmetro de path/query | `"$util.escapeJavaScript($x).replaceAll("\\'","'")"` |
| Valor JSON (não string) | campo do corpo | `$input.json('$.campo')` (já vem codificado, com aspas) |
| String **dentro de string** (ex.: `input` do `StartExecution`) | campo do corpo | `$util.escapeJavaScript($input.json('$.campo')).replaceAll("\\'","'")` |
| String dentro de string | claim | escape **duas vezes**: `#set($t = $util.escapeJavaScript($claim).replaceAll(...))` e depois `$util.escapeJavaScript($t).replaceAll(...)` |

O `.replaceAll("\\'","'")` vem da própria referência oficial: `escapeJavaScript` transforma `'` em
`\'`, que é JSON inválido.

## 3. Identidade e chaves

```velocity
#set($claims = $context.authorizer.claims)
#set($tenant = $util.escapeJavaScript($claims['custom:tenant_id']).replaceAll("\\'","'"))
#set($usuario = $util.escapeJavaScript($claims.sub).replaceAll("\\'","'"))
"pk": {"S": "T:$tenant:U:$usuario"},
"sk": {"S": "O:$util.escapeJavaScript($input.params('ordemId')).replaceAll("\\'","'")"}
```

- **Delimitador `:` e não `#`** nas chaves: `#` inicia diretiva no Velocity e `##` comenta o resto da
  linha — `T##...` some em silêncio.
- O id do cliente só entra na chave de ordenação. Teste obrigatório: id contendo `","pk":{...}` não
  cria nem sobrescreve chave (`VtlTemplatesTest.ObterOrdem.idAdulteradoNaoMudaParticao`).

## 4. Idempotência do `StartExecution` (Standard)

- `name` = `<sub>-<idempotencyKey>` (≤ 80 caracteres; UUIDs cabem).
- O `input` **não** pode ter valor por requisição (`requestId`, horário): repetição com o mesmo nome
  e input diferente vira `ExecutionAlreadyExists`. Teste: duas renderizações com `requestId`
  diferentes produzem corpo byte-idêntico.
- Resposta 202: extraia o id do **nome** da execução; nunca devolva o `executionArn`.

## 5. Números e aritmética

No Velocity, `"1" + 1` **concatena** (`"11"`) — comprovado no `velocity-engine-core` 2.4.1. Faça
aritmética só depois de validar:

```velocity
#set($esperada = "$input.path('$.versaoEsperada')")
#if($esperada.matches('^(0|[1-9][0-9]{0,8})$'))
#set($nova = $input.path('$.versaoEsperada') + 1)
#else
#set($esperada = 'invalido')
#set($nova = 'invalido')
#end
```

Valor inválido vira um `N` inválido → o DynamoDB responde `ValidationException` (400) em vez de
aceitar campos injetados.

## 6. Paginação

- Requisição: `Limit` validado por regex com teto (`^[1-9][0-9]?$`, senão 20); cursor =
  `base64Decode` da chave de ordenação; `ExclusiveStartKey.pk` **reconstruído da identidade**.
- Resposta: `#foreach` com `$foreach.hasNext` para vírgulas; `proximoCursor` =
  `base64Encode($LastEvaluatedKey.sk.S)`; `null` na última página. O cliente envia o cursor
  *urlencoded*. Lembre: `Limit` conta itens **avaliados** e `LastEvaluatedKey` presente não garante
  mais itens.

## 7. Erros e status

```velocity
#set($tipo = $input.path('$.__type'))
#if("$!tipo" != "" && $tipo.contains('ConditionalCheckFailed'))
#set($context.responseOverride.status = 409)
{"codigo": "VERSAO_DESATUALIZADA", "mensagem": "...", "correlacao": "$context.extendedRequestId"}
#end
```

- `selectionPattern` (`"4\\d{2}"`) casa o **status** da integração AWS; a distinção fina vem do `__type`.
- `"$!x" == ""` cobre referência nula e string vazia; `GetItem` sem resultado devolve `{}`.
- Cabeçalho com hífen (ex.: `Retry-After`) não é referência Velocity válida: `#set($context.responseOverride.header.Retry-After = ...)` dá `ParseErrorException` (verificado no 2.4.1) e derruba o template inteiro — oriente na mensagem.
- `$context.requestId` pode ser sobrescrito pelo cliente: use `extendedRequestId` (`VTL-004`).

## 8. O que o teste local NÃO prova

A versão do Velocity usada pela AWS não é documentada `[GAP]`; o tratamento exato de `null`,
números e espaços pode diferir. Antes de produção: `TestInvokeMethod` (REST) numa conta autorizada,
com os mesmos casos do `VtlTemplatesTest`.
