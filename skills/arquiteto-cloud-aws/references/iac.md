# Referência — Infraestrutura como Código (SAM, CDK, LocalStack)

> Parte da skill `arquiteto-cloud-aws`. Carregue este arquivo sob demanda quando a tarefa tocar este eixo. Hub: `../SKILL.md`.
## IaC — Infraestrutura como Código (obrigatório)

**Regra institucional: zero clique manual no console AWS em produção.**

### AWS SAM — Serverless Application Model (mais simples para Lambda)

```yaml
# template.yaml — toda a infraestrutura serverless em um arquivo
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Globals:
  Function:
    Runtime: python3.12
    MemorySize: 256
    Timeout: 30
    Environment:
      Variables:
        POWERTOOLS_SERVICE_NAME: pedido-service
        LOG_LEVEL: INFO

Resources:
  PedidoApi:
    Type: AWS::Serverless::Api
    Properties:
      StageName: prod
      Auth:
        DefaultAuthorizer: CognitoAuthorizer
        Authorizers:
          CognitoAuthorizer:
            UserPoolArn: !GetAtt UserPool.Arn

  BuscarPedidoFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: pedido.handler.buscar
      Events:
        Api:
          Type: Api
          Properties:
            RestApiId: !Ref PedidoApi
            Path: /pedidos/{id}
            Method: GET

  PedidoQueue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: pedidos-confirmados
      RedrivePolicy:
        deadLetterTargetArn: !GetAtt PedidoDLQ.Arn
        maxReceiveCount: 3  # 3 tentativas antes de ir para DLQ

  PedidoDLQ:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: pedidos-confirmados-dlq
      MessageRetentionPeriod: 1209600  # 14 dias para investigar falhas
```

### CDK Python — Para Arquiteturas Mais Complexas

```python
# infrastructure/app.py — CDK em Python (sem aprender CloudFormation YAML)
from aws_cdk import (
    App, Stack, Duration,
    aws_lambda as lambda_,
    aws_apigateway as apigw,
    aws_sqs as sqs,
    aws_lambda_event_sources as sources,
    aws_cognito as cognito,
    aws_rds as rds,
)
from constructs import Construct

class PedidoStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Cognito User Pool — autenticação sem código
        user_pool = cognito.UserPool(self, "UserPool",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(email=True),
            password_policy=cognito.PasswordPolicy(min_length=8),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
        )

        # SQS com DLQ automática
        dlq = sqs.Queue(self, "PedidoDLQ",
            retention_period=Duration.days(14))

        fila_pedidos = sqs.Queue(self, "FilaPedidos",
            visibility_timeout=Duration.seconds(60),
            dead_letter_queue=sqs.DeadLetterQueue(queue=dlq, max_receive_count=3),
        )

        # Lambda para API
        api_lambda = lambda_.Function(self, "PedidoApiLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="pedido.handler",
            code=lambda_.Code.from_asset("src"),
            memory_size=256,
            timeout=Duration.seconds(30),
            environment={"QUEUE_URL": fila_pedidos.queue_url},
        )
        fila_pedidos.grant_send_messages(api_lambda)

        # Lambda consumer SQS
        worker_lambda = lambda_.Function(self, "PedidoWorkerLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="worker.handler",
            code=lambda_.Code.from_asset("src"),
            memory_size=128,
        )
        worker_lambda.add_event_source(
            sources.SqsEventSource(fila_pedidos, batch_size=10))

        # API Gateway com Cognito Authorizer
        api = apigw.RestApi(self, "PedidoApi")
        authorizer = apigw.CognitoUserPoolsAuthorizer(self, "Authorizer",
            cognito_user_pools=[user_pool])
        pedidos = api.root.add_resource("pedidos")
        pedidos.add_method("POST",
            apigw.LambdaIntegration(api_lambda),
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )

app = App()
PedidoStack(app, "PedidoStack")
app.synth()
```

---

## Desenvolvimento Local com LocalStack

```bash
# docker-compose.yml — emula AWS localmente, zero custo de desenvolvimento
version: '3.8'
services:
  localstack:
    image: localstack/localstack:latest
    ports:
      - "4566:4566"
    environment:
      SERVICES: s3,sqs,dynamodb,lambda,apigateway,cognito,secretsmanager
      DEBUG: 0
    volumes:
      - ./scripts/localstack-init.sh:/etc/localstack/init/ready.d/init.sh

  app:
    build: .
    environment:
      AWS_ENDPOINT_URL: http://localstack:4566
      AWS_ACCESS_KEY_ID: test
      AWS_SECRET_ACCESS_KEY: test
      AWS_DEFAULT_REGION: us-east-1
```

```python
# Python — cliente boto3 apontando para LocalStack em desenvolvimento
import boto3
import os

def criar_cliente_aws(servico: str):
    """Usa LocalStack em dev, AWS real em prod — transparente para o código."""
    kwargs = {"region_name": os.getenv("AWS_DEFAULT_REGION", "us-east-1")}

    endpoint = os.getenv("AWS_ENDPOINT_URL")  # definido apenas em dev/test
    if endpoint:
        kwargs["endpoint_url"] = endpoint
        kwargs["aws_access_key_id"]     = "test"
        kwargs["aws_secret_access_key"] = "test"

    return boto3.client(servico, **kwargs)

# Uso — mesmo código em dev e prod
sqs_client = criar_cliente_aws("sqs")
s3_client  = criar_cliente_aws("s3")
```

---

### Infraestrutura como Código — AWS CDK com Java 25

```
Por que CDK Java em vez de TypeScript/YAML:
  ✓ Mesma linguagem do projeto — sem context switch
  ✓ Type safety — erros de infra detectados em compilação
  ✓ Reutilização — Constructs customizados como classes Java normais
  ✓ Testes — CDK assertions com JUnit 5, mesma pipeline CI/CD
  ✓ Records Java 25 — perfeitos para configuração de stacks
```

**pom.xml — Dependências mínimas CDK Java 25:**

```xml
<dependency>
    <groupId>software.amazon.awscdk</groupId>
    <artifactId>aws-cdk-lib</artifactId>
    <version>2.130.0</version>
</dependency>
<dependency>
    <groupId>software.amazon.awscdk</groupId>
    <artifactId>assertions</artifactId>
    <version>2.130.0</version>
    <scope>test</scope>
</dependency>
```

#### Stack 1 — Lambda com SnapStart, VPC, IAM, DLQ, X-Ray

```java
// Java 25 — CDK Lambda Stack com SnapStart
public class PedidoLambdaStack extends Stack {

    record LambdaConfig(
        String functionName,
        String codeLocation,      // S3 bucket com .jar
        int memoryMiB,
        int timeoutSeconds,
        String runtimeVersion     // java25
    ) {
        static LambdaConfig padrao() {
            return new LambdaConfig("pedido-processor", "s3://builds/pedido-lambda.jar",
                512, 60, "java25");
        }
    }

    public PedidoLambdaStack(Construct scope, String id, LambdaConfig config) {
        super(scope, id);

        // VPC compartilhada (Lambda acessa RDS, ElastiCache)
        var vpc = Vpc.Builder.create(this, "LambdaVpc")
            .cidr("10.0.0.0/16")
            .maxAzs(2)
            .natGateways(1)
            .build();

        // Security group para Lambda
        var sgLambda = SecurityGroup.Builder.create(this, "LambdaSg")
            .vpc(vpc)
            .allowAllOutbound(true)
            .build();

        // IAM role com permissões mínimas
        var lambdaRole = Role.Builder.create(this, "LambdaRole")
            .assumedBy(new ServicePrincipal("lambda.amazonaws.com"))
            .managedPolicies(List.of(
                ManagedPolicy.fromAwsManagedPolicyName("service-role/AWSLambdaVPCAccessExecutionRole")
            ))
            .build();

        // SQS DLQ para retries falhados
        var dlq = Queue.Builder.create(this, "PedidoDLQ")
            .queueName("pedido-processor-dlq")
            .retentionPeriod(Duration.days(14))
            .build();

        // Lambda function — SnapStart elimina cold start
        var lambdaFunction = Function.Builder.create(this, "PedidoFunction")
            .runtime(Runtime.JAVA_25)
            .code(Code.fromAsset(config.codeLocation()))
            .handler("org.springframework.cloud.function.adapter.aws.FunctionInvoker::handleRequest")
            .role(lambdaRole)
            .memorySize(config.memoryMiB())
            .timeout(Duration.seconds(config.timeoutSeconds()))
            .vpc(vpc)
            .vpcSubnets(SubnetSelection.builder().subnetType(SubnetType.PRIVATE_WITH_NAT).build())
            .securityGroups(List.of(sgLambda))
            .deadLetterQueue(dlq)
            .snapStart(SnapStartConf.ON)  // ← Ativa SnapStart (zero config)
            .tracingConfig(TracingConfig.ACTIVE)  // X-Ray automático
            .onFailure(new SqsQueue(dlq))
            .environment(Map.of(
                "SPRING_PROFILES_ACTIVE", "aws",
                "AWS_XRAY_SDK_ENABLED", "true"
            ))
            .build();

        // CloudWatch log group com retention
        var logGroup = LogGroup.Builder.create(this, "LambdaLogs")
            .logGroupName("/aws/lambda/" + config.functionName())
            .retention(RetentionDays.ONE_MONTH)
            .build();

        // SQS trigger
        var sourceQueue = Queue.Builder.create(this, "PedidoQueue")
            .queueName("pedido-requests")
            .deadLetterQueue(DeadLetterQueue.builder()
                .queue(dlq)
                .maxReceiveCount(3)
                .build())
            .build();

        lambdaFunction.addEventSourceMapping("SqsEventSource",
            EventSourceMappingOptions.builder()
                .eventSourceId("pedido-queue")
                .batchSize(10)
                .maxConcurrency(25)  // Virtual Threads
                .reportBatchItemFailures(true)
                .build());
    }
}
```

#### Stack 2 — ECS Fargate com ALB, Health Checks, Auto-scaling, SQS

```java
// Java 25 — CDK ECS Fargate Stack com Spring Boot 4
public class PedidoEcsFargateStack extends Stack {

    record EcsConfig(
        String serviceName,
        String dockerImage,
        int cpu,           // 256 = 0.25 vCPU
        int memoryMiB,
        int desiredCount,
        int containerPort
    ) {
        static EcsConfig padrao() {
            return new EcsConfig("pedido-api",
                "123.dkr.ecr.us-east-1.amazonaws.com/pedido-api:latest",
                256, 512, 2, 8080);
        }
    }

    public PedidoEcsFargateStack(Construct scope, String id, EcsConfig config) {
        super(scope, id);

        // VPC
        var vpc = Vpc.Builder.create(this, "EcsVpc")
            .maxAzs(2)
            .natGateways(1)
            .build();

        // ECS Cluster
        var cluster = Cluster.Builder.create(this, "EcsCluster")
            .vpc(vpc)
            .containerInsights(true)  // CloudWatch metrics
            .build();

        // Security group com ALB
        var sgEcs = SecurityGroup.Builder.create(this, "EcsSg")
            .vpc(vpc)
            .allowAllOutbound(true)
            .build();
        sgEcs.addIngressRule(Peer.anyIpv4(), Port.tcp(config.containerPort()),
            "Allow container port");

        // CloudWatch log group
        var logGroup = LogGroup.Builder.create(this, "EcsLogs")
            .logGroupName("/ecs/" + config.serviceName())
            .retention(RetentionDays.ONE_WEEK)
            .build();

        // Fargate service com ALB
        var service = ApplicationLoadBalancedFargateService.Builder
            .create(this, "FargateService")
            .cluster(cluster)
            .cpu(config.cpu())
            .memoryLimitMiB(config.memoryMiB())
            .desiredCount(config.desiredCount())
            .serviceName(config.serviceName())
            .taskImageOptions(ApplicationLoadBalancedTaskImageOptions.builder()
                .image(ContainerImage.fromRegistry(config.dockerImage()))
                .containerPort(config.containerPort())
                .environment(Map.of(
                    "SPRING_PROFILES_ACTIVE", "aws",
                    "JAVA_TOOL_OPTIONS", "-XX:+UseZGC -XX:+ZGenerational"
                ))
                .logDriver(LogDriver.awsLogs(AwsLogDriverProps.builder()
                    .logGroup(logGroup)
                    .streamPrefix("ecs")
                    .build()))
                .build())
            .healthCheckGracePeriod(Duration.seconds(60))
            .publicLoadBalancer(true)
            .build();

        // Health check via Spring Boot Actuator
        service.getTargetGroup().configureHealthCheck(HealthCheck.builder()
            .path("/actuator/health/liveness")
            .healthyHttpCodes("200")
            .interval(Duration.seconds(30))
            .timeout(Duration.seconds(5))
            .healthyThresholdCount(2)
            .unhealthyThresholdCount(2)
            .build());

        // Auto-scaling por CPU
        var scaling = service.getService().autoScaleTaskCount(
            EnableScalingProps.builder()
                .minCapacity(1)
                .maxCapacity(4)
                .build()
        );
        scaling.scaleOnCpuUtilization("CpuScaling",
            CpuUtilizationScalingProps.builder()
                .targetUtilizationPercent(70)
                .build());

        // Auto-scaling por SQS queue depth (pedidos em processamento)
        var sqs = Queue.Builder.create(this, "PedidoQueue")
            .queueName("pedido-processamento")
            .build();

        scaling.scaleOnMetric("QueueDepthScaling",
            ScalingTarget.scaleOnMetric(
                metric: new Metric(MetricProps.builder()
                    .namespace("AWS/SQS")
                    .metricName("ApproximateNumberOfMessagesVisible")
                    .dimensions(Map.of("QueueName", sqs.getQueueName()))
                    .statistic("Average")
                    .period(Duration.minutes(5))
                    .build()),
                targetValue: 10  // 10 mensagens por task
            ));
    }
}
```

#### Stack 3 — RDS Postgres com Read Replica Cross-Region, Secrets Manager

```java
// Java 25 — CDK RDS Stack com multi-AZ, cross-region replica
public class RdsPostgresStack extends Stack {

    record RdsConfig(
        String dbName,
        int allocatedStorageGb,
        String instanceClass,  // db.t3.micro, db.t3.small
        String masterUsername
    ) {
        static RdsConfig padrao() {
            return new RdsConfig("pedidodb", 20, "t3.micro", "postgres");
        }
    }

    public RdsPostgresStack(Construct scope, String id, RdsConfig config) {
        super(scope, id);

        // VPC para RDS
        var vpc = Vpc.Builder.create(this, "RdsVpc")
            .maxAzs(2)
            .natGateways(0)  // RDS não precisa NAT
            .build();

        // Security group
        var sgRds = SecurityGroup.Builder.create(this, "RdsSg")
            .vpc(vpc)
            .allowAllOutbound(true)
            .build();
        sgRds.addIngressRule(Peer.anyIpv4(), Port.tcp(5432), "PostgreSQL");

        // Secrets Manager — senha gerenciada automaticamente
        var secret = Secret.Builder.create(this, "DbSecret")
            .secretName("rds/pedido-db-password")
            .generateSecretString(SecretStringGenerator.builder()
                .secretStringTemplate(
                    "{\"username\": \"" + config.masterUsername() + "\"}")
                .generateStringKey("password")
                .excludeCharacters("/@\\")
                .passwordLength(32)
                .build())
            .build();

        // Primary RDS — Multi-AZ
        var primaryDb = DatabaseInstance.Builder.create(this, "PrimaryDb")
            .engine(DatabaseInstanceEngine.postgres(
                PostgresEngineProps.builder().version(EngineVersion.of("16", "1")).build()))
            .instanceType(InstanceType.of(InstanceClass.T3, InstanceSize.MICRO))
            .allocatedStorage(config.allocatedStorageGb())
            .databaseName(config.dbName())
            .credentials(Credentials.fromSecret(secret))
            .multiAz(true)  // HA automática
            .vpc(vpc)
            .storageEncrypted(true)
            .backupRetention(Duration.days(7))
            .preferredBackupWindow("03:00-04:00")
            .preferredMaintenanceWindow("sun:04:00-sun:05:00")
            .removalPolicy(RemovalPolicy.SNAPSHOT)  // Snapshot antes de deletar
            .securityGroups(List.of(sgRds))
            .publiclyAccessible(false)
            .iamDatabaseAuthenticationEnabled(true)  // IAM auth via role
            .build();

        // Cross-region read replica (us-west-2)
        var replicaVpc = Vpc.Builder.create(this, "ReplicaVpc")
            .cidr("10.1.0.0/16")
            .maxAzs(2)
            .build();

        var replicaSg = SecurityGroup.Builder.create(this, "ReplicaSg")
            .vpc(replicaVpc)
            .build();
        replicaSg.addIngressRule(Peer.ipv4("10.0.0.0/8"), Port.tcp(5432));

        var readReplica = primaryDb.addReadReplica("ReadReplica",
            ReadReplicaProps.builder()
                .region("us-west-2")  // Cross-region
                .vpc(replicaVpc)
                .multiAz(false)  // Dev: single AZ suficiente
                .publiclyAccessible(false)
                .securityGroup(replicaSg)
                .build());

        // CloudWatch alarms
        Alarm.Builder.create(this, "DatabaseCpuAlarm")
            .metric(primaryDb.metricCPUUtilization())
            .threshold(80)
            .evaluationPeriods(2)
            .alarmName("RDS-Pedido-CPU-High")
            .treatMissingData(TreatMissingData.NOT_BREACHING)
            .build();

        Alarm.Builder.create(this, "ReplicationLagAlarm")
            .metric(readReplica.metricReplicationLag())
            .threshold(30)  // 30 segundos
            .evaluationPeriods(1)
            .alarmName("RDS-ReadReplica-Lag-High")
            .build();
    }
}
```

#### Teste de Infrastructure com CDK Assertions

```java
// Java 25 — Teste de CDK Stack com JUnit 5
public class RdsPostgresStackTest {

    @Test
    void shouldCreateMultiAzDatabase() {
        // Arrange
        var stack = new Stack();
        new RdsPostgresStack(stack, "TestStack", RdsConfig.padrao());

        // Act & Assert
        var template = Template.fromStack(stack);

        // Verifica que RDS existe com Multi-AZ
        template.hasResourceProperties("AWS::RDS::DBInstance", Map.of(
            "MultiAZ", true,
            "DBName", "pedidodb",
            "Engine", "postgres"
        ));

        // Verifica que Secret Manager foi criado
        template.resourceCountIs("AWS::SecretsManager::Secret", 1);

        // Verifica que backup está configurado
        template.hasResourceProperties("AWS::RDS::DBInstance",
            Match.objectLike(Map.of(
                "BackupRetentionPeriod", 7
            )));

        // Verifica que replicação foi criada
        template.hasResourceProperties("AWS::RDS::DBInstance",
            Match.objectLike(Map.of(
                "SourceDBInstanceIdentifier", Match.stringLikeRegexp("PrimaryDb.*")
            )));
    }

    @Test
    void shouldHaveCloudWatchAlarms() {
        var stack = new Stack();
        new RdsPostgresStack(stack, "TestStack", RdsConfig.padrao());

        var template = Template.fromStack(stack);

        // Verifica alarms
        template.resourceCountIs("AWS::CloudWatch::Alarm", 2);
        template.hasResourceProperties("AWS::CloudWatch::Alarm", Map.of(
            "AlarmName", "RDS-Pedido-CPU-High",
            "Threshold", 80
        ));
    }
}
```

**Ciclo típico CDK em CI/CD:**

```bash
# Desenvolvimento local
cdk diff                  # Mostra mudanças de infra

# No PR — validação automática
cdk synth                 # Gera CloudFormation
mvn test -Dtest=*StackTest  # Testa assertions

# Deploy em CD
cdk deploy --require-approval=never  # Staging/Prod
```

**Benefícios da abordagem CDK Java 25:**
- ✓ **Type safety**: Erros de config detectados em compilação
- ✓ **Reuso via constructs**: Classes Java compartilhadas entre stacks
- ✓ **Testes nativos**: JUnit 5 + CDK assertions
- ✓ **Versionamento**: IaC vive no mesmo repo que código
- ✓ **Context values**: Parametrização por environment (dev/staging/prod)

---

