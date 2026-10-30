package com.squadai.taskbox.web;

import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import com.squadai.taskbox.ErroDeDominio;
import com.squadai.taskbox.TarefaInexistente;

/// Handler central: erro de dominio -> ProblemDetail (RFC 9457).
@RestControllerAdvice
public class TratadorDeErros {

    @ExceptionHandler(ErroDeDominio.class)
    public ProblemDetail traduzir(ErroDeDominio erro) {
        var status = statusDe(erro);
        var problema = ProblemDetail.forStatus(status);
        problema.setTitle("violacao de regra de negocio");
        problema.setDetail(erro.getMessage());
        return problema;
    }

    private HttpStatus statusDe(ErroDeDominio erro) {
        if (erro instanceof TarefaInexistente) {
            return HttpStatus.NOT_FOUND;
        }
        return HttpStatus.UNPROCESSABLE_ENTITY;
    }
}
