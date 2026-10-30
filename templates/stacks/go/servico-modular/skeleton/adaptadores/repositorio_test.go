package adaptadores

import (
	"sync"
	"testing"

	"{{project_name}}/dominio"
)

func TestRepositorioConcorrente(t *testing.T) {
	repositorio := NovoRepositorioMemoria()
	var espera sync.WaitGroup
	for indice := 0; indice < 32; indice++ {
		espera.Add(1)
		go func() {
			defer espera.Done()
			titulo, _ := dominio.NovoTitulo("tarefa concorrente")
			repositorio.Guardar(dominio.NovaTarefa(titulo))
		}()
	}
	espera.Wait()
	if quantidade := len(repositorio.Pendentes()); quantidade != 32 {
		t.Fatalf("quer 32 pendentes, veio %d", quantidade)
	}
	if _, err := repositorio.Concluir("fantasma"); err == nil {
		t.Fatal("concluir inexistente deveria falhar")
	}
}
