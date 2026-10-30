# Playbook de Performance Engineering JVM — baseado em evidência

> **Regra de ouro:** toda otimização nasce de uma medição e é validada por outra. Alegações sem
> benchmark reproduzível são rejeitadas. Fontes de ferramentas verificadas em 09/2026.

## 1. Classificação do problema (antes de qualquer ferramenta)

| Categoria | Sintoma | Ferramenta primária |
|---|---|---|
| **CPU-bound** | CPU ~100% em poucas threads; latência cresce com CPU | async-profiler CPU / JFR (hot methods) |
| **I/O-bound** | CPU ociosa; latência dominada por rede/disco/DB | async-profiler wall + JFR sockets/jdbc events |
| **Memory-bound** | GC frequente; pausas; OOM | GC logs + heap dump (MAT) + async-profiler alloc |
| **Lock/contention** | threads bloqueadas; throughput estagna com mais concorrência | async-profiler lock / thread dumps |

## 2. Toolchain (versões verificadas 09/2026)

| Ferramenta | Uso | Comando-chave |
|---|---|---|
| **JMH** | microbenchmarks (métodos/algoritmos) | `@BenchmarkMode`, `@Warmup(5)`, `@Measurement`, `@Fork(3)` |
| **async-profiler 4.4** | flame graphs CPU/alloc/lock/wall | `asprof -e cpu -d 30 -f flame.html <PID>`; `-e alloc`; `-e lock`; `-e wall` (VT/I-O) |
| **JFR + JMC 9.1.2** | perfil contínuo de produção | `-XX:StartFlightRecording=filename=app.jfr,settings=profile`; abrir no JMC |
| **GC logs** | diagnóstico de pausas/alocação | `-Xlog:gc*:file=gc.log:time,uptime,level,tags` (analisar com gceasy-like local ou manual) |
| **Heap dump** | vazamentos/reta de memória | `jcmd <PID> GC.heap_dump app.hprof` → **Eclipse MAT 1.17** (leak suspects, dominator tree) |
| **Thread dump** | deadlock/threads presas | `jcmd <PID> Thread.print` (JSON v2 no JDK 27 — parsers devem aceitar números) |
| **Startup bench** | cold start | `labs/java-spring-quarkus-benchmark/scripts/measure-startup.ps1` (primeiro HTTP 200 + RSS) |
| **Latência p50/p95/p99** | percentis sob carga | `LoadGen.java` do lab (JDK HttpClient + virtual threads, zero deps) |
| **AOT Cache / CDS** | cortar startup JVM | Boot 4.1+Java25: `-XX:AOTCacheOutput/ -XX:AOTCache`; Java<25: CDS |

## 3. Disciplina de benchmark reproduzível (JMH e carga)

1. **Mesmas condições:** mesmo JDK/versão de dependências, mesma máquina (ou ambiente descrito),
   mesmo heap (`-Xms`/`-Xmx` fixos), carga de fundo mínima.
2. **Warmup explícito:** JIT precisa aquecer (JMH: forks+warmup; carga: descartar primeiras N requests).
3. **N ≥ 3 runs, reportar MEDIANA** (e min–max quando o spread for relevante). Média mente sob cauda.
4. **A/B no mesmo commit:** mudança de performance compara com baseline medido na mesma sessão.
5. **Variação registrada:** se p95 do run A ≈ p95 do run B ±ruído, a conclusão é "sem diferença medida".
6. **COH/GC mudam entre JDKs** (COH default no 27 = −22% heap) — comparar sempre no mesmo JDK alvo.

## 4. Fluxo de diagnóstico de latência (P50/P95/P99)

```
1. Definir SLA: p99 < X ms sob Y RPS (sem SLA não há critério de parada — arquiteto-performance)
2. Medir distribuição (LoadGen com concorrência realista) — NUNCA olhar só média
3. p50 alto  → tudo lento: CPU-bound? path crítico? → flame graph CPU
4. p95/p99 alto (cauda) → GC pauses? locks? cold paths? retries? → GC logs + lock/wall profiles
5. Correção → re-medir mesmo protocolo → registrar antes/depois no ADR
```

## 5. Fluxo de diagnóstico de memória

1. GC logs: frequência/pausas → ajustar heap/GC **só com evidência de ganho**.
2. Heap dump em 2 momentos (Δ) → MAT "histogram" + dominator tree → quem retém.
3. Verificar COH (JDK 25 opt-in / 27 default) e `-XX:MaxRAMPercentage` em containers.
4. Otimização de alocação: async-profiler `-e alloc` aponta os hot spots de alocação.

## 6. Checklist de saída (toda recomendação de performance carrega)

- [ ] Métrica medida (qual), protocolo (como), antes → depois (números)
- [ ] Mediana de N runs + ambiente descrito (JDK, heap, máquina/instância)
- [ ] Custo da otimização (complexidade P1, build, manutenção)
- [ ] Riscos (regressão em outro percentil? piora de memória?)
- [ ] Rollback da mudança

> **Antipadrões:** otimizar sem perfil ("parece lento" não é dado); trocar GC por moda; usar média
> como métrica de latência; benchmark de 1 run; concluir ganho dentro do ruído.
