package com.squadai.taskbox.web;

import java.util.List;
import java.util.Map;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.squadai.taskbox.ServicoDeTarefas;

/// Borda fina: DTOs sao records; rota so orquestra o servico.
@RestController
public class TarefaControlador {

    /// Contrato de entrada da API (nunca a entidade de dominio).
    public record NovaTarefaCorpo(String titulo) {
    }

    public record TarefaCriada(String identificador) {
    }

    private final ServicoDeTarefas servico;

    public TarefaControlador(ServicoDeTarefas servico) {
        this.servico = servico;
    }

    @GetMapping("/health")
    public Map<String, String> saude() {
        return Map.of("situacao", "ok");
    }

    @GetMapping("/tarefas")
    public List<String> pendentes() {
        return servico.pendentes();
    }

    @PostMapping("/tarefas")
    @ResponseStatus(HttpStatus.CREATED)
    public TarefaCriada criar(@RequestBody NovaTarefaCorpo corpo) {
        return new TarefaCriada(servico.criar(corpo.titulo()));
    }

    @PostMapping("/tarefas/{identificador}/concluir")
    public Map<String, String> concluir(@PathVariable String identificador) {
        return Map.of("tarefa", servico.concluir(identificador));
    }
}
