# Breaking changes e playbook de migração entre JDKs

> **Fonte:** pesquisa 2026-09-27 (release notes oficiais + JEPs) para a janela 21→27;
> caminhos legados (8/11/17→21) por conhecimento consolidado da Squad (sem fonte viva —
> validar com jdeprscan no projeto real). **Regra:** nada de "não quebra nada" sem
> jdeprscan/jdeps + suite verde no alvo.

## 1. Remoções/desativações confirmadas — janela 21 → 27

| O quê | Quando | Impacto / remédio |
|---|---|---|
| String Templates (preview) | 23 | código com `STR.\{...}` não compila mais — reescrever (JDK-8329949) |
| RMI Activation | 23 | serviços legados de ativação RMI quebram |
| Security Manager desativado | 24 (JEP 486) | `System.setSecurityManager()` lança `UnsupportedOperationException`; migrar p/ permissões de SO/container; ~24 classes `*Permission` deprecadas no 25 |
| TLS 1.0/1.1 desabilitados | 24 | clientes/servidores antigos precisam TLS ≥ 1.2 |
| ZGC não-geracional removido | 24 (JEP 490) | `-XX:+UseZGC -XX:-ZGenerational` não funciona mais |
| Unsafe/JNI: avisos | 24 (JEP 498/472) | preparar migração p/ FFM API |
| Port 32-bit x86 | 25 (JEP 503) | apps 32-bit ficam no 24 ou migram |
| Graal JIT experimental | 25 | removido; JVMCI sai de vez no 27 |
| `UseCompressedClassPointers` | deprec. 25, obsoleto 27 | sempre comprimido agora — remover a flag |
| PerfData sampling / `sun.rt._sync*` | 25 | migrar monitoramento p/ JFR/JMX |
| `VFORK` launch mechanism | deprec. 25, removido 27 | usar POSIX_SPAWN (default) ou FORK |
| `java.locale.useOldISOCodes` | deprec. 25, removido 27 | usar códigos ISO atuais (he, yi, id) |
| Applet API | 26 (JEP 504) | `java.applet` removido |
| Mutação de `final` via reflexão | 26 (JEP 500) | warning na 1ª ocorrência; corrigir antes do enforcement |
| JVMCI / Graal JIT | 27 | módulos `jdk.internal.vm.ci`, `jdk.graal.compiler.*` e `-XX:+UseGraalJIT` removidos — usar GraalVM ou JDK 26 |
| `ThreadPoolExecutor.finalize()` | 27 | subclass que chama `super.finalize()` quebra compilação; finalização segue rumo à remoção total (JEP 421) |
| `-noverify` / `-Xverify:none` / `-noclassgc` / `-verifyremote` | 27 | scripts de launch antigos falham; `-Xnoclassgc` substitui |
| JNDI/LDAP factories default | 27 | apps que dependiam de defaults precisam setar as properties |
| HttpServer prefix matching | 27 | `/foo` não casa mais `/foobar`; flag de compat `sun.net.httpserver.pathMatcher` |
| G1 flags | 27 | `InitiatingHeapOccupancyPercent` → `G1IHOP`; `Min/MaxHeapFreeRatio` default 0/100 |
| ML-KEM/ML-DSA key encoding | 27 | default `seed` — chaves novas não são lidas por JDKs ≤ 26; `expandedKey` p/ compat |
| ZLIB TLS cert compression | 27 | habilitado por default (`jdk.tls.client.disableExtensions` desliga) |
| JSON thread dump formato v2 | 27 | parsers próprios devem aceitar números (tids/contagens) |

## 2. Caminhos legados — 8 / 11 / 17 → 21 (conhecimento consolidado)

| Salto | Principais breaking changes |
|---|---|
| **8 → 11** | Módulos Java EE removidos do JDK (JAXB, JAX-WS, CORBA, JTA, Activation — adicionar deps explícitas ou migrar); Nashorn → GraalJS; `_` vira keyword (9); version strings novas; `--illegal-access` passa a avisar (9-15) |
| **11 → 17** | Encapsulamento forte default: acesso reflexivo ilegal **negado** (16); `--illegal-access` removido (17); Security Manager deprecado (JEP 411); Applet e RMI Activation deprecados p/ remoção; finalização deprecada p/ remoção (18); CMS GC removido (14); biased locking deprecado (15) |
| **17 → 21** | previews viram final (Pattern Matching for switch, Record Patterns, Virtual Threads, Sequenced Collections); TLS 1.0/1.1 desabilitados por default; RMI Activation removido (23); String Templates previews removidos (23); warning de `final` mutado (preparação) |

**Bibliotecas que costumam quebrar** (validar versão antes do salto): ASM/CGLIB (Spring em 17+ exige ASM9),
Lombok (versões antigas não suportam 21+), Byte Buddy/Mockito (inline mock maker), JaCoCo, plugins Maven
antigos (compiler ≤ 3.8, surefire ≤ 2.x), Gradle < 8.5 p/ Java 21+, conteineres base sem o JDK alvo,
GraalVM deve casar com o JDK alvo (Mandrel 25 p/ Java 25).

## 3. Playbook oficial de migração (ordem obrigatória)

1. **`jdeprscan --release <alvo> --for-removal app.jar`** — primeira triagem de APIs deprecadas/removidas.
2. **`jdeps --jdk-internals --multi-release 21 app.jar`** — uso de APIs internas (`sun.misc.Unsafe`, `com.sun.*`).
3. **Compilar com `-Xlint:deprecation -Xlint:removal` e `--release <alvo>`** — warnings viram lista de trabalho.
4. **Varredura de padrões de risco:** `setSecurityManager`, `AccessController`, `sun.misc.Unsafe`,
   `finalize(` sobrescrito, `STR.` (templates), `System.loadLibrary` (JNI), `-XX:+UnlockExperimentalVMOptions`,
   `--enable-preview` no build (toda preview pode sumir), TLS ≤ 1.1 em `jdk.tls.disabledAlgorithms`.
5. **Flags de GC:** ZGC só-geracional; G1 default universal (27); Shenandoah geracional vira default no 28.
6. **Leyden/CDS:** reavaliar flags AOT antigas (`-XX:AOTCache`); `-XX:AOTMode=required` no 27.
7. **Tooling:** parsers de thread dump devem aceitar JSON v2 (27).
8. **Medir startup/perf antes/depois** (JFR/JMH) — COH default no 27 muda o uso de heap.

## 4. Template de plano de migração (artefato do GATE 1)

```markdown
# Plano de migração: <projeto> — Java <origem> → <destino>
- **Decisão de alvo:** <versão> (<LTS?> | suporte da distribuição escolhida>)
- **Inventário:** jdeprscan: N achados | jdeps internals: N achados | previews em uso: <lista>
- **Matriz de trabalho:**

| Item | Categoria | Impacto | Ação | Risco | Validação |
|---|---|---|---|---|---|
| ex.: Uso de sun.misc.Unsafe em X | API interna | alto | migrar p/ FFM (JEP 454) | médio | teste unit + JMH |

- **Ordem:** 1) build no alvo → 2) testes → 3) GC/flags → 4) container → 5) perf baseline
- **Rollback:** <como voltar (build anterior + imagem anterior)>
- **Status de features usadas:** <todas final; NENHUMA preview/incubator sem decisão humana>
```
