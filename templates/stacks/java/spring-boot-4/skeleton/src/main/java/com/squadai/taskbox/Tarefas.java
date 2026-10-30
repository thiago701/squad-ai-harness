package com.squadai.taskbox;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/// Colecao de primeira classe: o comportamento do conjunto mora aqui.
public final class Tarefas {

    private final Map<String, Tarefa> itens = new LinkedHashMap<>();

    public void adicionar(Tarefa tarefa) {
        itens.put(tarefa.identificador(), tarefa);
    }

    public Tarefa concluir(String identificador) {
        var existente = itens.get(identificador);
        if (existente == null) {
            throw new TarefaInexistente(identificador);
        }
        var concluida = existente.concluir();
        itens.put(identificador, concluida);
        return concluida;
    }

    public List<Tarefa> pendentes() {
        return itens.values().stream().filter(Tarefa::pendente).toList();
    }

    public int total() {
        return itens.size();
    }
}
