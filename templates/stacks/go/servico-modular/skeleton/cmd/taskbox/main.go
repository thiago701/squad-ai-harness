// Comando taskbox: borda CLI com handler central de erros e slog JSON.
package main

import (
	"fmt"
	"log/slog"
	"os"
	"strings"

	"{{project_name}}/adaptadores"
	"{{project_name}}/aplicacao"
)

func main() {
	os.Exit(executar(os.Args[1:], slog.New(slog.NewJSONHandler(os.Stderr, nil))))
}

func executar(argumentos []string, registro *slog.Logger) int {
	servico := aplicacao.NovoServico(adaptadores.NovoRepositorioMemoria())
	saida, err := despachar(servico, argumentos)
	if err != nil {
		registro.Error("falha de dominio", "erro", err.Error())
		return 2
	}
	fmt.Println(saida)
	return 0
}

func despachar(servico *aplicacao.Servico, argumentos []string) (string, error) {
	if len(argumentos) == 0 {
		return listar(servico), nil
	}
	return comando(servico, argumentos)
}

func comando(servico *aplicacao.Servico, argumentos []string) (string, error) {
	nome := argumentos[0]
	if nome == "criar" && len(argumentos) > 1 {
		return servico.Criar(strings.Join(argumentos[1:], " "))
	}
	if nome == "concluir" && len(argumentos) > 1 {
		return servico.Concluir(argumentos[1])
	}
	return listar(servico), nil
}

func listar(servico *aplicacao.Servico) string {
	pendentes := servico.Pendentes()
	if len(pendentes) == 0 {
		return "(sem pendencias)"
	}
	return strings.Join(pendentes, "\n")
}
