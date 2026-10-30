package dominio

import "fmt"

// Tarefas e a colecao de primeira classe: o comportamento do conjunto mora aqui.
type Tarefas struct {
	itens map[string]Tarefa
}

// NovasTarefas cria a colecao pronta para uso.
func NovasTarefas() *Tarefas {
	return &Tarefas{itens: make(map[string]Tarefa)}
}

// Adicionar guarda a tarefa na colecao.
func (c *Tarefas) Adicionar(tarefa Tarefa) {
	c.itens[tarefa.Identificador()] = tarefa
}

// Concluir marca a tarefa e devolve a versao nova.
func (c *Tarefas) Concluir(id string) (Tarefa, error) {
	existente, achou := c.itens[id]
	if !achou {
		return Tarefa{}, fmt.Errorf("%w: %s", ErrTarefaInexistente, id)
	}
	concluida := existente.Concluir()
	c.itens[id] = concluida
	return concluida, nil
}

// Pendentes lista as tarefas que exigem acao.
func (c *Tarefas) Pendentes() []Tarefa {
	pendentes := make([]Tarefa, 0, len(c.itens))
	for _, tarefa := range c.itens {
		if tarefa.Pendente() {
			pendentes = append(pendentes, tarefa)
		}
	}
	return pendentes
}

// Total conta todas as tarefas conhecidas.
func (c *Tarefas) Total() int { return len(c.itens) }
