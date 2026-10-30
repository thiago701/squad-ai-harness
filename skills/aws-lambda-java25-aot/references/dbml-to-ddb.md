# DBML → DynamoDB Single-Table Mapping

Como traduzir um schema DBML (formato SQL-relacional) para um modelo
single-table DynamoDB que escala. Esta é a etapa mais crítica do workflow —
um mapping ruim aqui condena toda a Lambda a queries lentas e custos altos.

## Índice

1. [Por que single-table](#por-que-single-table)
2. [Anatomia de um item DDB single-table](#anatomia-de-um-item-ddb-single-table)
3. [Algoritmo de mapping passo a passo](#algoritmo-de-mapping-passo-a-passo)
4. [Convenções de chaves](#convenções-de-chaves)
5. [Inferência de GSIs](#inferência-de-gsis)
6. [Exemplo completo: e-commerce](#exemplo-completo-e-commerce)
7. [Casos especiais](#casos-especiais)
8. [Quando refutar single-table](#quando-refutar-single-table)

## Por que single-table

DynamoDB cobra por leitura/escrita por item, não por bytes ou conexão. Em
cenários com relações (User → Orders → OrderItems), multi-table exige N
queries para montar a view completa — em Lambda, cada round-trip adiciona
~5-10ms. Single-table colapsa essas N queries em 1 query usando
`PK = USER#42` + `SK begins_with(ORDER#)`, retornando o user e todas as
orders num único call ~5-10ms.

Trade-off: o modelo fica mais cognitivamente custoso (PKs e SKs encodam
relações), e access patterns precisam ser planejados antes da modelagem.
Por isso a skill **sempre confirma os GSIs com o usuário antes de gerar
código**.

## Anatomia de um item DDB single-table

Cada linha da tabela tem este formato canônico:

| Atributo | Tipo | Função |
|---|---|---|
| `PK` | String | Partition key — agrupa itens relacionados na mesma partição |
| `SK` | String | Sort key — ordena itens dentro da partição, permite `begins_with` |
| `_type` | String | Discriminador — diz à camada Java qual classe deserializar |
| `GSI1PK` / `GSI1SK` | String? | Chaves do GSI1 — invertem ou recortam o acesso |
| `GSI2PK` / `GSI2SK` | String? | Idem GSI2 |
| `<atributos da entidade>` | varia | Os campos próprios (name, email, total, etc.) |

`PK`/`SK` são **strings sintéticas** com prefixo do tipo: `USER#42`,
`ORDER#abc-123`, `ITEM#sku-456`. Isso evita colisão entre tipos diferentes
no mesmo PK e permite queries `begins_with(SK, "ORDER#")`.

## Algoritmo de mapping passo a passo

Aplique nesta ordem:

### Passo 1 — Identifique entidades raiz

Entidades **raiz** são as que aparecem no topo de relacionamentos (User,
Product, Order). Entidades **dependentes** existem apenas no contexto de
outra (OrderItem só faz sentido com Order, Address só com User).

Heurística: se a tabela DBML tem FK obrigatória para outra tabela e não tem
relacionamentos próprios, é dependente. Caso contrário, raiz.

### Passo 2 — Defina PK/SK das raízes

Para cada entidade raiz `E` com primary key `id`:

```
PK = "E#" + id
SK = "E#" + id        (mesmo valor — item é "self-pointing")
_type = "E"
```

Exemplo:

```
User { id: "42", email: "x@y.com" }
→
PK="USER#42", SK="USER#42", _type="USER", email="x@y.com"
```

### Passo 3 — Defina PK/SK das dependentes

Para cada entidade dependente `D` com FK para entidade pai `P`:

```
PK = "P#" + parentId       (mesma partition do pai → 1 query traz tudo)
SK = "D#" + sortAttr       (sortAttr = timestamp, sequência, ou id da própria D)
_type = "D"
```

Exemplo: Order pertence a User, ordenada por data:

```
Order { id: "abc", user_id: "42", created_at: "2026-04-28T10:00:00Z", total: 100 }
→
PK="USER#42", SK="ORDER#2026-04-28T10:00:00Z#abc", _type="ORDER", total=100
```

`begins_with(SK, "ORDER#")` em `PK=USER#42` retorna todas as orders do user
em ordem cronológica. Sub-prefixar o id no SK garante unicidade quando
duas orders chegam no mesmo timestamp.

### Passo 4 — Identifique access patterns

Antes de inferir GSIs, liste os **access patterns**:

- "Buscar user por id" → query base: `PK=USER#<id>, SK=USER#<id>`
- "Listar orders de um user" → query base: `PK=USER#<id>, SK begins_with ORDER#`
- "Listar items de uma order" → ⚠ não cobre na tabela base se Order é dependente
  de User; precisa GSI ou compor o item Order com itens embedded.
- "Buscar order por id (sem saber o user)" → ⚠ não cobre; precisa GSI.

Para cada access pattern não coberto pela PK/SK base, defina um GSI.

### Passo 5 — Defina GSIs

Aplique a regra: **um GSI por access pattern não coberto**, até o limite de
20 GSIs (mas pratique frugalidade — 3-5 GSIs cobrem 95% dos casos).

Convenção de nomes: `GSI1`, `GSI2`, ..., `GSIn`. Cada GSI tem `GSInPK` e
`GSInSK`. Exemplos:

| Access pattern | GSI |
|---|---|
| "Buscar order por id global" | `GSI1PK="ORDER#"+orderId, GSI1SK="ORDER#"+orderId` |
| "Listar todas orders por status, ordenadas por data" | `GSI2PK="STATUS#"+status, GSI2SK=createdAt` |
| "Listar users por email (índice único)" | `GSI3PK="EMAIL#"+email, GSI3SK="USER#"+id` |

### Passo 6 — Type discriminator

Sempre adicione `_type` no item. Quando a Lambda lê `Map<String,
AttributeValue>` de DynamoDB, usa `_type` para decidir qual record Java
instanciar. Sem `_type`, código fica condicional em campos presentes (frágil).

## Convenções de chaves

- **Prefixo em CAIXA ALTA** — `USER#`, `ORDER#`, não `user#`. Convenção que
  diferencia partição lógica de id natural.
- **Separador `#`** — não `:`, não `_`. Padrão da AWS, fácil de grepar em logs.
- **IDs no SK preservam ordem** — use ULID ou timestamp ISO-8601 para SKs
  ordenáveis cronologicamente. UUID v4 não ordena.
- **Strings, sempre** — DynamoDB suporta Number como key, mas String
  composição é trivial e sortable lexicograficamente.

## Inferência de GSIs

Quando o usuário não declara access patterns explícitos, a skill propõe GSIs
baseado nas FKs reversas e índices declarados no DBML.

Heurísticas:

1. **FK reversa** — se `Order` tem `user_id` → propõe `GSI1` para "listar
   orders por user" (já coberto pela PK/SK base se Order é dependente,
   mas confirme).
2. **Índices declarados** — `Indexes { email [unique] }` no DBML →
   `GSI<n>PK=EMAIL#<email>, SK=USER#<id>`.
3. **Status fields** — colunas como `status`, `state`, `phase` → propõe
   GSI para "listar por status".

**Regra de ouro**: nunca infira mais GSIs do que access patterns confirmados.
Cada GSI duplica o custo de write. Pergunte ao usuário, não chute.

## Exemplo completo: e-commerce

DBML de entrada:

```dbml
Table users {
  id varchar [pk]
  email varchar [unique]
  name varchar
  created_at timestamp
}

Table orders {
  id varchar [pk]
  user_id varchar [ref: > users.id]
  status varchar
  total decimal
  created_at timestamp
}

Table order_items {
  id varchar [pk]
  order_id varchar [ref: > orders.id]
  sku varchar
  quantity int
  price decimal
}
```

Access patterns (perguntados ao usuário e confirmados):

1. Buscar user por id
2. Buscar user por email
3. Listar orders de um user (paginado, mais recente primeiro)
4. Buscar order por id global
5. Listar items de uma order
6. Listar orders por status (admin dashboard)

Mapping resultante:

| Entidade | PK | SK | GSI1PK | GSI1SK | GSI2PK | GSI2SK |
|---|---|---|---|---|---|---|
| User | `USER#<id>` | `USER#<id>` | `EMAIL#<email>` | `USER#<id>` | — | — |
| Order | `USER#<userId>` | `ORDER#<createdAt>#<id>` | `ORDER#<id>` | `ORDER#<id>` | `STATUS#<status>` | `ORDER#<createdAt>` |
| OrderItem | `ORDER#<orderId>` | `ITEM#<id>` | — | — | — | — |

Verificação:

| Access pattern | Query |
|---|---|
| 1. User por id | `Get(PK=USER#42, SK=USER#42)` |
| 2. User por email | `Query(GSI1, PK=EMAIL#x@y.com)` |
| 3. Orders de user | `Query(PK=USER#42, SK begins_with ORDER#)` ordem desc |
| 4. Order por id | `Query(GSI1, PK=ORDER#abc)` |
| 5. Items de order | `Query(PK=ORDER#abc, SK begins_with ITEM#)` |
| 6. Orders por status | `Query(GSI2, PK=STATUS#PENDING)` |

Tabela única, 2 GSIs, 6 access patterns cobertos. Custos: ~3x write por item
(item base + 2 GSIs), mas read fica trivial e barato.

## Casos especiais

### Many-to-many (N:N)

Tabela de junção no DBML (ex: `user_roles { user_id, role_id }`):

- Crie 2 itens espelhados:
  - `PK=USER#<userId>, SK=ROLE#<roleId>`
  - `PK=ROLE#<roleId>, SK=USER#<userId>`
- Permite tanto "roles de um user" quanto "users de um role" sem GSI extra.

### Hierarquias profundas (3+ níveis)

User → Project → Task → Comment:

- Comment vira dependente de Task: `PK=TASK#<taskId>, SK=COMMENT#<created>`
- Task continua dependente de Project: `PK=PROJECT#<projectId>, SK=TASK#<id>`
- Project continua dependente de User: `PK=USER#<userId>, SK=PROJECT#<id>`
- Para "listar todos comments de um user" (cross-hierarchy), precisa GSI:
  `GSI1PK=USER#<userId>, GSI1SK=COMMENT#<created>` — denormaliza userId
  em cada Comment.

### TTL (expiração automática)

DynamoDB suporta atributo `ttl` (epoch seconds). Use para:

- Sessions (login JWT)
- Caches temporários
- Eventos de evento sourcing antigos

Declare no `template.yaml`: `TimeToLiveSpecification: { AttributeName: ttl,
Enabled: true }`. Adicione `ttl` no record Java para entidades efêmeras.

## Quando refutar single-table

Single-table não é dogma. Refute e proponha multi-table quando:

- **Governança / multi-account** — entidades de domínios diferentes que não
  compartilham access patterns. Ex: `users` (auth) e `products` (catálogo)
  com times distintos.
- **Volume desproporcional** — uma entidade com 100x o volume das outras
  pode justificar tabela própria por isolamento de hot partitions.
- **Auditoria com requisitos legais** — eventos imutáveis (append-only)
  com retention policy específica costumam viver em tabela dedicada.
- **Schema instável** — se a entidade ainda está "se descobrindo" e muda
  forma toda semana, single-table amplifica o custo de mudança.

Em todos esses casos, peça justificativa ao usuário e documente no
`README.md` por que multi-table foi escolhido.
