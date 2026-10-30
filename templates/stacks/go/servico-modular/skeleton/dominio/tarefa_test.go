package dominio

import (
	"errors"
	"strings"
	"testing"
)

func TestNovoTituloTabela(t *testing.T) {
	casos := []struct {
		nome    string
		entrada string
		querErr error
	}{
		{"valido", "estudar go", nil},
		{"normaliza espacos", "  ler adr  ", nil},
		{"curto demais", "ab", ErrTituloInvalido},
		{"longo demais", strings.Repeat("x", 121), ErrTituloInvalido},
	}
	for _, caso := range casos {
		t.Run(caso.nome, func(t *testing.T) {
			_, err := NovoTitulo(caso.entrada)
			if !errors.Is(err, caso.querErr) {
				t.Fatalf("NovoTitulo(%q) erro = %v, quer %v", caso.entrada, err, caso.querErr)
			}
		})
	}
}

func TestTarefaImutavelEDescricao(t *testing.T) {
	titulo, _ := NovoTitulo("revisar pr")
	original := NovaTarefa(titulo)
	concluida := original.Concluir()
	if !original.Pendente() || concluida.Pendente() {
		t.Fatal("Concluir deve devolver nova versao sem mutar a original")
	}
	if concluida.Identificador() != original.Identificador() {
		t.Fatal("identidade deve sobreviver a conclusao")
	}
	if !strings.HasPrefix(concluida.Descrever(), "[x]") {
		t.Fatalf("descricao concluida errada: %s", concluida.Descrever())
	}
}
