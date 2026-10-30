package com.squadai.qa.restassured;

import com.squadai.qa.restassured.model.ConfirmarPedidoResponse;
import com.squadai.qa.restassured.support.ApiSpecs;
import com.squadai.qa.restassured.support.WireMockApiTest;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static io.restassured.RestAssured.given;
import static io.restassured.module.jsv.JsonSchemaValidator.matchesJsonSchemaInClasspath;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.greaterThan;
import static org.junit.jupiter.api.Assertions.assertAll;
import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * Suíte funcional do endpoint POST /api/pedidos/{id}/confirmar, cobrindo os eixos de cenário
 * preditivo da skill (happy path, autenticação, não-encontrado, conflito de estado) com o
 * DSL given/when/then do RestAssured, specs reutilizáveis, validação por JSON Schema,
 * SLA de latência e desserialização tipada.
 */
@DisplayName("POST /api/pedidos/{id}/confirmar — contrato funcional (RestAssured + WireMock)")
class ConfirmarPedidoApiTest extends WireMockApiTest {

    @Test
    @DisplayName("HAPPY PATH: 200, corpo conforme JSON Schema e dentro do SLA")
    void confirma_pedido_pendente_retorna_200_conforme_schema() {
        given()
                .spec(base).auth().oauth2(ApiSpecs.TOKEN)
        .when()
                .post("/pedidos/{id}/confirmar", 1)
        .then()
                .spec(jsonSla)
                .statusCode(200)
                .body("status", equalTo("CONFIRMADO"))
                .body("pedidoId", equalTo(1))
                .body("valorTotal", greaterThan(0f))
                .body(matchesJsonSchemaInClasspath("schemas/confirmar-pedido-response.schema.json"));
    }

    @Test
    @DisplayName("SERIALIZAÇÃO: resposta desserializa em POJO tipado (BigDecimal exato)")
    void confirma_pedido_desserializa_em_pojo() {
        ConfirmarPedidoResponse resposta = given()
                .spec(base).auth().oauth2(ApiSpecs.TOKEN)
        .when()
                .post("/pedidos/{id}/confirmar", 1)
        .then()
                .statusCode(200)
                .extract().as(ConfirmarPedidoResponse.class);

        assertAll(
                () -> assertEquals(1L, resposta.getPedidoId()),
                () -> assertEquals("CONFIRMADO", resposta.getStatus()),
                () -> assertEquals(0, new BigDecimal("150.00").compareTo(resposta.getValorTotal()))
        );
    }

    @Test
    @DisplayName("AUTENTICAÇÃO: sem Bearer token retorna 401")
    void confirma_pedido_sem_autenticacao_retorna_401() {
        given()
                .spec(base)                      // sem .auth() — cenário negativo
        .when()
                .post("/pedidos/{id}/confirmar", 1)
        .then()
                .statusCode(401)
                .body("erro", equalTo("nao_autenticado"));
    }

    @Test
    @DisplayName("NÃO ENCONTRADO: pedido inexistente retorna 404 com mensagem")
    void confirma_pedido_inexistente_retorna_404() {
        given()
                .spec(base).auth().oauth2(ApiSpecs.TOKEN)
        .when()
                .post("/pedidos/{id}/confirmar", 999)
        .then()
                .spec(jsonSla)
                .statusCode(404)
                .body("mensagem", equalTo("Pedido 999 nao encontrado"));
    }

    @Test
    @DisplayName("CONFLITO DE ESTADO: pedido já confirmado retorna 409")
    void confirma_pedido_ja_confirmado_retorna_409() {
        given()
                .spec(base).auth().oauth2(ApiSpecs.TOKEN)
        .when()
                .post("/pedidos/{id}/confirmar", 2)
        .then()
                .spec(jsonSla)
                .statusCode(409)
                .body("estadoAtual", equalTo("CONFIRMADO"));
    }
}
