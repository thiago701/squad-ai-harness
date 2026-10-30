# Radar de JEPs — o que cada versão entregou (25 / 26 / 27 / 28)

> **Verificado 2026-09-27.** 1 linha por JEP. Detalhe e fontes: `versions-status.md` e
> `feature-status-catalog.md`. Cadeias de JEP significam iterações de preview/incubator até o estado atual.

## JDK 25 (LTS — GA 16/09/2025)

| JEP | Feature | Status na entrega | Impacto prático |
|---|---|---|---|
| 506 | Scoped Values | **Final** | substitui ThreadLocal p/ dados imutáveis por requisição |
| 511 | Module Import Declarations | **Final** | `import module java.base;` reduz boilerplate |
| 512 | Compact Source Files / `void main` | **Final** | programas single-file sem cerimônia |
| 513 | Flexible Constructor Bodies | **Final** | código antes de `super()`/`this()` |
| 502 | Stable Values | Preview | lazy constants (renomeado "Lazy Constants" no 26) |
| 505 | Structured Concurrency | 5º Preview | ainda não final |
| 507 | Primitive Types in Patterns | 3º Preview | Valhalla-lang; ainda preview |
| 508 | Vector API | 10º Incubator | não estabilizou |
| 470 | PEM Encodings | Preview | crypto PEM sem lib externa |
| 510 | Key Derivation Function API | **Final** | HKDF no javax.crypto |
| 519 | Compact Object Headers | Produto (opt-in) | header 96→64 bits |
| 521 | Generational Shenandoah | Produto (opt-in) | modo geracional sem flag experimental |
| 503 | Remove 32-bit x86 Port | Remoção | último 32-bit: JDK 24 |
| 509 | JFR CPU-Time Profiling | Experimental | profiling CPU Linux |
| 514/515 | Leyden: AOT CLI ergonomics / Method Profiling | **Final** | caches AOT + warmup JIT |
| 518/520 | JFR Cooperative Sampling / Method Timing | **Final** | JFR mais estável |

**Outros:** Graal JIT experimental removido; `UseCompressedClassPointers` deprecado; ~24 classes
`*Permission` deprecadas p/ remoção; `ForkJoinPool` implementa `ScheduledExecutorService`.

## JDK 26 (non-LTS — GA 17/03/2026)

| JEP | Feature | Status | Impacto prático |
|---|---|---|---|
| 517 | HTTP/3 no HttpClient | **Final** | HTTP/3 nativo |
| 522 | G1: reduzir sincronização | Final | throughput do G1 ≈ Serial |
| 516 | AOT Object Caching com qualquer GC | Final | Leyden sem restrição de GC |
| 504 | Remover Applet API | Remoção | `java.applet` fora do JDK |
| 500 | Prepare to Make Final Mean Final | Final | warning ao mutar `final` por reflexão |
| 524–530 | PEM/SC/Lazy Constants/Vector/Primitive Patterns | Previews/Incubators | iterações incrementais |

## JDK 27 (non-LTS ⚠️ — GA 15/09/2026)

| JEP | Feature | Status | Impacto prático |
|---|---|---|---|
| 523 | G1 default em TODOS os ambientes | **Final** | fim do Serial automático em ambientes pequenos |
| 527 | PQC híbrido TLS 1.3 | **Final** | X25519MLKEM768 preferido por default |
| 534 | Compact Object Headers POR DEFAULT | **Final** | −22% heap (SPECjbb2015), −8% CPU |
| 536 | JFR In-Process Data Redaction | **Final** | segredos redigidos antes de sair do processo |
| 531–538 | Lazy Constants (3º), Primitive Patterns (5º), SC (7º), Vector (12º), PEM (3º) | Previews/Incubators | Structured Concurrency: 7 previews, sem data de final |

**Remoções do 27:** JVMCI/Graal JIT; `ThreadPoolExecutor.finalize()`; `-noverify`/`-Xverify:none`/`-noclassgc`/`-verifyremote`;
VFORK; `java.locale.useOldISOCodes`. **Perf:** SHA-3 AVX-512 (ML-KEM +46–48%, ML-DSA +38–74%);
X25519/Ed25519 +46–55%; ZLIB cert compression.

## JDK 28 (EA — GA ~mar/2027) e além

| JEP | Feature | Status (21/09/2026) |
|---|---|---|
| 401 | **Value Objects (Valhalla) — Preview** | **Integrado** |
| 539 | Strict Field Initialization in the JVM (Preview) | Integrado |
| 535 | Shenandoah geracional POR DEFAULT | Targeted |
| 540 | Simple JSON API (Incubator) | Targeted |
| 542 | PEM Encodings (final) | Targeted |
| 541 | Deprecate macOS/x64 Port | Targeted |
| 544 | Leyden: Ahead-of-Time Code Compilation | Proposto |

- **Valhalla:** value classes em preview no 28; finalização esperada no ciclo 28/29 (LTS 29 é o alvo provável).
- **Babylon:** pesquisa (code reflection + HAT p/ GPU/AI); sem JEP na mainline até o 27.
- **Leyden:** 483 (24) → 514/515 (25) → 516 (26) → 544 proposto (28).

## Regra prática de adoção

- **Produção hoje:** Java 25 LTS (Temurin/Corretto) — usar somente features **Final**; previews só com
  `--enable-preview` + decisão humana registrada.
- **Acompanhar sem adotar:** 27 (COH/PQC/G1 universal — valem como gains "de graça" ao subir para 29),
  JDK 28 EA (Valhalla preview — testar em labs).
- **Próximo alvo LTS:** Java 29 (set/2027).
