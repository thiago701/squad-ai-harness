# Catálogo de Regras SonarQube MQR — Java 21/25, Python 3.12+ e TypeScript/Angular 21+

> **Fonte executável:** `scripts/sonar/catalogo.py` (`VERSAO_REGRAS = "sonar-first-2026.10"`).
> Mapeia a taxonomia **Multi-Quality Rule Mode (MQR)** (`SECURITY`, `RELIABILITY`, `MAINTAINABILITY`)
> e os tipos legados (`VULNERABILITY`, `SECURITY_HOTSPOT`, `BUG`, `CODE_SMELL`) em restrições
> preventivas acionadas na **Fase A/B** e verificadas na **Fase C/E**.

---

## 1. Regras Universais de Complexidade e Estrutura (AST / Estrutural)

| Regra | Qualidade MQR | Severidade | Limiar | Restrição Preventiva (Fase B) |
|---|---|---|:---:|---|
| `*:S3776` | `MAINTAINABILITY` | `HIGH` | `<= 15` | Manter Cognitive Complexity `<= 15` usando Guard Clauses (early return), extração de métodos curtos (`<= 30` linhas) e Pattern Matching. |
| `*:S1541` | `MAINTAINABILITY` | `MEDIUM` | `<= 15` | Manter Cyclomatic Complexity `<= 15` substituindo cascatas de `if/else` por tabelas de despacho, polimorfismo ou `switch` exaustivo sobre `sealed` types. |
| `*:S107` | `MAINTAINABILITY` | `MEDIUM` | `<= 7` | Nunca declarar métodos/funções com mais de 7 parâmetros; agrupar em `record` (Java 25), `@dataclass(frozen=True)` (Python) ou interface tipada (TS). |
| `*:S1192` | `MAINTAINABILITY` | `MEDIUM` | `< 3 rep.` | Extrair literais de string (`>= 12` caracteres) repetidos 3 ou mais vezes para constantes nomeadas. |
| `SONAR-NOSONAR` | `MAINTAINABILITY` | `BLOCKER` | `0` | Proibido usar `// NOSONAR`, `# NOSONAR`, `@SuppressWarnings("all")` ou `# noqa` para silenciar violações. |

---

## 2. Java 21 / 25 LTS + Spring Boot 4 (`REGRAS_JAVA`)

| Regra | Qualidade MQR | Severidade | CWE | Restrição Preventiva & Idioma Moderno Java 25 | Autofix (Fase D) |
|---|---|---|:---:|---|---|
| `java:S6881` | `RELIABILITY` | `HIGH` | — | Em Virtual Threads (Java 21/25), nunca usar bloco `synchronized` com I/O bloqueante (evitar *pinning* da carrier thread); usar `ReentrantLock`. | Escalar especialista |
| `java:S6204` | `MAINTAINABILITY` | `LOW` | — | Usar `.toList()` (Java 16+) em vez de `.collect(Collectors.toList())` para coleções imutáveis. | `java_stream_to_list` |
| `java:S3655` | `RELIABILITY` | `HIGH` | 476 | Nunca chamar `Optional.get()` sem checagem prévia; usar `.orElseThrow()`, `.orElse()` ou `.map()`. | Escalar especialista |
| `java:S2142` | `RELIABILITY` | `HIGH` | 391 | Ao capturar `InterruptedException`, chamar `Thread.currentThread().interrupt()` antes de relançar ou encerrar. | Escalar especialista |
| `java:S1181` | `RELIABILITY` | `HIGH` | 396 | Nunca capturar `Throwable` ou `Error` diretamente; capturar `Exception` ou exceção de domínio. | Escalar especialista |
| `java:S112` | `MAINTAINABILITY` | `MEDIUM` | 397 | Nunca lançar `new RuntimeException(...)` ou `new Exception(...)` genéricas; usar exceções de domínio ou standard específicas (`IllegalArgumentException`, `IllegalStateException`). | Escalar especialista |
| `java:S106` | `MAINTAINABILITY` | `MEDIUM` | — | Nunca usar `System.out.println` ou `System.err.println`; usar logger estruturado SLF4J (`LOGGER.info`, `LOGGER.error`). | `substituir_stdio_por_logger` |
| `java:S1148` | `SECURITY` | `MEDIUM` | 209 | Nunca chamar `e.printStackTrace()`; registrar com `LOGGER.error("Contexto", e)`. | `substituir_printstacktrace_por_logger` |
| `java:S4973` | `RELIABILITY` | `HIGH` | 597 | Nunca comparar `String` ou tipos boxed (`Integer`, `Long`, `Boolean`) com `==` ou `!=`; usar `Objects.equals(a, b)`. | Escalar especialista |
| `java:S1143` | `RELIABILITY` | `BLOCKER` | 584 | Nunca usar `return` ou `throw` dentro de bloco `finally`. | Escalar especialista |
| `java:S2095` | `RELIABILITY` | `BLOCKER` | 404 | Abrir todo recurso `AutoCloseable` (`Connection`, `PreparedStatement`, `InputStream`) em bloco `try (...)` (*try-with-resources*). | Escalar especialista |
| `java:S2068` | `SECURITY` | `BLOCKER` | 798 | Zero senhas, chaves ou tokens hardcoded no código; ler de variáveis de ambiente ou Secrets Manager. | Escalar especialista |
| `java:S3649` | `SECURITY` | `BLOCKER` | 89 | Zero concatenação de strings em SQL/JPQL; usar `PreparedStatement` com `?` ou parâmetros nomeados `:param`. | Escalar especialista |
| `java:S4790` | `SECURITY` | `HIGH` | 328 | Não usar `MD5` ou `SHA-1`; usar `SHA-256` ou `Argon2id`/`BCrypt` para senhas. | Escalar especialista |
| `java:S2245` | `SECURITY` | `HIGH` | 330 | Não usar `java.util.Random` nem `Math.random()` para tokens/IDs sensíveis; usar `java.security.SecureRandom`. | Escalar especialista |
| `java:S5145` | `SECURITY` | `HIGH` | 117 | Sanitizar quebras de linha (`\r`, `\n`) antes de registrar entradas externas em logs. | Escalar especialista |
| `java:S5332` | `SECURITY` | `HIGH` | 319 | Usar sempre `https://` em integrações externas. | Escalar especialista |

---

## 3. Python 3.12 / 3.13 / 3.14 (`REGRAS_PYTHON`)

| Regra | Qualidade MQR | Severidade | CWE | Restrição Preventiva Python Moderno | Autofix (Fase D) |
|---|---|---|:---:|---|---|
| `python:S5754` | `RELIABILITY` | `HIGH` | 396 | Nunca usar `except:` vazio (*bare except*), pois captura `SystemExit` e `KeyboardInterrupt`; usar `except Exception as erro:` ou exceção específica. | `tipar_excecao_python` |
| `python:S1126` | `MAINTAINABILITY` | `LOW` | — | Não escrever bloco `else`/`elif` imediatamente após `return`, `raise`, `continue` ou `break`. | Escalar especialista |
| `python:S1066` | `MAINTAINABILITY` | `LOW` | — | Combinar `if cond1:` aninhado com único `if cond2:` (sem `else`) em `if cond1 and cond2:`. | Escalar especialista |
| `python:S2068` | `SECURITY` | `BLOCKER` | 798 | Ler credenciais via `os.environ.get()` sem valor default sensível literal. | Escalar especialista |
| `python:S3649` | `SECURITY` | `BLOCKER` | 89 | Nunca montar SQL com `f"SELECT ... {var}"`, `%` ou `.format()`; usar bind parameters da DB-API. | Escalar especialista |
| `python:S4790` | `SECURITY` | `HIGH` | 328 | Usar `hashlib.sha256()` (ou declarar `usedforsecurity=False` em checksums não criptográficos). | Escalar especialista |
| `python:S2245` | `SECURITY` | `HIGH` | 330 | Usar o módulo `secrets` da stdlib para geração de tokens, desafios ou chaves. | Escalar especialista |
| `python:S6397` | `SECURITY` | `BLOCKER` | 78 | Nunca usar `subprocess.run(..., shell=True)`, `eval()` ou `exec()`; passar lista de argumentos e usar `ast.literal_eval` / `json.loads`. | Escalar especialista |
| `python:S5332` | `SECURITY` | `HIGH` | 319 | Nunca usar `http://` em chamadas externas. | Escalar especialista |

---

## 4. TypeScript / Angular 21+ (`REGRAS_TYPESCRIPT`)

| Regra | Qualidade MQR | Severidade | CWE | Restrição Preventiva TypeScript / Angular | Autofix (Fase D) |
|---|---|---|:---:|---|---|
| `typescript:S3504` | `MAINTAINABILITY` | `MEDIUM` | — | Declarar variáveis com `const` (padrão) ou `let`; nunca usar `var`. | `substituir_var_por_const` |
| `typescript:S1440` | `RELIABILITY` | `MEDIUM` | — | Usar sempre igualdade estrita (`===` e `!==`) em vez de `==` e `!=`. | `aplicar_igualdade_estrita_ts` |
| `typescript:S4325` | `MAINTAINABILITY` | `MEDIUM` | — | Evitar `: any` explícito; usar tipos estritos, unions, generics ou `unknown` com type guards. | Escalar especialista |
| `typescript:S106` | `MAINTAINABILITY` | `LOW` | — | Não deixar `console.log` ou `console.debug` em código de produção. | Escalar especialista |
| `typescript:S6268` | `SECURITY` | `BLOCKER` | 79 | Nunca usar `DomSanitizer.bypassSecurityTrustHtml/Script/Url` com dados não sanitizados. | Escalar especialista |
| `typescript:S5247` | `SECURITY` | `HIGH` | 79 | Nunca atribuir HTML bruto diretamente a `.innerHTML` ou `.outerHTML` (DOM XSS). | Escalar especialista |
| `typescript:S2068` | `SECURITY` | `BLOCKER` | 798 | Nunca embutir chaves privadas, tokens ou senhas no código TypeScript/frontend. | Escalar especialista |
| `angular:OnPush` | `MAINTAINABILITY` | `MEDIUM` | — | Declarar `changeDetection: ChangeDetectionStrategy.OnPush` em todo `@Component`. | Escalar especialista |
