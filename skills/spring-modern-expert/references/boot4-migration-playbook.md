# Playbook de migração Spring Boot 3 → 4 (com evidência)

> **Base:** guia oficial de migração (wiki spring-boot), release notes Framework 7.0/Boot 4.0,
> docs 4.0.8/4.1.1, pesquisa 2026-09-27. Ferramenta padrão da Squad: **OpenRewrite** +
> **spring-boot-properties-migrator** (SBM não suporta 3→4 — repo parado desde 08/2024).

## 1. Sequência de baixo risco (validada)

1. **Suba ao último 3.5.x (3.5.16)** e limpe deprecações com `spring-boot-properties-migrator`
   (scope runtime; remover ao final). Suíte verde. Commit.
2. **OpenRewrite** — receitas oficiais (YAMLs `spring-boot-40.yml`, `spring-boot-40-modular-starters.yml`):
   `UpgradeSpringBoot_4_0`, `AddModularStarterDependencies`. Rodar uma receita por vez, suite verde entre passos.
3. **Starters:** `starter-web`→`starter-webmvc`, `starter-aop`→`starter-aspectj`,
   `starter-oauth2-*`→`starter-security-oauth2-*`; ou use **classic starters**
   (`spring-boot-starter-classic`/`starter-test-classic`) como etapa intermediária.
4. **Jackson 2 → 3** (`tools.jackson`): `ObjectMapper`→`JsonMapper.builder()`,
   `Jackson2ObjectMapperBuilderCustomizer`→`JsonMapperBuilderCustomizer`, `@JsonComponent`→`@JacksonComponent`,
   `spring.jackson.*`→`spring.jackson.json.*`. Se necessário, `spring.jackson.use-jackson2-defaults=true`
   como muleta temporária (Jackson 2 será removido no Framework 7.2).
5. **HTTP:** `RestTemplate` perde auto-config no Boot 4 (deprecated no 7.1) → `RestClient`/`@HttpExchange`.
6. **Testes:** `@MockBean`/`@SpyBean` **removidos** → `@MockitoBean`/`@MockitoSpyBean`;
   `@SpringBootTest` não fornece mais MockMvc/TestRestTemplate (usar `@AutoConfigureMockMvc`/`@AutoConfigureTestRestTemplate`).
7. **Security 7:** revisar filter chain (`authorizeHttpRequests`), Jackson modules (`SecurityJacksonModules`),
   validação `typ` de JWT default, Authorization Server standalone → módulo do Security core.
8. **AOT/Native:** revalidar hints p/ formato unificado GraalVM 25; testar nativamente no CI.
9. **Rollback:** tag + imagem anterior + `git revert` do passo; nunca migrar "tudo de uma vez" sem gates verdes.

## 2. Breaking changes (compilado das release notes oficiais)

| Área | Mudança | Impacto |
|---|---|---|
| Jakarta | EE 11: Servlet 6.1 (Tomcat 11/Jetty 12.1), JPA 3.2, Bean Validation 3.1 | **Undertow removido**; Hibernate ORM 7.x obrigatório (7.2.x no 4.0, 7.4.x no 4.1) |
| JSON | Jackson 3 default | código com `ObjectMapper` precisa migrar; anotações continuam em `com.fasterxml.jackson` |
| Null-safety | JSpecify (JSR-305 deprecated) | revisar @Nullable em assinaturas Kotlin/Java |
| HTTP | `HttpHeaders` não é mais `MultiValueMap` | código que manipulava headers como mapa quebra |
| SpEL | limite 10.000 operações por default (7.0.8) | expressões complexas precisam de `spring.expression.maxOperations` |
| Config | `server.error.*`→`spring.web.error.*`; `management.otlp.*`→`management.opentelemetry.*`; `spring.data.mongodb.*`→`spring.mongodb.*` | properties-migrator cobre |
| Actuator | probes ON por default; `management.endpoint.<id>.enabled`→`.access` | revisar exposure e segurança dos endpoints |
| Remoções | spring-jcl, `javax.annotation/inject`, ListenableFuture, OkHttp3, Theme, suffix matching, Pulsar Reactive, Spock, launch scripts fully-executable | compilar primeiro e tratar os erros um a um |
| Retry | `@Retryable`/`@ConcurrencyLimit` no spring-core | remover dependência spring-retry |
| Boot 4.1 | AOT Cache (JEP 483) exige Java 25+; AOT de testes não é pulado por `-DskipTests` (usar `maven.test.skip`) | ajustar pipeline |

## 3. Ferramentas e evidências

| Ferramenta | Papel | Estado |
|---|---|---|
| `spring-boot-properties-migrator` | migra/renomeia properties em runtime + diagnóstico | oficial, ativo |
| OpenRewrite (rewrite-spring) | refatorações automáticas Boot 4 | oficial, ativo (8.71.0) |
| spring-boot-migrator (SBM) | 2.7→3.0 / JEE→Boot | **não suporta 3→4**; parado desde 08/2024 — DESCARTAR p/ 3→4 |
| Spring Application Advisor | análise de upgrade | comercial |
| Migration Guide wiki | breaking changes canônicos | https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide |

## 4. Riscos conhecidos e mitigação

- **Jackson 3 semântica:** teste de serialização/desserialização de todos os contratos (PII/data numérica).
- **Hibernate 7/JPA 3.2:** revisar queries nativas e critérios; roda smoke de migração Flyway/Liquibase.
- **Security 7:** validação `typ` de JWT pode rejeitar tokens antigos emitidos por outros sistemas — alinhar antes.
- **AOT/Native:** reflexão não declarada = falha em runtime; `RuntimeHintsRegistrar` + testes nativos no CI.
- **Cloud:** não há train oficial p/ Boot 4.1 — manter 2025.1.x (≥ 2025.1.3, que corrige 17 CVEs) até o 2026.0 GA.

## 5. Modelo de plano (artefato GATE 1)

```markdown
# Migração Spring Boot 3.x → 4.x — <app>
- Versões atuais → alvo: Boot <x> → 4.1.1 | Java <n> → 25 LTS | Framework 7.0.9
- Inventário: RestTemplate: N usos | @MockBean: N | Jackson2: N | starters legados: <lista>
- Passos: (1) 3.5.16 limpo → (2) OpenRewrite → (3) starters → (4) Jackson 3 → (5) testes → (6) Security
- Riscos: <tabela item|impacto|mitigação>
- Rollback: <tag/imagem>
- Validação: suite verde + startup JFR antes/depois + smoke AOT/native (se aplicável)
```
