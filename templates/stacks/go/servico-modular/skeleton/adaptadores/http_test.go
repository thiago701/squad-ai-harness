package adaptadores

import (
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"{{project_name}}/aplicacao"
)

func servidorDeTeste() *httptest.Server {
	servico := aplicacao.NovoServico(NovoRepositorioMemoria())
	return httptest.NewServer(NovoRoteador(servico, slog.New(slog.DiscardHandler)))
}

func TestBordaHTTPFluxoCompleto(t *testing.T) {
	servidor := servidorDeTeste()
	defer servidor.Close()
	saude, err := http.Get(servidor.URL + "/health")
	if err != nil || saude.StatusCode != http.StatusOK {
		t.Fatalf("health falhou: %v %v", err, saude)
	}
	criada, _ := http.Post(servidor.URL+"/tarefas", "application/json",
		strings.NewReader(`{"titulo":"integrar http moderno"}`))
	if criada.StatusCode != http.StatusCreated {
		t.Fatalf("criar quer 201, veio %d", criada.StatusCode)
	}
	lista, _ := http.Get(servidor.URL + "/tarefas")
	if lista.StatusCode != http.StatusOK {
		t.Fatalf("listar quer 200, veio %d", lista.StatusCode)
	}
}

func TestBordaHTTPTraduzErros(t *testing.T) {
	servidor := servidorDeTeste()
	defer servidor.Close()
	casos := []struct {
		nome       string
		fazer      func() (*http.Response, error)
		querStatus int
	}{
		{"titulo invalido", func() (*http.Response, error) {
			return http.Post(servidor.URL+"/tarefas", "application/json", strings.NewReader(`{"titulo":"ab"}`))
		}, http.StatusUnprocessableEntity},
		{"json quebrado", func() (*http.Response, error) {
			return http.Post(servidor.URL+"/tarefas", "application/json", strings.NewReader(`{`))
		}, http.StatusUnprocessableEntity},
		{"concluir fantasma", func() (*http.Response, error) {
			return http.Post(servidor.URL+"/tarefas/fantasma/concluir", "application/json", nil)
		}, http.StatusNotFound},
	}
	for _, caso := range casos {
		t.Run(caso.nome, func(t *testing.T) {
			resposta, err := caso.fazer()
			if err != nil {
				t.Fatalf("requisicao falhou: %v", err)
			}
			if resposta.StatusCode != caso.querStatus {
				t.Fatalf("quer %d, veio %d", caso.querStatus, resposta.StatusCode)
			}
		})
	}
}
