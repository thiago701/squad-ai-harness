# Catálogo de status de features do JDK — tabela-mestra

> **Verificado em 2026-09-27.** Status = situação no **JDK 27** (GA 15/09/2026) salvo indicação.
> Regra de uso: **Final** = produção; **Preview** = só com `--enable-preview` + decisão humana
> (pode ser removida sem aviso — precedente: String Templates); **Incubator/Experimental** = nunca em produção.

| Feature | Status atual | Onde nasceu / evento-chave | JEP(s) |
|---|---|---|---|
| Virtual Threads | **Final** (21) | `synchronized` sem pinning desde o 24 | 444 → 491 |
| Structured Concurrency | **Preview (7ª rodada, 27)** — sem data de final | evolução desde o 21; design ainda em ajuste | 428→453→462→480→499→505→525→533 |
| Scoped Values | **Final** (25) | substituto seguro do ThreadLocal | 429→…→506 |
| Foreign Function & Memory API | **Final** (22) | avisos p/ JNI/Unsafe (24); downcall state init (27) | 442→454; 472, 498 |
| Vector API | **Incubator (12ª rodada, 27)** | recordista; estabilização bloqueada em Valhalla | 338→…→537 |
| Class-File API | **Final** (24) | java.lang.classfile | 457→466→484 |
| Module Import Declarations | **Final** (25) | `import module java.base;` | 476→494→511 |
| Compact Source Files / `void main` | **Final** (25) | scripts single-file limpos | 445→…→512 |
| Flexible Constructor Bodies | **Final** (25) | código antes de super()/this() | 492→…→513 |
| String Templates | **REMOVIDO (23)** | preview 21/22; design processor-centric abandonado | 430/459 → JDK-8329949 |
| Compact Object Headers | **Default (27)** | experimental 24 → produto opt-in 25 → **default 27** | 450→519→534 |
| Stable Values → **Lazy Constants** | Preview (3ª, 27) | renomeado no 26 | 502→526→531 |
| Primitive Patterns (int/float/boolean em patterns) | Preview (5ª, 27) | segue p/ o 28 com Valhalla | 455→488→507→530→532 |
| Value Classes/Objects (Valhalla) | **Preview previsto p/ JDK 28** | integrado na mainline | 401 (+539) |
| PEM Encodings (crypto) | Preview (3ª, 27) · **final targeted p/ 28** | chaves/certs PEM sem lib externa | 470→524→538→542 |
| Simple JSON API | Incubator targeted p/ 28 | JSON padrão no JDK | 540 |
| HTTP/3 no HttpClient | **Final** (26) | jdk.httpclient + provider HTTP/3 | 517 |
| PQC híbrido TLS 1.3 | **Final** (27) | X25519MLKEM768 preferido por default | 527 |
| JFR in-process data redaction | **Final** (27) | segredos redigidos antes de sair do processo | 536 |
| Key Derivation Function API | **Final** (25) | HKDF no javax.crypto | 510 |
| Security Manager | **Desativado de vez** (24) | setSecurityManager lança UnsupportedOperationException; *Permission deprecadas no 25 | 486 |
| Applet API | **Removido** (26) | java.applet fora do JDK | 504 |
| Port 32-bit x86 | **Removido** (25) | último suporte: 24 | 503 |
| ZGC | **Só-geracional** (default 23; não-geracional removido 24) | latência < 1 ms | 474, 490 |
| Shenandoah | Geracional = produto (25, opt-in); **default no 28** | — | 404→521→535 |
| G1 | **Default universal** (27); throughput melhorado (26) | fim do Serial automático em ambientes restritos | 523, 522, 475 |
| Epsilon | Experimental inalterado | testes/benchmarks | 318 |
| Leyden (AOT caches) | Produto (25-27); **compilação AOT proposta p/ 28** | `-XX:AOTMode=required` é alias oficial no 27 | 483→514/515→516→544 |
| JVMCI / Graal JIT | **Removido** (27) | uso de Graal JIT nativo exige GraalVM ou JDK 26 | — |
| Finalização (`Object.finalize`) | Caminho de remoção | deprecada desde 18; ThreadPoolExecutor.finalize() removido no 27 | 421 |

## Impactos medidos (para decisões de performance — encaminhar a java-pro/arquiteto-performance)

- **COH (JEP 534):** header 96→64 bits; SPECjbb2015 **−22% heap, −8% CPU**, −15% coletas (G1/Parallel);
  benchmark JSON paralelo +10%. Amazon em produção (backports p/ 21/17); SAP default no SapMachine.
  Desligar: `-XX:-UseCompactObjectHeaders` (layout antigo será deprecado). Incompatível com ZGC em versões antigas — **no 27 é default para todos os GCs**.
- **Cripto (27):** SHA-3 AVX-512 → ML-KEM +46–48%, ML-DSA +38–74%; X25519/Ed25519 +46–55%.
- **AOT/Leyden:** startup mais rápido sem sacrificar pico de performance (Quarkus 3.32 mediu 370→80 ms;
  ver `quarkus-graalvm-notes.md`).

## Fontes primárias

- https://openjdk.org/projects/jdk/25/ · /26/ · /27/ · /28/ (listas de JEPs)
- https://jdk.java.net/27/release-notes
- https://openjdk.org/jeps/534 · /523 · /527 · /536
- https://openjdk.org/projects/valhalla/
- https://bugs.openjdk.org/browse/JDK-8329949 (remoção de String Templates)
