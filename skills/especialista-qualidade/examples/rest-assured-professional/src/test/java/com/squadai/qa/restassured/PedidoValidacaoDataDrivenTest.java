package com.squadai.qa.restassured;

import com.squadai.qa.restassured.support.WireMockApiTest;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;

import java.util.stream.Stream;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.empty;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.not;

/**
 * Teste data-driven (eixo INPUT VALIDATION): um único método verifica muitas variações de
 * payload inválido via {@code @MethodSource}. Adicionar um caso = adicionar uma linha, sem
 * duplicar o corpo do teste. O caso válido (201 + Location) fecha o par positivo/negativo.
 */
@DisplayName("POST /api/pedidos — validação data-driven de payload")
class PedidoValidacaoDataDrivenTest extends WireMockApiTest {

    static Stream<Arguments> payloadsInvalidos() {
        return Stream.of(
                Arguments.of("corpo vazio", "{}"),
                Arguments.of("sem itens", "{\"clienteId\":\"c1\"}"),
                Arguments.of("sem clienteId", "{\"itens\":[{\"sku\":\"S1\",\"qtd\":1}]}"),
                Arguments.of("lista de itens vazia", "{\"clienteId\":\"c1\",\"itens\":[]}")
        );
    }

    @ParameterizedTest(name = "[{index}] {0} -> 400")
    @MethodSource("payloadsInvalidos")
    @DisplayName("payload inválido retorna 400 com errors[] não vazio")
    void payload_invalido_retorna_400(String descricao, String body) {
        given()
                .spec(base).body(body)
        .when()
                .post("/pedidos")
        .then()
                .statusCode(400)
                .body("errors", not(empty()));
    }

    @Test
    @DisplayName("HAPPY PATH: payload válido retorna 201 + header Location")
    void payload_valido_retorna_201_com_location() {
        given()
                .spec(base)
                .body("{\"clienteId\":\"c1\",\"itens\":[{\"sku\":\"S1\",\"qtd\":2}]}")
        .when()
                .post("/pedidos")
        .then()
                .statusCode(201)
                .header("Location", equalTo("/api/pedidos/1"));
    }
}
