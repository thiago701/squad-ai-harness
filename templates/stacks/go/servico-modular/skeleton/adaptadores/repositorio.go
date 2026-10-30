// Package adaptadores implementa as portas com detalhes de infraestrutura.
package adaptadores

import (
	"sync"

	"{{project_name}}/dominio"
)

// RepositorioMemoria protege a colecao com mutex (seguro p/ concorrencia).
type RepositorioMemoria struct {
	guarda  sync.Mutex
	tarefas *dominio.Tarefas
}

// NovoRepositorioMemoria cria o adaptador pronto.
func NovoRepositorioMemoria() *RepositorioMemoria {
	return &RepositorioMemoria{tarefas: dominio.NovasTarefas()}
}

// Guardar persiste a tarefa em memoria.
func (r *RepositorioMemoria) Guardar(tarefa dominio.Tarefa) {
	r.guarda.Lock()
	defer r.guarda.Unlock()
	r.tarefas.Adicionar(tarefa)
}

// Concluir delega a colecao sob trava.
func (r *RepositorioMemoria) Concluir(id string) (dominio.Tarefa, error) {
	r.guarda.Lock()
	defer r.guarda.Unlock()
	return r.tarefas.Concluir(id)
}

// Pendentes lista com snapshot seguro.
func (r *RepositorioMemoria) Pendentes() []dominio.Tarefa {
	r.guarda.Lock()
	defer r.guarda.Unlock()
	return r.tarefas.Pendentes()
}
