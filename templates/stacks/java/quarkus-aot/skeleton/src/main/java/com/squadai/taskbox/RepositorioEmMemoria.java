package com.squadai.taskbox;

import java.util.List;

/// Adaptador em memoria sobre a colecao de primeira classe.
public final class RepositorioEmMemoria implements RepositorioDeTarefas {

    private final Tarefas tarefas = new Tarefas();

    @Override
    public void guardar(Tarefa tarefa) {
        tarefas.adicionar(tarefa);
    }

    @Override
    public Tarefa concluir(String identificador) {
        return tarefas.concluir(identificador);
    }

    @Override
    public List<Tarefa> pendentes() {
        return tarefas.pendentes();
    }
}
