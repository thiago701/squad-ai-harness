# Heurísticas de investigação de erros — catálogo reutilizável

> Memória procedimental do Error Investigator. Cada erro recorrente vira uma linha
> `sinal → causa provável → checagem → correção típica`. Alimentado pelos `Doctors`
> de cada stack e pelo loop de melhoria contínua (`scripts/improvement_loop.py`).
> **Regra de entrada:** só registra o que apareceu ≥2 vezes **ou** tem evidência clara.
> **Pareamento:** o `Architecture Regression Guard` valida toda correção com
> [`clean-code-craftsman`](../../clean-code-craftsman/SKILL.md) (qualidade micro) e o
> `Java Doctor` consulta [`java25-spring-boot`](../../java25-spring-boot/SKILL.md).

## Como usar
1. Classifique o erro (taxonomia da skill umbrella). 2. Procure o sinal abaixo.
3. Rode a **checagem** (ela confirma/descarta a causa — não pule). 4. Aplique a
correção **mínima** + teste red→green. 5. Se foi um sinal novo, adicione aqui.

---

## Cross-stack (universais)

| Sinal | Causa provável | Checagem | Correção típica |
|---|---|---|---|
| Erro só no CI, não local | ambiente divergente (versão/lock/env) | reproduzir o **comando exato** do CI localmente | fixar versão/lockfile; alinhar env/imagem |
| Falha intermitente (flaky) | estado/tempo/ordem compartilhados | rodar N× com ordem aleatória | isolar estado; tempo determinístico |
| Stack trace aponta o framework | sintoma ≠ causa | achar o 1º frame do **seu** código / último `Caused by` | corrigir a origem, não o sintoma |
| "Funciona na minha máquina" | dependência/encoding/perfil | diff de ambiente (versões, env) | conteinerizar; fixar encoding/perfil |
| Correção "resolve" mas reaparece | tratou sintoma, não causa raiz | reproduzir o caso de borda original | voltar ao diagnóstico; cobrir com teste |

---

## Java

### Build & dependências (Maven/Gradle)
| Sinal | Causa | Checagem | Correção |
|---|---|---|---|
| `NoSuchMethodError` / `NoClassDefFoundError` | 2 versões da mesma lib | `mvn dependency:tree -Dverbose` / `gradle dependencyInsight` | BOM / `dependencyManagement` / `exclusions` |
| `invalid target release` | JDK ≠ `maven.compiler.release` | `java -version` vs `JAVA_HOME` vs toolchain | alinhar toolchain/`release` |
| mojibake em mensagens | encoding não-UTF-8 | `project.build.sourceEncoding` / `-Dfile.encoding` | fixar UTF-8 no build e no runtime |
| `cannot find symbol` em classe gerada | annotation processor não rodou | ordem em `annotationProcessorPaths` | Lombok **antes** de MapStruct; `hibernate-jpamodelgen` |
| `Unmapped target property` | MapStruct sem mapping | `@Mapping`/`unmappedTargetPolicy` | declarar o mapping ou `IGNORE` justificado |

### Spring Boot / Quarkus (runtime)
| Sinal | Causa | Checagem | Correção |
|---|---|---|---|
| `NoSuchBeanDefinitionException` | bean ausente / fora do scan / profile | `--debug` → Condition Evaluation Report | registrar `@Bean`/scan; corrigir profile/condição |
| `BeanCurrentlyInCreationException` | dependência circular | grafo de injeção | extrair colaborador; `@Lazy` (último recurso) |
| `@ConfigurationProperties` nulo | falta `@EnableConfigurationProperties`/prefixo | logar as props no startup | corrigir prefixo / habilitar binding |
| `Cannot determine embedded database driver` | datasource não configurado | `spring.datasource.*` | configurar URL/driver ou Testcontainers |
| `Connection refused` (DB/Kafka) | infra fora / `bootstrap.servers` errado | `docker ps` / `nc -z host port` | subir infra; corrigir host/porta |
| `Table doesn't exist` | migração não rodou / `ddl-auto` | `flyway info` / log de migração | rodar migração; `ddl-auto: validate` |
| `LazyInitializationException` | sessão JPA fechada | onde o `get` da relação ocorre | fetch join / DTO / dentro de `@Transactional` |
| Jackson `UnrecognizedPropertyException` | DTO sem campo/construtor | payload vs DTO | `@JsonCreator`/`@JsonIgnoreProperties` |
| 401/403 inesperado | ordem do `SecurityFilterChain` / issuer | log `DEBUG` de security | corrigir matcher/ordem; JWK/issuer |

### Testes Java
| Sinal | Causa | Checagem | Correção |
|---|---|---|---|
| `Could not find a valid Docker environment` | Docker off / CI sem Docker | `docker ps` | habilitar Docker; Testcontainers Cloud |
| `UnnecessaryStubbingException` | stub não usado (strict) | qual stub | remover stub ou `lenient()` justificado |
| `@SpringBootTest` lento/quebrando | contexto inteiro | usar fatia | `@WebMvcTest`/`@DataJpaTest` |
| teste verde sem asserção real | cobertura ≠ qualidade | mutation (PIT) | adicionar asserções de comportamento |

### Lambda / AOT
| Sinal | Causa | Checagem | Correção |
|---|---|---|---|
| cold start alto | JIT / sem AOT | tempo de init medido | GraalVM AOT + `reachability-metadata.json` |
| `ClassNotFoundException` só em native | reflection não registrada | reachability metadata | registrar reflect/resource config |

---

## Python

| Sinal | Causa | Checagem | Correção |
|---|---|---|---|
| `ModuleNotFoundError` | venv errado / não editable / circular | `which python`; `pip show`; grep do import | ativar venv; `pip install -e .`; quebrar ciclo |
| `AttributeError: 'NoneType'...` | retorno `None` não tratado | de onde vem o `None` | early-return / `Optional` + guarda |
| `coroutine was never awaited` | faltou `await` | grep `async def` chamado sync | `await` / `asyncio.run` |
| loop travado (async lento) | I/O síncrono no event loop | `py-spy dump` | `run_in_executor` / lib async |
| `DetachedInstanceError` (SQLAlchemy) | sessão fechada | escopo da sessão | carregar na sessão / `joinedload` |
| `pydantic.ValidationError` | payload/env inválido | ler `loc`/`type` do erro | corrigir schema/env; migrar v1→v2 |
| `ImproperlyConfigured` (Django) | settings/env ausente | `DJANGO_SETTINGS_MODULE` / `.env` | configurar settings/env |
| `OperationalError: could not connect` | DB/Docker fora | `pg_isready` / `docker ps` | subir DB; corrigir DSN |
| Celery `Received unregistered task` | task não importada | `include`/autodiscover | registrar o módulo da task |
| pytest flaky | estado/tempo/ordem | `pytest -p randomly` | isolar estado; `freezegun`; `pytest-asyncio` mode |
| `mock` não aplica | patch no caminho errado | onde o símbolo é **usado** | `patch('modulo_que_usa.simbolo')` |
| build de wheel falha | headers/libs do SO | log do `pip` | instalar libs; usar wheel pré-compilada |

---

## Angular / TypeScript

| Sinal | Causa | Checagem | Correção |
|---|---|---|---|
| `NullInjectorError: No provider for X` | serviço fora do escopo de DI | onde é injetado | `providedIn:'root'`; providers da rota/standalone |
| `NG0200 Circular dependency` | DI circular | grafo de injeção | `inject()` tardio / redesenho |
| `NG0100 ExpressionChanged...` | valor muda durante a detecção | de onde vem o valor | mover p/ `ngOnInit`/`OnPush`; sinais |
| chamadas HTTP duplicadas | `subscribe` sem cleanup | template/serviço | `async` pipe / `takeUntilDestroyed()` |
| `TS2532 / TS18048` (undefined) | `strictNullChecks` | a expressão exata | `?` / guard / `!` justificado |
| `TS2307` módulo não encontrado | path / lib não instalada | `tsconfig` paths / `npm ls` | corrigir path / instalar dep |
| erro só no `--configuration production` | AOT / metadata dinâmica | `ng build` prod local | corrigir decorator/template não-AOT |
| `NG0303`/`NG0301` (binding) | diretiva/módulo não importado | imports do componente standalone | importar a diretiva/módulo |
| bundle estourou budget | dependência pesada / sem lazy | `source-map-explorer` | lazy load / ajustar `budgets` |
| teste `NullInjectorError` | `TestBed` incompleto | `configureTestingModule` | adicionar providers/imports; `provideHttpClientTesting()` |
| teste assíncrono não resolve | falta `tick()`/`flush()` | `fakeAsync`/`whenStable` | `tick()`/`HttpTestingController.flush()` |
| stream "morre" silenciosamente | sem `catchError` | onde o erro ocorre | `catchError` com fallback/re-notificação |

---

## Promoção de heurística
1. O `Doctor` da stack registra o par (sinal→correção) **com evidência** no diagnóstico.
2. Reincidiu? Adicione a linha aqui com a **checagem** que confirma a causa.
3. Heurística madura vira **checklist** do `Build/Runtime/Test Doctor` da skill da stack
   e, se for de qualidade, instinto do `clean-code-craftsman`.
