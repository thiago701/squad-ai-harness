// Package aplicacao orquestra o dominio atras de portas pequenas.
package aplicacao

import "{{project_name}}/dominio"

// Repositorio e a porta minima que o caso de uso exige (definida no consumidor).
type Repositorio interface {
	Guardar(tarefa dominio.Tarefa)
	Concluir(id string) (dominio.Tarefa, error)
	Pendentes() []dominio.Tarefa
}

// Servico expoe os casos de uso de tarefas.
type Servico struct {
	repositorio Repositorio
}

// NovoServico injeta a unica dependencia.
func NovoServico(repositorio Repositorio) *Servico {
	return &Servico{repositorio: repositorio}
}

// Criar valida o titulo, cria e guarda a tarefa.
func (s *Servico) Criar(tituloBruto string) (string, error) {
	titulo, err := dominio.NovoTitulo(tituloBruto)
	if err != nil {
		return "", err
	}
	tarefa := dominio.NovaTarefa(titulo)
	s.repositorio.Guardar(tarefa)
	return tarefa.Identificador(), nil
}

// Concluir marca a tarefa como feita e devolve a descricao.
func (s *Servico) Concluir(id string) (string, error) {
	tarefa, err := s.repositorio.Concluir(id)
	if err != nil {
		return "", err
	}
	return tarefa.Descrever(), nil
}

// Pendentes descreve as tarefas em aberto.
func (s *Servico) Pendentes() []string {
	tarefas := s.repositorio.Pendentes()
	descricoes := make([]string, 0, len(tarefas))
	for _, tarefa := range tarefas {
		descricoes = append(descricoes, tarefa.Descrever())
	}
	return descricoes
}
