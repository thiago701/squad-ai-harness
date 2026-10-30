package com.squadai.taskbox;

import java.util.List;

/// Caso de uso: unica dependencia e a porta.
public final class ServicoDeTarefas {

    private final RepositorioDeTarefas repositorio;

    public ServicoDeTarefas(RepositorioDeTarefas repositorio) {
        this.repositorio = repositorio;
    }

    public String criar(String tituloBruto) {
        var tarefa = Tarefa.nova(tituloBruto);
        repositorio.guardar(tarefa);
        return tarefa.identificador();
    }

    public String concluir(String identificador) {
        return repositorio.concluir(identificador).descrever();
    }

    public List<String> pendentes() {
        return repositorio.pendentes().stream().map(Tarefa::descrever).toList();
    }
}
