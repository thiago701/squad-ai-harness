# Referência — Lambda Deploy (SAM, SnapStart, Aliases, Power Tuning)

> Parte da skill `engenheiro-devops`. Carregue sob demanda quando a tarefa tocar deploy de Lambda. Hub: `../SKILL.md`.

## SAM CLI — Build e Deploy no Pipeline

O AWS SAM (Serverless Application Model) é o IaC padrão para Lambda. Gera CloudFormation, resolve dependências e executa testes locais.

```yaml
# .github/workflows/lambda-deploy.yml
name: Lambda Deploy

on:
  push:
    branches: [main]

permissions:
  id-token: write   # OIDC para assumir role AWS sem credenciais long-lived
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::${{ vars.AWS_ACCOUNT_ID }}:role/github-actions-deployer
          aws-region: us-east-1

      - uses: actions/setup-java@v4
        with:
          java-version: '25'
          distribution: temurin
          cache: maven

      - name: Build
        run: mvn -T 1C package -DskipTests

      - name: SAM Build (container)
        run: sam build --use-container

      - name: SAM Deploy
        run: |
          sam deploy \
            --stack-name ${{ vars.STACK_NAME }} \
            --s3-bucket ${{ vars.SAM_BUCKET }} \
            --capabilities CAPABILITY_IAM \
            --no-confirm-changeset \
            --no-fail-on-empty-changeset
```

### Estrutura Canônica de template.yaml

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Globals:
  Function:
    Runtime: java25
    Timeout: 30
    MemorySize: 512
    Architectures: [arm64]            # Graviton — 20% mais rápido, 20% mais barato
    Environment:
      Variables:
        POWERTOOLS_SERVICE_NAME: !Ref AWS::StackName
        POWERTOOLS_LOG_LEVEL: INFO
    Tracing: Active                   # X-Ray automático
    Layers:
      - !Sub "arn:aws:lambda:${AWS::Region}:017000801446:layer:AWSLambdaPowertoolsJava:1"

Resources:
  PedidoFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: org.springframework.cloud.function.adapter.aws.FunctionInvoker::handleRequest
      CodeUri: target/function.jar
      SnapStart:
        ApplyOn: PublishedVersions    # Elimina cold start — use sempre para Java
      AutoPublishAlias: live          # Publica versão + aponta alias live para ela
      DeploymentPreference:
        Type: Canary10Percent5Minutes # 10% do tráfego por 5 min antes de 100%
        Alarms:
          - !Ref LatencyAlarm
          - !Ref ErrorRateAlarm
      Events:
        ApiPost:
          Type: HttpApi
          Properties:
            Path: /pedidos
            Method: POST

  # Alarmes para rollback automático
  LatencyAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: !Sub "${AWS::StackName}-p99-latency"
      Namespace: AWS/Lambda
      MetricName: Duration
      ExtendedStatistic: p99
      Threshold: 3000   # 3s — se p99 passar disso, rollback
      ComparisonOperator: GreaterThanThreshold
      EvaluationPeriods: 2
      Period: 60
      Dimensions:
        - Name: FunctionName
          Value: !Ref PedidoFunction

  ErrorRateAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: !Sub "${AWS::StackName}-error-rate"
      Namespace: AWS/Lambda
      MetricName: Errors
      Statistic: Sum
      Threshold: 5
      ComparisonOperator: GreaterThanThreshold
      EvaluationPeriods: 1
      Period: 60
      Dimensions:
        - Name: FunctionName
          Value: !Ref PedidoFunction
```

## Canary Deploy com Lambda Aliases

Lambda Aliases permitem canary **sem ALB** — tráfego roteado pelo próprio Lambda.

```bash
# Manual (CI pode fazer o mesmo via CLI)

# 1. Publica nova versão
NEW_VERSION=$(aws lambda publish-version --function-name pedido-fn --query Version --output text)

# 2. Atualiza alias "live" com pesos: 10% nova versão, 90% anterior
PREV_VERSION=$(aws lambda get-alias --function-name pedido-fn --name live \
  --query 'RoutingConfig.AdditionalVersionWeights | keys(@)[0]' --output text 2>/dev/null || echo "1")

aws lambda update-alias \
  --function-name pedido-fn \
  --name live \
  --function-version $PREV_VERSION \
  --routing-config AdditionalVersionWeights={"$NEW_VERSION"=0.1}  # 10% canary

# 3. Monitorar por 5 min e promover (ou rollback)
sleep 300
ERROR_COUNT=$(aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda --metric-name Errors \
  --dimensions Name=FunctionName,Value=pedido-fn \
               Name=Resource,Value="pedido-fn:live" \
  --start-time $(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 --statistics Sum --query 'Datapoints[0].Sum' --output text)

if [ "$ERROR_COUNT" = "None" ] || [ "$ERROR_COUNT" = "0" ]; then
  # Promover 100%
  aws lambda update-alias --function-name pedido-fn --name live \
    --function-version $NEW_VERSION --routing-config AdditionalVersionWeights={}
  echo "✅ Canary promovido: versão $NEW_VERSION é 100%"
else
  # Rollback
  aws lambda update-alias --function-name pedido-fn --name live \
    --function-version $PREV_VERSION --routing-config AdditionalVersionWeights={}
  echo "🔴 Rollback: $ERROR_COUNT erros detectados"
fi
```

## Lambda Power Tuning — Otimizar Memória/Custo

Lambda Power Tuning roda sua função com 11 configurações de memória e encontra o ponto
ótimo entre velocidade e custo. **Rodar antes de definir `MemorySize` em produção** — a
configuração padrão 128MB raramente é a mais econômica.

```bash
# Instalar e rodar Lambda Power Tuning via SAR (Serverless Application Repository)
aws serverlessrepo create-cloud-formation-change-set \
  --application-id arn:aws:serverlessrepo:us-east-1:451282441545:applications/aws-lambda-power-tuning \
  --semantic-version 4.3.4 \
  --stack-name lambda-power-tuning \
  --capabilities CAPABILITY_IAM

# Após deploy, invocar via Step Functions:
INPUT='{
  "lambdaARN": "arn:aws:lambda:us-east-1:123:function:pedido-fn",
  "powerValues": [128, 256, 512, 1024, 2048, 3008],
  "num": 50,
  "payload": {"body": "{\"clienteId\": \"abc\"}"},
  "parallelInvocation": true
}'

aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:us-east-1:123:stateMachine:powerTuningMachine \
  --input "$INPUT"
```

**Interpretando o resultado:**

| Memória | Duração (ms) | Custo/10k req |
|---------|-------------|----------------|
| 128MB   | 1800ms       | $0.38          |
| 256MB   | 900ms        | $0.19          |
| 512MB   | 380ms        | $0.14 ← ótimo  |
| 1024MB  | 200ms        | $0.14 (empate) |
| 2048MB  | 120ms        | $0.18 (caro)   |

Escolha o ponto onde **cost/invocation** é mínimo, não onde a duração é mínima.
Para Java + SnapStart, o ótimo frequentemente fica em **512MB–1024MB**.

## SnapStart — Checklist de Pipeline

SnapStart captura o estado da JVM após inicialização e restaura em milissegundos.
**Não é automático:** requer `PublishedVersions` E invoke do alias (não do `$LATEST`).

```yaml
# Checklist SnapStart no CI/CD:
# □ SnapStart.ApplyOn = PublishedVersions (não PublishedVersions só não basta)
# □ AutoPublishAlias configurado (alias aponta para versão publicada)
# □ Teste de cold start no pipeline (aws lambda invoke com alias, medir InitDuration)
# □ Implementar CRaCResource se houver recursos com estado (conexões DB, etc.)
# □ Não usar System.nanoTime() ou random pré-gerado no init — valores fixos no snapshot
```

```java
// Spring Boot — Lifecyle hook para SnapStart
@Component
public class SnapStartWarmup implements CracResource {

    private final DataSource dataSource;

    public SnapStartWarmup(DataSource dataSource) {
        Core.getGlobalContext().register(this);  // registra no CRaC
        this.dataSource = dataSource;
    }

    @Override
    public void beforeCheckpoint(Context<? extends Resource> context) throws Exception {
        // Fechar conexões antes do snapshot — não podem ser congeladas
        dataSource.getConnection().close();
    }

    @Override
    public void afterRestore(Context<? extends Resource> context) throws Exception {
        // Reaquecer conexões após restore do snapshot
        dataSource.getConnection().close(); // warm up pool
    }
}
```

## Heurísticas Lambda Deploy

| Situação | Ação |
|---|---|
| Java Lambda com cold start > 500ms | Habilitar SnapStart (zero código) |
| Cold start ainda > 300ms após SnapStart | GraalVM Native Image (< 100ms) |
| Custo mensal inesperado | Rodar Lambda Power Tuning (quase sempre recupera 20-40%) |
| Deploy sem rollback | Adicionar `DeploymentPreference` + CloudWatch Alarms |
| Lambda timeout em produção | Aumentar timeout E checar async downstream; nunca só aumentar timeout |
| Erro de permissão no invoke | Verificar resource policy (invoke cross-account) vs execution role (SDK calls) |
| Throttling 429 na Lambda | Aumentar `ReservedConcurrencyLimit` ou adicionar SQS buffer |
