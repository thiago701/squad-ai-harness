package com.squadai.taskbox.web;

import java.util.Map;

import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.ext.ExceptionMapper;
import jakarta.ws.rs.ext.Provider;

import com.squadai.taskbox.ErroDeDominio;
import com.squadai.taskbox.TarefaInexistente;

/// Mapper central: ErroDeDominio -> resposta HTTP honesta.
@Provider
public class TratadorDeErros implements ExceptionMapper<ErroDeDominio> {

    @Override
    public Response toResponse(ErroDeDominio erro) {
        var status = erro instanceof TarefaInexistente ? 404 : 422;
        return Response.status(status).entity(Map.of("erro", erro.getMessage())).build();
    }
}
