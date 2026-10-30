package com.squadai.taskbox;

/// Borda CLI nativa: handler central de erros, saida honesta, zero reflexao.
public final class Aplicacao {

    private Aplicacao() {
    }

    public static void main(String[] argumentos) {
        System.exit(executar(argumentos));
    }

    static int executar(String[] argumentos) {
        var servico = new ServicoDeTarefas(new RepositorioEmMemoria());
        try {
            System.out.println(despachar(servico, argumentos));
            return 0;
        } catch (ErroDeDominio erro) {
            System.err.println("{\"nivel\":\"erro\",\"mensagem\":\"" + erro.getMessage() + "\"}");
            return 2;
        }
    }

    private static String despachar(ServicoDeTarefas servico, String[] argumentos) {
        if (argumentos.length > 1 && "criar".equals(argumentos[0])) {
            return servico.criar(String.join(" ", java.util.Arrays.copyOfRange(argumentos, 1, argumentos.length)));
        }
        if (argumentos.length > 1 && "concluir".equals(argumentos[0])) {
            return servico.concluir(argumentos[1]);
        }
        return listar(servico);
    }

    private static String listar(ServicoDeTarefas servico) {
        var pendentes = servico.pendentes();
        if (pendentes.isEmpty()) {
            return "(sem pendencias)";
        }
        return String.join("\n", pendentes);
    }
}
