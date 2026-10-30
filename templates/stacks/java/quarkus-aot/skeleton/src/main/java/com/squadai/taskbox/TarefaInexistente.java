package com.squadai.taskbox;

public final class TarefaInexistente extends ErroDeDominio {

    public TarefaInexistente(String identificador) {
        super("tarefa " + identificador + " nao encontrada");
    }
}
