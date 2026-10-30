package com.squadai.taskbox;

/// Base selada das violacoes de regra de negocio (tipadas, testaveis).
public sealed abstract class ErroDeDominio extends RuntimeException
        permits TituloInvalido, TarefaInexistente {

    protected ErroDeDominio(String mensagem) {
        super(mensagem);
    }
}
