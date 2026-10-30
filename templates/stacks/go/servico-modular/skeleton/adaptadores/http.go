package adaptadores

import (
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"

	"{{project_name}}/aplicacao"
	"{{project_name}}/dominio"
)

const limiteBody = 16 * 1024

// NovoRoteador monta a borda HTTP moderna (ServeMux 1.22+: metodo na rota).
func NovoRoteador(servico *aplicacao.Servico, registro *slog.Logger) http.Handler {
	roteador := http.NewServeMux()
	roteador.HandleFunc("GET /health", saude)
	roteador.HandleFunc("GET /tarefas", listarTarefas(servico))
	roteador.HandleFunc("POST /tarefas", criarTarefa(servico, registro))
	roteador.HandleFunc("POST /tarefas/{id}/concluir", concluirTarefa(servico, registro))
	return roteador
}

func saude(resposta http.ResponseWriter, _ *http.Request) {
	responderJSON(resposta, http.StatusOK, map[string]string{"situacao": "ok"})
}

func listarTarefas(servico *aplicacao.Servico) http.HandlerFunc {
	return func(resposta http.ResponseWriter, _ *http.Request) {
		responderJSON(resposta, http.StatusOK, servico.Pendentes())
	}
}

type corpoNovaTarefa struct {
	Titulo string `json:"titulo"`
}

func criarTarefa(servico *aplicacao.Servico, registro *slog.Logger) http.HandlerFunc {
	return func(resposta http.ResponseWriter, pedido *http.Request) {
		var corpo corpoNovaTarefa
		leitor := http.MaxBytesReader(resposta, pedido.Body, limiteBody)
		if err := json.NewDecoder(leitor).Decode(&corpo); err != nil {
			responderErro(resposta, registro, dominio.ErrTituloInvalido)
			return
		}
		identificador, err := servico.Criar(corpo.Titulo)
		if err != nil {
			responderErro(resposta, registro, err)
			return
		}
		responderJSON(resposta, http.StatusCreated, map[string]string{"identificador": identificador})
	}
}

func concluirTarefa(servico *aplicacao.Servico, registro *slog.Logger) http.HandlerFunc {
	return func(resposta http.ResponseWriter, pedido *http.Request) {
		descricao, err := servico.Concluir(pedido.PathValue("id"))
		if err != nil {
			responderErro(resposta, registro, err)
			return
		}
		responderJSON(resposta, http.StatusOK, map[string]string{"tarefa": descricao})
	}
}

func statusDe(err error) int {
	if errors.Is(err, dominio.ErrTarefaInexistente) {
		return http.StatusNotFound
	}
	return http.StatusUnprocessableEntity
}

func responderErro(resposta http.ResponseWriter, registro *slog.Logger, err error) {
	status := statusDe(err)
	registro.Warn("erro de dominio na borda", "status", status, "erro", err.Error())
	responderJSON(resposta, status, map[string]string{"erro": err.Error()})
}

func responderJSON(resposta http.ResponseWriter, status int, corpo any) {
	resposta.Header().Set("Content-Type", "application/json")
	resposta.WriteHeader(status)
	if err := json.NewEncoder(resposta).Encode(corpo); err != nil {
		slog.Default().Error("falha ao serializar resposta", "erro", err.Error())
	}
}
