# AWS SAM template.yaml — Lambda Native + DynamoDB + API Gateway + Streams

Template canônico que a skill gera. Cobre Custom Runtime al2023, ARM64,
DynamoDB single-table, API Gateway HTTP API e DynamoDB Streams trigger.

## Índice

1. [Estrutura completa do template](#estrutura-completa-do-template)
2. [Globals — defaults para todas as funções](#globals--defaults-para-todas-as-funções)
3. [Função API Gateway HTTP](#função-api-gateway-http)
4. [Função DynamoDB Streams](#função-dynamodb-streams)
5. [DynamoDB single-table + Streams](#dynamodb-single-table--streams)
6. [Permissões IAM mínimas](#permissões-iam-mínimas)
7. [Outputs](#outputs)
8. [Makefile + samconfig.toml](#makefile--samconfigtoml)

## Estrutura completa do template

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: '<DomainName> Lambda Java 25 + GraalVM Native + DynamoDB single-table'

Parameters:
  Stage:
    Type: String
    Default: dev
    AllowedValues: [dev, stg, prd]

Globals:
  Function:
    Runtime: provided.al2023
    Architectures: [arm64]
    MemorySize: 512
    Timeout: 10
    Tracing: Active
    Environment:
      Variables:
        SINGLE_TABLE_NAME: !Ref SingleTable
        AWS_REGION: !Ref AWS::Region
        POWERTOOLS_SERVICE_NAME: !Ref AWS::StackName
        POWERTOOLS_METRICS_NAMESPACE: !Ref AWS::StackName
        POWERTOOLS_LOG_LEVEL: INFO
        POWERTOOLS_LOGGER_LOG_EVENT: true

Resources:

  # ───── DynamoDB Single Table ─────────────────────────────────────────────
  SingleTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub ${AWS::StackName}-single-table
      AttributeDefinitions:
        - AttributeName: pk
          AttributeType: S
        - AttributeName: sk
          AttributeType: S
        - AttributeName: gsi1pk
          AttributeType: S
        - AttributeName: gsi1sk
          AttributeType: S
        - AttributeName: gsi2pk
          AttributeType: S
        - AttributeName: gsi2sk
          AttributeType: S
      KeySchema:
        - AttributeName: pk
          KeyType: HASH
        - AttributeName: sk
          KeyType: RANGE
      GlobalSecondaryIndexes:
        - IndexName: GSI1
          KeySchema:
            - AttributeName: gsi1pk
              KeyType: HASH
            - AttributeName: gsi1sk
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
        - IndexName: GSI2
          KeySchema:
            - AttributeName: gsi2pk
              KeyType: HASH
            - AttributeName: gsi2sk
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
      BillingMode: PAY_PER_REQUEST
      StreamSpecification:
        StreamViewType: NEW_AND_OLD_IMAGES
      TimeToLiveSpecification:
        AttributeName: ttl
        Enabled: true
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true

  # ───── API Gateway Function ─────────────────────────────────────────────
  ApiGatewayFunction:
    Type: AWS::Serverless::Function
    Metadata:
      BuildMethod: makefile
    Properties:
      FunctionName: !Sub ${AWS::StackName}-api
      CodeUri: .
      Handler: org.springframework.cloud.function.adapter.aws.FunctionInvoker
      Environment:
        Variables:
          SPRING_CLOUD_FUNCTION_DEFINITION: apiGatewayHandler
      Policies:
        - DynamoDBCrudPolicy:
            TableName: !Ref SingleTable
        - !Sub
          - |
            { "Statement": [{
              "Effect": "Allow",
              "Action": ["dynamodb:Query", "dynamodb:GetItem"],
              "Resource": "${TableArn}/index/*"
            }] }
          - TableArn: !GetAtt SingleTable.Arn
      Events:
        GetUser:
          Type: HttpApi
          Properties:
            Path: /users/{id}
            Method: GET
        ListOrders:
          Type: HttpApi
          Properties:
            Path: /users/{userId}/orders
            Method: GET
        CreateOrder:
          Type: HttpApi
          Properties:
            Path: /orders
            Method: POST

  # ───── DynamoDB Streams Function ─────────────────────────────────────────
  StreamHandlerFunction:
    Type: AWS::Serverless::Function
    Metadata:
      BuildMethod: makefile
    Properties:
      FunctionName: !Sub ${AWS::StackName}-stream
      CodeUri: .
      Handler: org.springframework.cloud.function.adapter.aws.FunctionInvoker
      Environment:
        Variables:
          SPRING_CLOUD_FUNCTION_DEFINITION: streamHandler
          IDEMPOTENCY_TABLE: !Ref IdempotencyTable
      Policies:
        - DynamoDBCrudPolicy:
            TableName: !Ref IdempotencyTable
        - DynamoDBStreamReadPolicy:
            TableName: !Ref SingleTable
            StreamName: !Select [3, !Split ['/', !GetAtt SingleTable.StreamArn]]
      Events:
        DDBStream:
          Type: DynamoDB
          Properties:
            Stream: !GetAtt SingleTable.StreamArn
            StartingPosition: LATEST
            BatchSize: 100
            MaximumBatchingWindowInSeconds: 5
            FilterCriteria:
              Filters:
                - Pattern: '{"eventName":["INSERT","MODIFY","REMOVE"]}'
            FunctionResponseTypes: [ReportBatchItemFailures]
            BisectBatchOnFunctionError: true
            MaximumRetryAttempts: 3

  # ───── Idempotency table (para PowerTools @Idempotent) ───────────────────
  IdempotencyTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub ${AWS::StackName}-idempotency
      AttributeDefinitions:
        - AttributeName: id
          AttributeType: S
      KeySchema:
        - AttributeName: id
          KeyType: HASH
      BillingMode: PAY_PER_REQUEST
      TimeToLiveSpecification:
        AttributeName: expiration
        Enabled: true

Outputs:
  ApiUrl:
    Description: Base URL of the HTTP API
    Value: !Sub https://${ServerlessHttpApi}.execute-api.${AWS::Region}.amazonaws.com
  SingleTableName:
    Value: !Ref SingleTable
  SingleTableArn:
    Value: !GetAtt SingleTable.Arn
```

## Globals — defaults para todas as funções

`Globals.Function` evita repetição. Os defaults importantes:

- **`Runtime: provided.al2023`** — Custom Runtime obrigatório para binário GraalVM.
- **`Architectures: [arm64]`** — Graviton tem cold start ~20% menor + custo
  ~20% menor que x86_64.
- **`MemorySize: 512`** — sweet spot para Java native em Lambda. Abaixo de
  256MB, CPU é gargalo; acima de 1GB, custo cresce sem ganho proporcional.
  Ajuste por workload via Lambda Power Tuning.
- **`Tracing: Active`** — habilita X-Ray automaticamente.

## Função API Gateway HTTP

Pontos importantes:

- **`BuildMethod: makefile`** + `Metadata` no nível Function — diz ao SAM
  para invocar o target `build-<FunctionName>` do Makefile em vez de
  builder Java padrão.
- **`Handler: FunctionInvoker`** — Spring Cloud Function adapter.
- **`SPRING_CLOUD_FUNCTION_DEFINITION`** — nome do bean `Function<I,O>`
  declarado no Spring.
- **`Events: HttpApi`** (não `Api`) — HTTP API v2 é mais barata, mais rápida
  e tem menos features que REST API. Para CRUD típico, HTTP API é o caminho.
- **Path parameters** (`{id}`) viram `event.getPathParameters()`.

## Função DynamoDB Streams

Pontos críticos:

- **`StartingPosition: LATEST`** — começa a processar a partir do deploy.
  Use `TRIM_HORIZON` se quiser processar histórico (quando a stream foi
  criada antes da Lambda).
- **`BatchSize: 100`** — máximo de records por invocação. Equilibra latência
  vs throughput. Para CDC pesado, 500-1000.
- **`MaximumBatchingWindowInSeconds: 5`** — acumula records até 5s antes de
  invocar. Reduz custo em workloads com burst esparso.
- **`FilterCriteria`** — filtra eventos antes da invocação (cobrança = só
  o que passou no filtro). Caso típico: filtrar por `_type`:

  ```yaml
  FilterCriteria:
    Filters:
      - Pattern: '{"dynamodb":{"NewImage":{"_type":{"S":["ORDER"]}}}}'
  ```

- **`FunctionResponseTypes: [ReportBatchItemFailures]`** — permite à Lambda
  reportar parcialmente quais records falharam, evitando reprocessamento
  do batch inteiro.
- **`BisectBatchOnFunctionError: true`** — em caso de erro em todo batch,
  bissecta e retenta. Isola o "poison message".
- **`MaximumRetryAttempts: 3`** — após 3 falhas, manda para DLQ
  (configure `OnFailure` para SQS DLQ se quiser preservar).

## DynamoDB single-table + Streams

A tabela é o output principal da Etapa 3 do workflow (mapping). Pontos:

- **`StreamSpecification: NEW_AND_OLD_IMAGES`** — captura before/after
  para o handler de Streams ter contexto completo. Outras opções:
  `KEYS_ONLY` (só keys, mais barato), `NEW_IMAGE` (sem before).
- **`BillingMode: PAY_PER_REQUEST`** — sem provisioning. Ideal para Lambda
  com tráfego variável. Migre para `PROVISIONED` apenas se atingir steady-state
  alto e previsível.
- **`PointInTimeRecoveryEnabled: true`** — backups automáticos por 35 dias.
  Custo trivial (~20% do storage), recuperação salva-vidas.
- **`TimeToLiveSpecification.AttributeName: ttl`** — convenção: campo `ttl`
  com epoch seconds expira o item automaticamente. A skill adiciona o
  campo aos records que precisam.

## Permissões IAM mínimas

Princípio do menor privilégio. SAM tem `Policies` declarativas que geram
IAM Role automaticamente:

- **`DynamoDBCrudPolicy: { TableName: !Ref SingleTable }`** — CRUD na tabela.
- **`DynamoDBReadPolicy`** — só leitura (use em handlers de listagem).
- **`DynamoDBStreamReadPolicy: { TableName, StreamName }`** — para função
  consumir a Stream.
- **Inline policy** para queries em GSIs — `DynamoDBCrudPolicy` não cobre
  `dynamodb:Query` em índices secundários, então adicione manualmente:

  ```yaml
  - !Sub
    - |
      { "Statement": [{
        "Effect": "Allow",
        "Action": ["dynamodb:Query"],
        "Resource": "${TableArn}/index/*"
      }] }
    - TableArn: !GetAtt SingleTable.Arn
  ```

Permissões automáticas (não precisam declarar):

- CloudWatch Logs (CreateLogGroup, PutLogEvents)
- X-Ray (PutTraceSegments) — ativada pelo `Tracing: Active`

## Outputs

Sempre exporte recursos críticos para integração com outras stacks ou CI:

```yaml
Outputs:
  ApiUrl:
    Value: !Sub https://${ServerlessHttpApi}.execute-api.${AWS::Region}.amazonaws.com
    Export:
      Name: !Sub ${AWS::StackName}-api-url
  SingleTableName:
    Value: !Ref SingleTable
    Export:
      Name: !Sub ${AWS::StackName}-table-name
  ApiGatewayFunctionArn:
    Value: !GetAtt ApiGatewayFunction.Arn
```

## Makefile + samconfig.toml

`Makefile` na raiz (chamado pelo `BuildMethod: makefile`):

```makefile
build-ApiGatewayFunction:
	mvn -Pnative native:compile -DskipTests
	cp target/bootstrap $(ARTIFACTS_DIR)/bootstrap
	chmod +x $(ARTIFACTS_DIR)/bootstrap

build-StreamHandlerFunction:
	mvn -Pnative native:compile -DskipTests
	cp target/bootstrap $(ARTIFACTS_DIR)/bootstrap
	chmod +x $(ARTIFACTS_DIR)/bootstrap

# Convenience targets
.PHONY: build deploy invoke clean

build:
	sam build --use-container

deploy: build
	sam deploy

invoke:
	sam local invoke ApiGatewayFunction --event events/get-user.json

clean:
	mvn clean
	rm -rf .aws-sam
```

`samconfig.toml` (gerado pelo `sam deploy --guided` da primeira vez):

```toml
version = 0.1
[default.deploy.parameters]
stack_name = "myapp-dev"
s3_bucket = "aws-sam-cli-managed-default-samclisourcebucket-xxx"
s3_prefix = "myapp"
region = "us-east-1"
confirm_changeset = true
capabilities = "CAPABILITY_IAM"
parameter_overrides = "Stage=dev"
image_repositories = []
```

Ambiente isolado por stage:

```bash
sam deploy --config-env dev   # lê [dev.deploy.parameters]
sam deploy --config-env stg
sam deploy --config-env prd
```
