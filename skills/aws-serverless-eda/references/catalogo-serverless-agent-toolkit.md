# Catálogo Serverless & Event-Driven (Agent Toolkit for AWS)

> **Procedência:** absorvido e reescrito em PT-BR a partir de `aws/agent-toolkit-for-aws` (`skills/core-skills/aws-serverless`, `aws-messaging-and-streaming` e as 12 skills de `skills/specialized-skills/serverless-skills/*`, commit `658b852f0612ca629d56d0a4de52738fb6a58714`, Apache-2.0).

---

## 1. Matriz de Decisão do Formato de Compute Serverless (`aws-serverless`)

Antes de gerar código ou IaC, classifique a carga de trabalho na modalidade exata do ecossistema Lambda e Serverless:

| Modalidade | Skill de Origem | Quando escolher | Quando recusar |
|---|---|---|---|
| **Lambda Event Function (Padrão)** | `aws-serverless` | Processamento orientado a eventos (SQS, SNS, S3, EventBridge, Streams), jobs curtos (< 15 min), tráfego elástico com escala a zero | Tráfego constante de alta concorrência por instância ou processos > 15 min |
| **Lambda Web Function (Adapter / Response Streaming)** | `aws-lambda-web-functions` | APIs HTTP/REST ou apps web completas (Spring Boot, FastAPI, Express) empacotadas como handler HTTP com suporte a response streaming e portabilidade para containers | Funções puras de evento assíncrono onde o modelo nativo de eventos é mais enxuto (P1) |
| **Lambda Durable Functions** | `aws-lambda-durable-functions` | Fluxos multi-etapas em código sequencial com persistência automática de estado, *replay* determinístico após suspensão, `wait`, callbacks e retries duráveis sem escrever ASL | Orquestrações puramente declarativas entre serviços AWS sem lógica de código entre passos (prefira Step Functions) |
| **Lambda Managed Instances (LMI)** | `aws-lambda-managed-instances` | Carga constante/previsível (> 30–40% de utilização contínua), necessidade de multi-concorrência real na mesma JVM/processo para eliminar cold start e reduzir custo por requisição em escala | Cargas esporádicas que precisam escalar a zero ou código que não é estritamente *thread-safe* |
| **Lambda MicroVMs** | `aws-lambda-microvms` | Sandboxes isoladas por Firecracker com retomada rápida via snapshot único por sessão (ex.: execução de código de agentes de IA, ambientes por tenant com estado em memória/disco efêmero) | APIs stateless comuns |
| **AWS Step Functions** | `aws-step-functions` | Coordenação visual/declarativa de múltiplos serviços AWS em ASL (JSONata), sagas, `.sync`, aprovação humana (`waitForTaskToken`) e Distributed Map sobre S3 | Transformação síncrona simples de 1 passo |
| **Híbrido Lambda + Fargate via Step Functions** | `processing-s3-uploads-with-step-functions` | Processamento de arquivos no S3 onde itens ≤ 6 MB rodam em Lambda e itens > 6 MB (ou > 15 min) são roteados via `Choice` para tarefa ECS Fargate | Todos os objetos cabem com folga no limite de tempo/memória da Lambda |

---

## 2. Lambda Durable Functions (`aws-lambda-durable-functions`)

Permite escrever fluxos duráveis de longa duração diretamente na linguagem de programação:

1. **Determinismo de Replay:** o código fora dos blocos de *step* durável é reexecutado a cada retomada; **nunca** chame relógio do sistema (`Instant.now()`), gerador aleatório (`UUID.randomUUID()`) ou I/O de rede fora de uma operação durável persistida.
2. **Idempotência de Steps:** cada step persistido grava seu resultado no log de execução durável; na retomada, o runtime devolve o valor gravado sem reexecutar o efeito colateral.
3. **Operações Concorrentes e Timeouts:** defina timeouts explícitos para cada espera externa (callback/aprovação) e trate falhas não-recuperáveis separadamente de erros transitórios.

---

## 3. Diagnóstico Sistemático de Timeouts em Lambda (`debugging-lambda-timeouts`)

Ao investigar `Task timed out after X.XX seconds`, siga a árvore determinística em 5 passos (nunca aumente apenas o timeout às cegas):

1. **Classificar o padrão no CloudWatch Logs (`REPORT RequestId`):**
   - `Duration ≈ Timeout` com `Init Duration` alto → gargalo no **Cold Start** (migrar para SnapStart / GraalVM AOT / inicializar clientes SDK fora do handler).
   - `Duration == Timeout` sem logs de erro intermediários → **blackhole de rede** (Lambda anexada a VPC sem rota para NAT Gateway ou VPC Endpoint ao chamar AWS SDK/API externa, ou Security Group bloqueando egress TCP 443).
   - `Max Memory Used ≈ Memory Size` → **estrangulamento de CPU/GC** (na Lambda, a vCPU é proporcional à memória configurada; pouca memória = fração mínima de CPU e thrashing de GC).
2. **Rastrear dependências downstream (X-Ray / Logs estruturados):**
   - Verifique se o cliente HTTP/SDK tem `connectTimeout` e `readTimeout` **menores** que o tempo restante da invocação (`context.getRemainingTimeInMillis()`). Sem timeout de socket, uma única chamada travada consome 100% do tempo da função.
3. **Loops de Retry do AWS SDK:**
   - O retry padrão do SDK somado ao timeout do endpoint pode ultrapassar o timeout da Lambda. Calibre `maxAttempts` e `apiCallAttemptTimeout`.
4. **Exaustão de Pool de Conexões (RDS/Aurora/HTTP):**
   - Em picos de concorrência, aguardar conexão no pool causa timeout em cascata; use RDS Proxy ou DSQL e dimensione o pool por ambiente de execução.

---

## 4. Integrações API Gateway ↔ Lambda ↔ DynamoDB

### 4.1. Conectando Lambda ao API Gateway e Criando Stages (`connecting-lambda-to-api-gateway`, `creating-api-gateway-stage`, `deploying-custom-domain-rest-api`)

- **Permissão de invocação por recurso:** conceda `lambda:InvokeFunction` ao principal `apigateway.amazonaws.com` **sempre com `--source-arn`** restrito à API/stage/método (nunca curinga aberto a qualquer conta).
- **Hardening obrigatório de Stage (`creating-api-gateway-stage`):**
  1. Access Logs estruturados em JSON enviados a Log Group criptografado com KMS.
  2. `TracingEnabled: true` (AWS X-Ray ativo).
  3. `ThrottlingBurstLimit` e `ThrottlingRateLimit` definidos na stage e por método crítico.
  4. Associação de Web ACL do **AWS WAF** na stage regional/edge.
- **Domínio Customizado (`deploying-custom-domain-rest-api`):**
  - Exija certificado ACM com política mínima **`TLS_1_2`**, mapeamento explícito de base path para a stage e registro Route 53 **Alias (`A`/`AAAA`)** apontando para o domínio regional/edge do API Gateway.

### 4.2. Conectando Lambda ao DynamoDB (`connecting-lambda-to-dynamodb`)

- **IAM de privilégio mínimo:** separe papéis de leitura (`GetItem`, `Query`) de escrita (`PutItem`, `UpdateItem`, `DeleteItem`), restringindo o `Resource` ao ARN da tabela e de seus índices (`table/<Nome>/index/*`).
- **Event Source Mapping (DynamoDB Streams → Lambda):**
  - Habilite sempre `BisectBatchOnFunctionError: true` (isola o registro corrompido dividindo o lote ao meio).
  - Configure `MaximumRetryAttempts` (ex.: 3 a 5) e `MaximumRecordAgeInSeconds` para não travar a shard indefinidamente.
  - Configure `DestinationConfig` (`OnFailure` apontando para fila SQS DLQ ou tópico SNS) para capturar o metadado do registro rejeitado sem perder eventos.
  - Use **Filter Criteria** no Event Source Mapping para filtrar `eventName: ["INSERT", "MODIFY"]` antes da invocação, economizando invocações e tokens/custo (P3).

---

## 5. EventBridge Event Bus e Mensageria (`amazon-eventbridge-event-bus`, `aws-messaging-and-streaming`)

- **Escolha do serviço de mensageria (`aws-messaging-and-streaming`):**
  - **SQS:** fila ponto a ponto, buffer de escrita, controle de concorrência por consumidor, DLQ nativa.
  - **SNS:** fan-out pub/sub de alto throughput para múltiplos assinantes conhecidos (filas SQS, Lambdas, HTTP).
  - **EventBridge Event Bus:** roteamento desacoplado baseado em conteúdo/regras, integração SaaS, Schema Registry, Archive & Replay.
  - **Kinesis Data Streams / MSK:** streams ordenados por chave de partição com múltiplos consumidores independentes e retenção para reprocessamento posicional.
- **Boas práticas no EventBridge Event Bus:**
  - Defina **custom event bus** por domínio (evite misturar eventos de negócio com eventos de infraestrutura do `default` bus).
  - Configure **DLQ + Retry Policy** em **cada Target** da regra (o EventBridge tenta entregar por até 24h por padrão; sem DLQ no target, falhas de permissão IAM ou indisponibilidade do destino descartam o evento silenciosamente).
  - Ative **Archive** com filtro de eventos críticos para permitir **Replay** controlado em recuperação de incidentes.
