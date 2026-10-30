package com.squadai.taskbox.web;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Produces;

import com.squadai.taskbox.RepositorioEmMemoria;
import com.squadai.taskbox.ServicoDeTarefas;

/// Unico ponto de composicao CDI (baixo acoplamento com o container).
public final class Produtores {

    @Produces
    @ApplicationScoped
    ServicoDeTarefas servicoDeTarefas() {
        return new ServicoDeTarefas(new RepositorioEmMemoria());
    }
}
