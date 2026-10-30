# Trace2Local — sintoma → causa → correção

> Casos reais da validação na stack alvo (`examples/finance-pix`) e do caso `lambda-sqs`. Cada um virou correção
> + teste no repositório do Trace2Local — se reaparecer, é regressão: abra issue com o `executionId`.

| sintoma | causa provável | correção |
|---|---|---|
| nenhuma execução das Lambdas aparece | sampler `parentBased` + `X-Amzn-Trace-Id …Sampled=0` do API Gateway (LocalStack) | versão atual usa `alwaysOn`; confira se a função usa a lib ≥ 0.1.0 e `Trace2LocalLambdaHandler` |
| idem, com log `WARN Trace2Local: o envio ao Station não confirmou…` | endpoint/token errados ou Station fora da rede da função | `TRACE2LOCAL_STATION_ENDPOINT` com host da rede do compose (`http://trace2local-station:19877`), token igual ao do Station; `LAMBDA_DOCKER_NETWORK` |
| raiz marcada ÓRFÃ | chamador não instrumentado (API Gateway) | normal resolver sozinho (raiz de entrada); se persistir, o evento não trouxe o contexto — use `remoteParentOf` correto |
| consumidor SQS/SNS em árvore separada (PARTIAL) | publicação sem atributos de trace | `Trace2LocalMessaging.sqsAttributes()`/`snsAttributes()` nos `messageAttributes` + `fromSqsEvent`/`fromSnsEvent` |
| consumidor chega depois da quiescência | cold start / polling da fila | fundido automaticamente (continuação tardia, `late-continuation-ms`) — aguarde |
| execução `PARTIAL` com raízes órfãs após reiniciar o Station | mensagens reentregues cujo produtor não foi observado | comportamento honesto; dispare o fluxo de novo |
| UI 421 | Host fora da allowlist | acesse por `localhost`/`127.0.0.1` ou `TRACE2LOCAL_ALLOWED_HOSTS` |
| UI/API 401 | perfil corporate exige token | abra a URL com `?token=…` do log de boot; MCP: `TRACE2LOCAL_UI_TOKEN` |
| mutação 403 | falta `X-Trace2Local: 1` (anti-CSRF) | clientes e scripts enviam o cabeçalho em POST/PUT/DELETE |
| Δ SQL sem valores ("inferida do SQL") | `jdbc.mutation-capture=inferred` não lê antes/depois | esperado: operação, tabela e chave; confira o dado no banco |
| homologação "violada" que parece injusta | regra escrita como descrição ambígua no glossário | escreva estados como enum (`SETTLED`), use **deve/só/nunca**; regra de caminho de falha fica inconclusiva sem falha |
| conselheiro de mocks sugere hosts `localhost` | treino do native-image-agent exportou para o Station | limpe o acervo após o treino |
| passo de parceiro sem selo SIM com mock plugado | cliente não roteia | `Trace2LocalHttp` + `TRACE2LOCAL_MOCKS_ROUTING=on`, ou aponte a URL base para o endpoint do binding |
| variação sob demanda não aplica | baggage não chegou ao serviço | cabeçalho `baggage: t2l.mock=<id>` na chamada ao serviço; `baggageOf` sobrescrito no handler; id sem predicado próprio |
| Terraform trava criando DynamoDB no LocalStack | provider AWS 6.x (`WarmThroughput`) | `version = "~> 5.100"` |
| imagem Lambda Java 25 enorme | JRE do GraalVM com JVMCI | jlink a partir do Temurin 25 |
| MCP: "Trace2Local inacessível" | URL/porta | `TRACE2LOCAL_URL` (embedded `:9876`, Station `:19877`) e app/Station de pé |
| MCP: ferramenta "desligada" | mutações bloqueadas por padrão | proponha ao dev; só ele liga `TRACE2LOCAL_MCP_ALLOW_MUTATIONS=true` |
