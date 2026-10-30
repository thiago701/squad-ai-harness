package com.squadai.taskbox;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class AplicacaoTeste {

    @Test
    void bordaTraduzErroDeDominioEmCodigoDeSaida() {
        assertEquals(0, Aplicacao.executar(new String[]{}));
        assertEquals(0, Aplicacao.executar(new String[]{"criar", "nova tarefa"}));
        assertEquals(2, Aplicacao.executar(new String[]{"criar", "ab"}));
        assertEquals(2, Aplicacao.executar(new String[]{"concluir", "fantasma"}));
        assertEquals(0, Aplicacao.executar(new String[]{"desconhecido"}));
    }
}
