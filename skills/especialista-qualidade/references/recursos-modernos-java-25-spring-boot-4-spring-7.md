# especialista-qualidade · Recursos Modernos: Java 25 + Spring Boot 4 / Spring 7

> Reference da skill `especialista-qualidade` (movida da SKILL.md em 11/10/2026 — hub + references, I3). Carregue só quando a tarefa pedir este tema.

## Recursos Modernos: Java 25 + Spring Boot 4 / Spring 7

**Sempre que estiver gerando ou revisando teste em Java/Kotlin de stack 2025+, leia primeiro `references/java25-spring7-testing.md`.** Cobre:

- `@MockitoBean` / `@MockitoSpyBean` (Spring 6.2+) substituindo `@MockBean` deprecated
- `@ServiceConnection` (Boot 3.1+) substituindo `@DynamicPropertySource` boilerplate
- `MockMvcTester` (Spring 6.2+) substituindo `MockMvc` cru com `andExpect` aninhado
- Slice tests modernos (`@WebMvcTest`, `@DataJpaTest`, `@JsonTest`, `@RestClientTest`)
- **Virtual Threads** + **`StructuredTaskScope`** em testes de concorrência reais (10k tasks sem OOM)
- **Awaitility** substituindo `Thread.sleep` em assertions assíncronas
- Sealed types + pattern matching exaustivo em asserções (compilador acusa nova variante)
- Records como DTOs/cenários de teste (zero builder boilerplate)
- **Spring Modulith** `ApplicationModules.verify()` como teste arquitetural
- `ApplicationContextRunner` para slice de configuração (sub-segundo)
- `RestTestClient` (Boot 4) substituindo `TestRestTemplate`
- **RestAssured 6.0.0** (baseline Java 17+, Groovy 5, **Spring 7 + Jackson 3**) para teste black-box de API HTTP com `given/when/then`; módulo `spring-mock-mvc` (`RestAssuredMockMvc`) para slice de controller — aprofundar em `references/rest-assured-api-testing.md`
- **Spring AOT + GraalVM Native Image** — testes que cobrem o caminho nativo
- AssertJ 3.26+ — `usingRecursiveComparison`, `extracting`, asserções customizadas de domínio
- JUnit 5.11+ — `@ParameterizedTest` com records, `@TestTemplate`, dynamic tests, `@DisplayNameGeneration`
- Mockito-inline default — mock de finais/statics/construtores
- **Calistenia de Objetos × Java 25 como critério de testabilidade** — código que segue as 9 regras (VOs com invariante na construção R3, imutabilidade/Tell-Don't-Ask R9, coleções de 1ª classe R4) é intrinsecamente mais testável: a invariante falha no compact constructor, não em runtime; a imutabilidade (`record` + `withX()` explícito) elimina flakiness de concorrência sob Virtual Threads. Régua canônica e antes/depois na skill `java-modernizer`. ⚠️ Valhalla (JEP 401) e withers (JEP 468) **não estão no JDK 25** — não escreva teste assumindo value class ou sintaxe `with`.

---
