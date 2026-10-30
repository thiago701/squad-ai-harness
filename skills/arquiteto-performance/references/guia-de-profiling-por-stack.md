# arquiteto-performance · Guia de Profiling por Stack

> Reference da skill `arquiteto-performance` (movida da SKILL.md em 11/10/2026 — hub + references, I3). Carregue só quando a tarefa pedir este tema.

## Guia de Profiling por Stack

### Python

**Identificando o gargalo:**
```python
# CPU-bound: use cProfile ou py-spy (sem overhead de produção)
# Instalação: pip install py-spy
py-spy top --pid <PID>                    # top-like para Python
py-spy record -o profile.svg --pid <PID>  # flamegraph

# I/O-bound: use async profiling ou logs de query
# Django: django-silk ou django-debug-toolbar
# FastAPI: opentelemetry-instrumentation-fastapi

# Memory: use memray (melhor opção atual)
# pip install memray
memray run -o output.bin meu_script.py
memray flamegraph output.bin
```

**CPU-bound em Python — soluções:**
```python
# GIL impede paralelismo real em threads para CPU-bound
# Use multiprocessing para CPU-bound real
from concurrent.futures import ProcessPoolExecutor

def processar_chunk(chunk):
    # processamento pesado
    return resultado

with ProcessPoolExecutor(max_workers=4) as executor:
    resultados = list(executor.map(processar_chunk, chunks))

# Ou: mova para C com numpy/pandas para operações vetorizadas
# Ruim (loop Python puro):
total = sum(x * 2 for x in lista_grande)
# Bom (vetorizado):
import numpy as np
total = np.array(lista_grande) * 2  # 10-100x mais rápido
```

**I/O-bound em Python — async é a resposta:**
```python
# FastAPI já é async — use corretamente
# Ruim: chamadas síncronas em endpoint async
@app.get("/dados")
async def get_dados():
    resultado = requests.get("http://api-externa")  # BLOQUEIA o event loop!
    return resultado.json()

# Bom: use httpx async
import httpx

@app.get("/dados")
async def get_dados():
    async with httpx.AsyncClient() as client:
        resultado = await client.get("http://api-externa")
    return resultado.json()

# Múltiplas chamadas em paralelo:
async def buscar_tudo():
    async with httpx.AsyncClient() as client:
        resultados = await asyncio.gather(
            client.get("http://api1"),
            client.get("http://api2"),
            client.get("http://api3"),
        )
    return resultados  # 3 chamadas no tempo de 1
```

**Pool de conexões com banco — erro mais comum:**
```python
# FastAPI + SQLAlchemy: configure pool adequadamente
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,          # conexões mantidas abertas
    max_overflow=20,       # conexões extras sob pico
    pool_pre_ping=True,    # valida conexão antes de usar
    pool_recycle=3600,     # recria conexões após 1h (evita timeout do servidor)
)
```

---

### Java / Kotlin

**Identificando o gargalo:**
```bash
# JVM Flight Recorder (sem overhead em produção)
# Ative na JVM:
-XX:+FlightRecorder -XX:StartFlightRecording=duration=60s,filename=recording.jfr

# Analise com JDK Mission Control (JMC)
# Mostra: CPU hotspots, alocações, GC, locks, I/O

# async-profiler (melhor opção, overhead < 1%)
./profiler.sh -d 30 -f flamegraph.html <PID>

# Para Spring Boot: Actuator + Micrometer já embutem métricas
# Adicione ao application.yml:
management:
  endpoints.web.exposure.include: health,metrics,prometheus
  metrics.distribution.percentiles-histogram.http.server.requests: true
```

**GC Pressure — diagnóstico e solução:**
```kotlin
// Sintoma: GC pause > 50ms frequentes, throughput caindo sob carga
// Diagnóstico: adicione flags JVM
// -Xlog:gc*:gc.log:time,uptime,level,tags

// Solução 1: G1GC (padrão JDK 11+) bem configurado
-XX:+UseG1GC
-XX:MaxGCPauseMillis=100      // meta de pausa máxima
-XX:G1HeapRegionSize=16m      // ajuste para heaps grandes

// Solução 2: ZGC Generational (padrão em Java 25 para heaps > 2GB)
// JDK 21 tornou -XX:+ZGenerational default, JDK 25 habilita ZGC Generational como padrão
// quando o heap passa de 2GB. Pausas < 1ms mesmo com heap 16TB.
-XX:+UseZGC -XX:+ZGenerational  // heap 8GB-16TB, p99 previsível
// Métricas: jfr "gc.zgc.phase" + "gc.phase.young/old" mostram pausas por fase

// Solução 3: CRaC (Coordinated Restore at Checkpoint) — startup em ms
// Checkpoint de JVM aquecida → restore em 40-100ms, equivalente a GraalVM Native
// Implementar Resource e responder beforeCheckpoint / afterRestore
// Use para: Lambda com cold start < 200ms, autoscaling agressivo em ECS

// Solução 4: JFR Event Streaming + OpenTelemetry — observabilidade contínua
// JFR "always on" com Event Streaming publica eventos em tempo real
// para OTel ou Prometheus, sem salvar arquivo .jfr
-XX:StartFlightRecording=filename=recording.jfr,maxage=30m,maxsize=1g
// + JFR Event Streaming API: capturar Allocation, GC, Exceptions em runtime

// No código Kotlin: evite alocações desnecessárias em hot paths
// Ruim: cria objeto a cada chamada
fun calcular(valor: Int): ResultWrapper = ResultWrapper(valor * 2)

// Bom: use tipos primitivos e evite boxing em loops críticos
fun calcular(valor: Int): Int = valor * 2
```

**Virtual Threads (Java 25 / Kotlin) — revolução para I/O-bound:**
```kotlin
// Spring Boot 3.2+ com Virtual Threads habilitados
// application.yml:
spring:
  threads:
    virtual:
      enabled: true

// Com isso, cada request HTTP roda em uma Virtual Thread
// Resultado: 10.000+ requisições concorrentes sem thread pool starvation
// Ideal para: APIs com muitas chamadas a banco/APIs externas

// Kotlin Coroutines para código explicitamente async:
suspend fun buscarDados(): DadosResponse = coroutineScope {
    val usuarios = async { usuarioRepository.findAll() }
    val pedidos  = async { pedidoRepository.findRecentes() }
    DadosResponse(usuarios.await(), pedidos.await()) // paralelo real
}
```

**N+1 em JPA/Hibernate — o assassino silencioso:**
```kotlin
// Ruim: N+1 clássico
val pedidos = pedidoRepository.findAll()
pedidos.forEach { pedido ->
    println(pedido.cliente.nome) // 1 query por pedido!
}

// Bom: fetch join explícito
@Query("SELECT p FROM Pedido p JOIN FETCH p.cliente WHERE p.status = :status")
fun findByStatusComCliente(status: String): List<Pedido>

// Bom: EntityGraph para casos mais complexos
@EntityGraph(attributePaths = ["cliente", "itens", "itens.produto"])
fun findAll(): List<Pedido>

// Detecte N+1 em desenvolvimento:
// application.yml:
spring.jpa.show-sql: true
logging.level.org.hibernate.stat: DEBUG
spring.jpa.properties.hibernate.generate_statistics: true
```

---
