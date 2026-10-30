# Trace2Local — instalação e configuração (modo embedded)

> Fonte: repositório `trace2local` (`README.md` "Começar", `docs/SPEC.md` §5.4, `docs/SEGURANCA-CORPORATIVA.md`,
> `trace2local-spring-boot-starter`, `trace2local-maven-plugin`). Versão de referência: `0.1.0-SNAPSHOT`
> (conferida no código em 01/10/2026).

## Requisitos

| eixo | suportado |
|---|---|
| JDK | 21+ (CI em 21 e 25; bytecode baseline 21) |
| Build | Maven 3.9+ (o wrapper `./mvnw` vem no repo da lib) ou Gradle |
| Spring Boot | 4.0 / 4.1 (Boot 3 está fora da matriz — ADR-009 da lib) |
| OpenTelemetry | SDK 1.66 / instrumentation 2.31 |
| AWS SDK | v2 (DynamoDB, SNS, SQS); Lambda `java21` / `java25` (custom runtime `provided.al2023`) |
| GraalVM | Native Image (JDK 25) — sem `-javaagent` |
| LocalStack | 3 / 4 (validado em 4.9) · Terraform AWS provider `~> 5.100` |

## 1. Lib no repositório Maven local

Sem release no Maven Central, publique uma vez por versão (e de novo a cada atualização da lib):

```bash
git clone https://github.com/thiago701/trace2local.git && cd trace2local
./mvnw -B install -DskipTests              # Windows: .\mvnw.cmd -B install -DskipTests
```

`AWS_REGION=us-east-1` só é necessário para rodar a suíte da lib (`mvn -B install` com testes).

## 2. Plugin Maven: analisar → configurar

```bash
P=tech.neural7.trace2local:trace2local-maven-plugin:0.1.0-SNAPSHOT
./mvnw -q compile $P:analyze
./mvnw $P:configure -Dtrace2local.version=0.1.0-SNAPSHOT
```

O prefixo curto (`mvn trace2local:analyze`) só resolve com `<pluginGroup>tech.neural7.trace2local</pluginGroup>`
no `~/.m2/settings.xml`; na dúvida, use a coordenada completa.

**`analyze`** — somente leitura, escaneia o **bytecode** (ASM) de `target/classes`: rode depois de `compile`, senão
o mapa sai vazio. Gera em `target/trace2local/`:
- `canvas-map.md` — o que vira nó: endpoints Spring MVC (catálogo + disparo), métodos `@Trace2Local` (BUSINESS),
  clientes AWS SDK v2 e JDBC. JAX-RS e outros frameworks entram só como sugestão manual.
- `report.md` — higiene de logs (SLF4J × `System.out` × `printStackTrace`) com sugestões concretas.

**`configure`** — idempotente, nunca sobrescreve arquivo existente:

| ação | resultado |
|---|---|
| `pom.xml` | `trace2local-bom` (import) + `trace2local-spring-boot-starter`; backup `pom.xml.trace2local.bak` na 1ª alteração; o arquivo é regravado pelo modelo Maven (a formatação pode mudar) |
| `src/main/resources/trace2local-business.md` | glossário de negócio (Narrativa e homologação) |
| `src/main/resources/application-trace2local.yml` | porta, redaction, retenção, Δ do DynamoDB — carregado pelo perfil `trace2local` |
| `src/main/resources/logback-spring.xml` | `trace_id`/`span_id` (OTel) + `dd.trace_id`/`dd.span_id` (Datadog) no padrão do log |

**Versão gravada:** passe sempre `-Dtrace2local.version=<versão da lib>` e confira o pom. Até 01/10/2026 o padrão
era `${project.version}` — a versão do **app** —, e o `configure` adicionava um BOM inexistente (corrigido para
`${plugin.version}`, teste `ConfigureMojoDescriptorTest`).

## 3. Dependência manual

Maven: `trace2local-bom` (`<scope>import</scope>`, `0.1.0-SNAPSHOT`) em `dependencyManagement` +
`trace2local-spring-boot-starter` sem versão. Gradle (Kotlin DSL):

```kotlin
repositories { mavenLocal(); mavenCentral() }
dependencies {
    implementation(platform("tech.neural7.trace2local:trace2local-bom:0.1.0-SNAPSHOT"))
    implementation("tech.neural7.trace2local:trace2local-spring-boot-starter")
}
```

Módulos extras conforme a integração: `trace2local-aws` (DynamoDB/SQS/SNS), `trace2local-jdbc` (SQL),
`trace2local-testing` (`<scope>test</scope>`).

## 4. Ligar: perfis e guarda de produção

O starter decide pelo perfil ativo (`ProductionGuard`):

| situação | resultado |
|---|---|
| perfil `trace2local`, `dev`, `development`, `local` ou `localstack` | liga; `trace2local` também carrega `application-trace2local.yml` |
| outro perfil, nada forçado | desliga sozinho — a dependência pode seguir no artefato |
| outro perfil com `trace2local.enabled=true` | **boot falha** ("NÃO DEVE subir em produção"), salvo `trace2local.i-know-what-im-doing=true` |
| `trace2local.enabled=false` | desliga tudo sem remover a dependência |

Prova de vida no boot: `INFO Trace2Local em http://127.0.0.1:9876/trace2local — modo Embedded | redaction=STRICT | capture-before=true`.
Com `trace2local.station.endpoint` definido (ou dentro de uma Lambda) o app entra em **Companion**: sem UI própria,
exporta OTLP ao Station e loga `modo Companion detectado …`.

**Código seguro para produção:** o bean `Trace2LocalConfig` só existe com a ferramenta ligada. Injete por
`ObjectProvider` e instrumente com `ifAvailable`:

```java
@Bean DynamoDbClient dynamoDb(ObjectProvider<Trace2LocalConfig> t2l) {
    DynamoDbClientBuilder b = DynamoDbClient.builder();
    t2l.ifAvailable(cfg -> Trace2LocalAws.instrument(b, cfg));
    return b.build();
}
```

App que já usa o OpenTelemetry Spring autoconfigure: o starter não cria outro `OpenTelemetry` e se pendura pelo
SPI `SdkTracerProviderConfigurer` (`Trace2LocalOtelConfigurer`). Lib instalada antes de 01/10/2026 apontava para
uma classe inexistente (`ServiceConfigurationError`) — reinstale. Nomes de bean são `trace2Local*`.

## 5. Instrumentação

```java
@Trace2Local("CriarPedido")                                                      // nó BUSINESS
public Pedido criar(NovoPedido r) { ... }

Trace2LocalAws.instrument(DynamoDbClient.builder(), cfg);                        // Δ EXATO do DynamoDB
Trace2LocalAws.instrument(SqsClient.builder());  Trace2LocalAws.instrument(SnsClient.builder());
Trace2LocalMessaging.sqsAttributes() / snsAttributes()                           // nos messageAttributes ao publicar
Trace2LocalJdbc.wrap(dataSource, cfg);                                           // SQL + Δ inferido (opcional)
Trace2LocalHttp.instrument(HttpClient.newHttpClient(), "Antifraude");            // nó HTTP_CLIENT com nome
```

UI: `http://localhost:9876/trace2local`. Visões (teclas): 1 Anatomia · 2 Árvore · 3 Linha do tempo ·
4 Investigação · 5 Narrativa · 6 Painel · 7 Comparar · 8 Infra · 9 Mocks (só no Station). Ctrl+K busca tudo.
A seção **API DO PROJETO** mostra o app pelo `spring.application.name` e dispara os endpoints.

## 6. Propriedades `trace2local.*`

| propriedade | padrão | nota |
|---|---|---|
| `enabled` | `true` | só vale em perfil de dev (§4) |
| `port` / `bind-address` / `base-path` | `9876` / `127.0.0.1` / `/trace2local` | `port: 0` = porta livre (testes) |
| `allow-non-loopback` | `false` | sair do loopback exige isto + perfil corporate |
| `buffer.capacity` | `4096` | descarte na borda é exibido na UI |
| `retention.max-executions` | `100` | LRU em memória |
| `payload.max-bytes` | `8192` | por nó |
| `redaction.mode` | `strict` | `strict` · `keys` · `off` |
| `aws.dynamodb.capture-before` | `true` | Δ exato; **eleva `ReturnValues`** da requisição (e restaura a resposta) |
| `jdbc.mutation-capture` | `off` | `inferred`: operação, tabela e chave (sem valores) |
| `quiescence-ms` / `late-continuation-ms` | `3000` / `600000` | fim da execução; consumidor tardio fundido na árvore do produtor |
| `flush-timeout-ms` | `200` | orçamento do flush no modo Companion |
| `station.endpoint` / `station.token` | — | liga o modo Companion (env `TRACE2LOCAL_STATION_ENDPOINT`/`_TOKEN`) |
| `infra.scan-dirs` | — | aba Infra: Terraform, compose, `.env`, `application*.yml` (segredos `[OCULTO]`) |
| `i-know-what-im-doing` | `false` | só para forçar fora de dev (§4) |

## 7. Glossário de negócio (homologação)

`trace2local-business.md`, formato `- termo: descrição`. Frases com **deve**, **só**, **nunca** ou **regra** viram
regras homologáveis: a Investigação cruza cada uma com os passos e dá veredito (respeitada, violada,
inconclusiva, não exercitada). Escreva estados como enum (`SETTLED`, `IN_REVIEW`) — siglas (API, SQS) não são
lidas como estado; regra sobre caminho de falha fica *inconclusiva* quando nada falhou (exercite com Mock Connect).

## 8. Inteligência: local por padrão

- Laudo, regras preditivas e micro-decisões rodam **determinísticos e locais** sem configuração.
- **Jev** liga sozinho quando há chave no ambiente (`JEV_API_KEY` ou `TRACE2LOCAL_JEV_API_KEY`, modo `AUTO`):
  metadados estruturais **redigidos** saem para o endpoint, com `WARN Inteligência Jev ATIVA …` no boot. Numa
  máquina com essa chave para outro uso, desligue com `TRACE2LOCAL_JEV_ENABLED=false`.
- Explicação por LLM é opcional, só por POST, e endpoint fora do loopback exige `TRACE2LOCAL_LLM_ALLOW_EXTERNAL=true`.

## 9. Segurança da UI (ADR-015 do Trace2Local)

- Loopback por padrão; mutações exigem cabeçalho `X-Trace2Local: 1` (anti-CSRF); allowlist de `Host`
  (`TRACE2LOCAL_ALLOWED_HOSTS`) contra DNS rebinding.
- Ambiente compartilhado: `TRACE2LOCAL_SECURITY_PROFILE=corporate` (token de UI gerado; abra a URL com `?token=`).
- Redaction na origem (chaves sensíveis, JWT, chaves AWS, cartão, CPF/CNPJ…) é mitigação, não garantia: campo de
  negócio com nome inocente pode passar. Nunca desligue `redaction.mode` em máquina com dado real.
