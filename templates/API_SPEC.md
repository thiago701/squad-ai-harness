# Especificação de API — [Nome da API]

<!--
  ESPECIFICAÇÃO DE API
  Quando usar: ao projetar ou alterar qualquer API. A especificação vem ANTES do código
  (design-first). Este documento complementa (não substitui) o OpenAPI/Swagger gerado.
  Quem preenche: engenheiro responsável pelo backend + engenheiro-especificacao.
  Convenções da Squad: REST/JSON, erros RFC 7807, versionamento na URL, snake_case ou
  camelCase consistente (escolha UMA e registre aqui).
-->

| Campo | Valor |
|---|---|
| **Projeto** | [Nome do Projeto] |
| **Versão da API** | [v1] |
| **Versão do documento** | [0.1.0] |
| **Data** | [AAAA-MM-DD] |
| **Autor(es)** | [Nome / Agente] |
| **Status** | [Rascunho \| Em revisão \| Aprovado] |
| **Base URL** | [`https://api.exemplo.com.br/v1`] |
| **OpenAPI** | [link para openapi.yaml / Swagger UI] |

---

## 1. Visão Geral

<!-- O que a API expõe, para quem (interna/parceiros/pública) e principais recursos. -->

[Descreva em 2-3 frases o propósito da API e seus consumidores.]

## 2. Convenções

### 2.1 Versionamento

- **Estratégia:** [na URL — `/v1/...`. Breaking change ⇒ nova versão major]
- **Política de depreciação:** [versão antiga mantida por X meses; header `Deprecation` + `Sunset`]

### 2.2 Formato de Erros (RFC 7807 — Problem Details)

<!-- TODOS os erros seguem este formato. Nunca exponha stack trace. -->

```json
{
  "type": "https://api.exemplo.com.br/erros/recurso-nao-encontrado",
  "title": "Recurso não encontrado",
  "status": 404,
  "detail": "Pedido com id '123' não existe.",
  "instance": "/v1/pedidos/123",
  "traceId": "abc-123-def"
}
```

### 2.3 Paginação, Ordenação e Filtros

| Aspecto | Convenção | Exemplo |
|---|---|---|
| Paginação | [offset: `page` + `size` \| cursor: `cursor` + `limit`] | [`GET /pedidos?page=0&size=20`] |
| Resposta paginada | [envelope com `content`, `page`, `totalElements`] | — |
| Ordenação | [`sort=campo,asc\|desc`] | [`?sort=criadoEm,desc`] |
| Filtros | [query params por campo] | [`?status=ATIVO&clienteId=42`] |

### 2.4 Outras Convenções

- **Nomenclatura JSON:** [camelCase]
- **Datas:** [ISO 8601 UTC — `2026-06-12T14:30:00Z`]
- **Idempotência:** [POSTs críticos aceitam header `Idempotency-Key`]
- **Correlação:** [header `X-Correlation-Id` propagado em toda a cadeia]

## 3. Autenticação e Autorização

<!-- Descreva o fluxo. Detalhes de segurança em SECURITY_REVIEW.md. -->

- **Mecanismo:** [OAuth2 / JWT Bearer via Cognito]
- **Header:** `Authorization: Bearer <token>`
- **Escopos/Papéis:**

| Escopo/Papel | Permissões |
|---|---|
| [`pedidos:read`] | [leitura de pedidos] |
| [`pedidos:write`] | [criação/alteração de pedidos] |

## 4. Rate Limits

| Consumidor | Limite | Janela | Resposta ao exceder |
|---|---|---|---|
| [Autenticado padrão] | [100 req] | [1 min] | [`429` + header `Retry-After`] |
| [Parceiro premium] | [1000 req] | [1 min] | [`429` + `Retry-After`] |

## 5. Endpoints — Visão Geral

<!-- Tabela-índice de todos os endpoints. Detalhe cada um na seção 6. -->

| Método | Rota | Descrição | Auth | Escopo |
|---|---|---|---|---|
| GET | `/[recursos]` | [lista com paginação e filtros] | Sim | [`recursos:read`] |
| GET | `/[recursos]/{id}` | [busca por id] | Sim | [`recursos:read`] |
| POST | `/[recursos]` | [cria novo] | Sim | [`recursos:write`] |
| PUT | `/[recursos]/{id}` | [substitui] | Sim | [`recursos:write`] |
| PATCH | `/[recursos]/{id}` | [atualização parcial] | Sim | [`recursos:write`] |
| DELETE | `/[recursos]/{id}` | [remove (lógico/físico?)] | Sim | [`recursos:admin`] |

## 6. Detalhamento dos Endpoints

<!-- Replique o bloco abaixo para CADA endpoint relevante. -->

### POST /[recursos]

**Descrição:** [o que faz e regras de negócio aplicadas.]

**Request:**

```json
{
  "campo1": "string — [descrição, obrigatório]",
  "campo2": 123,
  "campo3": "2026-06-12T14:30:00Z"
}
```

**Validações:** [campo1: 3-100 chars; campo2: > 0; ...]

**Response `201 Created`:** (header `Location: /v1/[recursos]/{id}`)

```json
{
  "id": "uuid",
  "campo1": "string",
  "campo2": 123,
  "criadoEm": "2026-06-12T14:30:00Z"
}
```

**Códigos de resposta:**

| Código | Quando ocorre |
|---|---|
| 201 | Criado com sucesso |
| 400 | Payload inválido (detalhes em RFC 7807) |
| 401 | Token ausente/inválido |
| 403 | Sem escopo `[recursos]:write` |
| 409 | [Conflito de negócio — ex.: duplicidade] |
| 422 | [Regra de negócio violada — qual?] |
| 429 | Rate limit excedido |

### GET /[recursos]/{id}

**Descrição:** [...]

| Código | Quando ocorre |
|---|---|
| 200 | Encontrado |
| 404 | Não existe ou não pertence ao usuário |

<!-- Repita para os demais endpoints... -->

## 7. Exemplos curl

```bash
# Autenticar e criar recurso
curl -X POST "https://api.exemplo.com.br/v1/[recursos]" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"campo1": "valor", "campo2": 123}'

# Listar com paginação e filtro
curl "https://api.exemplo.com.br/v1/[recursos]?status=ATIVO&page=0&size=20&sort=criadoEm,desc" \
  -H "Authorization: Bearer $TOKEN"
```

## 8. Changelog da API

<!-- Mudanças no CONTRATO (não do documento). Breaking changes em destaque. -->

| Versão | Data | Mudança | Breaking? |
|---|---|---|---|
| v1.1 | [AAAA-MM-DD] | [novo campo opcional `campo3` em POST /recursos] | Não |
| v1.0 | [AAAA-MM-DD] | Lançamento inicial | — |

---

## Histórico de Revisões do Documento

| Versão | Data | Autor | Mudança |
|---|---|---|---|
| 0.1.0 | [AAAA-MM-DD] | [autor] | Criação inicial |
