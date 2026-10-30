package com.squadai.taskbox;

import java.util.List;

/// Porta minima definida no consumidor (aplicacao).
public interface RepositorioDeTarefas {

    void guardar(Tarefa tarefa);

    Tarefa concluir(String identificador);

    List<Tarefa> pendentes();
}
