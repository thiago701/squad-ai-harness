# Virtual Threads — Deep Dive

## Internals: Como Funcionam

Virtual threads rodam em cima de "carrier threads" (platform threads gerenciados pelo ForkJoinPool).
Quando um virtual thread executa uma operação bloqueante (I/O, sleep, lock), ele é "unmounted"
do carrier thread, liberando-o para executar outro virtual thread. Quando a operação completa,
o virtual thread é remontado em qualquer carrier disponível.

### Carrier Thread Pool

```
Carrier threads = Runtime.getRuntime().availableProcessors()  // por padrão
```

O pool é gerenciado automaticamente pela JVM. Raramente precisa de tuning manual.
Se necessário: `-Djdk.virtualThreadScheduler.parallelism=N`

## Pinning — O Inimigo das Virtual Threads

Pinning ocorre quando um virtual thread não consegue ser desmontado do carrier thread.
Causa: o thread está dentro de um bloco `synchronized` ou executando código nativo via JNI.

### Detectando Pinning

```bash
# Flag de diagnóstico
-Djdk.tracePinnedThreads=full    # log detalhado no stderr
-Djdk.tracePinnedThreads=short   # apenas stack summary
```

```java
// JFR Event — monitoramento em produção
// Evento: jdk.VirtualThreadPinned
// Filtrar por duration > 20ms para encontrar pinning problemático
```

### Resolvendo Pinning

```java
// ANTES (causa pinning):
synchronized (lock) {
    database.query(sql);  // Operação bloqueante dentro de synchronized!
}

// DEPOIS (sem pinning):
private final ReentrantLock lock = new ReentrantLock();

lock.lock();
try {
    database.query(sql);
} finally {
    lock.unlock();
}
```

Bibliotecas que ainda usam `synchronized` internamente (algumas versões antigas de drivers JDBC,
por exemplo) podem causar pinning. Verifique as versões mínimas:

| Biblioteca | Versão Mínima sem Pinning |
|-----------|--------------------------|
| HikariCP | 5.1+ |
| PostgreSQL JDBC | 42.7+ |
| MySQL Connector/J | 9.0+ |
| Lettuce (Redis) | 6.3+ |
| Apache HttpClient | 5.3+ |

## Métricas para Monitoramento

```java
// Micrometer + virtual threads
@Bean
MeterBinder virtualThreadMetrics() {
    return registry -> {
        Gauge.builder("jvm.virtual_threads.active",
                Thread::activeCount)  // Nota: inclui platform threads
            .register(registry);
    };
}
```

Para métricas mais granulares, use JFR streaming:

```java
// JFR streaming em tempo real
try (var rs = new RecordingStream()) {
    rs.enable("jdk.VirtualThreadStart").withPeriod(Duration.ofSeconds(1));
    rs.enable("jdk.VirtualThreadEnd");
    rs.enable("jdk.VirtualThreadPinned").withThreshold(Duration.ofMillis(20));

    rs.onEvent("jdk.VirtualThreadPinned", event -> {
        log.warn("Virtual thread pinned por {}ms na thread {}",
            event.getDuration().toMillis(),
            event.getString("carrierThread"));
    });

    rs.startAsync();
}
```

## Padrão: Rate Limiting com Semaphore

Virtual threads facilitam a criação de milhares de tarefas, mas recursos downstream
(banco, APIs externas) têm limites. Use Semaphore para controlar concorrência:

```java
private static final Semaphore DB_PERMITS = new Semaphore(50); // max 50 queries simultâneas

public User findUser(Long id) {
    DB_PERMITS.acquire();
    try {
        return jdbcTemplate.queryForObject("SELECT ...", rowMapper, id);
    } finally {
        DB_PERMITS.release();
    }
}
```

## Padrão: Timeout com Structured Concurrency

```java
try (var scope = StructuredTaskScope.open(Joiner.allSuccessfulOrThrow())) {

    var task1 = scope.fork(() -> slowService.call());
    var task2 = scope.fork(() -> anotherService.call());

    // JDK 25 final API: timeout global de 5s
    scope.joinUntil(Instant.now().plusSeconds(5));  // Lança TimeoutException se exceder 5s

    return combine(task1.get(), task2.get());
}
```

## Anti-Padrões

### 1. Pool de Virtual Threads (sem necessidade)
```java
// ERRADO — não precisa de pool para virtual threads
ExecutorService pool = Executors.newFixedThreadPool(100, Thread.ofVirtual().factory());

// CORRETO — um VT por tarefa, sem pool
ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor();
```

### 2. ThreadLocal em contexto de virtual threads
```java
// ERRADO — não propaga para subtasks
private static final ThreadLocal<String> correlationId = new ThreadLocal<>();

// CORRETO — propaga automaticamente
private static final ScopedValue<String> CORRELATION_ID = ScopedValue.newInstance();
```

### 3. Ignorar que virtual threads são baratos mas não grátis
```java
// ERRADO — criar VTs em loop apertado sem necessidade
for (int i = 0; i < 1_000_000; i++) {
    Thread.startVirtualThread(() -> cpuIntensiveWork());  // CPU-bound!
}

// CORRETO — virtual threads para I/O, parallel streams para CPU
items.parallelStream().map(this::cpuIntensiveWork).toList();
```
