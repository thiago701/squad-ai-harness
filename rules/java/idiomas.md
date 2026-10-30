# Regras always-on — Java 25 + Spring Boot 4 (idiomas)

> **Origin:** `squad-ai` · **Escopo:** todo agente que toca código Java/Spring · **Natureza:** invariantes
> always-on (curtos, baratos, sempre verdadeiros). **Não é tutorial.** O aprofundamento (exemplos, casos,
> migração, tuning) vive na skill **`java25-spring-boot`** (`java25-spring-boot/SKILL.md` + `references/`).
> **Arbitragem:** P1-Simplicidade > P2-Performance > P3-CustoBaixo; segurança nunca negociável.

---

## 1. Linguagem — sempre prefira

| Em vez de | Prefira | Por quê (invariante) |
|---|---|---|
| classe POJO de dados / DTO mutável | **`record`** | imutável, `equals/hashCode/toString` grátis, intenção clara |
| hierarquia aberta de tipos fechados | **`sealed` interface + records** | exaustividade verificada pelo compilador |
| cadeia de `if/instanceof` + cast | **pattern matching for switch** (com record patterns) | sem cast manual; `switch` exaustivo sobre `sealed` |
| cadeia de `catch` tipados (log+resposta) | **método `mapError(Exception)` com pattern switch** | função pura, testável caso a caso |
| tipo explícito verboso em locais | **`var`** (só em locais, com inicializador legível) | menos ruído; nunca em campos/API pública |
| `null` para "ausência" | **`Optional`** no retorno (nunca em campo/param) | torna ausência explícita |
| concatenação/strings multilinha | **text blocks** (`"""`) | legibilidade de SQL/JSON |

## 2. Concorrência — sempre

- **Virtual Threads para I/O-bound.** Ativar `spring.threads.virtual.enabled=true`. HTTP, query, arquivo → VT.
- **Nunca `synchronized` em seção que bloqueia** sob virtual threads → causa *pinning* do carrier. Use **`ReentrantLock`**.
- **CPU-bound não vai para VT** — use `ForkJoinPool`/parallel streams.
- **VT não é bala de prata:** o gargalo real costuma ser o pool de conexões (dimensione o HikariCP por benchmark).
- **`ScopedValue` no lugar de `ThreadLocal`** (propaga em Structured Concurrency; sem `.remove()`, sem leak).

## 3. Spring Boot 4 — invariantes

- **Constructor injection sempre.** **Nunca** `@Autowired` em campo (impede teste sem container, esconde dependência).
- Dependência única → **injetar via construtor sem `@Autowired`** (Spring resolve sozinho); preferir `final`.
- **`@ConfigurationProperties` tipado** em vez de `@Value` espalhado.
- **HTTP clients declarativos** (`@HttpExchange`) em vez de `RestTemplate`/boilerplate.
- **`RestTestClient`/`@SpringBootTest`** para teste de controller; sem mockar o que dá para testar de verdade.

## 4. Persistência — invariantes

- **`spring.jpa.hibernate.ddl-auto=validate` em produção.** Nunca `update`/`create` fora de dev. Schema via migração (Flyway/Liquibase).
- **Fetch `LAZY` como padrão.** `EAGER` só com justificativa; resolver N+1 com `@EntityGraph`/`join fetch`, não com EAGER.
- **Pool dimensionado por benchmark** (`maximum-pool-size`), não pelo número de virtual threads.

## 5. Build, commits e invariantes de camada

- **Conventional Commits em PT-BR** (`feat`/`fix`/`refactor`/`docs`/`test`/`chore`/`perf`…); escopo = skill/módulo; sem ponto final.
- **ArchUnit** guarda os invariantes de camada (domínio não conhece infra; sem ciclos de pacote) — falha = build vermelho.
- **Maven 4 / Gradle 9**; Actions/plugins pinados; sem `--no-verify`.
- **`var`/records/sealed não dispensam testes** — TDD é o método; toda mudança de comportamento tem teste (A3).

---

> **Aprofundar:** skill `java25-spring-boot` — `SKILL.md` (Virtual Threads, Structured Concurrency, Scoped Values,
> pattern matching, GraalVM, tuning) e `references/` (`archunit-rules.md`, `clean-architecture-java.md`,
> `virtual-threads-deep-dive.md`, `migration-guide.md`, `testing-patterns.md`). Segurança → `rules/java/seguranca.md`.
