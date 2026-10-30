package com.squadai.qa.restassured.support;

import io.restassured.builder.RequestSpecBuilder;
import io.restassured.builder.ResponseSpecBuilder;
import io.restassured.http.ContentType;
import io.restassured.specification.RequestSpecification;
import io.restassured.specification.ResponseSpecification;

import static java.util.concurrent.TimeUnit.MILLISECONDS;
import static org.hamcrest.Matchers.lessThan;

/**
 * Especificações reutilizáveis — o coração de um framework RestAssured profissional.
 *
 * <p>Centralizar base URI, headers, content-type e o contrato transversal de resposta
 * (JSON + SLA de latência) elimina duplicação: cada teste declara apenas o que é
 * específico do seu cenário. Trocar de ambiente (local/staging) = trocar 1 linha.</p>
 */
public final class ApiSpecs {

    /** Token de teste. Em produção viria de variável de ambiente/secret, nunca hardcoded. */
    public static final String TOKEN = "test-jwt-token";

    private ApiSpecs() {
    }

    /** Requisição base (sem autenticação) — usada por cenários 401 e por criação pública. */
    public static RequestSpecification base(String baseUri) {
        return new RequestSpecBuilder()
                .setBaseUri(baseUri)
                .setBasePath("/api")
                .setContentType(ContentType.JSON)
                .setAccept(ContentType.JSON)
                .addHeader("X-Correlation-Id", "it-" + System.nanoTime())
                .build();
    }

    /**
     * Contrato transversal de resposta: sempre JSON e sempre dentro do SLA de latência.
     * Aplicado via {@code then().spec(...)} em todos os cenários — inclusive os de erro,
     * porque um 4xx lento também é um defeito.
     */
    public static ResponseSpecification jsonComSla(long slaMs) {
        return new ResponseSpecBuilder()
                .expectContentType(ContentType.JSON)
                .expectResponseTime(lessThan(slaMs), MILLISECONDS)
                .build();
    }
}
