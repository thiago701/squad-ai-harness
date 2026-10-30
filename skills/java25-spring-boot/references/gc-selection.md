# Garbage Collectors no JDK 25 — Guia de Seleção

> **Objetivo:** Escolher o GC correto para seu caso de uso (latência vs throughput),
> evitar padrão subótimo (G1 em tudo), e monitorar corretamente.

**Última atualização:** 2026-04-10

---

## 1. Landscape de GCs no JDK 25

| GC | Status | Pausa típica | Heap ideal | Caso de Uso |
|---|---|---|---|---|
| **Serial** | Stable | 10-100ms | < 256MB | CLI, batch, dev leve |
| **Parallel** | Stable | 50-500ms | 2-8GB | High-throughput batch |
| **G1** | Default | 10-200ms | 512MB-32GB | Balanceado (padrão) |
| **ZGC** | Stable (Java 15+) | < 10ms | 1-1000GB+ | Latência crítica |
| **Shenandoah** | Stable | < 10ms | 512MB-32GB | Latência crítica (alternativa) |
| **Epsilon** | Experimental | 0ms (no GC!) | Qualquer | Benchmarking, no-op |

---

## 2. Matriz de Decisão (Regra Prática)

| Cenário | Heap | Latência alvo | GC recomendado | Flags JVM |
|---|---|---|---|---|
| **CLI, batch, dev leve** | < 256MB | N/A | Serial | `-XX:+UseSerialGC` |
| **Microserviço comum** | 512MB-4GB | p99 < 500ms | **G1 (padrão)** | `-XX:+UseG1GC -XX:MaxGCPauseMillis=200` |
| **High-throughput batch** | 2-8GB | throughput >> latência | Parallel | `-XX:+UseParallelGC -XX:ParallelGCThreads=4` |
| **Latência crítica (trading)** | 1-32GB | p99 < 10ms | **ZGC** | `-XX:+UseZGC -XX:+ZGenerational` |
| **Heap gigante** | > 32GB | p99 < 10ms | **ZGC** | `-XX:+UseZGC -XX:+ZGenerational -Xmx64g` |
| **Latência extrema + heap pequeno** | < 8GB | p99 < 5ms | Shenandoah | `-XX:+UseShenandoahGC` |
| **Dev local / CI (startup rápido)** | qualquer | N/A | Serial | `-XX:+UseSerialGC -XX:TieredStopAtLevel=1` |
| **Latência consistente (finanças)** | 4-16GB | GC pause < 20ms | ZGC Generational | `-XX:+UseZGC -XX:+ZGenerational -XX:-ZGenerationalMode` |

---

## 3. Guia Detalhado por GC

### 3.1 Serial GC — `UseSerialGC`

**Características:**
- Single-threaded (1 thread para GC)
- Stop-the-world (todas threads Java pausam)
- Mínimo overhead, máxima simplicidade

**Quando usar:**
- CLI (command-line tools)
- Batch jobs (uma vez por dia)
- Desenvolvimento local
- Containers com < 256MB memória

**Flags:**
```bash
java -XX:+UseSerialGC -Xms128m -Xmx256m -jar app.jar
```

**Benchmark:**
```
Heap: 256MB
Throughput: ~100 ops/sec
GC Pause: 15-30ms
Frequency: ~10s

Adequado para: CLI tools que executam uma vez
Inadequado para: APIs web com requisições contínuas
```

---

### 3.2 Parallel GC — `UseParallelGC`

**Características:**
- Multi-threaded (N threads = CPU cores)
- Stop-the-world (todas threads Java pausam)
- Otimizado para **throughput**

**Quando usar:**
- Batch processing (nightly jobs, ETL)
- High-volume data processing
- Quando latência pica não importam

**Flags:**
```bash
java -XX:+UseParallelGC \
     -XX:ParallelGCThreads=4 \
     -Xms2g -Xmx8g \
     -jar app.jar
```

**Benchmark:**
```
Heap: 4GB, 4 cores
Throughput: ~50k ops/sec
GC Pause: 100-500ms (aceitável para batch)
Frequency: ~5min

Adequado para: MapReduce, Spark jobs locais
Inadequado para: APIs web (pausas longas inaceitáveis)
```

---

### 3.3 G1GC — `UseG1GC` (Padrão desde Java 9)

**Características:**
- Dividir heap em regions (1-32MB cada)
- Incremental: limpar regions parcialmente
- Balanceado: throughput ≈ latência

**Quando usar:**
- **Padrão para a maioria dos casos**
- Microserviços (500MB-4GB)
- APIs web com múltiplos clients
- Quando não há requirement extremo

**Flags:**
```bash
java -XX:+UseG1GC \
     -XX:MaxGCPauseMillis=200 \
     -Xms1g -Xmx4g \
     -jar app.jar
```

**Interpretação de flags:**
- `-XX:MaxGCPauseMillis=200` → target max pause de 200ms (não garantido, heurístico)
- Valores < 50ms: G1 pode não atingir (requer heap maior ou menos aplicações)
- Valores > 500ms: não há benefício vs Parallel

**Benchmark:**
```
Heap: 2GB, 4 cores
Throughput: ~30k ops/sec
GC Pause: Young 20-50ms, Mixed 80-200ms
Frequency: Young ~5s, Mixed ~30s

Adequado para: Servidor web padrão
Inadequado para: p99 < 10ms (use ZGC)
```

**Tuning G1:**
```bash
# Mais agressivo com full GC
java -XX:+UseG1GC \
     -XX:MaxGCPauseMillis=100 \
     -XX:InitiatingHeapOccupancyPercent=35 \
     -Xms2g -Xmx4g \
     -jar app.jar
```

---

### 3.4 ZGC — `UseZGC` (Java 11+, production-ready Java 15+)

**Características:**
- **Ultra-low latency:** pausas < 10ms GARANTIDAS
- Concurrent: não stop-the-world
- Heap de qualquer tamanho (até 16TB)
- Generational: Young/Old separation (Java 21+)

**Quando usar:**
- Trading, gaming, real-time systems
- p99 < 10ms é requirement
- Heap > 8GB com latência crítica

**Flags:**
```bash
# ZGC básico (Java 15-20)
java -XX:+UseZGC -Xms4g -Xmx16g -jar app.jar

# ZGC Generational (Java 21+) — RECOMENDADO
java -XX:+UseZGC \
     -XX:+ZGenerational \
     -Xms4g -Xmx16g \
     -jar app.jar
```

**Benchmark:**
```
Heap: 8GB, 4 cores
Throughput: ~25k ops/sec (5% menos que G1)
GC Pause: < 2ms GARANTIDO
Frequency: Continuous (concurrent, não pausável)

Trade-off: 5-10% throughput por garantia de < 10ms pause
Adequado para: Finanças, gaming, comunicação de baixa latência
```

**ZGC Generational vs Non-Generational:**

| Aspecto | Non-gen | Generational |
|---|---|---|
| Pause latency | < 10ms | < 10ms |
| Throughput | ~25k | ~27k |
| GC frequency | Contínuo | Contínuo |
| Heap suportado | Até 16TB | Até 16TB |
| Recomendação | Java 15-20 | **Java 21+ (padrão)** |

**Sempre usar `-XX:+ZGenerational` em Java 21+.**

---

### 3.5 Shenandoah GC — `UseShenandoahGC`

**Características:**
- Alternativa a ZGC
- Pausas < 10ms
- Concurrent marking + concurrent evacuation
- Melhor em heaps pequenos (< 8GB)

**Quando usar:**
- Alternativa a ZGC se preferir
- Latência crítica com heap < 8GB
- Comparar benchmarks com ZGC (resultados similares)

**Flags:**
```bash
java -XX:+UseShenandoahGC \
     -Xms2g -Xmx8g \
     -jar app.jar
```

**Benchmark:**
```
Heap: 4GB
Throughput: ~26k ops/sec
GC Pause: < 2ms
Trade-off: Similar a ZGC, ligeiramente menos bem documentado
```

---

### 3.6 Epsilon GC — Experimental

**NUNCA usar em produção.** Apenas para benchmarking e debugging.

```bash
# Apenas benchmarking — sem GC real
java -XX:+UnlockExperimentalVMOptions -XX:+UseEpsilonGC -jar app.jar
```

---

## 4. Critério "3x Rule" — Quando Trocar de GC

Se o seu p99 atual é **3x maior** que o target, considere mudar de GC:

```
Target p99: 50ms
Atual p99: 200ms  (200 ÷ 50 = 4x)
Ação: Avaliar troca para ZGC ou aumento de heap
```

**Exemplo real:**
```
Microserviço com G1:
  p50: 20ms ✓
  p95: 80ms ✓
  p99: 250ms ✗ (target era 100ms)

Troca para ZGC:
  p50: 18ms
  p95: 45ms
  p99: 8ms ✓
  
Custo: 5% throughput, +40% heap
Benefício: SLA atendido
```

---

## 5. Custo de Troca de GC

Antes de trocar, considere:

| Fator | Impacto | Tempo estimado |
|---|---|---|
| Warmup (JIT re-compila) | p99 cresce 2-3x por 15-30min | 15-30 min |
| Profiling novo | Aprender padrão de GC | 1-2 dias |
| Alertas recalibrados | Alertas antigos não aplicam | 2-4 horas |
| Testes de load | Validar novo GC | 1-2 dias |

**Timeline mínimo:** 2-3 horas (com confiança nível: baixo)
**Timeline recomendado:** 1-2 dias (validação + canary + rollout)

---

## 6. Métricas a Monitorar

### 6.1 Micrometer (Spring Boot 4)

```java
// Metrics já exportadas automaticamente
// GC metrics via OpenTelemetry ou JMX
```

**Chaves importantes:**

```
jvm.gc.pause                   # Latência de pausa (histogram)
jvm.gc.memory.allocated        # Memória alocada por GC
jvm.gc.memory.promoted         # Memória promovida (Young → Old)
jvm.gc.memory.used             # Uso atual de heap
jvm.gc.max                     # Heap máximo configurado
jvm.gc.live.data.size          # Dados "vivos" (reterá após GC)
jvm.threads.live               # Threads vivas (correlaciona com pausas)
```

### 6.2 Flags de Diagnóstico (Dev/Staging)

```bash
# Imprimir eventos de GC (verbose)
java -XX:+PrintGCDetails \
     -XX:+PrintGCDateStamps \
     -XX:+PrintGCTimeStamps \
     -Xloggc:gc.log \
     -jar app.jar

# Analyize com GCLogAnalyzer ou Censum
# Resultado: visualizar pausa, frequência, promção
```

### 6.3 JFR (Java Flight Recorder) — Production

```bash
# Ligar JFR em tempo de execução
jcmd <pid> JFR.start duration=60s filename=recording.jfr

# Analyize (abrir em JDK Mission Control)
jmc recording.jfr
```

---

## 7. Anti-Padrões Comuns

### "Use ZGC para tudo"

❌ ZGC não é bullet-proof:
- Adiciona ~5-10% overhead de throughput
- Requer tuning para heaps gigantes (> 32GB)
- Overkill para aplicações que toleram p99 de 200ms

✅ G1 é escolha correta para maioria dos microserviços.

### "Heap grande = melhor performance"

❌ Heap > 8GB aumenta:
- Tempo de Full GC (se ocorrer)
- Footprint (mais memória = mais custo)
- Complexidade de tuning

✅ Começar com 2GB, aumentar até 50% de uso sob pico.

### "Ignorar live data size"

❌ Se `jvm.gc.live.data.size` > 70% do heap:
- GC fica congestionado
- Pausas crescem exponencialmente
- Application "vai para o chão"

✅ Monitorar; se crescer, investigar memory leak.

---

## 8. Troubleshooting

### "p99 cresce continuamente"

**Sintoma:**
```
T0: p99 = 50ms
T1: p99 = 80ms
T2: p99 = 150ms
...
```

**Causas:**
1. Memory leak (live data size crescendo)
2. Full GC ativando (heap mal-dimensionado)
3. Padrão de acesso mudou (mais dados em memória)

**Solução:**
```bash
# 1. Criar heap dump
jcmd <pid> GC.heap_dump heap.hprof

# 2. Analyize com Eclipse MAT
# 3. Procurar por:
#    - Collections crescendo sem limite
#    - Caches sem eviction
#    - Ciclos de referência circulares

# Temporário: aumentar heap
java -Xmx8g -jar app.jar

# Permanente: fix memory leak
```

### "Full GC ocorre frequentemente"

**Sintoma:**
```
GC log: [Full GC (Ergonomics) 12345M->8765M(16384M), 5.234 secs]
```

**Causas:**
1. Young gen pequeno demais (promocão acelerada)
2. Concurrent mark não acompanha alocação
3. Swap ativado (máquina sem memória)

**Solução:**

Para G1:
```bash
java -XX:+UseG1GC \
     -XX:MaxGCPauseMillis=100 \    # Ser menos agressivo
     -XX:InitiatingHeapOccupancyPercent=30 \  # Começar coleta mais cedo
     -Xms4g -Xmx4g \               # Fixed size (evitar Full GC)
     -jar app.jar
```

### "ZGC crashes com OutOfMemoryError"

**ZGC não tem Full GC.** Se ocorrer OOM:
- Heap insuficiente (aumentar `-Xmx`)
- Allocation rate > GC rate (inaceitável)

```bash
# Diagnóstico
java -XX:+UseZGC \
     -XX:+PrintGCDetails \
     -Xmx16g \                     # Aumentar heap
     -jar app.jar

# Se ainda falhar: problema de app (leak)
```

---

## 9. Checklist: Escolher e Validar GC

- [ ] Requisito de latência definido (p50, p95, p99)
- [ ] Heap inicial estimado (regra: 2-4GB para start)
- [ ] GC candidato escolhido (usar matriz de decisão)
- [ ] Flags JVM configuradas
- [ ] Aplicação rodando com novo GC
- [ ] 30min de warmup (JIT compiler)
- [ ] Load test (JMeter, Gatling, etc.)
- [ ] Métricas coletadas (Micrometer, JFR)
- [ ] p99 dentro do target?
  - Sim: passar para staging
  - Não: ajustar flags ou trocar GC
- [ ] Alertas no Prometheus/DataDog reconfigurados
- [ ] Rollout progressivo (canary 5% → 25% → 100%)

---

## Referências

- [OpenJDK GC Tuning](https://docs.oracle.com/en/java/javase/25/gctuning/)
- [ZGC Documentation](https://openjdk.java.net/projects/zgc/)
- [GC LogAnalyzer](https://www.gceasy.io/)
- [Censum](https://www.jclarity.com/censum/)

