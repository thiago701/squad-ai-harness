# {{project_name}} (Spring Boot 4.1 / Java 25)

API REST atual gerada pelo **MITR**: `starter-webmvc` (nomenclatura SB4),
dominio puro compartilhado com os sabores GraalVM/Quarkus, DTOs como records,
`@RestControllerAdvice` central emitindo **ProblemDetail (RFC 9457)** e testes
`@WebMvcTest` de contexto minimo com gate jacoco >=90%.

```bash
mvn -B verify   # testes + jacoco check (gate)
mvn spring-boot:run
```
