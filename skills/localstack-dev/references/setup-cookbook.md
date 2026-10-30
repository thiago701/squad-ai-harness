# LocalStack — Cookbook de Setup (reference de `localstack-dev`)

> Conteudo operacional extraido do hub (Ciclo 9, progressive disclosure). O hub cobre o conceito; aqui esta o passo a passo de copiar-e-colar.

## docker-compose.yml — Orquestração LocalStack

```yaml
version: '3.9'

services:
  # ════════════════════════════════════════════════════════════════════════════
  # LocalStack — Emulador local de AWS (SQS, S3, Secrets Manager, CloudWatch)
  # ════════════════════════════════════════════════════════════════════════════

  localstack:
    image: localstack/localstack:4        # LocalStack 4+ (GA 2024-11): Bedrock/Lambda streaming
    container_name: circuit-palestras-localstack
    profiles: ["dev", "test"]             # usar com: docker compose --profile dev up
    ports:
      - "4566:4566"           # Main LocalStack endpoint (único necessário em LS 4+)
    environment:
      # Serviços a emular — adicionado Bedrock, Lambda, DynamoDB Streams, StepFunctions
      SERVICES: sqs,s3,secretsmanager,cloudwatch,logs,dynamodb,bedrock,lambda,stepfunctions,events
      # Modo debug — mostra chamadas AWS no console
      DEBUG: 1
      # Persistência — LocalStack 4+ usa Cloud Pods por padrão
      PERSISTENCE: 1
      # Credenciais fake (aceita qualquer valor)
      AWS_ACCESS_KEY_ID: test
      AWS_SECRET_ACCESS_KEY: test
      AWS_DEFAULT_REGION: us-east-1
      # LocalStack 4+ — Lambda com hot reloading do código (monta volume)
      LAMBDA_DOCKER_NETWORK: circuit-palestras-network
      # Bedrock mock: usa modelos Ollama localmente
      BEDROCK_MODEL_PROVIDER: ollama
    volumes:
      # Persistência de dados
      - localstack-data:/tmp/localstack
      # Script de inicialização (cria filas, buckets, etc.)
      - ./docker/localstack-init.sh:/docker-entrypoint-initaws.d/init.sh:ro
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4566/_localstack/health"]
      interval: 5s
      timeout: 3s
      retries: 10
    networks:
      - circuit-palestras-network

  # ════════════════════════════════════════════════════════════════════════════
  # PostgreSQL — Banco de dados principal
  # ════════════════════════════════════════════════════════════════════════════

  postgres:
    image: postgres:16-alpine
    container_name: circuit-palestras-db
    environment:
      POSTGRES_USER: circuito
      POSTGRES_PASSWORD: circuito_dev_2026
      POSTGRES_DB: circuito_palestras
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U circuito"]
      interval: 5s
      timeout: 3s
      retries: 10
    networks:
      - circuit-palestras-network

  # ════════════════════════════════════════════════════════════════════════════
  # Redis — Cache e sessões
  # ════════════════════════════════════════════════════════════════════════════

  redis:
    image: redis:7-alpine
    container_name: circuit-palestras-redis
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10
    networks:
      - circuit-palestras-network

networks:
  circuit-palestras-network:
    driver: bridge

volumes:
  localstack-data:
  postgres-data:
  redis-data:
```

**Uso:**
```bash
# Iniciar tudo
docker compose up -d

# Verificar logs LocalStack
docker compose logs -f localstack

# Parar tudo
docker compose down

# Remover volumes (limpar dados)
docker compose down -v
```

---

## localstack-init.sh — Script de Inicialização

Roda automaticamente ao iniciar o container LocalStack. Cria todos os recursos necessários.

```bash
#!/bin/bash
set -e

echo "🚀 Inicializando LocalStack..."

# Aguardar LocalStack estar pronto
until curl -f http://localhost:4566/_localstack/health 2>/dev/null; do
    echo "⏳ Aguardando LocalStack..."
    sleep 2
done

echo "✅ LocalStack pronto!"

# ════════════════════════════════════════════════════════════════════════════
# SQS — Criar fila principal + DLQ
# ════════════════════════════════════════════════════════════════════════════

echo "📨 Criando fila SQS..."

# Fila DLQ (Dead Letter Queue)
awslocal sqs create-queue \
    --queue-name circuit-breaker-dlq \
    --region us-east-1

# Fila principal com redrives para DLQ
awslocal sqs create-queue \
    --queue-name circuit-breaker-queue \
    --attributes \
        RedrivePolicy='{"deadLetterTargetArn":"arn:aws:sqs:us-east-1:000000000000:circuit-breaker-dlq","maxReceiveCount":"3"}' \
    --region us-east-1

echo "✓ Filas SQS criadas"

# ════════════════════════════════════════════════════════════════════════════
# S3 — Criar buckets
# ════════════════════════════════════════════════════════════════════════════

echo "🗂️  Criando buckets S3..."

# Bucket principal
awslocal s3 mb s3://circuit-palestras-local --region us-east-1

# Bucket para backups
awslocal s3 mb s3://circuit-palestras-backups --region us-east-1

# CORS policy para bucket principal
awslocal s3api put-bucket-cors \
    --bucket circuit-palestras-local \
    --cors-configuration '{
        "CORSRules": [{
            "AllowedOrigins": ["http://localhost:4200", "http://localhost:3000"],
            "AllowedMethods": ["GET", "PUT", "POST"],
            "AllowedHeaders": ["*"],
            "MaxAgeSeconds": 3000
        }]
    }' \
    --region us-east-1

echo "✓ Buckets S3 criados"

# ════════════════════════════════════════════════════════════════════════════
# Secrets Manager — Armazenar credenciais
# ════════════════════════════════════════════════════════════════════════════

echo "🔐 Criando secrets..."

awslocal secretsmanager create-secret \
    --name circuit/openai/key \
    --secret-string 'sk-proj-test-key-12345' \
    --region us-east-1

awslocal secretsmanager create-secret \
    --name circuit/twilio/token \
    --secret-string 'AC1234567890abcdef' \
    --region us-east-1

awslocal secretsmanager create-secret \
    --name circuit/google-calendar/credentials \
    --secret-string '{"type":"service_account","project_id":"test"}' \
    --region us-east-1

echo "✓ Secrets criados"

# ════════════════════════════════════════════════════════════════════════════
# CloudWatch Logs — Criar log groups
# ════════════════════════════════════════════════════════════════════════════

echo "📊 Criando log groups CloudWatch..."

awslocal logs create-log-group \
    --log-group-name /circuit-palestras/backend \
    --region us-east-1

awslocal logs create-log-group \
    --log-group-name /circuit-palestras/ms-expositores \
    --region us-east-1

awslocal logs create-log-group \
    --log-group-name /circuit-palestras/ms-instituicoes \
    --region us-east-1

echo "✓ Log groups criados"

# ════════════════════════════════════════════════════════════════════════════
# Verificação final
# ════════════════════════════════════════════════════════════════════════════

echo ""
echo "✅ LocalStack inicializado com sucesso!"
echo ""
echo "📋 Recursos criados:"
awslocal sqs list-queues --region us-east-1 || echo "  (nenhuma fila)"
awslocal s3 ls --region us-east-1
awslocal secretsmanager list-secrets --region us-east-1 --query 'SecretList[*].Name' || echo "  (nenhum secret)"
echo ""
```

**Instalação:**
```bash
# Copiar o script para o projeto
mkdir -p docker
cp localstack-init.sh docker/

# Dar permissão de execução
chmod +x docker/localstack-init.sh
```

---

## Separação de Variáveis: .env.local vs .env.prod

### .env.local (committed no repo, para dev)
```bash
# Django/Python backend (exemplo)
DATABASE_URL=postgresql://circuito:circuito_dev_2026@localhost:5432/circuito_palestras
REDIS_URL=redis://localhost:6379
AWS_ENDPOINT_URL=http://localhost:4566
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_S3_BUCKET=circuit-palestras-local
AWS_SQS_QUEUE_URL=http://localhost:4566/000000000000/circuit-breaker-queue
AWS_SQS_DLQ_URL=http://localhost:4566/000000000000/circuit-breaker-dlq
```

### .env.prod (secrets management, não commitado)
```bash
# Usado via Secrets Manager ou CI/CD variables
DATABASE_URL=postgresql://<usuario>:<senha-do-secrets-manager>@prod-rds.aws:5432/circuito_palestras_prod
REDIS_URL=redis://prod-elasticache.aws:6379
AWS_REGION=us-east-1
# endpoint-url: omitido — SDK usa AWS real
AWS_S3_BUCKET=circuit-palestras-prod
AWS_SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789012/circuit-breaker-queue
AWS_SQS_DLQ_URL=https://sqs.us-east-1.amazonaws.com/123456789012/circuit-breaker-dlq
```

---

## Padrão: localstack-deploy-cf.sh

Para testar CloudFormation templates localmente no LocalStack:

```bash
#!/bin/bash
set -e

TEMPLATE_FILE="${1:?Especifique arquivo CloudFormation (ex: vpc-template.yaml)}"

echo "📦 Aplicando template CloudFormation no LocalStack..."

awslocal cloudformation create-stack \
    --stack-name test-stack \
    --template-body file://$(pwd)/$TEMPLATE_FILE \
    --region us-east-1 \
    --parameters ParameterKey=Environment,ParameterValue=local

echo "⏳ Aguardando conclusão da stack..."
awslocal cloudformation wait stack-create-complete \
    --stack-name test-stack \
    --region us-east-1 || echo "Stack criada (talvez com avisos)"

echo "✅ Stack criada!"
awslocal cloudformation describe-stacks --stack-name test-stack --region us-east-1
```

**Uso:**
```bash
chmod +x localstack-deploy-cf.sh
./localstack-deploy-cf.sh infra/cloudformation/01-vpc.yaml
```

---

## Dependências AWS SDK

> **Nota**: a squad padroniza **Apache Maven 4** (ver `squad-ai/references/clean-architecture-java25.md`). O snippet Gradle abaixo serve apenas como referência para equipes que herdaram builds Gradle legados — em projetos novos, use o `pom.xml` canônico.

### build.gradle.kts (referência — apenas para builds Gradle legados)

```kotlin
dependencies {
    // AWS SDK v2 — Modular e otimizado para JDK 25
    implementation("software.amazon.awssdk:sqs:2.26.0")
    implementation("software.amazon.awssdk:s3:2.26.0")
    implementation("software.amazon.awssdk:secretsmanager:2.26.0")
    implementation("software.amazon.awssdk:cloudwatchlogs:2.26.0")
    
    // Spring boot starters
    implementation("org.springframework.boot:spring-boot-starter-web:4.0.x")
    implementation("org.springframework.boot:spring-boot-starter-data-jpa:4.0.x")
    
    // LocalStack em testes (container gerenciado)
    testImplementation("org.testcontainers:testcontainers:1.19.x")
    testImplementation("org.testcontainers:localstack:1.19.x")
}
```

---

## Comandos Úteis — awslocal CLI

LocalStack instala `awslocal` alias automaticamente em seu container:

```bash
# ════════════════════════════════════════════════════════════════════════════
# SQS
# ════════════════════════════════════════════════════════════════════════════

# Listar filas
docker exec circuit-palestras-localstack awslocal sqs list-queues --region us-east-1

# Enviar mensagem de teste
docker exec circuit-palestras-localstack awslocal sqs send-message \
    --queue-url http://localhost:4566/000000000000/circuit-breaker-queue \
    --message-body '{"expositor_id": 123, "event": "confirmed"}' \
    --region us-east-1

# Receber mensagem
docker exec circuit-palestras-localstack awslocal sqs receive-message \
    --queue-url http://localhost:4566/000000000000/circuit-breaker-queue \
    --region us-east-1

# ════════════════════════════════════════════════════════════════════════════
# S3
# ════════════════════════════════════════════════════════════════════════════

# Listar buckets
docker exec circuit-palestras-localstack awslocal s3 ls

# Fazer upload de arquivo
echo "test data" > /tmp/test.txt
docker exec -i circuit-palestras-localstack awslocal s3 cp /tmp/test.txt s3://circuit-palestras-local/test.txt

# Listar objetos em bucket
docker exec circuit-palestras-localstack awslocal s3 ls s3://circuit-palestras-local/

# ════════════════════════════════════════════════════════════════════════════
# Secrets Manager
# ════════════════════════════════════════════════════════════════════════════

# Listar secrets
docker exec circuit-palestras-localstack awslocal secretsmanager list-secrets --region us-east-1

# Ler valor de secret
docker exec circuit-palestras-localstack awslocal secretsmanager get-secret-value \
    --secret-id circuit/openai/key \
    --region us-east-1

# ════════════════════════════════════════════════════════════════════════════
# CloudWatch Logs
# ════════════════════════════════════════════════════════════════════════════

# Listar log groups
docker exec circuit-palestras-localstack awslocal logs describe-log-groups --region us-east-1

# Ver eventos de um log group
docker exec circuit-palestras-localstack awslocal logs tail /circuit-palestras/backend --region us-east-1
```

---

## Testes de Integração com LocalStack

### Exemplo: Teste de SQS

```java
package br.org.fepb.integration;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.testcontainers.containers.localstack.LocalStackContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import software.amazon.awssdk.services.sqs.SqsClient;
import software.amazon.awssdk.services.sqs.model.SendMessageRequest;

@SpringBootTest
@Testcontainers
@ActiveProfiles("test")
class SqsIntegrationTest {

    @Container
    static LocalStackContainer localstack = new LocalStackContainer()
        .withServices(LocalStackContainer.Service.SQS);

    @Autowired
    SqsClient sqsClient;

    @Test
    void shouldSendAndReceiveMessage() {
        // Arrange
        String queueUrl = "http://localhost:4566/000000000000/circuit-breaker-queue";
        String messageBody = "{\"expositor_id\": 123}";

        // Act
        sqsClient.sendMessage(
            SendMessageRequest.builder()
                .queueUrl(queueUrl)
                .messageBody(messageBody)
                .build()
        );

        // Assert — recuperar e validar
        var response = sqsClient.receiveMessage(r -> r.queueUrl(queueUrl));
        assertThat(response.messages()).hasSize(1);
        assertThat(response.messages().get(0).body()).contains("expositor_id");
    }
}
```

---

## Troubleshooting

### LocalStack não inicia
```bash
# Limpar container antigo
docker compose down -v
docker system prune

# Rebuildar
docker compose up -d localstack --force-recreate
```

### Erro: "Connection refused 4566"
```bash
# Verificar se LocalStack subiu
docker compose ps localstack

# Ver logs
docker compose logs localstack | tail -20
```

### S3: "InvalidBucketName"
```
Erro comum: path-style não configurado em Java
Solução: Adicionar forcePathStyleAccessEnabled(true) em dev (veja AwsConfig.java)
```

### Secretos não funcionam
```bash
# Verificar se secret foi criado
docker exec circuit-palestras-localstack awslocal secretsmanager list-secrets --region us-east-1

# Caso negativo, re-executar init.sh manualmente
docker exec circuit-palestras-localstack /docker-entrypoint-initaws.d/init.sh
```

---

## Lambda com LocalStack — Teste Local Completo

LocalStack 4+ emula Lambda com containers Docker reais — o mesmo runtime da AWS, localmente.

### Setup: Lambda com Hot Reloading

```yaml
# docker-compose.yml — Lambda com mount de código (hot reload)
localstack:
  image: localstack/localstack:4
  environment:
    SERVICES: lambda,sqs,s3,secretsmanager
    LAMBDA_DOCKER_NETWORK: myapp-network
    # Hot reloading: LocalStack monta o volume e re-deploy a cada mudança
    LAMBDA_DOCKER_FLAGS: "-v $(pwd)/src:/var/task:ro"
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock  # necessário para Lambda via Docker
    - ./lambda-src:/hot                           # código com hot reload
```

### Criar e Invocar Lambda com awslocal

```bash
# awslocal = aws CLI apontando automaticamente para LocalStack (localhost:4566)
pip install awscli-local

# Empacotar função Python
cd lambda-src && zip function.zip handler.py && cd ..

# Criar função no LocalStack
awslocal lambda create-function \
  --function-name ProcessarPedido \
  --runtime python3.13 \
  --handler handler.handler \
  --zip-file fileb://lambda-src/function.zip \
  --role arn:aws:iam::000000000000:role/lambda-role \
  --region us-east-1

# Invocar e ver resultado
awslocal lambda invoke \
  --function-name ProcessarPedido \
  --payload '{"pedidoId": "123", "valor": 99.90}' \
  --cli-binary-format raw-in-base64-out \
  /tmp/response.json && cat /tmp/response.json

# Re-deploy após mudança (hot reload alternativo)
zip function.zip handler.py && \
awslocal lambda update-function-code \
  --function-name ProcessarPedido \
  --zip-file fileb://function.zip
```

### Lambda Java com SAM Local (sem LocalStack)

```bash
# sam local não precisa do LocalStack — invoca Lambda localmente via Docker
# (LocalStack é necessário para SQS/S3/DynamoDB que a Lambda usa)

# Instalar SAM CLI
pip install aws-sam-cli

# Invocar Lambda única vez com evento simulado
sam local invoke ProcessarPedidoFunction \
  --event events/pedido-event.json \
  --env-vars env-local.json \
  --docker-network myapp-network   # conecta na rede do LocalStack

# events/pedido-event.json
{
  "body": "{\"pedidoId\": \"123\", \"valor\": 99.90}",
  "httpMethod": "POST",
  "path": "/pedidos"
}

# env-local.json — sobrescreve variáveis de ambiente
{
  "ProcessarPedidoFunction": {
    "SPRING_PROFILES_ACTIVE": "local",
    "AWS_ENDPOINT_URL": "http://localstack:4566",
    "AWS_ACCESS_KEY_ID": "test",
    "AWS_SECRET_ACCESS_KEY": "test"
  }
}
```

### API Gateway Local com SAM (testes E2E completos)

```bash
# Subir API local — intercepta HTTP e invoca Lambda
sam local start-api \
  --port 3000 \
  --env-vars env-local.json \
  --docker-network myapp-network \
  --warm-containers EAGER    # mantém container quente entre requests

# Testar como se fosse produção
curl -X POST http://localhost:3000/pedidos \
  -H "Content-Type: application/json" \
  -d '{"clienteId": "abc", "valor": 150.00}'

# Com token JWT (simular Cognito)
curl -X POST http://localhost:3000/pedidos \
  -H "Authorization: Bearer $(sam local generate-event cognito-idp-token)" \
  -d '{"clienteId": "abc", "valor": 150.00}'
```

### Trigger SQS → Lambda no LocalStack

```bash
# 1. Criar fila SQS no LocalStack
awslocal sqs create-queue --queue-name pedidos-queue

# 2. Criar mapeamento Lambda ← SQS
awslocal lambda create-event-source-mapping \
  --function-name ProcessarPedido \
  --event-source-arn arn:aws:sqs:us-east-1:000000000000:pedidos-queue \
  --batch-size 5

# 3. Enviar mensagem — Lambda será invocada automaticamente
awslocal sqs send-message \
  --queue-url http://localhost:4566/000000000000/pedidos-queue \
  --message-body '{"pedidoId": "456", "valor": 200.00}'

# 4. Verificar logs
awslocal logs get-log-events \
  --log-group-name /aws/lambda/ProcessarPedido \
  --log-stream-name $(awslocal logs describe-log-streams \
    --log-group-name /aws/lambda/ProcessarPedido \
    --query 'logStreams[-1].logStreamName' --output text)
```

### Spring Boot: Perfil `local` apontando para LocalStack Lambda

```java
// application-local.yml — Spring Cloud AWS aponta para LocalStack
spring:
  cloud:
    aws:
      endpoint: http://localhost:4566
      credentials:
        access-key: test
        secret-key: test
      region:
        static: us-east-1
```

```java
// Teste de integração Spring Boot + LocalStack Lambda
@SpringBootTest
@ActiveProfiles("local")
@Testcontainers
class LambdaIntegrationTest {

    @Container
    static LocalStackContainer localstack = new LocalStackContainer(
        DockerImageName.parse("localstack/localstack:4"))
        .withServices(Service.LAMBDA, Service.SQS);

    @Test
    void deveria_processar_pedido_via_sqs_lambda() throws Exception {
        // Setup: criar fila e função Lambda
        var sqsClient = SqsClient.builder()
            .endpointOverride(localstack.getEndpoint())
            .region(Region.US_EAST_1)
            .credentialsProvider(StaticCredentialsProvider.create(
                AwsBasicCredentials.create("test", "test")))
            .build();

        sqsClient.createQueue(r -> r.queueName("pedidos-queue"));
        // (criar Lambda, configurar mapeamento, etc.)

        // Act: enviar mensagem
        sqsClient.sendMessage(r -> r
            .queueUrl("http://localhost:4566/000000000000/pedidos-queue")
            .messageBody("{\"pedidoId\": \"999\"}"));

        // Assert: aguardar processamento e verificar resultado em DynamoDB/S3
        await().atMost(10, SECONDS).until(() -> resultadoSalvo("999"));
    }
}
```

### Heurísticas LocalStack + Lambda

| Situação | Solução |
|---|---|
| Lambda não inicia (imagem Docker) | `docker logs localstack` — verificar pull de imagem do runtime |
| SQS → Lambda não dispara | Verificar `event-source-mapping` criado; polling delay padrão é 5s |
| AWS SDK não conecta no LocalStack | `AWS_ENDPOINT_URL=http://localhost:4566` ou `@LocalStack` no CDK |
| `sam local` sem rede do LocalStack | Adicionar `--docker-network` com mesmo nome da network do compose |
| Hot reload não funciona | Volume montado? `LAMBDA_DOCKER_FLAGS` com `-v`? Rebuild zip? |
| Diferença de comportamento local vs AWS | Log verboso: `DEBUG=1` no LocalStack; `sam local` usa runtime real |

