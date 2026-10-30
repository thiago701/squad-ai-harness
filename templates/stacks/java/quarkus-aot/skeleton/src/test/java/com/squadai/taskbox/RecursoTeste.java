package com.squadai.taskbox;

import static io.restassured.RestAssured.given;
import static io.restassured.RestAssured.when;
import static org.hamcrest.CoreMatchers.equalTo;
import static org.hamcrest.CoreMatchers.notNullValue;

import org.junit.jupiter.api.Test;

import io.quarkus.test.junit.QuarkusTest;

/// Borda real: sobe o Quarkus de teste e exercita HTTP de verdade.
@QuarkusTest
class RecursoTeste {

    @Test
    void fluxoCompletoPelaBorda() {
        when().get("/health").then().statusCode(200).body("situacao", equalTo("ok"));
        given().contentType("application/json").body("{\"titulo\":\"integrar quarkus\"}")
                .when().post("/tarefas")
                .then().statusCode(201).body("identificador", notNullValue());
        when().get("/tarefas").then().statusCode(200);
    }

    @Test
    void mapperCentralTraduzErros() {
        given().contentType("application/json").body("{\"titulo\":\"ab\"}")
                .when().post("/tarefas").then().statusCode(422);
        given().contentType("application/json")
                .when().post("/tarefas/fantasma/concluir").then().statusCode(404);
    }
}
