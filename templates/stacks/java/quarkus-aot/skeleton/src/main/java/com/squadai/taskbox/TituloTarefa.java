package com.squadai.taskbox;

/// Primitivo encapsulado: compact constructor valida na construcao.
public record TituloTarefa(String valor) {

    public TituloTarefa {
        valor = valor.strip();
        if (valor.length() < 3 || valor.length() > 120) {
            throw new TituloInvalido("titulo deve ter entre 3 e 120 caracteres");
        }
    }
}
