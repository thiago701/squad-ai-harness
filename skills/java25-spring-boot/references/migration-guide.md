# Guia de Migração: Spring Boot 3.x → 4.0

## Pré-requisitos

- JDK 17+ (mínimo), JDK 25 recomendado
- **Apache Maven 4.0.0+** (padrão da squad — use `mvnup` para migrar POMs antigos)
- Migrar primeiro para Spring Boot 3.5.x antes de ir para 4.0

## 1. Atualizações de Dependência

### pom.xml (Apache Maven 4, modelo 4.1.0)
```xml
<project xmlns="http://maven.apache.org/POM/4.1.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.1.0
                             http://maven.apache.org/xsd/maven-4.1.0.xsd"
         root="true">

    <modelVersion>4.1.0</modelVersion>

    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>4.0.5</version>
    </parent>

    <groupId>com.squad</groupId>
    <artifactId>app</artifactId>
    <version>${revision}</version>

    <properties>
        <revision>1.0.0-SNAPSHOT</revision>
        <java.version>25</java.version>
        <maven.compiler.release>25</maven.compiler.release>
        <!-- Consumer POM: publica versão flattened no repositório -->
        <maven.consumer.pom.flatten>true</maven.consumer.pom.flatten>
    </properties>
</project>
```

### .mvn/extensions.xml — Build Cache Extension
```xml
<extensions xmlns="http://maven.apache.org/EXTENSIONS/1.2.0">
    <extension>
        <groupId>org.apache.maven.extensions</groupId>
        <artifactId>maven-build-cache-extension</artifactId>
        <version>1.2.0</version>
    </extension>
</extensions>
```

### .mvn/maven.config — Defaults de build
```
-T 1C
--batch-mode
--no-transfer-progress
```

## 2. Jackson 2 → Jackson 3

A mudança mais impactante. Jackson 3 tem breaking changes em:

### Renomeação de pacotes
```java
// ANTES (Jackson 2)
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.annotation.JsonProperty;

// DEPOIS (Jackson 3)
import tools.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.annotation.JsonProperty;  // annotations mantidas!
```

### Mudanças de API
```java
// ANTES
ObjectMapper mapper = new ObjectMapper();
mapper.configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);

// DEPOIS — Jackson 3 usa builder pattern
ObjectMapper mapper = JsonMapper.builder()
    .disable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES)
    .build();
```

Spring Boot 4 ainda inclui suporte deprecated para Jackson 2 (compatibilidade transitória),
mas migrar para Jackson 3 é fortemente recomendado.

## 3. Spring Security 7

### Filter Chain simplificada
```java
// ANTES (Spring Security 6)
@Bean
SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
    http
        .csrf(csrf -> csrf.disable())
        .authorizeHttpRequests(auth -> auth
            .requestMatchers("/api/public/**").permitAll()
            .anyRequest().authenticated()
        )
        .oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()));
    return http.build();
}

// DEPOIS (Spring Security 7 — mesma estrutura, mas com novas APIs)
@Bean
SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
    http
        .csrf(csrf -> csrf.disable())
        .authorizeHttpRequests(auth -> auth
            .requestMatchers("/api/public/**").permitAll()
            .anyRequest().authenticated()
        )
        .oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()));
    return http.build();
}
// A estrutura é similar, mas várias classes internas mudaram de pacote
// Verifique imports e deprecated warnings
```

## 4. Properties Renomeadas

| Antes (3.x) | Depois (4.0) |
|-------------|-------------|
| `management.tracing.enabled` | `management.tracing.export.enabled` |
| `spring.data.mongodb.*` (alguns) | Verificar release notes |
| `logging.pattern.console` | Continua, mas `logging.console.enabled` é novo |

## 5. MongoDB

```java
// Health indicators mudaram de módulo
// De: spring-boot-data-mongodb
// Para: spring-boot-mongodb

// Dependência atualizada:
// spring-boot-starter-data-mongodb continua funcionando
// mas health agora vem automaticamente do módulo base
```

## 6. Observabilidade

```properties
# ANTES
management.tracing.enabled=true

# DEPOIS
management.tracing.export.enabled=true

# NOVO — OpenTelemetry integrado
# Adicione spring-boot-starter-opentelemetry
# Configuração automática de OTLP exporter
management.otlp.tracing.endpoint=http://collector:4318/v1/traces
management.otlp.metrics.export.url=http://collector:4318/v1/metrics
```

## 7. Testcontainers 2.0

```java
// ANTES (Testcontainers 1.x)
@Container
static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16");

// DEPOIS (Testcontainers 2.0 — API simplificada)
@Container
static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:17");
// API permanece compatível, mas módulos internos foram refatorados
// Verifique se módulos custom ainda compilam
```

## 8. Checklist de Migração

- [ ] Atualizar parent/BOM para 4.0.x
- [ ] Atualizar JDK para 25 (ou mínimo 17)
- [ ] Migrar Jackson 2 → 3 (imports, builders)
- [ ] Revisar Spring Security filter chains
- [ ] Atualizar properties renomeadas
- [ ] Verificar MongoDB health indicators se aplicável
- [ ] Habilitar virtual threads (`spring.threads.virtual.enabled=true`)
- [ ] Adicionar starter OpenTelemetry se usando tracing
- [ ] Rodar testes completos (unit + integration)
- [ ] Testar com GraalVM native se usando AOT
- [ ] Migrar POM para Apache Maven 4 com `mvnup` (model 4.1.0)
- [ ] Habilitar Maven Build Cache Extension e `mvnd` localmente
