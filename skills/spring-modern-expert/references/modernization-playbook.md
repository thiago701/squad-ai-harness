# Playbook de modernização Spring — obsoleto → moderno, AOT, antipadrões, revisões

> **Base:** pesquisa 2026-09-27 (docs oficiais Boot 4.0.8/4.1.1, Framework 7, Security 7, blog spring.io).
> **Princípio:** cada troca exige **ganho concreto** (qualidade/segurança/perf/produtividade) e
> **zero regressão** — modernizar sem ganho viola P1.

## 1. Mapa completo obsoleto → moderno (com justificativa de ganho)

| Tradicional | Moderno | Ganho concreto |
|---|---|---|
| `RestTemplate` | `RestClient` (sync) / `@HttpExchange` / `WebClient` (reativo) | API fluente, conversão declarativa, futuro do Spring (RestTemplate sai no 8.0) |
| OpenFeign | HTTP Service Clients (`@HttpExchange` + `@ImportHttpServices`) | 1 dependência a menos; OpenFeign é manutenção-only desde 2022 |
| `ObjectMapper`/Jackson 2 | Jackson 3 `JsonMapper.builder()` (`tools.jackson`) | suportado no Framework 7; Jackson 2 removido no 7.2 |
| `@MockBean`/`@SpyBean` | `@MockitoBean`/`@MockitoSpyBean` | não compila no Boot 4 (removidos) |
| `spring.factories` (auto-config) | import em `META-INF/spring/*.imports` | padrão atual; factories só p/ casos residuais |
| XML config / `@Bean` condicional pesado | Java config + `BeanRegistrar` | AOT-friendly; menos reflection |
| `@Scheduled` sem rastreio | `@Scheduled` + Micrometer + correlation id (Scoped Values) | observabilidade de jobs |
| `ThreadLocal` p/ contexto | Scoped Values (Java 25) | imutável, sem leaks, propaga em VTs |
| `CompletableFuture` chains | Virtual Threads + `StructuredTaskScope` (preview ⚠️) | código sequencial legível; SC só com `--enable-preview` |
| `management.tracing.enabled` | `management.tracing.export.enabled` | nome correto no Boot 4 |
| `management.otlp.*` | `management.opentelemetry.*` | namespace novo; OTel starter oficial |
| `spring.data.mongodb.*` | `spring.mongodb.*` | 13 properties renomeadas no Boot 4 |
| Logback default | Logback UTF-8 (default no 4) + structured logging | prontidão p/ OTel |
| Hibernate 6/JPA 3.1 | Hibernate 7.x/JPA 3.2 (Boot 4) | provider oficial; `EntityManager` injetável com qualifiers |

## 2. Otimização de startup e memória (sempre medir com JFR antes/depois)

1. **AOT Cache (JEP 483)** — Boot 4.1 + Java 25+: treinar (`-XX:AOTCacheOutput=app.aot
   -Dspring.context.exit=onRefresh`) e rodar (`-XX:AOTCache=app.aot`, jar extraído). Recomendado sobre CDS.
2. **CDS** (Java < 25): `-XX:ArchiveClassesAtExit` + `-XX:SharedArchiveFile`.
3. **Virtual Threads opt-in**: `spring.threads.virtual.enabled=true` (NÃO é default no Boot 4).
4. **Beans lazy** (`spring.main.lazy-initialization`) p/ cortar bootstrap; cuidado com falhas tardias.
5. **Starters modulares** (Boot 4): menos classpath = menos scan; prefira o starter específico.
6. **JDK:** COH default no 27, G1 universal — ver `java-modern-expert` (mas produção = 25 LTS).
7. **GraalVM Native:** alvo sub-100 ms; custo: metadata + build lento + throughput de pico menor (~15%).
8. **CRaC** (Boot 4.1): restore rápido; lifecycle limitado (sockets/threads) — use hooks.

## 3. Preparação AOT/Native — checklist

- [ ] Reflection/proxies/serialização declarados (`RuntimeHintsRegistrar`, `@RegisterReflectionForBinding`).
- [ ] Sem scans de classpath imprevisíveis; imports de config explícitos.
- [ ] `spring-boot:process-aot` roda no build; `native:test` (ou `-Pnative test`) no CI.
- [ ] Testes rodam contra o binário native (`@SpringBootTest` native ou RestTestClient em porta real).
- [ ] Medir: startup, RSS, tamanho do binário, p99 — comparar com baseline JVM (decisão por número).

## 4. Antipadrões comuns (auditoria de app legada)

- **N+1** (Hibernate) — `@EntityGraph`/fetch joins; habilitar `hibernate.query.fail_on_pagination_over_collection_fetch`.
- **`@Transactional` em métodos privados/auto-invocação** — proxy não intercepta; mover para boundary.
- **Propriedades sensíveis em `application.properties` sem criptografia** — config server/Vault/SSM.
- **`server.error.include-stacktrace=always`** — vaza stack; usar `never`/`on_param` controlado.
- **Sem probes/healthcheck customizado** — Actuator probes já ON por default no Boot 4.
- **Pool de conexões sem timeout/leak detection** — HikariCP: `connection-timeout`, `leak-detection-threshold`.
- **Filtros com estado mutável compartilhado** — estado por request em Scoped Values.
- **Logs com PII/secrets** — redaction + structured logging + correlation id.

## 5. Revisão Spring Security (checklist rápido)

- [ ] CSRF ativo com `XorCsrfTokenRequestAttributeHandler` (BREACH); SPA via `csrf(spa())`.
- [ ] CORS via `CorsConfigurationSource` + `cors(withDefaults())` — nunca desabilitar globalmente.
- [ ] Senhas com `DelegatingPasswordEncoder` (bcrypt ~1s; Argon2/Scrypt/Balloon via Password4j no 7.0).
- [ ] JWT: validação de `typ` ativa (default no 7); `NimbusJwtDecoder` timeouts ≥ 30 s (default novo).
- [ ] OAuth2/OIDC: Authorization Code + PKCE; token introspection com `RestClientOpaqueTokenIntrospector` (7.1).
- [ ] Method security: `@EnableMethodSecurity` + `@PreAuthorize` (modelo AuthorizationManager).
- [ ] Headers de segurança default (HSTS, X-Content-Type-Options) não desativados sem motivo.
- [ ] Authorization Server próprio → módulo do Security 7 (standalone arquivado).

## 6. Observabilidade e resiliência

- **Métricas/traces:** Micrometer 1.17 + OTLP; starter `spring-boot-starter-opentelemetry`; tracing export explícito.
- **Resiliência:** `@Retryable`/`@ConcurrencyLimit` (spring-core, ex-Spring Retry); Resilience4j 2.3 via Circuit Breaker.
- **Logs:** structured logging + correlation id (Scoped Values) + redaction (JFR redaction no JDK 27).

## 7. Comparação tradicional × moderno — matriz de decisão (P1)

| Decisão | Tradicional | Moderno | Quando moderno vence |
|---|---|---|---|
| Cliente HTTP | RestTemplate | RestClient | código novo ou mudança de contrato |
| Serviço cliente entre apps | OpenFeign | @HttpExchange | novo cliente; menos deps |
| Contexto por request | ThreadLocal | Scoped Values | Java 25 + virtual threads |
| Concorrência | CompletableFuture | Virtual Threads (+ SC ⚠️ preview) | I/O-bound; SC só com flag |
| Boot de teste | @MockBean | @MockitoBean | obrigatório no Boot 4 |
| Startup serverless | JVM + CDS | AOT Cache / Native | medir: Native < 100 ms vs custo de build |
| DB simples | JPA/Hibernate | Spring Data JDBC / JdbcClient | domínio simples, DDD tático |

Regra: **moderno vence quando há ganho medido ou obrigatoriedade de versão; caso contrário, o
tradicional fica** — registrar a decisão como ADR.
