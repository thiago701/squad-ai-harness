# Domain-spec → value objects (parametrização do domínio)

O caminho vanilla (`generate_vanilla_lambda.py`) copia o blueprint verbatim e
deixa **um débito manual**: trocar os campos de exemplo (title, priority, status,
dueDate) pelos **value objects validados do seu domínio real**. No caso
`calendario-lambda` isso foi escrever à mão `Pais`, `Escopo`, `EventoId`,
`DataEvento`, `Horario`, `Descricao` + suas exceções — **~7 min**.

`scripts/value_objects.py` fecha esse débito: uma **domain-spec** declarativa
(JSON) → records de value object com validação no compact constructor + fábricas
+ a exceção base, cortando a adaptação para **~2-3 min** (escrever a spec) e
tornando o resultado **determinístico e regenerável** (não “na mão, uma vez”).

```bash
# depois do generate_vanilla_lambda.py:
python scripts/value_objects.py examples/calendario-domain.json \
    -o ./calendario-lambda/src/main/java --aggregate
```

## Formato da spec

```json
{
  "package": "com.squadai.calendario.domain",   // base; VOs → .model, exceções → .exception
  "value_objects": [ { "name": "...", "kind": "...", /* opções do arquétipo */ } ],
  "aggregate": { /* opcional, ver abaixo */ }
}
```

- `package` é a **base do domínio**. Os VOs vão para `<package>.model`, as exceções
  para `<package>.exception` — exatamente o layout do blueprint.
- `InvalidValueObject` (uma única exceção, `code` + `message`) é sempre emitida;
  cada VO lança `new InvalidValueObject("invalid-<nome>", "...")`. Isso casa com o
  `ApiErrors.mapError` do blueprint (`DomainException → 422` via `code()`).
- `DomainException` (base) só é emitida se **ainda não existir** no destino (não
  clobra a do blueprint). Force com `--emit-base`.

## Catálogo de arquétipos (`kind`)

| `kind` | Emite | Opções | Exemplo de uso |
|---|---|---|---|
| `string_pattern` | `record(String value)` + regex + `of()` | `pattern` (obrigatório), `normalize` (`upper`/`lower`/`none`), `message` | código ISO, CEP, placa |
| `bounded_string` | `record(String value)` 1..N ou opcional | `min_length` (0 = opcional → `asOptional()`), `max_length` | título, descrição |
| `enum` | `enum` + `parse()` case-insensitive | `values` (lista) | status, escopo, categoria |
| `identifier` | `record(String value)` charset `[A-Za-z0-9_-]` + `of()` + `generate()` (UUID) | `max_length` (default 128) | id de agregado |
| `local_date` | `record(LocalDate value)` `Comparable` + `parse()` + `asKey()` | — | data (dia/mês/ano) → SK/GSI-SK |
| `local_time` | `record(LocalTime value)` + `parse()` + `asText()` | — | horário isolado |
| `time_range` | `record(LocalTime inicio, LocalTime fim)` invariante `fim > início` | `start`/`end` (nomes dos componentes) | janela de horário |
| `integer_range` | `record(int value)` min..max | `min`, `max` | estoque, idade |
| `decimal` | `record(BigDecimal value)` + `parse()` | `positive` (default true) | preço, valor |
| `instant` | `record(Instant value)` + `parse()` + `asKey()` | — | timestamp de evento |

Cada arquétipo já nasce **compatível com o gate Checkstyle estrutural** do
blueprint (método ≤35 linhas, ≤5 params, arquivo ≤300 linhas) e com o
`DomainException.code()` → RFC 9457.

## Agregado opcional (`--aggregate`)

O bloco `aggregate` compõe os VOs num agregado rico (imutável, `criar` /
`rehydrate` / `copyWith` / mutadores + getters), no estilo do blueprint:

```json
"aggregate": {
  "name": "PagamentoCalendario",
  "identity": ["EventoId id", "Pais pais", "Escopo escopo"],   // imutáveis (compõem a chave)
  "sort":     "DataEvento data",                                // imutável (SK)
  "mutable":  ["Horario horario", "Descricao descricao"],       // mutáveis → geram alterar<Campo>(...)
  "timestamps": true,                                           // Timestamps createdAt/updatedAt
  "version": true                                               // Long version (optimistic locking)
}
```

`identity` + `sort` são imutáveis (mudá-los = outro item); cada campo `mutable`
gera um `alterar<Campo>(<Tipo> novo, Instant now)` que passa por `copyWith` e
avança `updatedAt`. Se `Timestamps` não existir no destino, é emitido. Cada entrada
de `identity`/`sort`/`mutable` é `"Tipo nome"` (2 tokens; para um tipo composto,
declare um VO e referencie-o pelo nome).

> **Gate:** `criar()`/`rehydrate()` são fábricas de campo-completo — com o gate
> Checkstyle estrutural ativo, suprima **`ParameterNumber` E `MethodLength`** para
> `<Agregado>.java` (`checks="ParameterNumber|MethodLength"`), como o template
> `assets/templates/checkstyle-suppressions.xml.tmpl` já faz. Em domínios grandes,
> `rehydrate()` passa de 35 linhas (1 param por linha) — o gerador avisa disso.

> O agregado é um **esqueleto correto por construção**, não um substituto do
> raciocínio de domínio: revise invariantes cross-field e regras de negócio que
> não cabem num VO isolado.

## Persistência: Item + ItemMapper single-table (`single_table_mapper.py`)

O **segundo** pedaço manual: o `@DynamoDbBean` (Item) e o mapper de chaves +
`toItem`/`toDomain`. Com os blocos `aggregate` + `single_table` na spec,
`scripts/single_table_mapper.py` os emite — reusa os arquétipos dos VOs para saber
como cada campo serializa para coluna(s):

```bash
python scripts/single_table_mapper.py examples/calendario-domain.json \
  -o ./calendario-lambda/src/main/java
```

Bloco `single_table`:

```json
"single_table": {
  "table_name": "calendario_pagamentos",
  "type_discriminator": "PAGAMENTO",
  "pk": "{pais}#{escopo}#{id}",                 // {campo} resolvido pelo key-expr do VO
  "sk": {"field": "data", "attribute": "DATA"},
  "gsi": {"name": "GSI1", "pk_attribute": "GSI1PK", "pk": "{pais}#{escopo}"},
  "columns": {                                   // campo → coluna(s); VO de 2 colunas vira objeto
    "id": "ID", "pais": "PAIS", "escopo": "ESCOPO",
    "horario": {"inicio": "HoraInicio", "fim": "HoraFim"},
    "descricao": "Descricao"
  }
}
```

Gera `<Agregado>Item.java` (bean flat com `@DynamoDbPartitionKey`/`@DynamoDbSortKey`/
`@DynamoDbSecondary*`/`@DynamoDbVersionAttribute`, a SK base reaproveitada como SK do
GSI) e `<Agregado>ItemMapper.java` (`partitionKey`/`indexPartitionKey` a partir dos
templates `{campo}` + `toItem`/`toDomain`). O **repositório** (queries/access patterns)
**não é gerado** — é o que a skill confirma com o usuário. Um bean muito largo pode
passar de 300 linhas (gate FileLength); o gerador avisa.

Serialização por arquétipo (coluna ↔ VO): `value()`/`name()`/`asKey()`/`asText()` na
escrita, `of()`/`parse()` na leitura; `time_range` ocupa **2 colunas** (início/fim).

## Um comando: rename + VOs + Item/Mapper

`generate_vanilla_lambda.py --domain-spec <spec>` faz o rename do blueprint **e** roda
os dois geradores numa tacada:

```bash
python scripts/generate_vanilla_lambda.py \
  --blueprint <repo>/app --entity PagamentoCalendario \
  --package com.squadai.calendario --table calendario_pagamentos \
  --app-dir ./calendario-lambda \
  --domain-spec examples/calendario-domain.json
```

Depois: apague os VOs/DTOs de exemplo do blueprint que sobraram, ligue o
repository/handler aos novos tipos, e `./mvnw verify`.

## Onde isso entra no workflow

Entre a **Etapa 4** (geração do projeto) e a **Etapa 5** (validação): depois do
`generate_vanilla_lambda.py` (ou já com `--domain-spec`), os VOs + Item/Mapper do
domínio real substituem os campos de exemplo do blueprint; ajuste o repository/DTOs e
rode `./mvnw verify`.

## Indicador

- **Antes:** ~7 min escrevendo N value objects + exceções à mão (calendário: 6 VOs
  + exceções ≈ 13 arquivos).
- **Depois:** ~2-3 min escrevendo a spec (~30 linhas JSON) + 1 comando → todos
  emitidos, determinísticos, regeneráveis.
- **Ganho lateral (não só velocidade):** consistência e correção — o mesmo
  arquétipo produz sempre a mesma validação; erro de VO deixa de ser retrabalho.

Testes do gerador: `scripts/test_value_objects.py` (stdlib `unittest`, zero-dep),
incluindo um **dogfood** que regenera o domínio do `calendario-lambda`.
