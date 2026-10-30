# GraalVM Native + Java 25 — Estado da Arte (SOTA 2025-2026)

> Quando ler: sempre que gerar/evoluir uma Lambda Java 25 **native** (o padrão da Squad —
> ver [[graalvm-native-java25-default]]), ou precisar de build args, metadata, versões e faixas
> de latência **atuais e com fonte**. Compilado de pesquisa web verificada (set/2025–2026);
> cada afirmação factual traz URL. Substitui números/versões desatualizados espalhados nas skills.

## 0. TL;DR das mudanças vs. o que as skills diziam

| Item | Estava (desatualizado) | Correto (2025-2026) |
|---|---|---|
| `native-maven-plugin` | 0.10.2 / 0.10.4 | **1.1.3** (série 1.x; 1.0.0 quebrou compat) |
| Metadata de reflexão | `reflect-config.json` separado | **`reachability-metadata.json`** unificado (JDK 23+) |
| RIC | 2.6.0 | **2.10.1+** (README mostra 2.11.0) |
| Powertools Java | v1 (`@Metrics`, Log4j) | **v2** (`@FlushMetrics`, SLF4J+MDC) — é onde está o suporte native |
| Edição GraalVM | "Enterprise vs CE" | **Oracle GraalVM (GFTC, grátis) vs CE** |
| Cold start native | "30–150 ms" (sem fonte) | ~**4× menor que java21**; p95 medido **~540 ms** instrumentado — medir |
| Java 25 + SnapStart | "não-GA / usar java21" | **GA 14/nov/2025** (`java25`); SnapStart Java 11+ inclui java25 |
| Java 25: "primitives em patterns" | citado como pronto | **PREVIEW (JEP 507)** |

## 1. Distribuição e licenciamento (a marca "Enterprise" acabou)

A partir do JDK 25 não existe mais "GraalVM Enterprise". A distinção que importa:

| Edição | Licença | Recursos exclusivos p/ native |
|---|---|---|
| **Oracle GraalVM 25** (25.0.x/25.1.x) | **GFTC** — grátis, **inclui produção** | `--gc=G1`, `-O3`/GraalNN (ML), **PGO**, obfuscation, SBOM |
| **GraalVM CE 25** (GPLv2+CPE) | livre | só Serial/Epsilon GC, `-O0/-Ob/-O2`, **sem PGO / sem G1 / sem -O3** |

- Oracle GraalVM for JDK 24 foi o último sob Java SE; do 25 em diante a Oracle aponta Java SE para o Project Leyden, **mas Native Image segue vivo e gratuito via GFTC** (produção inclusa). — graalvm.org/downloads, blogs.oracle.com/graal/graalvm-free-license, infoworld.com/article/4061937
- **Implicação prática:** se um Dockerfile/CI usa a imagem CE (`ghcr.io/graalvm/native-image-community:25`), então `--gc=G1`, `-O3` e PGO **não funcionam** (falham ou viram no-op). Para Lambda isso não dói — o GC certo é o **Serial** (§3).

## 2. `native-maven-plugin` 1.1.3 (era 0.10.x — duas séries atrás)

- Série atual **1.x**; última estável **1.1.3** (jun/2025). O **1.0.0 foi breaking change**: adotou o `reachability-metadata.json` e abandonou o `metadata/index.json` global. — github.com/graalvm/native-build-tools/releases
- **1.1.0+** adicionou a goal **`listLibrariesMissingMetadata`** (diagnóstico de metadata faltante).
- Agente e metadata-repository agora se configuram **pelo plugin** (§4), não invocando `-agentlib:` na mão.

```xml
<native.plugin.version>1.1.3</native.plugin.version>
```

## 3. Build args — o que usar em Lambda arm64/provided.al2023

Níveis de otimização (graalvm.org/latest/reference-manual/native-image/optimizations-and-performance):

| Flag | Uso | Nota |
|---|---|---|
| `-Ob` | quick build (CI/dev) | compila rápido, **peak menor** |
| `-O2` | **default de produção** | GraalSP (profiler estático) |
| `-Os` | binário mínimo | otimiza tamanho |
| `-O3` | máximo (GraalNN/ML) | **Oracle GraalVM apenas — no-op no CE** |

- **PGO (Profile-Guided Optimization)** — **Oracle GraalVM apenas**. Fluxo: `--pgo-instrument` → rodar exercitando caminhos reais (gera `.iprof`) → `--pgo=arquivo.iprof`. Sem PGO, o Oracle GraalVM já aplica ML profile inference (~6% de ganho). Ganho do PGO real varia por workload (a doc não crava %). — .../PGO/basic-usage
- **GC:** para Lambda use o **`serial` (default)** — footprint mínimo, processo efêmero, uma request por vez. **NÃO use `--gc=G1`** (é para long-running, e é Oracle-only + Linux). Serial já é generational.
- **`-march`:** build **em arm64** (Graviton). `-march=native` só é seguro se build e runtime forem o mesmo arm64; senão `-march=compatibility`.
- **Static linking:** `provided.al2023` traz glibc → **`--static-nolibc` (mostly-static)** basta; não precisa musl full-static. Se usar musl, exija **musl > 1.2.5** (CVE-2025-26519).
- **buildArgs recomendados p/ Lambda native (produção):**
  ```
  --no-fallback
  --enable-url-protocols=https
  -O2                              # (ou -O3 SÓ se build em Oracle GraalVM)
  ```
  **NÃO** coloque como default cego: `-O3` (Oracle-only), `--enable-preview` (só se o código usa feature preview do JDK — acopla o binário a features instáveis), `-H:+UnlockExperimentalVMOptions` (só junto da opção `-H:` experimental específica que o exige).
- **Footprint:** Serial GC usa por default 80% da RAM; para memória pequena, `-R:MaximumHeapSizePercent=<pct>` deixa folga ao runtime. Não fixe `-R:MaxHeapSize` absoluto (perde elasticidade ao reconfigurar a memória da função).

## 4. Reachability metadata — a mudança mais importante

O formato **`reachability-metadata.json`** (JDK 23+) **unifica** o que eram `reflect-config.json`,
`resource-config.json`, `proxy-config.json`, `jni-config.json`, `serialization-config.json`.
Local: `META-INF/native-image/<groupId>/<artifactId>/reachability-metadata.json`.
Os `*-config.json` separados **ainda funcionam (deprecados)** — não misture fontes duplicadas.
No JDK 25: JNI vive em `"reflection"` com `"jniAccessible": true`; bundles em `"resources"` com `"bundle"`.
— graalvm.org/latest/reference-manual/native-image/metadata, graalvm.org/release-notes/JDK_25

**Coletar metadata (preferir o agente via plugin, não `-agentlib:` na mão):**
```xml
<configuration>
  <metadataRepository><enabled>true</enabled></metadataRepository>  <!-- GraalVM Reachability Metadata Repo p/ libs conhecidas -->
  <agent><enabled>true</enabled></agent>
</configuration>
```
```bash
./mvnw -Pnative -Dagent=true test native:metadata-copy   # roda testes com agente → reachability-metadata.json
./mvnw -Pnative native:build listLibrariesMissingMetadata   # diagnóstico (plugin 1.1.0+)
```
Agente manual (fallback, com **merge** ao iterar):
```bash
java -agentlib:native-image-agent=config-merge-dir=src/main/resources/META-INF/native-image/<group>/<artifact> -jar app.jar
```
**Regra:** o agente só cobre o que você **exercita** — rode **todos** os access patterns (getItem/query/putItem/delete de cada entidade), senão um caminho novo quebra em produção.

**Inicialização build-time vs run-time:** classes de **logging (SLF4J/Log4j/Logback)** fazem binding via static blocks que dependem de runtime → devem ser `--initialize-at-run-time`, não build-time. ⚠️ Registrar `--initialize-at-build-time=org.slf4j.LoggerFactory` **cego** pode conflitar com a stack de logging (Log4j2/Logback) — validar caso-a-caso. Segredo lido num `<clinit>` inicializado em build-time fica **congelado/vazado** no binário.

**No JDK 25** os erros de metadata faltante agora são subclasses de **`LinkageError`** (antes tipos distintos) — atualize os `catch`/diagnóstico. Use `--exact-reachability-metadata` para pegar cedo.

## 5. As "3 AOTs" — a distinção que a skill deve ensinar

Três mecanismos diferentes reduzem cold start; não são a mesma coisa:

| Mecanismo | O que é | Runtime | Cold start | Custo |
|---|---|---|---|---|
| **GraalVM Native AOT** | app compilada p/ **binário nativo**; sem JVM | `provided.al2023` | mais baixo (~4× < java21) | build +min, reflect metadata |
| **Leyden AOT cache** (JEP 483 final/24 + 515 final/25) | **continua JVM**; pré-carrega classes + perfis de método num cache lido no boot | managed `java25` (**default**) | sub-2 s (melhor que JVM fria) | training run |
| **SnapStart** (Firecracker) | **snapshot** da JVM já inicializada, restaurado | managed Java 11+ | 200–500 ms (P99 −90%) | config SAM; **grátis p/ Java** |

- **Runtime gerenciado `java25`** (GA 14/nov/2025) liga **AOT caches (Leyden) por default** — substituiu o CDS tradicional. ⚠️ Se você habilitar CDS manual, a Lambda **desabilita** o AOT cache; e **AOT cache custom é desaconselhado no managed** (patching invalida). — aws.amazon.com/blogs/compute/aws-lambda-now-supports-java-25
- **SnapStart no Java 25:** deixou de parar a tiered compilation em C1 → melhor peak sem penalizar cold start.
- **Por que Native é o default da Squad p/ Java 25:** menor cold start (performance/P2, prioridade do usuário). SnapStart (`java25` agora disponível, **grátis p/ Java**) permanece o **override** de menor esforço/TCO. Native ≠ Leyden cache ≠ SnapStart.

## 6. Java 25 (LTS, GA 16/set/2025) — features com precisão (final vs preview)

| Feature | JEP | Status | Relevância Lambda |
|---|---|---|---|
| Virtual threads | 444 | **final desde 21** | só ganha em **fan-out de I/O** num handler; pinning em `synchronized` **resolvido no 24 (JEP 491)** |
| Scoped Values | 506 | **FINAL no 25** | substitui ThreadLocal p/ contexto de request |
| Structured Concurrency | 505 | **PREVIEW (5º)** | futuro do fan-out; **não** no caminho default (exige `--enable-preview`) |
| Compact Object Headers | 519 | **FINAL, opt-in** | `-XX:+UseCompactObjectHeaders` → **10–20% menos heap** = **menos GB-segundo** |
| Pattern matching for switch | 441 | **final desde 21** | é o mecanismo do `mapError(Exception)` da skill — correto |
| Record patterns | 440 | final desde 21 | desestruturação |
| Unnamed variables/patterns | 456 | final desde 22 | `catch (X _)`, bindings ignorados |
| **Primitives em patterns** | 507 | **PREVIEW (3º)** | ⚠️ a skill citava como pronto — **é preview**, não usar por default |
| FFM API | 454 | final desde 22 | nicho; em GraalVM 25 habilitado por default (registrar downcalls no build) |
| AOT Class Loading/Linking | 483 | final no 24 | base do AOT cache do managed |
| AOT Method Profiling | 515 | final no 25 | perfis no AOT cache → warmup mais rápido |

- ZGC/Shenandoah: **relevância baixa** em Lambda (heap pequeno, efêmero). Não recomendar por default.
- Modelagem de domínio: records + sealed + pattern-matching-for-switch (441) + record patterns (440) + unnamed (456) — **todos finais**, usar à vontade.

## 7. AWS Lambda + Native — produção

- **RIC (Runtime Interface Client):** padrão da skill (`mainClass=com.amazonaws.services.lambda.runtime.api.client.AWSLambda`, lê `_HANDLER` `classe::metodo`). **Versão atual 2.10.1+** (README mostra 2.11.0; era 2.6.0). Suporta arm64. — github.com/aws/aws-lambda-java-libs (RIC README)
- **INIT do `provided.al2023` SEMPRE foi cobrado** — custom runtime já incluía o INIT no billed duration (a padronização de 1/ago/2025 mudou só ZIP+managed on-demand). Narrativa correta: "native **paga** o INIT, mas o INIT é curtíssimo". — aws.amazon.com/blogs/compute/aws-lambda-standardizes-billing-for-init-phase
- **Cold start — números honestos (medir!):** native reduz ~**4× vs java21** (90% dos requests, AWS CRT blog); p95 medido **~542 ms** em função instrumentada com Powertools (vs 1682 ms na JVM). "30–150 ms" só para handler **enxuto** — não é fato citável; usar o `lambda-aot-benchmark/` interno como fonte e **medir por Power Tuning**. — aws.amazon.com/blogs/compute/introducing-v2-of-powertools-for-aws-lambda-java, aws.amazon.com/blogs/developer/aws-crt-client-for-java-adds-graalvm-native-image-support
- **DynamoDB Enhanced Client sob native:** `BeanTableSchema.fromBean` usa reflexão → precisa de metadata. SDK v2 tem suporte GraalVM out-of-the-box desde **2.16.1**; BOM atual **2.30.x+**. Preferir o **`native-image-agent` exercitando todos os access patterns** + hints; considerar **`@DynamoDbImmutable` + `StaticImmutableTableSchema` (records)** para reduzir superfície reflexiva. — docs.aws.amazon.com/sdk-for-java/latest/developer-guide/setup-project-graalvm.html
- **HTTP client:** `url-connection-client` (default leve, ótimo cold start) **ou** **`aws-crt-client`** (suporte native oficial desde SDK **2.28.7**, metadata embutida, "4× no cold start" medido). Escolha **um** (misturar infla o binário). Evite Netty em native.
- **Powertools for Java v2 (GA 31/jul/2025)** — é onde está o **suporte GraalVM native de todas as utilities**. API **mudou** vs v1: `@Metrics`→**`@FlushMetrics`**, `MetricsUtils`→`MetricsFactory.getMetricsInstance()`, `Unit`→`MetricUnit`, logging Log4j+`LoggingUtils.appendKey`→**SLF4J + `MDC.put()`**, `<LambdaJsonLayout/>`→`<JsonTemplateLayout eventTemplateUri="classpath:LambdaJsonLayout.json"/>`, artefatos `powertools-core`→`powertools-common`, `powertools-logging`→`powertools-logging-log4j`, idempotency split em `-core`+`-dynamodb`, e exige `org.aspectj:aspectjrt` explícito. — docs.aws.amazon.com/powertools/java/latest/upgrade
- **Build/deploy arm64:** `Metadata: BuildMethod: makefile` + target `build-<LogicalId>` (`mvn -Pnative native:compile` → copia `bootstrap`) + `sam build --use-container`. ⚠️ **GraalVM não cross-compila x86→arm64 de forma confiável** — compile **em arm64**: container `--platform=linux/arm64`, host Graviton, **CodeBuild ARM**, ou Apple Silicon. Não faça build x86 no CI e deploy arm64. — graalvmonlambda.com, github.com/oracle/graal/issues/4143
- **CI de testes native:** `native:test` compila a suíte em native (minutos, muita RAM) — caro por PR. **Estratégia:** testes na JVM (`mvn verify`, gate de cobertura) + **um `native:compile`** provando `--no-fallback` + **smoke test do `bootstrap`** (invoca 1-2 caminhos felizes por handler). Suíte native completa só em release.
- **Observabilidade em native:** X-Ray via **Powertools v2 `@Tracing`** (metadata inclusa) + `Tracing: Active`. ⚠️ o **agente ADOT/OTel Java NÃO funciona em native** (substrate VM, sem bytecode reescrito) — use o **OTel SDK / Spring Starter** (compile-time). — aws-otel.github.io/docs/getting-started/lambda/lambda-java

## 8. Backlog de migração (aplicar em passe dedicado, requer build)

Itens de maior porte que exigem editar templates + validar build (não feitos ainda; priorizados):
1. **Powertools v1 → v2** nos templates (`pom.xml.tmpl`, `log4j2.xml.tmpl`, handlers `.tmpl`, `lambda-powertools-java.md`). Maior impacto na corretude do código gerado.
2. **`reflect-config.json` → `reachability-metadata.json`** no `scaffold_lambda.py` / `reflect-config.json.tmpl`.
3. **Agente via plugin** (`<agent>` + `native:metadata-copy`) nos references de troubleshooting.
4. **CRT client** como opção premium em `aws-sdk-v2-dynamodb.md`; BOM SDK → 2.30.x+.

## Fontes primárias
graalvm.org/release-notes/JDK_25 · graalvm.org/latest/reference-manual/native-image/ (metadata, optimizations-and-performance, PGO, MemoryManagement, build-static-executables) · github.com/graalvm/native-build-tools/releases · graalvm.github.io/native-build-tools · openjdk.org/jeps/{444,454,456,483,491,505,506,507,515,519} · aws.amazon.com/blogs/compute/{aws-lambda-now-supports-java-25, introducing-v2-of-powertools-for-aws-lambda-java, aws-lambda-standardizes-billing-for-init-phase} · aws.amazon.com/blogs/developer/aws-crt-client-for-java-adds-graalvm-native-image-support · docs.aws.amazon.com/{lambda/latest/dg/snapstart.html, sdk-for-java/latest/developer-guide/setup-project-graalvm.html, powertools/java/latest/upgrade} · github.com/aws/aws-lambda-java-libs · aws-otel.github.io/docs/getting-started/lambda/lambda-java
