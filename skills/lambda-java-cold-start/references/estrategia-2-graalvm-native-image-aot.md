# lambda-java-cold-start · Estratégia 2: GraalVM Native Image (AOT)

> Reference da skill `lambda-java-cold-start` (movida da SKILL.md em 11/10/2026 — hub + references, I3). Carregue só quando a tarefa pedir este tema.

## Estratégia 2: GraalVM Native Image (AOT)

### Quando Usar

- SLA < 200ms de cold start
- Spring Boot 4 / Quarkus / Micronaut (suporte AOT first-class)
- Deploy de baixa frequência (build nativo demora 5-15min)
- Funções sem reflexão dinâmica não registrada

### Métricas Reais (Java 25 + Spring Boot 4, 2026)

| Cenário | JVM | SnapStart | Native (GraalVM 22+) |
|---|---|---|---|
| Lambda 256MB, arm64 | 3-5s | 300-500ms | 50-120ms |
| Lambda 512MB, arm64 | 2-4s | 250-400ms | 40-100ms |
| Lambda 1024MB, arm64 | 1.5-3s | 200-350ms | 30-80ms |

### Setup Maven

```xml
<!-- pom.xml -->
<profiles>
    <profile>
        <id>native</id>
        <properties>
            <repackage.classifier>exec</repackage.classifier>
            <native-buildtools.version>1.1.3</native-buildtools.version>
        </properties>
        <build>
            <plugins>
                <plugin>
                    <groupId>org.graalvm.buildtools</groupId>
                    <artifactId>native-maven-plugin</artifactId>
                    <version>${native-buildtools.version}</version>
                    <configuration>
                        <imageName>bootstrap</imageName>
                        <buildArgs>
                            <buildArg>--no-fallback</buildArg>
                            <buildArg>--enable-url-protocols=https</buildArg>
                            <buildArg>-O2</buildArg>
                            <!-- NAO usar como default cego: -O3/PGO sao Oracle GraalVM apenas
                                 (no-op no CE); --enable-preview so se o codigo usa feature preview
                                 do JDK; -H:+UnlockExperimentalVMOptions so junto da opcao -H:
                                 experimental especifica que o exige. Ver
                                 aws-lambda-java25-aot/references/graalvm-native-java25-sota.md -->
                        </buildArgs>
                    </configuration>
                    <executions>
                        <execution>
                            <goals>
                                <goal>compile-no-fork</goal>
                            </goals>
                            <phase>package</phase>
                        </execution>
                    </executions>
                </plugin>
            </plugins>
        </build>
    </profile>
</profiles>
```

### reflect-config.json obrigatório

```json
[
  {
    "name": "com.empresa.model.Order",
    "allDeclaredFields": true,
    "allDeclaredMethods": true,
    "allDeclaredConstructors": true
  },
  {
    "name": "software.amazon.awssdk.enhanced.dynamodb.mapper.BeanTableSchema",
    "allDeclaredMethods": true
  },
  {
    "name": "com.fasterxml.jackson.databind.ObjectMapper",
    "allDeclaredFields": true,
    "allDeclaredMethods": true,
    "allDeclaredConstructors": true
  }
]
```

```java
// Alternativa: RuntimeHints programático (Spring Boot 4)
@Component
public class NativeHints implements RuntimeHintsRegistrar {

    @Override
    public void registerHints(RuntimeHints hints, ClassLoader classLoader) {
        hints.reflection()
            .registerType(Order.class,
                MemberCategory.INVOKE_DECLARED_CONSTRUCTORS,
                MemberCategory.INVOKE_DECLARED_METHODS,
                MemberCategory.DECLARED_FIELDS)
            .registerType(Customer.class,
                MemberCategory.INVOKE_DECLARED_CONSTRUCTORS,
                MemberCategory.INVOKE_DECLARED_METHODS,
                MemberCategory.DECLARED_FIELDS);
    }
}
```

### SAM template para Native

```yaml
Globals:
  Function:
    Runtime: provided.al2023   # Custom runtime para binário nativo
    Architectures: [arm64]     # GraalVM nativo no arm64 tem cold start menor

Resources:
  ApiFunction:
    Type: AWS::Serverless::Function
    Metadata:
      BuildMethod: makefile      # SAM usa Makefile para build custom
    Properties:
      CodeUri: ./
      Handler: bootstrap

# Makefile target obrigatório
# build-ApiFunction:
#   mvn -Pnative native:compile -DskipTests
#   cp target/bootstrap $(ARTIFACTS_DIR)/bootstrap
```

### Debugging de falhas nativas

```bash
# Passo 1: Identifique a classe faltante no log
# Erro típico: MissingReflectionRegistrationError: 
#   com.empresa.model.Order accessed for reflective instantiation

# Passo 2: Use o tracing agent para capturar reflexão em runtime
java -agentlib:native-image-agent=config-output-dir=src/main/resources/META-INF/native-image \
     -jar target/app.jar

# Execute casos de uso representativos, depois compile nativo
mvn -Pnative native:compile
```
