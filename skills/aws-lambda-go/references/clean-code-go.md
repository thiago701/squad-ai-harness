# Clean code em Go aplicado a Lambda — antes → depois verificado

> Estado de verificação (2026-10-28, Go 1.24.13, `golangci-lint` v2.8.0 e v2.15.0): o gate de clean code da Squad deu **0 achados**
> no lab desta skill (depois das correções da §3) e **17 achados de 13 linters** no exemplo deliberadamente ruim (§2). O exemplo
> refatorado passa no gate e em `go test -race`. **Config e regras gerais de Go:** `../../golang-pro/references/clean-code-e-lint.md`
> (arquivo canônico — não copie). **Princípios gerais** (nomes, funções, smells, testes limpos): **clean-code-craftsman**.

## 1. O que muda no clean code quando o código roda no Lambda

| Regra | Por quê, no Lambda | Onde está no lab |
|---|---|---|
| `main` só monta dependências e chama `lambda.Start` | a init roda uma vez por ambiente e é cobrada; regra de negócio em `main` não se testa | `cmd/*/main.go` |
| Regra de negócio em pacote **puro** (`internal/`), sem tipo do SDK no meio da decisão | testa com `testing` comum, sem Runtime API nem AWS | `internal/batch`, `internal/stream` |
| Dependências da init (logger, clientes SDK, config) são as **únicas** globais — e só em `cmd/` | ciclo de vida do ambiente; fora de `cmd/` global é estado compartilhado entre invocações | exclusão por caminho no `.golangci.yml` |
| Config obrigatória ausente **falha na init** (`os.Exit(1)` com log) | erro visível uma vez, em vez de cada mensagem falhar | `cmd/sqsdyn` |
| Falha de **uma** mensagem nunca vira `error` do handler | `error` devolvido faz o lote inteiro voltar | `batch.Handle` |
| `ctx` com margem é o 1º parâmetro de tudo que faz I/O | o `ctx` do runtime expira **no** deadline; responder depois perde a resposta parcial | `internal/prazo` |
| Erro embrulhado com `%w` e decidido com `errors.Is/As`; logado **uma vez**, na borda | o mesmo erro logado em 3 camadas triplica custo de log e confunde o alarme | `batch.decodifica`, `evb.Decodifica` |
| Entrada tipada (`events.*`, struct com `DisallowUnknownFields`), nunca `map[string]any` + `x.(T)` | evento é entrada hostil; `x.(T)` sem `, ok` é pânico na invocação | `internal/evb`, `exemplos/bom` |
| Resposta tipada (`resposta.Pedido`, `omitzero`) em vez de `map` montado à mão | contrato estável, testável, sem campo zero vazando | `internal/resposta` |
| Nenhuma goroutine sobrevive ao `return` do handler | o ambiente congela; o trabalho "some" ou vaza para a próxima invocação | `prazo.Executa`, `cmd/streamurl` |

## 2. Antes → depois: um handler com os vícios de sempre

O "antes" é um módulo à parte (`exemplos/ruim`, com `go.mod` próprio — o `./...` do lab não o alcança) que concentra o que o gate
barra. **Não copie.**

`exemplos/ruim/handler.go`:

```go
// Package ruim reúne, de propósito, os vícios que o gate de clean code da Squad barra. NÃO copie.
package ruim

import (
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"strings"
)

var processados = map[string]bool{} // estado global mutável compartilhado entre invocações

var ErrDuplicado = errors.New("duplicado")

// Repositorio declarado pelo produtor, "por via das dúvidas", com métodos que ninguém usa.
type Repositorio interface {
	Salvar(id string, valor int) error
}

// Processa recebe parâmetros demais, tem o ctx fora do lugar (aqui nem existe) e mistura tudo.
func Processa(corpo string, repo Repositorio, origem string, tipo string, moeda string, canal string, tentativa int, limite int) (string, error) {
	var dados map[string]any
	json.Unmarshal([]byte(corpo), &dados)
	if origem == "pagamentos" {
		if tipo == "PedidoPago" {
			if moeda == "BRL" {
				if canal == "app" || canal == "web" {
					if tentativa < limite {
						id, ok := dados["id"].(string)
						if ok {
							if processados[id] {
								return "", ErrDuplicado
							} else {
								err := repo.Salvar(id, int(dados["valor"].(float64)))
								if err != nil {
									log.Printf("erro ao salvar: %v", err)
									return "", fmt.Errorf("Falha ao salvar: %v", err)
								}
								processados[id] = true
							}
						}
					}
				}
			}
		}
	}
	if strings.HasPrefix(origem, "pagamentos") && tipo == "PedidoPago" && moeda == "BRL" {
		return "pagamentos", nil
	}
	return "pagamentos", nil
}

// Notifica faz HTTP sem context nem timeout e ignora o corpo da resposta.
func Notifica(url string) error {
	resp, err := http.Get(url)
	if err != nil {
		return err
	}
	if resp.StatusCode != 200 {
		return errors.New("pagamentos")
	}
	return nil
}

// EhDuplicado compara erro com == (quebra quando o erro vem embrulhado).
func EhDuplicado(err error) bool {
	return err == ErrDuplicado
}
```

Saída real do gate sobre ele (`golangci-lint run -c ../../.golangci.yml ./...`, v2.8.0):

```text
handler.go:57:23: response body must be closed (bodyclose)
handler.go:25:16: Error return value of `json.Unmarshal` is not checked (errcheck)
handler.go:39:55: non-wrapping format verb for fmt.Errorf. Use `%w` to format errors (errorlint)
handler.go:69:9: comparing with == will fail on wrapped errors. Use errors.Is to check for a specific error (errorlint)
handler.go:36:9: right hand must be only type assertion (forcetypeassert)
handler.go:13:5: processados is a global variable (gochecknoglobals)
handler.go:23:1: cognitive complexity 39 of func `Processa` is high (> 15) (gocognit)
handler.go:26:15: string `pagamentos` has 3 occurrences, make it a constant (goconst)
handler.go:25:2: G104: Errors unhandled (gosec)
handler.go:57:15: G107: Potential HTTP request made with variable url (gosec)
handler.go:26:1: `if origem == "pagamentos"` has complex nested blocks (complexity: 29) (nestif)
handler.go:57:23: net/http.Get must not be called. use net/http.NewRequestWithContext and (*net/http.Client).Do(*http.Request) (noctx)
handler.go:15:5: exported: exported var ErrDuplicado should have comment or be unexported (revive)
handler.go:23:1: argument-limit: maximum number of arguments per function exceeded; max 7 but got 8 (revive)
handler.go:35:15: indent-error-flow: if block ends with a return statement, so drop this else and outdent its block (revive)
handler.go:39:21: ST1005: error strings should not be capitalized (staticcheck)
handler.go:61:24: "200" can be replaced by http.StatusOK (usestdlibvars)
```

O que **nenhum** linter pegou e a revisão precisa pegar: o `log.Printf` seguido de `return` (erro tratado duas vezes), a interface
declarada pelo produtor "por via das dúvidas" e o `return` final idêntico nos dois ramos. E a ciclomática ficou **abaixo** de 15 na
mesma função que mediu **39** de cognitiva — a pirâmide de `if` engana a métrica de caminhos.

O "depois" (`exemplos/bom`), com as mesmas regras de negócio:

`exemplos/bom/handler.go`:

```go
// Package bom é a versão refatorada de exemplos/ruim: mesmas regras de negócio, sem os vícios.
package bom

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
)

// Erros sentinela: o chamador decide com errors.Is, nunca comparando texto.
var (
	ErrDuplicado = errors.New("pedido duplicado")
	ErrRecusado  = errors.New("evento recusado")
)

// Evento agrupa o que antes eram 6 parâmetros soltos.
type Evento struct {
	Origem, Tipo, Moeda, Canal string
	Tentativa, Limite          int
	Corpo                      []byte
}

type pagamento struct {
	ID    string `json:"id"`
	Valor int64  `json:"valor"`
}

// salvador é a interface que ESTE pacote consome — pequena e declarada aqui, no consumidor.
type salvador interface {
	Salvar(ctx context.Context, id string, valor int64) error
}

// vistos guarda o que já foi processado; o dono é o chamador (sem global mutável).
type vistos interface {
	JaVisto(ctx context.Context, id string) (bool, error)
}

// Processa aplica as regras com retornos antecipados: cada condição recusada sai na hora.
func Processa(ctx context.Context, ev Evento, repo salvador, v vistos) error {
	if err := aceita(ev); err != nil {
		return err
	}
	p, err := decodifica(ev.Corpo)
	if err != nil {
		return err
	}
	ja, err := v.JaVisto(ctx, p.ID)
	if err != nil {
		return fmt.Errorf("consultar idempotência de %s: %w", p.ID, err)
	}
	if ja {
		return ErrDuplicado
	}
	if err := repo.Salvar(ctx, p.ID, p.Valor); err != nil {
		return fmt.Errorf("salvar pedido %s: %w", p.ID, err) // embrulha e devolve; quem loga é a borda
	}
	return nil
}

const origemPagamentos = "pagamentos"

func aceita(ev Evento) error {
	switch {
	case ev.Origem != origemPagamentos || ev.Tipo != "PedidoPago":
		return fmt.Errorf("%w: %s/%s", ErrRecusado, ev.Origem, ev.Tipo)
	case ev.Moeda != "BRL":
		return fmt.Errorf("%w: moeda %s", ErrRecusado, ev.Moeda)
	case ev.Canal != "app" && ev.Canal != "web":
		return fmt.Errorf("%w: canal %s", ErrRecusado, ev.Canal)
	case ev.Tentativa >= ev.Limite:
		return fmt.Errorf("%w: tentativa %d de %d", ErrRecusado, ev.Tentativa, ev.Limite)
	}
	return nil
}

func decodifica(corpo []byte) (pagamento, error) {
	dec := json.NewDecoder(bytes.NewReader(corpo))
	dec.DisallowUnknownFields()
	var p pagamento
	if err := dec.Decode(&p); err != nil {
		return pagamento{}, fmt.Errorf("%w: %w", ErrRecusado, err)
	}
	if p.ID == "" || p.Valor <= 0 {
		return pagamento{}, fmt.Errorf("%w: id/valor", ErrRecusado)
	}
	return p, nil
}

// Notifica usa o ctx da invocação (prazo) e um cliente com timeout criado na init pelo chamador.
func Notifica(ctx context.Context, c *http.Client, url string) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, http.NoBody)
	if err != nil {
		return fmt.Errorf("montar notificação: %w", err)
	}
	resp, err := c.Do(req)
	if err != nil {
		return fmt.Errorf("notificar: %w", err)
	}
	defer func() { _ = resp.Body.Close() }() // erro de Close do corpo já lido não muda o resultado
	_, _ = io.Copy(io.Discard, resp.Body)    // drena para reaproveitar a conexão keep-alive
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("notificar: status %d", resp.StatusCode)
	}
	return nil
}
```

`exemplos/bom/handler_test.go`:

```go
package bom

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

type repoFalso struct{ salvos map[string]int64 }

func (r *repoFalso) Salvar(_ context.Context, id string, v int64) error {
	r.salvos[id] = v
	return nil
}

type vistosFalso map[string]bool

func (v vistosFalso) JaVisto(_ context.Context, id string) (bool, error) { return v[id], nil }

func TestProcessa(t *testing.T) {
	base := Evento{
		Origem: "pagamentos", Tipo: "PedidoPago", Moeda: "BRL", Canal: "app", Limite: 3,
		Corpo: []byte(`{"id":"p1","valor":100}`),
	}
	com := func(f func(*Evento)) Evento { e := base; f(&e); return e }
	casos := []struct {
		nome string
		ev   Evento
		quer error
	}{
		{"aceito", base, nil},
		{"duplicado", com(func(e *Evento) { e.Corpo = []byte(`{"id":"ja","valor":1}`) }), ErrDuplicado},
		{"moeda", com(func(e *Evento) { e.Moeda = "USD" }), ErrRecusado},
		{"canal", com(func(e *Evento) { e.Canal = "fax" }), ErrRecusado},
		{"tentativas", com(func(e *Evento) { e.Tentativa = 3 }), ErrRecusado},
		{"campo extra", com(func(e *Evento) { e.Corpo = []byte(`{"id":"p1","valor":1,"x":1}`) }), ErrRecusado},
	}
	for _, c := range casos {
		t.Run(c.nome, func(t *testing.T) {
			repo := &repoFalso{salvos: map[string]int64{}}
			err := Processa(context.Background(), c.ev, repo, vistosFalso{"ja": true})
			if !errors.Is(err, c.quer) {
				t.Fatalf("err = %v, quer %v", err, c.quer)
			}
			if (c.quer == nil) != (len(repo.salvos) == 1) {
				t.Fatalf("salvos = %v", repo.salvos)
			}
		})
	}
}

func TestNotifica(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusTeapot)
	}))
	defer srv.Close()
	c := &http.Client{Timeout: time.Second}
	if err := Notifica(context.Background(), c, srv.URL); err == nil {
		t.Fatal("status != 200 deveria falhar")
	}
}
```

| Vício (antes) | Linter | Correção (depois) |
|---|---|---|
| 8 parâmetros soltos | `revive` argument-limit (S107) | struct `Evento` com o que anda junto |
| pirâmide de 6 `if` (cognitiva 39) | `gocognit` (S3776), `nestif` | `aceita` com `switch` de recusas + retornos antecipados |
| `json.Unmarshal` ignorado, `map[string]any`, `x.(float64)` | `errcheck`, `gosec`, `forcetypeassert` | `json.Decoder` com `DisallowUnknownFields` em struct tipada |
| `map` global de processados | `gochecknoglobals` | interface `vistos` pequena, injetada pelo chamador |
| `fmt.Errorf("Falha...: %v")` + `log.Printf` antes | `errorlint`, `staticcheck` ST1005 | `fmt.Errorf("salvar pedido %s: %w", ...)`, sem log (a borda loga) |
| `err == ErrDuplicado` | `errorlint` | `errors.Is` no chamador; sentinelas documentadas |
| `http.Get(url)` sem prazo, corpo não fechado, `200` literal | `noctx`, `bodyclose`, `gosec` G107, `usestdlibvars` | `NewRequestWithContext` + cliente com timeout + `defer Close` + `http.StatusOK` |
| `"pagamentos"` repetido | `goconst` | `const origemPagamentos` |
| `else` depois de `return` | `revive` indent-error-flow | retorno antecipado |

## 3. O gate no código real do lab: 14 achados → 0

Na primeira passada do gate sobre o lab (código que já passava em `vet`, `staticcheck` e testes), o `golangci-lint` achou 14
problemas reais (fora 4 falsos positivos do `misspell` em PT-BR, que levaram a desligá-lo): `errcheck` 2, `errorlint` 2, `gofumpt` 2,
`nilerr` 1, `revive` 4 (exportado sem doc), `usestdlibvars` 3. As correções que mudaram comportamento:

```go
// internal/batch: antes o erro do JSON virava texto (%v) e errors.As(err, *json.SyntaxError) não o encontrava mais
return Pedido{}, fmt.Errorf("%w: %v", ErrInvalido, err) // antes
return Pedido{}, fmt.Errorf("%w: %w", ErrInvalido, err) // depois: os dois continuam inspecionáveis (Go 1.20+)
```

```go
// cmd/http: o erro de serialização era engolido (nilerr); agora é registrado — a resposta 500 continua (502 do API Gateway é pior)
if err != nil {
	slog.Error("serializar resposta", "erro", err)
	return events.APIGatewayV2HTTPResponse{StatusCode: http.StatusInternalServerError, Body: `{"erro":"interno"}`}, nil
}
```

```go
// cmd/streamurl: escrita no pipe ignorada (errcheck) — se o cliente desconecta, a goroutine seguia gerando à toa
if _, err := fmt.Fprintf(pw, "parte %d\n", i); err != nil {
	return // o leitor fechou: pare de gerar
}
```

Efeito colateral visível no Runtime API simulado: o `errorType` do erro do EventBridge passou de `wrapError` para `wrapErrors`
(dois `%w`) — se algum alarme ou teste dependia do nome do tipo, ajuste (o texto da mensagem não mudou).

## 4. Zero supressão inline

Regra da Squad (Sonar-First, fases C/D): nada de `//nolint`, `//lint:ignore`/`//lint:file-ignore`, `#nosec` ou `NOSONAR` no código
(o `#nosec` cala o gosec e o `//lint:ignore` cala o staticcheck isolado — os dois verificados). Exceção inevitável vai para
`linters.exclusions` do `.golangci.yml`, por caminho e linter, com o porquê — no lab são duas (globais da init em `cmd/`; tamanho de
teste de tabela em `_test.go`). O comando do gate e por que não `! grep` nem `; test $? -eq 1`: reference canônica §4.

## 5. Gate (comando · critério)

Script completo, verificado com `bash -e`: `go-lambda.md` §11.

| Comando | Critério |
|---|---|
| `export GOTOOLCHAIN=go1.24.13` + `test "$(go env GOVERSION)" = go1.24.13` | toolchain **fixo** (o `toolchain` do go.mod é mínimo) |
| `test -z "$(gofmt -l .)"` | nenhum arquivo fora do formato |
| `go vet ./...` | saída 0 |
| `go tool staticcheck ./...` | saída 0 — **obrigatório** (staticcheck 2025.1.1 travado pela diretiva `tool`) |
| `golangci-lint run ./...` | **0 issues** com o `.golangci.yml` canônico (S3776 ≤ 15, S1541 ≤ 15, S107 ≤ 7, funlen 60/40, nestif reporta a partir de 4) |
| `rc=0; grep -rnE --include='*.go' -e '//[[:space:]]*nolint' -e '//[[:space:]]*lint:(file-)?ignore' -e '#nosec' -e 'NOSONAR' . \|\| rc=$?; test "$rc" -eq 1` | zero supressão inline (só o 1 do `grep` passa) |
| `go test -race -count=1 ./...` | verde, sem data race |
| `go test -count=1 -coverprofile=cover.out ./internal/...` + `go tool cover -func=cover.out \| awk '/^total:/ { sub("%", "", $3); exit !($3 + 0 >= 97) }'` | regra de negócio (`internal/`) **≥ 97 %** de instruções (no lab: 99,2 %; `cmd/` fica fora e é coberto pelo contrato com o Runtime API simulado) |
| `GOEXPERIMENT=synctest go test -count=1 ./internal/prazo` | o teste com relógio falso (build tag) também passa |
| `go tool govulncheck ./...` | sem vulnerabilidade alcançável — **com Go 1.24 reprova (28 em 2026-10-28; o número só cresce)**: só passa com aceite de risco do dono (`go-lambda.md` §13) |
| `make build-<Função> ARTIFACTS_DIR=…` + `file bootstrap` | ELF aarch64 estático, `bootstrap` na raiz do zip |
