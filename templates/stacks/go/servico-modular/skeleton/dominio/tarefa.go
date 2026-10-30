// Package dominio contem as regras de negocio puras (sem dependencia externa).
package dominio

import (
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"strings"
)

// Erros sentinela do dominio: distinguiveis via errors.Is.
var (
	ErrTituloInvalido    = errors.New("titulo deve ter entre 3 e 120 caracteres")
	ErrTarefaInexistente = errors.New("tarefa inexistente")
)

// Titulo encapsula o primitivo com validacao na construcao.
type Titulo struct {
	valor string
}

// NovoTitulo valida e normaliza; unico caminho para criar um Titulo.
func NovoTitulo(bruto string) (Titulo, error) {
	limpo := strings.TrimSpace(bruto)
	if len(limpo) < 3 || len(limpo) > 120 {
		return Titulo{}, fmt.Errorf("%w: %q", ErrTituloInvalido, bruto)
	}
	return Titulo{valor: limpo}, nil
}

// Texto devolve a representacao humana do titulo.
func (t Titulo) Texto() string { return t.valor }

// Tarefa e a entidade; imutavel — Concluir devolve nova versao.
type Tarefa struct {
	id        string
	titulo    Titulo
	concluida bool
}

// NovaTarefa cria a entidade com identidade propria.
func NovaTarefa(titulo Titulo) Tarefa {
	return Tarefa{id: novoIdentificador(), titulo: titulo}
}

func novoIdentificador() string {
	bruto := make([]byte, 8)
	if _, err := rand.Read(bruto); err != nil {
		panic("fonte de aleatoriedade indisponivel: " + err.Error())
	}
	return hex.EncodeToString(bruto)
}

// Identificador expoe a identidade estavel da tarefa.
func (t Tarefa) Identificador() string { return t.id }

// Pendente informa se a tarefa ainda exige acao.
func (t Tarefa) Pendente() bool { return !t.concluida }

// Concluir devolve a versao concluida (imutabilidade).
func (t Tarefa) Concluir() Tarefa {
	return Tarefa{id: t.id, titulo: t.titulo, concluida: true}
}

// Descrever produz a linha humana da tarefa (Tell, don't ask).
func (t Tarefa) Descrever() string {
	marcador := " "
	if t.concluida {
		marcador = "x"
	}
	return fmt.Sprintf("[%s] %s", marcador, t.titulo.Texto())
}
