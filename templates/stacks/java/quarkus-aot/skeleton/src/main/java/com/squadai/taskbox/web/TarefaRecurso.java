package com.squadai.taskbox.web;

import java.util.List;
import java.util.Map;

import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.core.Response;

import com.squadai.taskbox.ServicoDeTarefas;

/// Resource fino do quarkus-rest: so orquestra o servico.
@Path("/")
public class TarefaRecurso {

    public record NovaTarefaCorpo(String titulo) {
    }

    private final ServicoDeTarefas servico;

    public TarefaRecurso(ServicoDeTarefas servico) {
        this.servico = servico;
    }

    @GET
    @Path("health")
    public Map<String, String> saude() {
        return Map.of("situacao", "ok");
    }

    @GET
    @Path("tarefas")
    public List<String> pendentes() {
        return servico.pendentes();
    }

    @POST
    @Path("tarefas")
    public Response criar(NovaTarefaCorpo corpo) {
        var identificador = servico.criar(corpo.titulo());
        return Response.status(Response.Status.CREATED)
                .entity(Map.of("identificador", identificador)).build();
    }

    @POST
    @Path("tarefas/{identificador}/concluir")
    public Map<String, String> concluir(@PathParam("identificador") String identificador) {
        return Map.of("tarefa", servico.concluir(identificador));
    }
}
