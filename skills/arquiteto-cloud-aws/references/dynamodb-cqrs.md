# DynamoDB para CQRS — escrita condicional, versão, TTL, Streams e paginação

> Parte da skill `arquiteto-cloud-aws`. Hub: `../SKILL.md`. Fatos: `fatos-verificados-aws.md` §5.
> Modelagem geral (DBML, SQL × NoSQL): skill `especialista-banco`. Implementação de referência:
> `labs/aws-referencia-ordens` (ASL `Marcar*`, `AdaptadoresAws.DynamoLeitura`).

## 1. Dois modelos, duas tabelas

| | Escrita (comando) | Leitura (consulta) |
|---|---|---|
| Chave | `pk = T:<tenant>:O:<ordem>`, `sk = ESTADO` | `pk = T:<tenant>:U:<dono>`, `sk = O:<ordem>` |
| Quem escreve | só o workflow/serviço de comando | só a projeção |
| Garantia | escrita condicional com versão | "vence a maior versão" |
| Atende | regra de negócio | GET por id e lista paginada do dono |

Separador `:` (não `#`): a chave aparece em templates VTL, onde `#` é diretiva e `##` é comentário.

## 2. Transição idempotente (retry sem efeito duplo)

```text
UpdateExpression:    SET #s = :novo, versao = :vNova, ultimaTransicao = :tid, atualizadoEm = :agora
ConditionExpression: versao = :vAtual OR (versao = :vNova AND ultimaTransicao = :tid)
```

`:tid` e `:agora` são constantes entre tentativas do mesmo passo (no Step Functions:
`$$.Execution.Name#$$.State.Name` e `$$.State.EnteredTime`). Retry após sucesso perdido reescreve
os mesmos valores — sem incremento duplo. `ReturnValues: UPDATED_NEW` devolve a versão para o passo seguinte.

## 3. Projeção tolerante a duplicidade e desordem

```text
PutItem ... ConditionExpression: attribute_not_exists(pk) OR versao < :v
            ReturnValuesOnConditionCheckFailure: ALL_OLD   (não consome RCU)
CCF com versao atual == :v  → já aplicado (renotificar é seguro)
CCF com versao atual >  :v  → obsoleto (ignorar)
```

Evento precisa carregar o **estado** (não só o delta) para que aplicar a maior versão baste.

## 4. TTL não é remoção imediata

Exclusão "tipicamente em alguns dias"; itens vencidos **continuam aparecendo** em leituras e consultas
→ filtre pelo atributo de expiração na aplicação. TTL é limpeza, não regra de negócio.

## 5. Streams e CDC

Retenção de 24 h; ordem por item; cada modificação aparece uma vez no stream — mas o consumidor
(Lambda/Pipes) entrega **pelo menos uma vez**. `StreamViewType: NEW_IMAGE` basta para eventos com
estado. Via Pipes: filtro `eventName ∈ {INSERT, MODIFY}`, `TRIM_HORIZON`, retry com idade < 24 h,
`AUTOMATIC_BISECT`, DLQ — e só campos de charset restrito no input template (ele não escapa).

## 6. Paginação e isolamento

- `Limit` = itens **avaliados**; até 1 MB por chamada; `LastEvaluatedKey` presente não garante mais itens.
- Cursor opaco com só a chave de ordenação; partição sempre derivada da identidade.
- `dynamodb:LeadingKeys` (com `ForAllValues`) isola por usuário **apenas** quando a credencial é do
  usuário (identity pool / credenciais do chamador) — não numa integração direta com role do API Gateway.

## 7. Limites que mudam o desenho

Item ≤ 400 KB (estado grande → S3 + ponteiro); transação ≤ 100 itens/4 MB, `ClientRequestToken`
idempotente por 10 min; escrita condicional falha com `ConditionalCheckFailedException` (HTTP 400).
