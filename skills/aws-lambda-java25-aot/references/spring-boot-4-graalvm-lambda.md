# Spring Boot 4 + GraalVM Native Image em AWS Lambda

Configuração de AOT (Ahead-of-Time) compilation para gerar binários nativos
com cold start sub-100ms na AWS Lambda.

## Índice

1. [Por que AOT em Lambda](#por-que-aot-em-lambda)
2. [Custom Runtime al2023 + bootstrap](#custom-runtime-al2023--bootstrap)
3. [pom.xml — profile native completo](#pomxml--profile-native-completo)
4. [application.properties para Lambda](#applicationproperties-para-lambda)
5. [RuntimeHints e reflect-config](#runtimehints-e-reflect-config)
6. [Spring Cloud Function Adapter for AWS](#spring-cloud-function-adapter-for-aws)
7. [Build local + sam build com container](#build-local--sam-build-com-container)
8. [Debugging native build failures](#debugging-native-build-failures)
9. [Otimizações de cold start](#otimizações-de-cold-start)

## Por que AOT em Lambda

JIT em Lambda nunca chega ao steady-state. A Lambda é desligada após
~5-15 minutos de idle, então cada invocação fria volta a interpretar
bytecode. AOT elimina esse problema: o binário já está compilado para
máquina, não há classloading dinâmico, beans Spring são inicializados
em build-time via AOT processing.

Ganhos típicos com Spring Boot 4 + GraalVM em Lambda:

| Métrica | JIT (provided.al2) | Native (provided.al2023) |
|---|---|---|
| Cold start | 2.5–5s | 80–150ms |
| Memória mínima | 512MB | 128–256MB |
| Tempo de execução estável | ~similar (JIT um pouco melhor após warmup) | ~similar |
| Tamanho do package | 20–80MB | 30–60MB |

## Custom Runtime al2023 + bootstrap

GraalVM gera um binário ELF Linux. AWS Lambda Java runtime padrão
(`java21`) espera classpath, não suporta binário direto. A solução é
**Custom Runtime al2023**: você empacota seu próprio executável chamado
`bootstrap` num zip, configura `Runtime: provided.al2023` no SAM, e o
Lambda invoca o bootstrap via Runtime API.

Estrutura do zip:

```
function.zip
└── bootstrap          (binário ELF executável, gerado pelo native-image)
```

O `Makefile` que a skill gera tem este target:

```makefile
build-ApiGatewayFunction:
	mvn -Pnative native:compile -DskipTests
	cp target/bootstrap $(ARTIFACTS_DIR)/bootstrap
	chmod +x $(ARTIFACTS_DIR)/bootstrap
```

## pom.xml — profile native completo

Template canônico para Spring Boot 4 + Native + AWS Lambda:

```xml
<project>
  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>4.0.0</version>
  </parent>

  <properties>
    <java.version>25</java.version>
    <spring-cloud-function.version>4.3.0</spring-cloud-function.version>
    <aws-lambda-events.version>3.13.0</aws-lambda-events.version>
    <aws-sdk.version>2.30.0</aws-sdk.version>
    <powertools.version>1.20.0</powertools.version>
  </properties>

  <dependencies>
    <!-- Spring Boot 4 + Cloud Function adapter for AWS -->
    <dependency>
      <groupId>org.springframework.cloud</groupId>
      <artifactId>spring-cloud-function-adapter-aws</artifactId>
    </dependency>
    <dependency>
      <groupId>org.springframework.cloud</groupId>
      <artifactId>spring-cloud-function-context</artifactId>
    </dependency>

    <!-- AWS Lambda events models (APIGatewayV2, DynamoDB Streams) -->
    <dependency>
      <groupId>com.amazonaws</groupId>
      <artifactId>aws-lambda-java-events</artifactId>
      <version>${aws-lambda-events.version}</version>
    </dependency>
    <dependency>
      <groupId>com.amazonaws</groupId>
      <artifactId>aws-lambda-java-core</artifactId>
      <version>1.2.3</version>
    </dependency>

    <!-- AWS SDK v2 — DynamoDB Enhanced Client -->
    <dependency>
      <groupId>software.amazon.awssdk</groupId>
      <artifactId>dynamodb-enhanced</artifactId>
      <version>${aws-sdk.version}</version>
    </dependency>
    <dependency>
      <groupId>software.amazon.awssdk</groupId>
      <artifactId>url-connection-client</artifactId>
      <version>${aws-sdk.version}</version>
    </dependency>

    <!-- Lambda PowerTools — observability + idempotency -->
    <dependency>
      <groupId>software.amazon.lambda</groupId>
      <artifactId>powertools-logging</artifactId>
      <version>${powertools.version}</version>
    </dependency>
    <dependency>
      <groupId>software.amazon.lambda</groupId>
      <artifactId>powertools-metrics</artifactId>
      <version>${powertools.version}</version>
    </dependency>
    <dependency>
      <groupId>software.amazon.lambda</groupId>
      <artifactId>powertools-tracing</artifactId>
      <version>${powertools.version}</version>
    </dependency>

    <!-- Test deps: JUnit 5, Testcontainers (LocalStack), RestTestClient -->
    <dependency>
      <groupId>org.testcontainers</groupId>
      <artifactId>localstack</artifactId>
      <version>1.20.4</version>
      <scope>test</scope>
    </dependency>
  </dependencies>

  <build>
    <plugins>
      <plugin>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-maven-plugin</artifactId>
      </plugin>
    </plugins>
  </build>

  <profiles>
    <profile>
      <id>native</id>
      <build>
        <plugins>
          <plugin>
            <groupId>org.graalvm.buildtools</groupId>
            <artifactId>native-maven-plugin</artifactId>
            <configuration>
              <imageName>bootstrap</imageName>
              <buildArgs>
                <buildArg>--no-fallback</buildArg>
                <buildArg>--enable-url-protocols=http,https</buildArg>
                <buildArg>-H:+ReportExceptionStackTraces</buildArg>
                <buildArg>--initialize-at-build-time=org.slf4j.LoggerFactory</buildArg>
              </buildArgs>
            </configuration>
          </plugin>
        </plugins>
      </build>
    </profile>
  </profiles>
</project>
```

Pontos críticos:

- `<imageName>bootstrap</imageName>` — o binário precisa se chamar `bootstrap`
  para o Custom Runtime al2023 reconhecê-lo.
- `--no-fallback` — falha se reflect-config estiver incompleto. Sem isso,
  GraalVM gera um fallback JIT que destrói o cold start.
- `url-connection-client` em vez de `apache-client` — sem dependências
  pesadas (Netty, Apache HttpClient), AOT-friendly.
- Lambda PowerTools tem hints AOT registrados internamente; o SDK v2
  também — mas suas entidades **não**, daí a necessidade de
  `RuntimeHints` próprios.

## application.properties para Lambda

```properties
# Spring Boot — desabilita web server (Lambda não roda HTTP server interno)
spring.main.web-application-type=none

# Virtual threads — JDK 25 (auto-config no Spring Boot 4)
spring.threads.virtual.enabled=true

# Banner off — economiza ~50ms no cold start
spring.main.banner-mode=off

# Spring Cloud Function — declara a function bean default
spring.cloud.function.definition=apiGatewayHandler

# Lambda PowerTools
powertools.logger.log-event=true
powertools.metrics.namespace=${SAM_LOCAL:false:?MyApp}
powertools.tracing.service=${POWERTOOLS_SERVICE_NAME:lambda-java}

# AWS region — ler do env LAMBDA_AWS_REGION ou AWS_REGION
aws.region=${AWS_REGION:us-east-1}
```

## RuntimeHints e reflect-config

GraalVM precisa saber em build-time quais classes serão acessadas via
reflection em runtime. Spring AOT processing detecta a maioria
automaticamente, mas DynamoDB Enhanced Client + suas entidades exigem
declaração manual.

**Padrão recomendado**: classe `NativeHints` com
`@RegisterReflectionForBinding`:

```java
package com.example.config;

import org.springframework.aot.hint.MemberCategory;
import org.springframework.aot.hint.RuntimeHints;
import org.springframework.aot.hint.RuntimeHintsRegistrar;
import org.springframework.context.annotation.ImportRuntimeHints;
import org.springframework.boot.SpringBootApplication;

import com.example.model.User;
import com.example.model.Order;
import com.example.model.OrderItem;

@SpringBootApplication
@ImportRuntimeHints(NativeHints.class)
public class Application implements RuntimeHintsRegistrar {

    @Override
    public void registerHints(RuntimeHints hints, ClassLoader classLoader) {
        // Entidades — reflection completa para Enhanced Client deserialização
        for (Class<?> entity : new Class<?>[]{ User.class, Order.class, OrderItem.class }) {
            hints.reflection().registerType(
                entity,
                MemberCategory.INVOKE_DECLARED_CONSTRUCTORS,
                MemberCategory.DECLARED_FIELDS,
                MemberCategory.INVOKE_DECLARED_METHODS
            );
        }

        // BeanTableSchema usa proxy + introspection do Enhanced Client
        hints.reflection().registerType(
            software.amazon.awssdk.enhanced.dynamodb.mapper.BeanTableSchema.class,
            MemberCategory.INVOKE_DECLARED_METHODS
        );
    }
}
```

Alternativa equivalente via `reflect-config.json` em
`src/main/resources/META-INF/native-image/<group>/<artifact>/reflect-config.json`:

```json
[
  {
    "name": "com.example.model.User",
    "allDeclaredConstructors": true,
    "allDeclaredFields": true,
    "allDeclaredMethods": true
  },
  {
    "name": "com.example.model.Order",
    "allDeclaredConstructors": true,
    "allDeclaredFields": true,
    "allDeclaredMethods": true
  }
]
```

A skill gera ambos — `RuntimeHints` para legibilidade, `reflect-config.json`
para garantia em casos onde o AOT processing não pegou tudo.

## Spring Cloud Function Adapter for AWS

Para evitar Spring Web MVC dentro da Lambda (overhead alto), use
`spring-cloud-function-adapter-aws`. O handler é declarado como bean
`Function<Input, Output>`:

```java
@Configuration
public class Handlers {

    @Bean
    public Function<APIGatewayV2HTTPEvent, APIGatewayV2HTTPResponse> apiGatewayHandler(
            UserService userService) {
        return event -> {
            String userId = event.getPathParameters().get("id");
            User user = userService.findById(userId);
            return APIGatewayV2HTTPResponse.builder()
                .withStatusCode(200)
                .withBody(JsonMapper.toJson(user))
                .build();
        };
    }
}
```

A `template.yaml` aponta para o adapter como handler:

```yaml
Handler: org.springframework.cloud.function.adapter.aws.FunctionInvoker
```

## Build local + sam build com container

Para garantir que o binário ELF é compatível com al2023, **sempre** rode
`sam build --use-container`. Isso compila dentro de um container Amazon
Linux 2023 com GraalVM, evitando incompatibilidades de glibc/musl.

Comandos canônicos:

```bash
# build local (rápido, mas binário pode não rodar em al2023 se host for Mac/Win)
mvn -Pnative native:compile

# build via SAM container (lento, mas garantidamente compatível com al2023)
sam build --use-container --container-env-var-file env.json

# rodar localmente com SAM
sam local invoke ApiGatewayFunction --event events/get-user.json

# deploy
sam deploy --guided    # primeira vez
sam deploy             # subsequentes
```

## Debugging native build failures

Erros comuns e como resolver:

### `ClassNotFoundException` em runtime nativo

Causa: lib usa `Class.forName()` dinâmico não registrado.

Solução: rode com tracing agent para descobrir, depois adicione ao reflect-config.

```bash
# Compila JAR normal
mvn package

# Roda com tracing agent
java -agentlib:native-image-agent=config-output-dir=src/main/resources/META-INF/native-image \
     -jar target/app.jar

# Execute cenários representativos (test endpoints, batch process, etc.)
# O agent grava reflect-config.json + resource-config.json automaticamente.

# Recompila nativo
mvn -Pnative native:compile
```

### `MissingResourceException` para arquivos `.properties` ou templates

Causa: GraalVM não inclui resources por default.

Solução: `resource-config.json`:

```json
{
  "resources": {
    "includes": [
      { "pattern": "META-INF/spring.factories" },
      { "pattern": "application.properties" },
      { "pattern": "application-.*.properties" }
    ]
  }
}
```

### Binário gera segfault em Lambda mas funciona local

Causa: glibc do host ≠ glibc al2023.

Solução: **sempre** `sam build --use-container`. Se não quiser SAM,
compile dentro do container:

```bash
docker run --rm -v "$(pwd)":/work -w /work \
  public.ecr.aws/sam/build-provided.al2023:latest \
  mvn -Pnative native:compile
```

### `--initialize-at-build-time` errors

GraalVM tenta inicializar classes em build-time para reduzir runtime.
Algumas (Logback, classes com `static {}` dependentes de runtime) precisam
ser explicitamente `--initialize-at-run-time`:

```xml
<buildArg>--initialize-at-run-time=ch.qos.logback.classic.Logger</buildArg>
```

## Otimizações de cold start

Lista priorizada (maior impacto no topo):

1. **Custom Runtime al2023 + arm64** — graviton ARM tem cold start 20% menor
   que x86_64 em workloads I/O-bound.
2. **`spring.main.banner-mode=off`** — economiza 30-80ms.
3. **Memory size 512MB-1024MB** — Lambda dá CPU proporcional à memória; 128MB
   é falsa economia, eleva cold start.
4. **PGO (Profile-Guided Optimization)** — Oracle GraalVM Enterprise. Compila
   com perfis de execução real, ganhos de 15-25% em cold start. Não está
   disponível na Community Edition.
5. **`--gc=epsilon`** — desativa GC para Lambdas de execução curta (<100ms).
   Lambda é descartada antes de precisar coletar lixo. Reduz binário e
   startup. Requer cuidado com long-running invocations.
6. **`--strict-image-heap`** — aumenta tempo de build mas reduz tamanho do
   binário e melhora startup ~5%.
7. **Provisioned Concurrency** — paga para manter N instâncias quentes.
   Custo adicional, mas elimina cold start completamente. Use quando SLO
   exige p99 < 50ms.
