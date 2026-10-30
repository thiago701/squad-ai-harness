package main

import (
	"log/slog"
	"testing"
)

func registroSilencioso() *slog.Logger {
	return slog.New(slog.DiscardHandler)
}

func TestExecutarTabela(t *testing.T) {
	casos := []struct {
		nome       string
		argumentos []string
		querCodigo int
	}{
		{"listar vazio", nil, 0},
		{"criar valido", []string{"criar", "nova tarefa"}, 0},
		{"criar invalido", []string{"criar", "ab"}, 2},
		{"concluir inexistente", []string{"concluir", "fantasma"}, 2},
		{"comando desconhecido vira listar", []string{"outra"}, 0},
	}
	for _, caso := range casos {
		t.Run(caso.nome, func(t *testing.T) {
			if codigo := executar(caso.argumentos, registroSilencioso()); codigo != caso.querCodigo {
				t.Fatalf("executar(%v) = %d, quer %d", caso.argumentos, codigo, caso.querCodigo)
			}
		})
	}
}
