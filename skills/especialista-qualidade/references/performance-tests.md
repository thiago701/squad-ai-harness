# Testes de Performance — k6, Locust, Gatling, Pipeline CI

> **Quando ler:** ao definir SLAs como código, criar suítes de load/stress/spike/soak, ou integrar performance no pipeline.

> **Princípio:** performance é requisito não-funcional executável. SLA em percentil (p95/p99), nunca média. No CI sempre — não como sprint de estabilização.

---

## CAMADA 4 — Testes de Performance

Testes de performance são **requisitos executáveis de SLA** — não relatórios de benchmark. Pertencem ao pipeline de CI e bloqueiam merge quando SLAs são violados.

### Tipos de Testes de Performance

| Tipo | Objetivo | Duração | Métricas Chave |
|---|---|---|---|
| **Baseline** | Estabelecer referência em condições normais | 5 min | p50, p95, p99, RPS |
| **Load** | Validar SLA sob carga esperada sustentada | 20-30 min | p95 < SLA, error rate < 1% |
| **Stress** | Encontrar ponto de ruptura | até quebrar | RPS máximo, degradação gradual |
| **Spike** | Recuperação após pico repentino | pico 1 min + recovery | tempo de recuperação < X seg |
| **Soak** | Detectar vazamentos e degradação gradual | 2-8 horas | memória, GC, latência ao longo do tempo |
| **Concurrency** | Validar comportamento sob acesso simultâneo | 10 min | deadlocks, erros de concorrência |

### k6 — Scripts de Performance (Python e Java usam igualmente)
```javascript
// tests/performance/load/confirmar_pedido_load.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Métricas customizadas
const erroRate      = new Rate('errors');
const latenciaP95   = new Trend('latencia_p95');
const confirmacoes  = new Counter('confirmacoes_sucesso');

// Definição dos SLAs como código — falha o teste se violados
export const options = {
  stages: [
    { duration: '2m',  target: 100  },  // ramp-up
    { duration: '10m', target: 100  },  // carga sustentada
    { duration: '2m',  target: 0    },  // ramp-down
  ],
  thresholds: {
    'http_req_duration{name:confirmar}': ['p(95)<200', 'p(99)<500'],  // SLA contratual
    'errors':                            ['rate<0.01'],               // max 1% de erro
    'http_req_failed':                   ['rate<0.01'],
  },
};

export function setup() {
  // Cria dados de teste e retorna contexto compartilhado
  const pedidos = criarPedidosParaTeste(200);
  return { pedidos, token: autenticar() };
}

export default function(data) {
  const pedido = data.pedidos[Math.floor(Math.random() * data.pedidos.length)];

  const res = http.post(
    `${__ENV.BASE_URL}/api/v1/pedidos/${pedido.id}/confirmar`,
    JSON.stringify({ operador_id: 'operador-teste' }),
    {
      headers: {
        'Content-Type':  'application/json',
        'Authorization': `Bearer ${data.token}`,
      },
      tags: { name: 'confirmar' },  // agrupa métricas por operação
    }
  );

  const sucesso = check(res, {
    'status é 200 ou 409': (r) => r.status === 200 || r.status === 409,
    'resposta tem pedido_id': (r) => JSON.parse(r.body).pedido_id !== undefined,
    'latência abaixo de 500ms': (r) => r.timings.duration < 500,
  });

  erroRate.add(!sucesso);
  latenciaP95.add(res.timings.duration);
  if (res.status === 200) confirmacoes.add(1);

  sleep(0.1);  // 10 RPS por VU
}

export function teardown(data) {
  limparDadosDeTeste(data.pedidos);
}
```

```javascript
// tests/performance/stress/confirmar_pedido_stress.js
// Encontra o ponto de ruptura aumentando carga progressivamente
export const options = {
  stages: [
    { duration: '3m', target: 100  },
    { duration: '3m', target: 300  },
    { duration: '3m', target: 500  },
    { duration: '3m', target: 800  },
    { duration: '3m', target: 1200 },  // além do limite esperado
    { duration: '5m', target: 0   },   // recovery
  ],
  thresholds: {
    // Não falha — apenas coleta dados para análise do ponto de ruptura
    'http_req_duration': ['p(99)<2000'],
  },
};
```

```javascript
// tests/performance/spike/confirmar_pedido_spike.js
export const options = {
  stages: [
    { duration: '1m',  target: 100  },  // baseline
    { duration: '30s', target: 2000 },  // pico repentino
    { duration: '30s', target: 2000 },  // mantém o pico
    { duration: '3m',  target: 100  },  // recovery
    { duration: '2m',  target: 100  },  // valida estabilidade pós-pico
  ],
  thresholds: {
    // Sistema deve se recuperar em menos de 30s após o pico
    'http_req_duration{phase:recovery}': ['p(95)<300'],
  },
};

export default function() {
  // Taga a fase atual para separar métricas de pico e recovery
  const fase = __ITER < 2000 ? 'spike' : 'recovery';
  http.post(`${__ENV.BASE_URL}/api/v1/pedidos/confirmar`,
    null, { tags: { phase: fase } });
}
```

### Locust — Performance em Python com lógica de negócio
```python
# tests/performance/load/locustfile.py
from locust import HttpUser, task, between, events
from decimal import Decimal
import random

class OperadorPedidosUser(HttpUser):
    """Simula um operador confirmando pedidos no sistema."""

    wait_time = between(0.5, 2.0)  # think time realista
    token: str = ""

    def on_start(self):
        """Autentica e prepara dados de teste para este usuário virtual."""
        response = self.client.post("/auth/token", json={
            "username": "operador-teste", "password": "senha-teste"
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # Cria pedidos para este usuário usar nos testes
        self.pedidos_ids = [
            self._criar_pedido_pendente() for _ in range(10)
        ]

    @task(5)  # peso 5 — operação mais frequente
    def confirmar_pedido(self):
        if not self.pedidos_ids:
            self.pedidos_ids = [self._criar_pedido_pendente() for _ in range(5)]

        pedido_id = self.pedidos_ids.pop()
        with self.client.post(
            f"/api/v1/pedidos/{pedido_id}/confirmar",
            headers=self.headers,
            name="/pedidos/[id]/confirmar",  # agrupa métricas
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 409:
                response.success()  # idempotente — esperado
            else:
                response.failure(f"Status inesperado: {response.status_code}")

    @task(3)
    def buscar_pedido(self):
        pedido_id = random.randint(1, 1000)
        self.client.get(
            f"/api/v1/pedidos/{pedido_id}",
            headers=self.headers,
            name="/pedidos/[id]",
        )

    @task(1)
    def listar_pedidos(self):
        self.client.get(
            "/api/v1/pedidos?status=PENDENTE&page=0&size=20",
            headers=self.headers,
            name="/pedidos?status=PENDENTE",
        )

    def _criar_pedido_pendente(self) -> int:
        response = self.client.post(
            "/api/v1/pedidos",
            json={"valor": str(Decimal("100.00")), "produto_id": 1},
            headers=self.headers,
            name="/pedidos [setup]",
        )
        return response.json()["id"]


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("Iniciando testes de performance — validando SLAs...")

@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    # Falha o pipeline se SLAs forem violados
    stats = environment.stats.total
    if stats.avg_response_time > 200:
        environment.process_exit_code = 1
        print(f"FALHA: latência média {stats.avg_response_time:.0f}ms > SLA 200ms")
    if stats.fail_ratio > 0.01:
        environment.process_exit_code = 1
        print(f"FALHA: error rate {stats.fail_ratio:.1%} > SLA 1%")
```

### Gatling — Performance para Java/Kotlin (DSL Scala/Kotlin)
```kotlin
// tests/performance/ConfirmarPedidoSimulation.kt
import io.gatling.javaapi.core.*
import io.gatling.javaapi.core.CoreDsl.*
import io.gatling.javaapi.http.*
import io.gatling.javaapi.http.HttpDsl.*
import java.time.Duration

class ConfirmarPedidoSimulation : Simulation() {

    val httpProtocol = http
        .baseUrl(System.getenv("BASE_URL") ?: "http://localhost:8080")
        .acceptHeader("application/json")
        .contentTypeHeader("application/json")
        .shareConnections()

    val autenticar = exec(
        http("autenticar").post("/auth/token")
            .body(StringBody("""{"username":"operador","password":"senha"}"""))
            .check(jsonPath("$.access_token").saveAs("token"))
    )

    val confirmarPedido = exec(
        http("confirmar pedido").post("/api/v1/pedidos/#{pedidoId}/confirmar")
            .header("Authorization", "Bearer #{token}")
            .check(status().`in`(200, 409))  // 409 = idempotente, ok
            .check(responseTimeInMillis().lt(500))  // SLA por requisição
    )

    val cenarioOperador = scenario("Operador Confirmando Pedidos")
        .exec(autenticar)
        .feed(csv("pedidos_ids.csv").circular())  // IDs dos pedidos de teste
        .repeat(50) {
            exec(confirmarPedido).pause(Duration.ofMillis(100))
        }

    // SLAs definidos como código — falham o pipeline automaticamente
    init {
        setUp(
            cenarioOperador.injectOpen(
                rampUsers(50).during(Duration.ofMinutes(2)),   // ramp-up
                constantUsersPerSec(100.0).during(Duration.ofMinutes(10)), // carga
            )
        )
        .protocols(httpProtocol)
        .assertions(
            global().responseTime().percentile(95.0).lt(200),  // p95 < 200ms
            global().responseTime().percentile(99.0).lt(500),  // p99 < 500ms
            global().failedRequests().percent().lt(1.0),        // error rate < 1%
            global().requestsPerSec().gt(80.0),                 // throughput mínimo
        )
    }
}
```

### Integração de Performance no Pipeline CI/CD
```yaml
# .github/workflows/quality.yml
stages:
  unit-tests:
    script: pytest tests/unit/ -x --tb=short
    threshold: 100% pass

  integration-tests:
    script: pytest tests/integration/ --tb=short
    services: [postgres:16, kafka:7.5]

  functional-tests:
    script: pytest tests/functional/ --tb=short

  performance-tests:
    script: |
      # Baseline (rápido — executa em todo PR)
      k6 run --duration 2m --vus 50 tests/performance/load/baseline.js \
        -e BASE_URL=$STAGING_URL

      # Load completo (apenas em merge para main)
      if [ "$CI_BRANCH" == "main" ]; then
        k6 run tests/performance/load/confirmar_pedido_load.js \
          -e BASE_URL=$STAGING_URL \
          --out json=results.json

        # Compara com baseline anterior — falha se regressão > 10%
        python scripts/compare_performance.py results.json baselines/last.json
      fi
```

---
