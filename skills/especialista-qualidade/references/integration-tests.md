# Testes de Integração — Detalhamento Completo

> **Quando ler:** ao escrever testes de integração com infraestrutura real. Pré-requisito: SKILL.md + unit-tests.md.

> **Princípio inegociável:** infraestrutura real sempre. Zero H2, zero mocks de repositório. Use Testcontainers + `@ServiceConnection` (Boot 3.1+).

## CAMADA 2 — Testes de Integração

Testes de integração verificam o **contrato entre camadas** com infraestrutura real — banco de dados, filas de mensagem, caches e serviços externos. Nenhum mock de infraestrutura é aceito nesta camada.

### Princípios de Testes de Integração
- **Infraestrutura real sempre**: use Testcontainers — nunca H2, nunca mocks de repositório.
- **Isolamento por teste**: cada teste começa com estado limpo. Use transações com rollback ou truncate entre testes.
- **Teste o contrato, não os detalhes**: verifique que os dados persistidos e recuperados preservam as invariantes do domínio.
- **Erros de infraestrutura são cidadãos de primeira classe**: teste o que acontece quando o banco está lento, a fila está cheia, o índice está ausente.

### Python — Testcontainers com PostgreSQL e Kafka
```python
# tests/integration/repository/test_pedido_repository.py
import pytest
from decimal import Decimal
from testcontainers.postgres import PostgresContainer
from testcontainers.kafka import KafkaContainer
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# ── FIXTURES DE INFRAESTRUTURA ────────────────────────────────────────────────

@pytest.fixture(scope="session")
def postgres():
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg

@pytest.fixture(scope="session")
def kafka():
    with KafkaContainer("confluentinc/cp-kafka:7.5.0") as kf:
        yield kf

@pytest.fixture(scope="session")
def async_engine(postgres):
    url = postgres.get_connection_url().replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(url, echo=False, pool_size=5)
    yield engine

@pytest.fixture(scope="session", autouse=True)
async def criar_schema(async_engine):
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@pytest.fixture
async def session(async_engine):
    """Cada teste recebe uma sessão com rollback automático — estado sempre limpo."""
    async with async_engine.connect() as conn:
        await conn.begin()
        async_session = AsyncSession(bind=conn)
        yield async_session
        await conn.rollback()  # garante isolamento entre testes

# ── TESTES DE CONTRATO DO REPOSITÓRIO ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_salva_e_recupera_pedido_com_todos_os_campos(session):
    repo = PedidoSQLAlchemyRepository(session)
    pedido = PedidoBuilder.pendente().com_valor(Decimal("250.75")).build()

    await repo.salvar(pedido)
    recuperado = await repo.buscar_por_id(pedido.id)

    assert recuperado is not None
    assert recuperado.valor == Decimal("250.75")
    assert recuperado.status == StatusPedido.PENDENTE
    assert recuperado.cliente.email == pedido.cliente.email

@pytest.mark.asyncio
async def test_buscar_por_id_retorna_none_para_id_inexistente(session):
    repo = PedidoSQLAlchemyRepository(session)

    resultado = await repo.buscar_por_id(pedido_id=99999)

    assert resultado is None

@pytest.mark.asyncio
async def test_rollback_nao_persiste_pedido_quando_excecao_ocorre(session):
    repo = PedidoSQLAlchemyRepository(session)
    pedido = PedidoBuilder.pendente().build()

    await repo.salvar(pedido)
    await session.rollback()  # simula falha explícita

    resultado = await repo.buscar_por_id(pedido.id)
    assert resultado is None  # rollback garantido

@pytest.mark.asyncio
async def test_listagem_por_status_retorna_apenas_correspondentes(session):
    repo = PedidoSQLAlchemyRepository(session)
    confirmados = [PedidoBuilder.confirmado().com_id(i).build() for i in range(1, 4)]
    cancelados  = [PedidoBuilder.cancelado().com_id(i).build() for i in range(4, 7)]

    for p in confirmados + cancelados:
        await repo.salvar(p)

    resultado = await repo.listar_por_status(StatusPedido.CONFIRMADO)

    assert len(resultado) == 3
    assert all(p.status == StatusPedido.CONFIRMADO for p in resultado)

@pytest.mark.asyncio
async def test_concorrencia_dois_saves_do_mesmo_pedido_sem_corrupcao(session, async_engine):
    """Invariante: acesso concorrente não deve corromper o estado do pedido."""
    import asyncio
    repo = PedidoSQLAlchemyRepository(session)
    pedido = PedidoBuilder.pendente().build()
    await repo.salvar(pedido)

    async def confirmar():
        async with AsyncSession(async_engine) as s:
            r = PedidoSQLAlchemyRepository(s)
            p = await r.buscar_por_id(pedido.id)
            if p and p.status == StatusPedido.PENDENTE:
                p.confirmar()
                await r.salvar(p)
                await s.commit()

    # Dispara 10 confirmações simultâneas para o mesmo pedido
    await asyncio.gather(*[confirmar() for _ in range(10)])

    final = await repo.buscar_por_id(pedido.id)
    assert final.status == StatusPedido.CONFIRMADO  # estado consistente

# ── TESTE DE INTEGRAÇÃO COM MENSAGERIA ────────────────────────────────────────

@pytest.mark.asyncio
async def test_evento_pedido_confirmado_publicado_no_kafka(kafka):
    from aiokafka import AIOKafkaConsumer
    publisher = PedidoKafkaPublisher(bootstrap_servers=kafka.get_bootstrap_server())
    pedido = PedidoBuilder.confirmado().build()

    await publisher.pedido_confirmado(pedido)

    consumer = AIOKafkaConsumer(
        "pedidos.confirmados",
        bootstrap_servers=kafka.get_bootstrap_server(),
        auto_offset_reset="earliest",
        consumer_timeout_ms=5000,
    )
    async with consumer:
        mensagens = [m async for m in consumer]

    assert len(mensagens) == 1
    payload = json.loads(mensagens[0].value)
    assert payload["pedido_id"] == pedido.id
    assert payload["status"] == "CONFIRMADO"
```

### Java 25 / Kotlin — Testcontainers com Spring Boot
```kotlin
// tests/integration/PedidoRepositorioIntegrationTest.kt
@SpringBootTest
@Testcontainers
@Transactional  // rollback automático após cada teste
class PedidoRepositorioIntegrationTest {

    companion object {
        @Container @JvmStatic
        val postgres = PostgreSQLContainer<Nothing>("postgres:16-alpine")
            .withDatabaseName("testdb")
            .withReuse(true)  // reutiliza container entre runs — mais rápido

        @Container @JvmStatic
        val kafka = KafkaContainer(DockerImageName.parse("confluentinc/cp-kafka:7.5.0"))
            .withReuse(true)

        @DynamicPropertySource @JvmStatic
        fun configureProperties(registry: DynamicPropertyRegistry) {
            registry.add("spring.datasource.url",            postgres::getJdbcUrl)
            registry.add("spring.datasource.username",       postgres::getUsername)
            registry.add("spring.datasource.password",       postgres::getPassword)
            registry.add("spring.kafka.bootstrap-servers",   kafka::getBootstrapServers)
        }
    }

    @Autowired lateinit var repositorio: PedidoRepository
    @Autowired lateinit var testEntityManager: TestEntityManager

    // ── HAPPY PATH ────────────────────────────────────────────────────────────
    @Test
    fun `deve persistir pedido e recuperar com todos os campos intactos`() {
        val pedido = PedidoBuilder.pendente().comValor(BigDecimal("250.75")).build()

        repositorio.save(pedido)
        testEntityManager.flush()
        testEntityManager.clear()  // limpa cache de primeiro nível

        val recuperado = repositorio.findById(pedido.id!!).orElseThrow()
        recuperado.valor  shouldBe BigDecimal("250.75")
        recuperado.status shouldBe StatusPedido.PENDENTE
        recuperado.cliente.email shouldBe pedido.cliente.email
    }

    // ── BOUNDARY ──────────────────────────────────────────────────────────────
    @Test
    fun `deve retornar Optional vazio para id inexistente`() {
        repositorio.findById(Long.MAX_VALUE).isPresent shouldBe false
    }

    // ── CONCORRÊNCIA ──────────────────────────────────────────────────────────
    @Test
    fun `acesso concorrente nao deve corromper estado do pedido`() {
        val pedido = PedidoBuilder.pendente().build()
        repositorio.save(pedido)

        val resultados = (1..20).map {
            CompletableFuture.runAsync {
                try {
                    val p = repositorio.findById(pedido.id!!).orElseThrow()
                    if (p.status == StatusPedido.PENDENTE) {
                        p.confirmar()
                        repositorio.save(p)
                    }
                } catch (_: OptimisticLockingFailureException) {
                    // esperado — apenas uma thread vence
                }
            }
        }
        CompletableFuture.allOf(*resultados.toTypedArray()).join()

        val final = repositorio.findById(pedido.id!!).orElseThrow()
        final.status shouldBe StatusPedido.CONFIRMADO
    }

    // ── INTEGRAÇÃO COM KAFKA ───────────────────────────────────────────────────
    @Test
    fun `deve publicar evento no kafka ao confirmar pedido`() {
        val pedido = PedidoBuilder.pendente().comValor(BigDecimal("100.00")).build()
        repositorio.save(pedido)

        val usecase = ConfirmarPedidoUseCase(repositorio, kafkaPublisher)
        usecase.executar(pedido.id!!)

        val mensagem = kafkaConsumer.poll(Duration.ofSeconds(10))
            .records("pedidos.confirmados")
            .first()

        val payload = objectMapper.readTree(mensagem.value())
        payload["pedido_id"].asLong() shouldBe pedido.id
        payload["status"].asText()    shouldBe "CONFIRMADO"
    }
}
```

### Testes de Coerência DBML ↔ Persistência

Testes obrigatórios para garantir que o código de persistência reflete o DBML:

```kotlin
// tests/integration/persistence/DbmlCoherenceTest.kt
@SpringBootTest
@Testcontainers
@Transactional
class DbmlCoherenceTest {

    companion object {
        @Container @JvmStatic
        val postgres = PostgreSQLContainer<Nothing>("postgres:16-alpine")
            .withReuse(true)

        @DynamicPropertySource @JvmStatic
        fun configureProperties(registry: DynamicPropertyRegistry) {
            registry.add("spring.datasource.url",      postgres::getJdbcUrl)
            registry.add("spring.datasource.username",  postgres::getUsername)
            registry.add("spring.datasource.password",  postgres::getPassword)
        }
    }

    @Autowired lateinit var entityManager: TestEntityManager

    // 1. Mapper ida-e-volta: Domain → JPA → Domain sem perda de dados
    @Test
    fun `mapper deve preservar todos os campos na conversao ida e volta`() {
        val domain = PedidoBuilder.pendente()
            .comValor(BigDecimal("999.99"))
            .comItens(3)
            .build()

        val jpa = PedidoJpaMapper.toJpa(domain)
        val roundTrip = PedidoJpaMapper.toDomain(jpa)

        roundTrip.id        shouldBe domain.id
        roundTrip.status    shouldBe domain.status
        roundTrip.valorTotal shouldBe domain.valorTotal
        roundTrip.itens.size shouldBe domain.itens.size
    }

    // 2. Flyway migrations executam sem erro
    @Test
    fun `flyway migrations devem executar completamente`() {
        // Se chegou aqui, Flyway já executou no @SpringBootTest
        // Validar que tabelas existem conforme DBML
        val result = entityManager.entityManager
            .createNativeQuery("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            .resultList

        result.map { it.toString() } shouldContainAll listOf("pedidos", "itens_pedido", "clientes")
    }

    // 3. Constraints do DBML refletidas no banco
    @Test
    fun `deve rejeitar pedido sem cliente (FK not null no DBML)`() {
        val pedidoSemCliente = PedidoJpaEntity().apply {
            status = StatusPedido.PENDENTE
            valorTotal = BigDecimal("100.00")
            // cliente = null → FK obrigatória no DBML
        }

        shouldThrow<ConstraintViolationException> {
            entityManager.persistAndFlush(pedidoSemCliente)
        }
    }

    // 4. Indexes existem conforme DBML
    @Test
    fun `indexes definidos no DBML devem existir no banco`() {
        val indexes = entityManager.entityManager
            .createNativeQuery("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'pedidos' AND schemaname = 'public'
            """)
            .resultList

        indexes.map { it.toString() } shouldContainAll listOf(
            "idx_pedidos_cliente_id", "idx_pedidos_status", "idx_status_criado"
        )
    }

    // 5. Cascade delete conforme DBML (itens_pedido depende de pedidos)
    @Test
    fun `deletar pedido deve remover itens em cascade`() {
        val pedido = PedidoBuilder.persistido(entityManager).comItens(2).build()
        val pedidoId = pedido.id

        entityManager.remove(pedido)
        entityManager.flush()

        entityManager.entityManager
            .createNativeQuery("SELECT COUNT(*) FROM itens_pedido WHERE pedido_id = :id")
            .setParameter("id", pedidoId)
            .singleResult shouldBe 0L
    }
}
```

```
REGRA: Todo projeto com banco de dados DEVE ter:
  □ Teste de mapper ida-e-volta (Domain ↔ JPA)
  □ Teste de Flyway migrations (executam sem erro)
  □ Teste de constraints (FKs, unique, not null conforme DBML)
  □ Teste de indexes (existem conforme DBML)
  □ Teste de cascade (conforme relacionamentos do DBML)
```

### Testes de Constraints DBML — DEFAULT, CHECK, UNIQUE

Constraints no DBML devem ser validadas em testes com banco real (PostgreSQL via Testcontainers). H2 não replica todas as constraints.

**Exemplo DBML:**

```dbml
Table pedidos {
  id bigint [primary key]
  status varchar [default: 'PENDING', note: "Padrão é PENDING"]
  valor decimal [note: "CHECK (valor > 0)"]
  email varchar [unique, note: "Email único por cliente"]
  created_at timestamp [default: `now()`]
}
```

**Testes de Constraint — Kotlin com Testcontainers PostgreSQL:**

```kotlin
// tests/integration/persistence/ConstraintTest.kt
@SpringBootTest
@Testcontainers
@Transactional
class PedidoConstraintTest {

    companion object {
        @Container @JvmStatic
        val postgres = PostgreSQLContainer<Nothing>("postgres:16-alpine")
            .withDatabaseName("testdb")
            .withReuse(true)

        @DynamicPropertySource @JvmStatic
        fun configureProperties(registry: DynamicPropertyRegistry) {
            registry.add("spring.datasource.url",      postgres::getJdbcUrl)
            registry.add("spring.datasource.username",  postgres::getUsername)
            registry.add("spring.datasource.password",  postgres::getPassword)
        }
    }

    @Autowired lateinit var entityManager: TestEntityManager

    // ── TESTE 1: DEFAULT constraint ───────────────────────────────────────
    @Test
    fun `deve usar DEFAULT 'PENDING' quando status nao eh fornecido`() {
        val pedido = PedidoJpaEntity().apply {
            id = 1L
            valor = BigDecimal("100.00")
            email = "test@example.com"
            // status NÃO É SETADO — deve usar DEFAULT
        }

        entityManager.persistAndFlush(pedido)
        val recuperado = entityManager.entityManager
            .createNativeQuery("SELECT status FROM pedidos WHERE id = 1")
            .singleResult as String

        recuperado shouldBe "PENDING"  // DEFAULT aplicado pelo banco
    }

    // ── TESTE 2: CHECK constraint (valor > 0) ─────────────────────────────
    @Test
    fun `deve rejeitar valor negativo via CHECK constraint`() {
        val pedido = PedidoJpaEntity().apply {
            id = 2L
            status = "PENDING"
            valor = BigDecimal("-10.00")  // VIOLAÇÃO do CHECK
            email = "test2@example.com"
        }

        shouldThrow<DataIntegrityViolationException> {
            entityManager.persistAndFlush(pedido)
        }.also { ex ->
            assertThat(ex.cause)
                .isInstanceOf(PSQLException::class.java)
                .hasMessageContaining("CHECK")
        }
    }

    @Test
    fun `deve rejeitar valor zero via CHECK constraint`() {
        val pedido = PedidoJpaEntity().apply {
            id = 3L
            status = "PENDING"
            valor = BigDecimal("0.00")  // VIOLAÇÃO do CHECK (valor > 0)
            email = "test3@example.com"
        }

        shouldThrow<DataIntegrityViolationException> {
            entityManager.persistAndFlush(pedido)
        }
    }

    @Test
    fun `deve aceitar valor positivo cumprindo CHECK constraint`() {
        val pedido = PedidoJpaEntity().apply {
            id = 4L
            status = "PENDING"
            valor = BigDecimal("0.01")  // Mínimo válido
            email = "test4@example.com"
        }

        entityManager.persistAndFlush(pedido)
        val recuperado = entityManager.find(PedidoJpaEntity::class.java, 4L)

        recuperado.valor shouldBe BigDecimal("0.01")
    }

    // ── TESTE 3: UNIQUE constraint ──────────────────────────────────────────
    @Test
    fun `deve rejeitar email duplicado via UNIQUE constraint`() {
        val email = "duplicado@example.com"
        
        val pedido1 = PedidoJpaEntity().apply {
            id = 5L
            status = "PENDING"
            valor = BigDecimal("100.00")
            email = email
        }
        entityManager.persistAndFlush(pedido1)

        val pedido2 = PedidoJpaEntity().apply {
            id = 6L
            status = "PENDING"
            valor = BigDecimal("200.00")
            email = email  // MESMO EMAIL — violação de UNIQUE
        }

        shouldThrow<DataIntegrityViolationException> {
            entityManager.persistAndFlush(pedido2)
        }.also { ex ->
            // PostgreSQL retorna SQLState 23505 para UNIQUE violation
            assertThat(ex.cause)
                .isInstanceOf(PSQLException::class.java)
                .matches { (it as PSQLException).sqlState == "23505" }
        }
    }

    @Test
    fun `deve aceitar emails diferentes cumprindo UNIQUE constraint`() {
        val pedido1 = PedidoJpaEntity().apply {
            id = 7L
            status = "PENDING"
            valor = BigDecimal("100.00")
            email = "user1@example.com"
        }
        entityManager.persistAndFlush(pedido1)

        val pedido2 = PedidoJpaEntity().apply {
            id = 8L
            status = "PENDING"
            valor = BigDecimal("200.00")
            email = "user2@example.com"  // Email diferente — OK
        }
        entityManager.persistAndFlush(pedido2)

        val count = entityManager.entityManager
            .createNativeQuery("SELECT COUNT(*) FROM pedidos WHERE email IN (?, ?)")
            .setParameter(1, "user1@example.com")
            .setParameter(2, "user2@example.com")
            .singleResult as Long

        count shouldBe 2L
    }

    // ── TESTE 4: NOT NULL constraint (implícito via FK) ─────────────────────
    @Test
    fun `deve rejeitar pedido com cliente_id nulo (FK obrigatória)`() {
        val pedido = PedidoJpaEntity().apply {
            id = 9L
            status = "PENDING"
            valor = BigDecimal("100.00")
            email = "test@example.com"
            cliente = null  // FK NOT NULL — violação
        }

        shouldThrow<ConstraintViolationException> {
            entityManager.persistAndFlush(pedido)
        }
    }
}
```

**Checklist Constraint Testing:**
- ✅ Usar banco real (PostgreSQL/MySQL) via Testcontainers — nunca H2
- ✅ DEFAULT: inserir sem setar campo, validar que banco aplicou padrão
- ✅ CHECK: tentar inserir valores que violam expressão, capturar `DataIntegrityViolationException`
- ✅ UNIQUE: inserir duplicado, capturar exception com SQLState 23505
- ✅ NOT NULL (FK): inserir com foreignKey nulo, capturar `ConstraintViolationException`
- ✅ Validar root cause (ex: `PSQLException`)
- ✅ Testes são isolados — cada um commita sua transação própria

### Testes de Integração com Serviços Externos (WireMock)
```kotlin
// tests/integration/adapter/NotificacaoAdapterTest.kt
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@WireMockTest(httpPort = 9999)
class NotificacaoAdapterTest {

    @Autowired lateinit var adapter: NotificacaoHttpAdapter

    @Test
    fun `deve notificar cliente com payload correto`(wireMock: WireMockRuntimeInfo) {
        wireMock.wireMock.register(
            post(urlEqualTo("/api/notificacoes"))
                .withRequestBody(matchingJsonPath("$.pedido_id"))
                .willReturn(aResponse().withStatus(200).withBody("""{"aceito":true}"""))
        )
        val pedido = PedidoBuilder.confirmado().build()

        adapter.pedidoConfirmado(pedido)

        wireMock.wireMock.verifyThat(
            postRequestedFor(urlEqualTo("/api/notificacoes"))
                .withRequestBody(matchingJsonPath("$.pedido_id", equalTo(pedido.id.toString())))
        )
    }

    @Test
    fun `deve lançar exceção com retry quando serviço retorna 503`(wireMock: WireMockRuntimeInfo) {
        wireMock.wireMock.register(
            post(urlEqualTo("/api/notificacoes"))
                .willReturn(aResponse().withStatus(503).withFixedDelay(100))
        )

        shouldThrow<NotificacaoIndisponivel> {
            adapter.pedidoConfirmado(PedidoBuilder.confirmado().build())
        }

        // verifica que houve retry — 3 tentativas configuradas
        wireMock.wireMock.verifyThat(3, postRequestedFor(urlEqualTo("/api/notificacoes")))
    }

    @Test
    fun `deve lançar timeout após 2 segundos sem resposta`(wireMock: WireMockRuntimeInfo) {
        wireMock.wireMock.register(
            post(urlEqualTo("/api/notificacoes"))
                .willReturn(aResponse().withFixedDelay(5000))  // mais lento que o timeout
        )

        shouldThrow<NotificacaoTimeoutException> {
            adapter.pedidoConfirmado(PedidoBuilder.confirmado().build())
        }
    }
}
```

### Testes de Integração com AWS — Testcontainers + LocalStack

Para projetos AWS, testes de integração devem validar a interação real com serviços como SQS, DynamoDB, S3 e Secrets Manager — sem depender de conta AWS nem gerar custo.

#### Setup com Testcontainers + LocalStack

```java
// Java 25 — Testcontainers 2.0 + LocalStack para testes de integração AWS
// Dependências:
//   org.testcontainers:localstack:2.x
//   org.testcontainers:junit-jupiter:2.x

@Testcontainers
@SpringBootTest
class PedidoSQSIntegrationTest {

    @Container
    static LocalStackContainer localstack = new LocalStackContainer(
            DockerImageName.parse("localstack/localstack:3.x"))
        .withServices(LocalStackContainer.Service.SQS, LocalStackContainer.Service.DYNAMODB);

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.cloud.aws.region.static", () -> localstack.getRegion());
        registry.add("spring.cloud.aws.credentials.access-key", () -> localstack.getAccessKey());
        registry.add("spring.cloud.aws.credentials.secret-key", () -> localstack.getSecretKey());
        registry.add("spring.cloud.aws.sqs.endpoint",
            () -> localstack.getEndpointOverride(LocalStackContainer.Service.SQS).toString());
    }

    @Autowired
    PedidoPublisher publisher;

    @Autowired
    SqsTemplate sqsTemplate;

    @Test
    void devePublicarPedidoConfirmadoNaFila() {
        // Given
        var pedido = PedidoTestFixture.confirmado();

        // When
        publisher.publicarPedidoConfirmado(pedido);

        // Then — consome da fila real (LocalStack) e valida
        var mensagem = sqsTemplate.receive(
            SqsReceiveOptions.builder().queue("pedidos-confirmados").build()
        );
        assertThat(mensagem).isPresent();
        assertThat(mensagem.get().getPayload())
            .extracting("pedidoId")
            .isEqualTo(pedido.id().valor());
    }
}
```

```python
# Python — pytest + Testcontainers + LocalStack
# pip install testcontainers[localstack] boto3 pytest

import pytest
from testcontainers.localstack import LocalStackContainer
import boto3
import json

@pytest.fixture(scope="module")
def localstack():
    with LocalStackContainer(image="localstack/localstack:3.x") as lsc:
        lsc.with_services("sqs", "dynamodb")
        yield lsc

@pytest.fixture
def sqs_client(localstack):
    return boto3.client(
        "sqs",
        endpoint_url=localstack.get_url(),
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )

def test_publicar_pedido_na_fila(sqs_client, pedido_publisher):
    # Setup — cria fila no LocalStack
    queue = sqs_client.create_queue(QueueName="pedidos-confirmados")
    queue_url = queue["QueueUrl"]

    # When
    pedido_publisher.publicar_confirmado(pedido_fixture(), queue_url)

    # Then
    msgs = sqs_client.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1)
    assert len(msgs["Messages"]) == 1
    corpo = json.loads(msgs["Messages"][0]["Body"])
    assert corpo["evento"] == "PEDIDO_CONFIRMADO"
```

#### Quando usar — Regras de Ouro

Testcontainers + LocalStack é OBRIGATÓRIO para testes de integração AWS.

**Serviços cobertos pelo LocalStack (free tier):**
- ✓ SQS, SNS, S3, DynamoDB, Secrets Manager, SSM Parameter Store
- ✓ Lambda, API Gateway, CloudWatch Logs, EventBridge
- ✓ IAM (básico), STS, CloudFormation

**Quando usar:**
- ✓ Validar producer/consumer SQS reais (sem mocks)
- ✓ Validar queries DynamoDB com dados reais
- ✓ Validar upload/download S3
- ✓ Validar rotação de secrets

**Quando NÃO usar (mock é suficiente):**
- ✗ Testes unitários de lógica de domínio
- ✗ Testes de service layer que não toca infra AWS

### Testes LSP — Liskov Substitution Principle com Múltiplos Adapters

Para garantir que dois adapters de um mesmo port são intercambiáveis, usamos **testes parametrizados** que rodam o mesmo contrato contra ambas as implementações.

**Exemplo:** `PedidoRepository` com duas implementações:
1. `JpaPedidoAdapter` — leitura/escrita via JPA + PostgreSQL
2. `MongoPedidoAdapter` — read model via MongoDB (CQRS)

Ambos devem passar no mesmo teste contrato — validar LSP.

```java
// src/main/java/.../domain/port/PedidoRepository.java
public interface PedidoRepository {
    Optional<Pedido> buscarPorId(PedidoId id);
    void salvar(Pedido pedido);
    List<Pedido> listarPorStatus(StatusPedido status);
}

// Implementação 1: JPA + PostgreSQL
@Repository
public class JpaPedidoAdapter implements PedidoRepository {
    @Autowired private JpaPedidoDAO jpaDao;
    
    @Override
    public Optional<Pedido> buscarPorId(PedidoId id) {
        return jpaDao.findById(id.valor())
            .map(PedidoJpaMapper::toDomain);
    }
    
    @Override
    public void salvar(Pedido pedido) {
        var entity = PedidoJpaMapper.toJpa(pedido);
        jpaDao.save(entity);
    }
    
    @Override
    public List<Pedido> listarPorStatus(StatusPedido status) {
        return jpaDao.findByStatus(status.value())
            .stream()
            .map(PedidoJpaMapper::toDomain)
            .toList();
    }
}

// Implementação 2: MongoDB (read model / CQRS)
@Repository
@ConditionalOnProperty(name = "pedido.repository.type", havingValue = "mongo")
public class MongoPedidoAdapter implements PedidoRepository {
    @Autowired private MongoTemplate mongoTemplate;
    
    @Override
    public Optional<Pedido> buscarPorId(PedidoId id) {
        var query = Query.query(Criteria.where("_id").is(id.valor()));
        PedidoMongoDocument doc = mongoTemplate.findOne(query, PedidoMongoDocument.class);
        return Optional.ofNullable(doc)
            .map(PedidoMongoMapper::toDomain);
    }
    
    @Override
    public void salvar(Pedido pedido) {
        var doc = PedidoMongoMapper.toMongo(pedido);
        mongoTemplate.save(doc, "pedidos");
    }
    
    @Override
    public List<Pedido> listarPorStatus(StatusPedido status) {
        var query = Query.query(Criteria.where("status").is(status.value()));
        return mongoTemplate.find(query, PedidoMongoDocument.class, "pedidos")
            .stream()
            .map(PedidoMongoMapper::toDomain)
            .toList();
    }
}
```

**Teste LSP — Contrato validado contra ambos adapters:**

```java
// Teste parametrizado — roda contra TODAS as implementações
@ParameterizedTest(name = "Repository: {0}")
@MethodSource("pedidoRepositories")
@Transactional  // rollback isolado
class PedidoRepositoryLspTest {

    private PedidoRepository repository;
    private TestEntityManager entityManager;

    // Fornece instância do adapter
    static Stream<Arguments> pedidoRepositories() {
        return Stream.of(
            Arguments.of("JpaPedidoAdapter", 
                new JpaPedidoAdapter(mockJpaDao())),
            Arguments.of("MongoPedidoAdapter", 
                new MongoPedidoAdapter(mockMongoTemplate()))
        );
    }

    @BeforeEach
    void setup(PedidoRepository repo) {
        this.repository = repo;
    }

    // ── CONTRATO: HAPPY PATH ──────────────────────────────────────────────
    @Test
    @DisplayName("Deve persistir e recuperar pedido com todos os campos intactos")
    void devePeristireRecuperarCompleto(PedidoRepository repo) {
        var pedido = PedidoBuilder.pendente()
            .comValor(BigDecimal("250.75"))
            .comCliente(ClienteBuilder.padrao().build())
            .comItens(3)
            .build();

        // Salvar via adapter
        repo.salvar(pedido);

        // Recuperar e validar — contrato invariante
        var recuperado = repo.buscarPorId(pedido.id())
            .orElseThrow(() -> new AssertionError("Pedido não persistido"));

        assertThat(recuperado)
            .satisfies(p -> {
                assertThat(p.id()).isEqualTo(pedido.id());
                assertThat(p.valor()).isEqualTo(pedido.valor());
                assertThat(p.status()).isEqualTo(pedido.status());
                assertThat(p.cliente().email()).isEqualTo(pedido.cliente().email());
                assertThat(p.itens()).hasSize(3);
            });
    }

    // ── CONTRATO: ID INEXISTENTE ─────────────────────────────────────────
    @Test
    @DisplayName("Deve retornar Optional vazio para ID inexistente")
    void deveRetornarVazioParaIdInexistente(PedidoRepository repo) {
        var resultado = repo.buscarPorId(new PedidoId(999999L));
        
        assertThat(resultado).isEmpty();
    }

    // ── CONTRATO: LISTAR POR STATUS ──────────────────────────────────────
    @Test
    @DisplayName("Deve retornar apenas pedidos do status especificado")
    void deveListarApenasDoStatusEspecificado(PedidoRepository repo) {
        var confirmado1 = PedidoBuilder.confirmado().comId(1L).build();
        var confirmado2 = PedidoBuilder.confirmado().comId(2L).build();
        var cancelado1 = PedidoBuilder.cancelado().comId(3L).build();

        repo.salvar(confirmado1);
        repo.salvar(confirmado2);
        repo.salvar(cancelado1);

        var resultado = repo.listarPorStatus(StatusPedido.CONFIRMADO);

        assertThat(resultado)
            .hasSize(2)
            .allMatch(p -> p.status() == StatusPedido.CONFIRMADO)
            .extracting(Pedido::id)
            .containsExactlyInAnyOrder(confirmado1.id(), confirmado2.id());
    }

    // ── CONTRATO: IDEMPOTÊNCIA ───────────────────────────────────────────
    @Test
    @DisplayName("Salvar mesmo pedido 2x deve ser idempotente")
    void deveSalvarIdempotentemente(PedidoRepository repo) {
        var pedido = PedidoBuilder.pendente().comId(1L).build();

        repo.salvar(pedido);
        repo.salvar(pedido);  // Salvar novamente

        var listagem = repo.listarPorStatus(StatusPedido.PENDENTE);
        
        assertThat(listagem)
            .filteredOn(p -> p.id().equals(pedido.id()))
            .hasSize(1);  // Apenas uma cópia, não duplicadas
    }

    // ── CONTRATO: MODIFICAÇÃO REFLETIDA ───────────────────────────────────
    @Test
    @DisplayName("Modificar pedido deve ser refletido na próxima leitura")
    void deveRefletirModificacoes(PedidoRepository repo) {
        var pedido = PedidoBuilder.pendente().comId(1L).build();
        repo.salvar(pedido);

        // Modificar: buscar, alterar estado, salvar
        var recuperado = repo.buscarPorId(pedido.id()).orElseThrow();
        recuperado.confirmar();
        repo.salvar(recuperado);

        // Validar que estado foi persistido
        var atualizado = repo.buscarPorId(pedido.id()).orElseThrow();
        assertThat(atualizado.status()).isEqualTo(StatusPedido.CONFIRMADO);
    }
}
```

**Configuração por Property — Trocar adapter sem modificar código:**

```yaml
# application-jpa.yml
pedido:
  repository:
    type: jpa  # Use JpaPedidoAdapter

---

# application-mongo.yml
pedido:
  repository:
    type: mongo  # Use MongoPedidoAdapter
```

```bash
# Rodar testes com JPA
mvn test -Dspring.profiles.active=jpa

# Rodar testes com MongoDB
mvn test -Dspring.profiles.active=mongo
```

**Checklist LSP com Múltiplos Adapters:**
- ✅ Interface port define contrato claramente (semanticamente invariante)
- ✅ Múltiplas implementações (JPA, Mongo, etc) não modificam signature
- ✅ Teste parametrizado roda mesmo contrato contra ambos adapters
- ✅ Ambos adapters passam em 100% dos testes
- ✅ Troca de implementação via `@ConditionalOnProperty` ou profile
- ✅ Se um adapter falha contrato, é violação de LSP — deve ser corrigida

---

### Testcontainers Reutilizáveis — Testes sem Espera

Por padrão, Testcontainers destrói e recria containers a cada execução de teste.
Para suites grandes, isso adiciona 10-30s de overhead. Containers reutilizáveis
mantêm banco e cache rodando entre execuções — feedback de teste em < 5 segundos.

#### Configuração Global

```properties
# ~/.testcontainers.properties (na home do dev)
testcontainers.reuse.enable=true
```

#### Java 25 — Container Reutilizável

```java
@Testcontainers
@SpringBootTest
class PedidoRepositoryTest {

    @Container
    @ServiceConnection
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine")
        .withReuse(true);  // NÃO destrói após testes — reaproveita entre execuções

    @Container
    @ServiceConnection
    static GenericContainer<?> redis = new GenericContainer<>("redis:7-alpine")
        .withExposedPorts(6379)
        .withReuse(true);

    // Testes rodam contra containers JÁ RODANDO — startup: 0s
    @Test
    void deveSalvarPedido() {
        var pedido = PedidoTestFixture.novo();
        repository.salvar(pedido);
        assertThat(repository.buscarPorId(pedido.id())).isPresent();
    }
}
```

#### Python — Container Reutilizável

```python
# conftest.py — fixture com reuse
import pytest
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def postgres():
    container = PostgresContainer("postgres:16-alpine")
    container.with_kwargs(reuse=True)  # reutiliza entre execuções
    with container as pg:
        yield pg
```

#### Impacto nos Tempos de Teste

```
Sem reuse:     startup containers (15-30s) + testes (5-10s) = 20-40s
Com reuse:     startup containers (0s)     + testes (5-10s) = 5-10s

Em uma suite de 200 testes de integração, reuse economiza ~2 minutos por execução.

REGRA:
  ✓ Desenvolvimento local → reuse=true SEMPRE (feedback rápido)
  ✗ Pipeline CI → reuse=false (garantir isolamento entre builds)
```

#### Cleanup quando necessário

```bash
# Parar todos os containers Testcontainers reutilizáveis
docker rm -f $(docker ps -q --filter "label=org.testcontainers=true")

# Ou via Testcontainers Desktop (UI para gerenciar containers)
```

---

## Testando Domain Event → Integration Event (Transactional Outbox + Relay)

> **Por que esta seção existe.** O padrão Outbox é o coração da consistência entre o domínio (Aggregate Root emite Domain Event) e a fronteira do bounded context (Integration Event publicado em fila/tópico). Errar aqui causa o pior tipo de bug distribuído: **mensagem perdida silenciosamente** ou **duplicada sem idempotência**. Os testes desta seção verificam o **contrato completo de propagação** com infraestrutura real (Postgres + fila), não com mocks.

### O que precisa ser testado (matriz canônica de 6 cenários)

| # | Cenário | Eixo preditivo | Observável |
|---|---|---|---|
| 1 | Happy path: commit do agregado grava `outbox_events` na mesma transação | HAPPY + INVARIANT atomicidade | linha em `outbox_events` com `published_at IS NULL` |
| 2 | Relay publica e marca `published_at` | HAPPY | `published_at` preenchido + mensagem na fila |
| 3 | Falha no commit do agregado → nada na outbox | INVARIANT atomicidade | `outbox_events` vazia + nada na fila |
| 4 | Relay processa mesma linha 2× → publica 1× (idempotência do relay) | INVARIANT idempotência | `published_at` setado uma vez |
| 5 | Consumer recebe mensagem duplicada → processa 1× (idempotência do consumer via `message_id`) | INVARIANT idempotência | efeito aplicado uma única vez na base de destino |
| 6 | Conversão Domain Event → Integration Event preserva contrato (campos canônicos, versão, timestamp) | CONTRATO | payload JSON publicado bate com schema esperado |

**Regra de ouro:** se você testou só o cenário 1, **não testou Outbox** — testou que sua INSERT funciona. Outbox **só vale** quando os 6 estão verdes.

### Stack canônico

- **Postgres** (Testcontainers + `@ServiceConnection`) — base do agregado e da `outbox_events`
- **Kafka** (Testcontainers + `@ServiceConnection`) — destino do Integration Event
- **Awaitility** — esperar a publicação assíncrona sem `Thread.sleep`
- **Spring Modulith Outbox** ou implementação caseira com Flyway migration `V1__outbox.sql`

### Schema canônico da `outbox_events` (Flyway)

```sql
CREATE TABLE outbox_events (
    id            UUID         PRIMARY KEY,
    aggregate_id  VARCHAR(64)  NOT NULL,
    event_type    VARCHAR(120) NOT NULL,
    payload       JSONB        NOT NULL,
    schema_version SMALLINT    NOT NULL,
    occurred_at   TIMESTAMPTZ  NOT NULL,
    published_at  TIMESTAMPTZ  NULL,            -- NULL = pendente
    attempts      SMALLINT     NOT NULL DEFAULT 0,
    last_error    TEXT         NULL
);
CREATE INDEX idx_outbox_pending ON outbox_events (occurred_at) WHERE published_at IS NULL;

CREATE TABLE processed_messages (
    message_id    UUID         PRIMARY KEY,
    consumer      VARCHAR(80)  NOT NULL,
    processed_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
```

### Suíte de testes — Java 25 + Spring Boot 4 / Spring 7

```java
package com.empresa.pedidos.outbox;

import com.empresa.pedidos.PedidosApplication;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.test.utils.KafkaTestUtils;
import org.testcontainers.containers.KafkaContainer;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.time.Duration;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.awaitility.Awaitility.await;

@SpringBootTest(classes = PedidosApplication.class)
@Testcontainers
class OutboxRelayIT {

    @Container @ServiceConnection
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine").withReuse(true);

    @Container @ServiceConnection
    static KafkaContainer kafka = new KafkaContainer("apache/kafka:3.7.0").withReuse(true);

    @Autowired ConfirmarPedidoUseCase useCase;
    @Autowired JdbcTemplate jdbc;
    @Autowired OutboxRelay relay;
    @Autowired KafkaTemplate<String, String> kafkaTemplate;
    @Autowired KafkaTestConsumerFactory consumerFactory;

    // ── 1. HAPPY: commit do agregado grava outbox na MESMA transação ──────────
    @Test
    void confirmarPedido_deveGravarOutboxEventNaMesmaTransacao() {
        var pedidoId = umPedidoPendentePersistido();

        useCase.executar(pedidoId);

        var pendentes = jdbc.queryForList("""
            SELECT event_type, payload::text AS payload, published_at
              FROM outbox_events
             WHERE aggregate_id = ?""", String.valueOf(pedidoId));

        assertThat(pendentes).hasSize(1);
        assertThat(pendentes.get(0).get("event_type")).isEqualTo("pedido.confirmado.v1");
        assertThat(pendentes.get(0).get("published_at")).isNull();   // ainda não publicado
        assertThat((String) pendentes.get(0).get("payload"))
            .contains("\"pedidoId\":" + pedidoId)
            .contains("\"status\":\"CONFIRMADO\"");
    }

    // ── 2. HAPPY: relay publica e marca published_at ──────────────────────────
    @Test
    void relay_devePublicarEventoEMarcarPublishedAt() {
        var pedidoId = umPedidoPendentePersistido();
        useCase.executar(pedidoId);
        var consumer = consumerFactory.subscribe("pedidos.confirmados");

        relay.processarPendentes();

        // Mensagem chegou no tópico (espera assíncrona via Awaitility)
        await().atMost(Duration.ofSeconds(5)).untilAsserted(() -> {
            ConsumerRecord<String, String> msg = KafkaTestUtils.getSingleRecord(
                consumer, "pedidos.confirmados", Duration.ofMillis(200));
            assertThat(msg.key()).isEqualTo(String.valueOf(pedidoId));
            assertThat(msg.value()).contains("\"pedidoId\":" + pedidoId);
        });

        // Linha marcada como publicada
        var publishedAt = jdbc.queryForObject(
            "SELECT published_at FROM outbox_events WHERE aggregate_id = ?",
            java.sql.Timestamp.class, String.valueOf(pedidoId));
        assertThat(publishedAt).isNotNull();
    }

    // ── 3. INVARIANT atomicidade: rollback do agregado → nada na outbox ───────
    @Test
    void seCommitFalhar_outboxNaoRecebeNada() {
        var pedidoId = umPedidoPendentePersistido();
        var consumer = consumerFactory.subscribe("pedidos.confirmados");

        // Força falha após o INSERT da outbox e antes do commit do agregado
        assertThatThrownBy(() -> useCase.executarComFalhaForcada(pedidoId))
            .isInstanceOf(RuntimeException.class);

        // Garantia 1: outbox vazia para esse agregado (rollback transacional)
        Long count = jdbc.queryForObject(
            "SELECT COUNT(*) FROM outbox_events WHERE aggregate_id = ?",
            Long.class, String.valueOf(pedidoId));
        assertThat(count).isZero();

        // Garantia 2: nada chega no Kafka mesmo se o relay rodar
        relay.processarPendentes();
        assertThat(KafkaTestUtils.getRecords(consumer, Duration.ofSeconds(2))).isEmpty();
    }

    // ── 4. INVARIANT idempotência do relay: 2 execuções → 1 publicação ────────
    @Test
    void relay_executadoDuasVezes_publicaApenasUmaVez() {
        var pedidoId = umPedidoPendentePersistido();
        useCase.executar(pedidoId);
        var consumer = consumerFactory.subscribe("pedidos.confirmados");

        relay.processarPendentes();
        relay.processarPendentes();   // segunda passada: published_at já preenchido = pula

        var registros = KafkaTestUtils.getRecords(consumer, Duration.ofSeconds(3));
        assertThat(registros.count()).isEqualTo(1);

        Integer attempts = jdbc.queryForObject(
            "SELECT attempts FROM outbox_events WHERE aggregate_id = ?",
            Integer.class, String.valueOf(pedidoId));
        assertThat(attempts).isEqualTo(1);
    }

    // ── 5. INVARIANT idempotência do consumer: mensagem duplicada → efeito 1× ─
    @Test
    void consumer_aoReceberMensagemDuplicada_aplicaEfeitoApenasUmaVez() {
        var pedidoId = umPedidoPendentePersistido();
        var messageId = UUID.randomUUID();
        var payload = """
            {"messageId":"%s","pedidoId":%d,"status":"CONFIRMADO","schemaVersion":1}
            """.formatted(messageId, pedidoId);

        // Publica 2× a MESMA mensagem (mesmo messageId)
        kafkaTemplate.send("pedidos.confirmados", String.valueOf(pedidoId), payload);
        kafkaTemplate.send("pedidos.confirmados", String.valueOf(pedidoId), payload);

        // Espera consumer processar (idempotente via processed_messages.message_id UNIQUE)
        await().atMost(Duration.ofSeconds(5)).untilAsserted(() -> {
            Long processados = jdbc.queryForObject(
                "SELECT COUNT(*) FROM processed_messages WHERE message_id = ?",
                Long.class, messageId);
            assertThat(processados).isEqualTo(1L);
        });

        // Efeito de negócio aplicado UMA vez (auditoria do destino)
        Long auditoria = jdbc.queryForObject(
            "SELECT COUNT(*) FROM auditoria_pedido WHERE pedido_id = ? AND evento = 'confirmado'",
            Long.class, pedidoId);
        assertThat(auditoria).isEqualTo(1L);
    }

    // ── 6. CONTRATO: payload publicado bate com schema canônico ───────────────
    @Test
    void payloadPublicado_deveSeguirSchemaCanonicoDoIntegrationEvent() {
        var pedidoId = umPedidoPendentePersistido();
        useCase.executar(pedidoId);
        var consumer = consumerFactory.subscribe("pedidos.confirmados");

        relay.processarPendentes();
        var msg = KafkaTestUtils.getSingleRecord(consumer, "pedidos.confirmados", Duration.ofSeconds(5));

        // Schema canônico: messageId, eventType, schemaVersion, occurredAt, aggregateId, data{}
        assertThat(msg.value())
            .contains("\"messageId\":")
            .contains("\"eventType\":\"pedido.confirmado.v1\"")
            .contains("\"schemaVersion\":1")
            .contains("\"occurredAt\":")
            .contains("\"aggregateId\":\"" + pedidoId + "\"")
            .contains("\"data\":{");

        // Validação JSON-Schema (registry local em src/test/resources/schemas/)
        var validador = new JsonSchemaValidator("classpath:/schemas/pedido-confirmado-v1.json");
        assertThat(validador.valida(msg.value())).isTrue();
    }
}
```

### Padrões de armadilha (e como evitar)

| Armadilha | Sintoma | Como evitar no teste |
|---|---|---|
| Outbox em transação separada | `published_at IS NOT NULL` mesmo após rollback do agregado | Cenário 3 — força falha após gravar outbox e verifica que linha sumiu |
| Sem index parcial em `published_at IS NULL` | Relay fica lento conforme tabela cresce | Teste de carga (`performance-tests.md`) com 100k linhas pendentes; deve manter < 200ms p95 |
| Relay processa fora de ordem | `pedido.cancelado` chega antes de `pedido.confirmado` | Teste com 2 eventos do mesmo agregado; verificar ordering por `occurred_at` |
| Consumer sem tabela `processed_messages` | Cenário 5 falha (efeito aplicado 2×) | Nunca aceitar consumer sem idempotência via `message_id` único + UNIQUE constraint |
| Schema do payload não versionado | Quebra de contrato silenciosa | Cenário 6 — `eventType` sempre com sufixo `.vN` |
| Retenção infinita em `outbox_events` | Tabela cresce indefinidamente | Job de limpeza com teste: `DELETE WHERE published_at < now() - interval '30 days'` |

### Quando NÃO testar tudo isso

Outbox testing **completo** custa ~ 8-15 segundos por suíte (subir Postgres+Kafka). Se o seu serviço **não publica eventos para fora do bounded context**, não existe Outbox — não escreva esses testes. Se publica, **os 6 cenários são piso, não teto**.

### Conexão com a SKILL.md

Esta seção fecha o critério **"Domain Events vs Integration Events"** do OBJ-2 do `skills-review.md`. O conceito conceitual vive em `engenheiro-clean-architect/SKILL.md` (matriz canônica 8 critérios) e `squad-ai/references/cqrs-outbox.md` (padrão arquitetural); aqui está a **prova executável** do contrato.

---
