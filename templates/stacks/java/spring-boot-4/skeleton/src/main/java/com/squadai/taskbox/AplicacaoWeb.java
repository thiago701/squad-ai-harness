package com.squadai.taskbox;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;

/// Composition root no pacote raiz: component scan cobre os subpacotes (.web).
@SpringBootApplication
public class AplicacaoWeb {

    public static void main(String[] argumentos) {
        SpringApplication.run(AplicacaoWeb.class, argumentos);
    }

    @Bean
    ServicoDeTarefas servicoDeTarefas() {
        return new ServicoDeTarefas(new RepositorioEmMemoria());
    }
}
