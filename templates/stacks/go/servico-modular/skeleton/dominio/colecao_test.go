package dominio

import (
	"errors"
	"testing"
)

func TestColecaoConcluirEPendentes(t *testing.T) {
	colecao := NovasTarefas()
	titulo, _ := NovoTitulo("escrever teste")
	tarefa := NovaTarefa(titulo)
	colecao.Adicionar(tarefa)
	if colecao.Total() != 1 || len(colecao.Pendentes()) != 1 {
		t.Fatal("colecao deveria ter 1 pendente")
	}
	if _, err := colecao.Concluir(tarefa.Identificador()); err != nil {
		t.Fatalf("concluir valido falhou: %v", err)
	}
	if len(colecao.Pendentes()) != 0 {
		t.Fatal("pendentes deveria esvaziar")
	}
	if _, err := colecao.Concluir("fantasma"); !errors.Is(err, ErrTarefaInexistente) {
		t.Fatalf("quer ErrTarefaInexistente, veio %v", err)
	}
}
