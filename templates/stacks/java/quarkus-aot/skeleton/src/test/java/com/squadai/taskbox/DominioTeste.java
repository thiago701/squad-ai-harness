package com.squadai.taskbox;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class DominioTeste {

    @ParameterizedTest
    @ValueSource(strings = {"ab", "  a  "})
    void tituloInvalidoLancaErroTipado(String bruto) {
        assertThrows(TituloInvalido.class, () -> new TituloTarefa(bruto));
    }

    @Test
    void tituloNormalizaELimita() {
        assertEquals("comprar cafe", new TituloTarefa("  comprar cafe  ").valor());
        assertThrows(TituloInvalido.class, () -> new TituloTarefa("x".repeat(121)));
    }

    @Test
    void tarefaImutavelConcluirDevolveNova() {
        var original = Tarefa.nova("estudar java 25");
        var concluida = original.concluir();
        assertTrue(original.pendente());
        assertFalse(concluida.pendente());
        assertEquals(original.identificador(), concluida.identificador());
        assertTrue(concluida.descrever().startsWith("[x]"));
    }

    @Test
    void colecaoDePrimeiraClasseControlaConjunto() {
        var tarefas = new Tarefas();
        var tarefa = Tarefa.nova("revisar pr");
        tarefas.adicionar(tarefa);
        assertEquals(1, tarefas.total());
        tarefas.concluir(tarefa.identificador());
        assertTrue(tarefas.pendentes().isEmpty());
        assertThrows(TarefaInexistente.class, () -> tarefas.concluir("fantasma"));
    }
}
