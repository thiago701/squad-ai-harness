# Testes Funcionais Automatizados — API, BDD, Contract, E2E

> **Quando ler:** ao escrever testes que validam o comportamento do sistema pela perspectiva do consumidor (cliente HTTP, API consumer, usuário final).

> **Princípio:** cobre entrada/saída observáveis. Não conhece a implementação interna. Inclui REST, BDD/Gherkin, Contract Testing (Pact), E2E (Playwright), WireMock.

## CAMADA 3 — Testes Funcionais Automatizados

Testes funcionais verificam o **comportamento do sistema pela perspectiva do consumidor** — seja um usuário, uma API cliente ou outro serviço. Não conhecem a implementação interna; validam apenas entradas e saídas observáveis.

### 3A — Testes de API REST (Python com httpx + pytest)
```python
# tests/functional/api/test_pedido_api.py
import pytest
import httpx
from decimal import Decimal

@pytest.fixture(scope="session")
def api_base_url(live_server):
    """live_server é fixture que sobe a aplicação real para testes."""
    return f"http://localhost:{live_server.port}/api/v1"

@pytest.fixture(scope="session")
def cliente_autenticado(api_base_url):
    token = obter_token_teste(api_base_url)
    return httpx.Client(base_url=api_base_url, headers={"Authorization": f"Bearer {token}"})


class TestConfirmarPedidoAPI:
    """Testa o contrato HTTP do endpoint POST /pedidos/{id}/confirmar."""

    def test_retorna_200_e_status_confirmado(self, cliente_autenticado, pedido_pendente_criado):
        response = cliente_autenticado.post(f"/pedidos/{pedido_pendente_criado.id}/confirmar")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "CONFIRMADO"
        assert body["pedido_id"] == pedido_pendente_criado.id
        assert "confirmado_em" in body  # campo obrigatório no contrato

    def test_retorna_400_para_body_malformado(self, cliente_autenticado):
        response = cliente_autenticado.post("/pedidos/confirmar", json={"invalido": True})

        assert response.status_code == 400
        body = response.json()
        assert "errors" in body  # contrato: erros de validação em campo errors[]
        assert len(body["errors"]) > 0

    def test_retorna_401_sem_autenticacao(self, api_base_url):
        response = httpx.post(f"{api_base_url}/pedidos/1/confirmar")  # sem token
        assert response.status_code == 401

    def test_retorna_403_para_pedido_de_outro_usuario(self, cliente_autenticado, pedido_outro_usuario):
        response = cliente_autenticado.post(f"/pedidos/{pedido_outro_usuario.id}/confirmar")
        assert response.status_code == 403

    def test_retorna_404_para_pedido_inexistente(self, cliente_autenticado):
        response = cliente_autenticado.post("/pedidos/999999/confirmar")

        assert response.status_code == 404
        body = response.json()
        assert "999999" in body.get("message", "")

    def test_retorna_409_para_pedido_ja_confirmado(self, cliente_autenticado, pedido_ja_confirmado):
        response = cliente_autenticado.post(f"/pedidos/{pedido_ja_confirmado.id}/confirmar")
        assert response.status_code == 409

    def test_idempotencia_confirmacoes_repetidas_retornam_mesmo_estado(
        self, cliente_autenticado, pedido_pendente_criado
    ):
        r1 = cliente_autenticado.post(f"/pedidos/{pedido_pendente_criado.id}/confirmar")
        r2 = cliente_autenticado.post(f"/pedidos/{pedido_pendente_criado.id}/confirmar")

        # Idempotente: ambos retornam o mesmo estado (seja 200 ou 409, deve ser consistente)
        assert r1.json()["status"] == r2.json()["status"]
```

### 3B — BDD com Gherkin (Python pytest-bdd + Java Cucumber)
```gherkin
# tests/functional/bdd/features/confirmar_pedido.feature
Feature: Confirmar Pedido
  Como um operador do sistema
  Quero confirmar pedidos pendentes
  Para que os clientes sejam notificados e o pedido siga para processamento

  Background:
    Given que existe um cliente "João Silva" com email "joao@exemplo.com"
    And que o cliente está autenticado no sistema

  Scenario: Confirmar pedido pendente com valor válido
    Given que existe um pedido pendente com valor R$150,00
    When o operador confirma o pedido
    Then o pedido deve ter status "CONFIRMADO"
    And o cliente deve ter recebido uma notificação de confirmação
    And o evento "pedido.confirmado" deve ter sido publicado

  Scenario: Rejeitar pedido com valor abaixo do mínimo
    Given que existe um pedido pendente com valor R$9,99
    When o operador tenta confirmar o pedido
    Then o sistema deve retornar erro "Valor mínimo de pedido não atingido"
    And o pedido deve permanecer com status "PENDENTE"
    And nenhuma notificação deve ter sido enviada

  Scenario Outline: Rejeitar confirmação de pedido em estado inválido
    Given que existe um pedido com status "<status_atual>"
    When o operador tenta confirmar o pedido
    Then o sistema deve retornar erro de transição de estado inválida
    And o pedido deve permanecer com status "<status_atual>"

    Examples:
      | status_atual |
      | CONFIRMADO   |
      | CANCELADO    |
      | ENVIADO      |
      | DEVOLVIDO    |
```

```python
# tests/functional/bdd/steps/confirmar_pedido_steps.py
from pytest_bdd import given, when, then, parsers
from decimal import Decimal

@given(parsers.parse('que existe um pedido pendente com valor R${valor}'))
def pedido_pendente_criado(valor, db_session, context):
    pedido = PedidoBuilder.pendente().com_valor(Decimal(valor.replace(",", "."))).build()
    db_session.add(pedido)
    db_session.commit()
    context["pedido"] = pedido

@when("o operador confirma o pedido")
def confirmar_pedido(context, api_client):
    context["response"] = api_client.post(f"/pedidos/{context['pedido'].id}/confirmar")

@then(parsers.parse('o pedido deve ter status "{status_esperado}"'))
def verificar_status(context, status_esperado, db_session):
    db_session.refresh(context["pedido"])
    assert context["pedido"].status.value == status_esperado

@then('o cliente deve ter recebido uma notificação de confirmação')
def verificar_notificacao(context, notificacao_spy):
    assert notificacao_spy.foi_chamado_com(pedido_id=context["pedido"].id)

@then(parsers.parse('o sistema deve retornar erro "{mensagem_esperada}"'))
def verificar_mensagem_erro(context, mensagem_esperada):
    body = context["response"].json()
    assert mensagem_esperada in body.get("message", "") or \
           any(mensagem_esperada in e for e in body.get("errors", []))
```

### 3C — Contract Testing com Pact
```python
# tests/functional/contract/test_pedido_consumer.py
# Consumer define o contrato esperado — gerado como arquivo JSON (pact)
import pytest
from pact import Consumer, Provider

@pytest.fixture(scope="session")
def pact():
    return Consumer("pedido-service").has_pact_with(
        Provider("notificacao-service"),
        pact_dir="./pacts",
        publish_verification_results=True,
    )

def test_contrato_notificar_pedido_confirmado(pact):
    expected_body = {"aceito": True, "mensagem_id": Like("uuid-qualquer")}
    headers = {"Content-Type": "application/json"}

    (
        pact
        .given("serviço de notificação disponível")
        .upon_receiving("requisição de notificação de pedido confirmado")
        .with_request(
            method="POST",
            path="/notificacoes",
            body={"pedido_id": Like(1), "cliente_email": Like("email@exemplo.com")},
            headers=headers,
        )
        .will_respond_with(status=200, body=expected_body, headers=headers)
    )

    with pact:
        adapter = NotificacaoHttpAdapter(base_url=pact.uri)
        resultado = adapter.notificar_confirmacao(pedido_id=1, email="email@exemplo.com")

    assert resultado.aceito is True
```

---

## Testes E2E no Navegador — Playwright (padrão canônico)

Playwright substitui Selenium/Cypress como ferramenta E2E da squad: single-binary, Chromium/Firefox/WebKit,
headless por padrão, API Java estável, traces visuais, auto-wait.

```java
@Test
void usuario_consegue_concluir_checkout_com_passkey() {
    try (Playwright pw = Playwright.create()) {
        var browser = pw.chromium().launch(new LaunchOptions().setHeadless(true));
        var ctx = browser.newContext(new Browser.NewContextOptions()
            .setBaseURL(System.getenv("E2E_BASE_URL"))
            .setRecordVideoDir(Path.of("target/e2e-videos")));
        Page page = ctx.newPage();
        page.navigate("/login");
        page.getByLabel("Email").fill("teste@empresa.com");
        page.getByRole(AriaRole.BUTTON, new Page.GetByRoleOptions().setName("Entrar com Passkey")).click();
        page.waitForURL("**/checkout");
        assertThat(page.getByTestId("total")).containsText("R$ 149,90");
        page.getByRole(AriaRole.BUTTON, new Page.GetByRoleOptions().setName("Pagar")).click();
        page.waitForURL("**/sucesso");
        assertThat(page.getByText("Pedido confirmado")).isVisible();
    }
}
```

**Regras E2E:** no máximo 5% da pirâmide; rodar em CI apenas após unit + integração verdes;
3-5 fluxos críticos (login, checkout, cancelamento, busca, recuperação); sempre `getByRole`,
`getByTestId`, `getByLabel` — nunca XPath ou CSS complexo.

## Contratos HTTP — RestTestClient (Spring Boot 4)

Substitui TestRestTemplate/WebTestClient. Blocking, type-safe, assertions fluentes.

```java
@SpringBootTest(webEnvironment = RANDOM_PORT)
@AutoConfigureRestTestClient
class PedidoControllerIT {
    @Autowired RestTestClient restTest;

    @Test void cria_pedido_retorna_201_com_location() {
        restTest.post().uri("/pedidos")
            .contentType(APPLICATION_JSON)
            .bodyValue(new CriarPedidoRequest("cliente-123", List.of(new Item("SKU-1", 2))))
            .exchange()
            .expectStatus().isCreated()
            .expectHeader().exists(LOCATION)
            .expectBody(PedidoResponse.class)
                .value(p -> assertThat(p.status()).isEqualTo("CONFIRMADO"));
    }
}
```

## RestAssured — API REST black-box em Java (given/when/then)

Para exercer um serviço REST **em pé** (local/staging/prod-like) pela borda HTTP em Java, a ferramenta
canônica é **RestAssured** — não o `RestTestClient` (in-process do Spring). A cobertura profissional
completa — specs reutilizáveis (`RequestSpecBuilder`/`ResponseSpecBuilder`), validação por JSON Schema,
serialização POJO, auth OAuth2/JWT, data-driven, `RestAssuredMockMvc` (slice Spring), a fronteira clara
vs `MockMvcTester`/`RestTestClient`, anti-padrões e checklist de PR — está em
**`rest-assured-api-testing.md`**, com projeto **executável** (ciclo RED→GREEN) em
`examples/rest-assured-professional/`.

## WireMock para Integração com APIs Externas

WireMock simula gateways de pagamento, CEP, validação de CPF sem depender do ambiente deles.

```java
@Testcontainers
@SpringBootTest
class GatewayPagamentoIT {
    @Container
    static WireMockContainer wm = new WireMockContainer("wiremock/wiremock:3.10.0")
        .withMappingFromResource("wiremock/gateway-pagamento.json");

    @DynamicPropertySource static void props(DynamicPropertyRegistry r) {
        r.add("gateway.pagamento.url", wm::getBaseUrl);
    }

    @Test void aciona_fallback_quando_gateway_timeout() {
        wm.stubFor(post("/v1/cobrancas").willReturn(aResponse().withFixedDelay(5000).withStatus(200)));
        var resultado = useCase.processar(pedido);
        assertThat(resultado).isInstanceOf(Resultado.Fallback.class);
    }
}
```

