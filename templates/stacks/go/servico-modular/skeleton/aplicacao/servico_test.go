package aplicacao

import (
	"errors"
	"testing"

	"{{project_name}}/dominio"
)

type repositorioFalso struct {
	guardadas []dominio.Tarefa
}

func (r *repositorioFalso) Guardar(tarefa dominio.Tarefa) {
	r.guardadas = append(r.guardadas, tarefa)
}

func (r *repositorioFalso) Concluir(id string) (dominio.Tarefa, error) {
	for _, tarefa := range r.guardadas {
		if tarefa.Identificador() == id {
			return tarefa.Concluir(), nil
		}
	}
	return dominio.Tarefa{}, dominio.ErrTarefaInexistente
}

func (r *repositorioFalso) Pendentes() []dominio.Tarefa { return r.guardadas }

func TestServicoFluxoCompleto(t *testing.T) {
	servico := NovoServico(&repositorioFalso{})
	id, err := servico.Criar("planejar sprint")
	if err != nil || id == "" {
		t.Fatalf("criar falhou: %v", err)
	}
	if descricoes := servico.Pendentes(); len(descricoes) != 1 {
		t.Fatalf("quer 1 pendente, veio %d", len(descricoes))
	}
	if _, err := servico.Concluir(id); err != nil {
		t.Fatalf("concluir falhou: %v", err)
	}
	if _, err := servico.Criar("ab"); err == nil {
		t.Fatal("titulo invalido deveria falhar")
	}
	if _, err := servico.Concluir("fantasma"); !errors.Is(err, dominio.ErrTarefaInexistente) {
		t.Fatal("erro sentinela deveria propagar")
	}
}
