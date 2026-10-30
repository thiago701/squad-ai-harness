package com.squadai.taskbox;

import java.util.UUID;

/// Entidade imutavel: concluir devolve nova versao.
public record Tarefa(String identificador, TituloTarefa titulo, boolean concluida) {

    public static Tarefa nova(String tituloBruto) {
        return new Tarefa(UUID.randomUUID().toString(), new TituloTarefa(tituloBruto), false);
    }

    public Tarefa concluir() {
        return new Tarefa(identificador, titulo, true);
    }

    public boolean pendente() {
        return !concluida;
    }

    public String descrever() {
        var marcador = concluida ? "x" : " ";
        return "[%s] %s".formatted(marcador, titulo.valor());
    }
}
