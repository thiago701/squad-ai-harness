package com.squadai.taskbox;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import com.squadai.taskbox.web.TarefaControlador;
import com.squadai.taskbox.web.TratadorDeErros;

/// Contexto minimo: so a fatia web (sem subir aplicacao inteira).
@WebMvcTest(TarefaControlador.class)
@Import(TratadorDeErros.class)
class ControladorTeste {

    @Autowired
    private MockMvc mvc;

    @Test
    void fluxoCompletoPelaBorda() throws Exception {
        mvc.perform(get("/health")).andExpect(status().isOk());
        mvc.perform(post("/tarefas").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"titulo\":\"integrar sb4\"}"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.identificador").isNotEmpty());
        mvc.perform(get("/tarefas")).andExpect(status().isOk())
                .andExpect(jsonPath("$[0]").value("[ ] integrar sb4"));
    }

    @Test
    void adviceTraduzErrosEmProblemDetail() throws Exception {
        mvc.perform(post("/tarefas").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"titulo\":\"ab\"}"))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.title").value("violacao de regra de negocio"));
        mvc.perform(post("/tarefas/fantasma/concluir"))
                .andExpect(status().isNotFound());
    }
}
