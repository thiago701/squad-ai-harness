# GraalVM Native Image — Guia de Produção

## Benchmarks Reais (Spring Boot 4 + Java 25)

| Métrica | JVM (G1GC) | Native Image |
|---------|-----------|-------------|
| Startup | 2-4s | 50-200ms |
| Memória RSS | 300-500MB | 50-100MB |
| Peak throughput | 100% (baseline) | ~85% |
| Build time | 10-30s | 3-10min |
| Tamanho binário | JRE + JARs (~200MB) | 50-120MB (single binary) |

## Quando Native Image Compensa

### Sim:
- AWS Lambda / Azure Functions / Google Cloud Functions
- Kubernetes com scale-to-zero (KEDA)
- CLI tools (startup instantâneo)
- Ambientes com billing por memória/CPU (redução de 60-85% custo)
- Microserviços com deploy frequente

### Não:
- Monólitos de longa duração (JIT otimiza melhor ao longo do tempo)
- Aplicações CPU-bound que precisam de peak throughput
- Protótipos/MVPs (tempo de build nativo é alto)
- Heavy use de reflection dinâmica (classloading runtime)

## Configuração Completa

### Apache Maven 4 (padrão da squad)
```xml
<!-- pom.xml — profile nativo com Maven 4 (model 4.1.0) -->
<profiles>
    <profile>
        <id>native</id>
        <build>
            <plugins>
                <plugin>
                    <groupId>org.graalvm.buildtools</groupId>
                    <artifactId>native-maven-plugin</artifactId>
                    <configuration>
                        <buildArgs>
                            <arg>--no-fallback</arg>
                            <arg>-O2</arg>
                            <arg>-H:+ReportExceptionStackTraces</arg>
                            <!-- NAO usar como default cego (a imagem native-image-community abaixo e CE):
                                 --gc=G1 e -O3/PGO sao Oracle GraalVM APENAS (no CE falham/no-op) — para
                                 workload efemero/serverless o Serial GC (default) e o certo de qualquer forma.
                                 -march=native so se build e runtime sao a MESMA CPU (perigoso em CI x86 ->
                                 Graviton; use -march=compatibility p/ portabilidade). Ver
                                 aws-lambda-java25-aot/references/graalvm-native-java25-sota.md -->
                        </buildArgs>
                    </configuration>
                    <executions>
                        <execution>
                            <id>build-native</id>
                            <phase>package</phase>
                            <goals>
                                <goal>compile-no-fork</goal>
                            </goals>
                        </execution>
                    </executions>
                </plugin>
            </plugins>
        </build>
    </profile>
</profiles>
```

Build nativo paralelizado com `mvnd`:
```bash
mvnd -Pnative -T 1C native:compile
```

## AOT Processing do Spring Boot 4

Spring Boot 4 executa AOT processing automaticamente durante a compilação nativa:
- Beans são resolvidos em tempo de compilação
- Configuration properties são validadas
- Proxy classes são geradas antecipadamente
- Reflection hints são coletados automaticamente

### Registrando Hints Manualmente

Para código que usa reflection não detectável pelo AOT engine:

```java
@RegisterReflectionForBinding({
    MyDto.class,
    MyResponse.class
})
@Configuration
public class NativeConfig {
}

// Ou via RuntimeHintsRegistrar para casos mais complexos:
public class MyRuntimeHints implements RuntimeHintsRegistrar {
    @Override
    public void registerHints(RuntimeHints hints, ClassLoader classLoader) {
        hints.reflection().registerType(MyDynamicClass.class,
            MemberCategory.INVOKE_PUBLIC_METHODS,
            MemberCategory.INVOKE_PUBLIC_CONSTRUCTORS);

        hints.resources().registerPattern("templates/*.html");
    }
}
```

## Tracing Agent — Workflow

```bash
# 1. Compile normalmente
./mvnw package -DskipTests

# 2. Execute com o tracing agent sob carga representativa
java -agentlib:native-image-agent=config-output-dir=src/main/resources/META-INF/native-image \
     -jar target/app.jar &

# 3. Execute cenários (testes de integração, requests manuais, etc.)
curl http://localhost:8080/api/users
curl -X POST http://localhost:8080/api/orders -H 'Content-Type: application/json' -d '{...}'

# 4. Pare a aplicação — configs são geradas automaticamente

# 5. Compile nativo
./mvnw -Pnative native:compile

# 6. SEMPRE teste em modo nativo antes de deploy
./mvnw -Pnative native:test
```

## Dockerfile Multi-stage para Native Image

```dockerfile
# Stage 1: Build
FROM ghcr.io/graalvm/native-image-community:25 AS builder
WORKDIR /app
COPY . .
RUN ./mvnw -Pnative native:compile -DskipTests

# Stage 2: Runtime (distroless para segurança)
FROM gcr.io/distroless/base-nossl-debian12
COPY --from=builder /app/target/app /app
EXPOSE 8080
ENTRYPOINT ["/app"]
```

Resultado: imagem Docker de ~80MB com startup < 100ms.

## Troubleshooting Comum

### ClassNotFoundException em runtime nativo
Causa: classe acessada via reflection não registrada.
Solução: Adicionar `@RegisterReflectionForBinding` ou usar tracing agent.

### Serialization issues com Jackson 3
Causa: Jackson 3 usa patterns diferentes de reflection.
Solução: Spring Boot 4 AOT já cobre a maioria dos casos. Para DTOs custom,
use `@RegisterReflectionForBinding`.

### Native test failures
Causa: Testcontainers ou mocks que dependem de dynamic proxy.
Solução: Separar testes nativos dos testes que precisam de mocking dinâmico.
Use `@DisabledInNativeImage` para testes incompatíveis.

## Monitoramento de Native Images

```properties
# Habilitar JFR em native image
-XX:+FlightRecorder
-XX:StartFlightRecording=filename=recording.jfr,duration=60s

# Métricas de memória nativa
management.endpoints.web.exposure.include=health,info,metrics,prometheus
management.metrics.tags.application=${spring.application.name}
```
