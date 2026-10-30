package com.squadai.taskbox;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.junit.jupiter.api.Test;

class ServicoTeste {

    @Test
    void fluxoCompletoCriarListarConcluir() {
        var servico = new ServicoDeTarefas(new RepositorioEmMemoria());
        var identificador = servico.criar("escrever adr");
        assertEquals(List.of("[ ] escrever adr"), servico.pendentes());
        assertEquals("[x] escrever adr", servico.concluir(identificador));
        assertTrue(servico.pendentes().isEmpty());
        assertThrows(TituloInvalido.class, () -> servico.criar("ab"));
        assertThrows(TarefaInexistente.class, () -> servico.concluir("fantasma"));
    }
}
