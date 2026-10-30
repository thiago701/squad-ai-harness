package com.squadai.qa.restassured.support;

import com.github.tomakehurst.wiremock.WireMockServer;
import io.restassured.RestAssured;
import io.restassured.specification.RequestSpecification;
import io.restassured.specification.ResponseSpecification;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;

import static com.github.tomakehurst.wiremock.client.WireMock.aResponse;
import static com.github.tomakehurst.wiremock.client.WireMock.matching;
import static com.github.tomakehurst.wiremock.client.WireMock.matchingJsonPath;
import static com.github.tomakehurst.wiremock.client.WireMock.post;
import static com.github.tomakehurst.wiremock.client.WireMock.urlEqualTo;
import static com.github.tomakehurst.wiremock.core.WireMockConfiguration.options;

/**
 * Base de teste: sobe um WireMock in-process (a "API sob teste") em porta dinâmica e
 * aponta os specs do RestAssured para ele. Sem Docker, sem servidor externo.
 *
 * <p><b>Demonstração de TDD (RED &rarr; GREEN):</b> os stubs em
 * {@link #stubContratoImplementado()} representam a API <i>implementada</i>. Rode com a
 * variável de ambiente {@code RED_PHASE=1} para simular o contrato ainda NÃO implementado
 * (fase RED — a suíte falha porque a API não existe); rode sem ela para a fase GREEN.</p>
 */
public abstract class WireMockApiTest {

    protected static WireMockServer wm;
    protected static RequestSpecification base;
    protected static ResponseSpecification jsonSla;

    @BeforeAll
    static void startServer() {
        wm = new WireMockServer(options().dynamicPort());
        wm.start();
        String baseUri = "http://localhost:" + wm.port();

        base = ApiSpecs.base(baseUri);
        jsonSla = ApiSpecs.jsonComSla(2000);

        // Boa prática: não polua o log no verde; imprima request+response só quando a asserção falha.
        RestAssured.enableLoggingOfRequestAndResponseIfValidationFails();

        if (!"1".equals(System.getenv("RED_PHASE"))) {
            stubContratoImplementado();
        }
    }

    @AfterAll
    static void stopServer() {
        if (wm != null) {
            wm.stop();
        }
    }

    /** Stubs que representam a API já implementada (fase GREEN). */
    static void stubContratoImplementado() {
        // Criar pedido VÁLIDO (tem clienteId e ao menos 1 item com sku) -> 201 + Location
        wm.stubFor(post(urlEqualTo("/api/pedidos"))
                .atPriority(1)
                .withRequestBody(matchingJsonPath("$.clienteId"))
                .withRequestBody(matchingJsonPath("$.itens[0].sku"))
                .willReturn(aResponse().withStatus(201)
                        .withHeader("Content-Type", "application/json")
                        .withHeader("Location", "/api/pedidos/1")
                        .withBody("{\"id\":1,\"status\":\"PENDENTE\"}")));

        // Criar pedido INVÁLIDO (fallback de menor prioridade) -> 400 + errors[]
        wm.stubFor(post(urlEqualTo("/api/pedidos"))
                .atPriority(10)
                .willReturn(aResponse().withStatus(400)
                        .withHeader("Content-Type", "application/json")
                        .withBody("{\"errors\":[{\"campo\":\"payload\",\"mensagem\":\"requisicao invalida\"}]}")));

        // Confirmar pedido 1 AUTENTICADO -> 200
        wm.stubFor(post(urlEqualTo("/api/pedidos/1/confirmar"))
                .atPriority(1)
                .withHeader("Authorization", matching("Bearer .+"))
                .willReturn(aResponse().withStatus(200)
                        .withHeader("Content-Type", "application/json")
                        .withBody("{\"pedidoId\":1,\"status\":\"CONFIRMADO\","
                                + "\"confirmadoEm\":\"2026-07-05T12:00:00Z\",\"valorTotal\":150.00}")));

        // Confirmar pedido 1 SEM auth (fallback) -> 401
        wm.stubFor(post(urlEqualTo("/api/pedidos/1/confirmar"))
                .atPriority(20)
                .willReturn(aResponse().withStatus(401)
                        .withHeader("Content-Type", "application/json")
                        .withBody("{\"erro\":\"nao_autenticado\"}")));

        // Confirmar pedido INEXISTENTE -> 404
        wm.stubFor(post(urlEqualTo("/api/pedidos/999/confirmar"))
                .atPriority(1)
                .withHeader("Authorization", matching("Bearer .+"))
                .willReturn(aResponse().withStatus(404)
                        .withHeader("Content-Type", "application/json")
                        .withBody("{\"mensagem\":\"Pedido 999 nao encontrado\"}")));

        // Confirmar pedido JÁ CONFIRMADO -> 409
        wm.stubFor(post(urlEqualTo("/api/pedidos/2/confirmar"))
                .atPriority(1)
                .withHeader("Authorization", matching("Bearer .+"))
                .willReturn(aResponse().withStatus(409)
                        .withHeader("Content-Type", "application/json")
                        .withBody("{\"erro\":\"estado_invalido\",\"estadoAtual\":\"CONFIRMADO\"}")));
    }
}
