# Mock Connect — mocks de parceiros no modelo do Kafka Connect

> Fonte: `docs/MOCKS.md` e ADR-016 do repositório `trace2local`. Roda no Station (`TRACE2LOCAL_MOCKS=on`, padrão).

## Modelo

`SOURCE → TRANSFORMS (+ PREDICATES) → SINK`, configuração **plana** por binding, validada chave a chave.

```properties
name=antifraude-variacoes
target=antifraude.partner.local:8080       # host:porta da API real substituída
source=proxy                               # openapi · observed · inline · proxy (repasse + variações)
transforms=ausente
transforms.ausente.type=remove-field
transforms.ausente.pointer=/decision
transforms.ausente.predicate=pedido
predicates=pedido
predicates.pedido.type=header-matches
predicates.pedido.name=baggage
predicates.pedido.regex=.*t2l\.mock=ausente.*
sink=embedded                              # embedded · wiremock · file
```

Segredos por `${env:NOME}`; valores `PASSWORD` nunca são persistidos nem exibidos.

## Plugins embutidos (21)

| tipo | plugins |
|---|---|
| SOURCE | `openapi` (exemplos/schema do contrato) · `observed` (replay dos traces) · `inline` · `proxy` |
| TRANSFORM | `set-field` · `remove-field` · `rename-field` · `set-status` · `set-header` · `latency` · `fault` (connection-reset, empty-response, timeout) · `template` |
| PREDICATE | `path-matches` · `method-is` · `header-matches` · `body-matches` · `call-count` (1, 1-2, 3+, every:3) · `probability` |
| SINK | `embedded` (journal, near-misses, roteamento) · `wiremock` (publica num WireMock existente) · `file` (mappings para CI) |

Plugin próprio: implementar `StubSource` / `ResponseTransform` / `RequestPredicate` / `StubSink`, declarar as chaves
em `config()`, registrar em `META-INF/services/tech.squadai.trace2local.mocks.spi.MockPlugin`, JAR em
`TRACE2LOCAL_MOCKS_PLUGIN_PATH` (classloader isolado por JAR).

## Como a chamada chega ao mock

| caminho | quando |
|---|---|
| roteamento no cliente (`Trace2LocalHttp` + `TRACE2LOCAL_MOCKS_ROUTING=on`) | serviço Java instrumentado — desvia só os hosts com binding ativo |
| URL base do binding (`http://<station>:<porta>/<binding>`) | qualquer cliente/linguagem |
| `sink=wiremock` | o time já usa WireMock |
| `sink=file` / Exportar WireMock | regressão em CI |

Toda resposta leva `X-Trace2Local-Mock` → atributo `t2l.mock` → selo **SIM** (simulado) ou **↪** (repasse da API
real sem variação) na árvore, no inspetor e na narrativa.

## Variação sob demanda (não atrapalha o time)

`mode=on-demand` na aplicação da sugestão: a variação só vale quando a requisição ao **seu** serviço traz
`baggage: t2l.mock=<id>` — o baggage W3C atravessa os serviços instrumentados até o parceiro simulado.

```bash
curl -X POST "$API/pix/transfers" -H 'Content-Type: application/json' -H 'baggage: t2l.mock=decision-ausente' -d @t.json
```

## REST (`/trace2local/api/mocks`, espelha o Kafka Connect)

`GET /mocks` · `GET /mocks/plugins` · `PUT /mocks/validate` · `GET|PUT /mocks/bindings/{n}/config` ·
`DELETE /mocks/bindings/{n}` · `PUT …/pause|resume` · `POST …/restart` · `GET …/stubs|export` · `GET /mocks/journal` ·
`GET /mocks/suggestions` · `POST /mocks/suggestions/{id}/apply {variations, mode}`. Mutações com `X-Trace2Local: 1`.

## Checklist de uso responsável

1. Plugue a partir da **sugestão** (tem evidência e config gerada do contrato).
2. Prefira **sob demanda**; "Sempre" só em ambiente individual.
3. Confira o selo SIM/↪ no passo e o journal do binding.
4. Remova o binding ao terminar (confirmação em dois passos na UI; `control_mock_binding action=delete` no MCP).
5. Variação que achou bug vira teste: exporte o mapping (`sink=file`) ou escreva a jornada.
