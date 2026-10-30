# Go idiomático — padrões, decisões e armadilhas

> Síntese autoral (Squad AI) a partir de Effective Go, Go Code Review Comments, Google Go Style Guide,
> Uber Go Style Guide e das práticas comunitárias auditadas (ver `docs/ATTRIBUTIONS.md`). Reescrito;
> sem trechos copiados. Os blocos com `package` foram compilados com o Go 1.27.1.

## 1. Estrutura e nomes

- **Comece plano.** Um módulo com poucos pacotes. Crie pacote quando há fronteira real de responsabilidade, não por camada.
  `cmd/<app>/main.go` (só *wiring*), `internal/...` para o que não deve ser importado de fora. Evite `pkg/`, `utils/`, `common/`, `models/`.
- **Nome do pacote = o que ele oferece**, curto, minúsculo, sem `_`. O chamador lê `orders.Store`, então não repita: `orders.OrdersStore` é *stutter*.
- Getter sem `Get` (`o.Name()`), setter com `Set`; interface de um método termina em `-er` (`Reader`, `Closer`).
- Acrônimos em caixa única: `ID`, `URL`, `HTTP`, `userID`, `ServeHTTP`.
- Receptor curto e consistente (`s *Store`), nunca `this`/`self`. Não misture receptores de valor e de ponteiro no mesmo tipo: se um método precisa de ponteiro, todos usam.
- Exporte o mínimo. Cada símbolo exportado é contrato.

## 2. Erros

- **Embrulhe uma vez, com contexto do que *você* estava fazendo**: `fmt.Errorf("carregar pedido %s: %w", id, err)`.
  Mensagem em minúsculas, sem ponto final, sem "failed to" repetido em cada camada.
- **Trate uma vez**: ou loga **ou** retorna — nunca os dois (gera log duplicado). Quem decide é a borda (handler/`main`).
- **Sentinela** (`var ErrNotFound = errors.New(...)`) para condição que o chamador testa com `errors.Is`;
  **tipo** (`*ValidationError`) quando carrega dados — consuma com `errors.AsType[*ValidationError](err)` (1.26+).
- Vários erros independentes → `errors.Join`. Cuidado: `Join` de lista vazia retorna `nil`.
- `panic` só para bug de programador (invariante violada) ou inicialização impossível; HTTP/worker recupera na **borda** e converte em 500.

```go
package errs

import (
	"errors"
	"fmt"
)

var ErrNotFound = errors.New("não encontrado")

type ValidationError struct{ Field, Msg string }

func (e *ValidationError) Error() string { return e.Field + ": " + e.Msg }

func find(id string) error {
	if id == "" {
		return &ValidationError{Field: "id", Msg: "obrigatório"}
	}
	return fmt.Errorf("pedido %q: %w", id, ErrNotFound)
}

func Classify(id string) string {
	err := find(id)
	switch {
	case errors.Is(err, ErrNotFound):
		return "404"
	default:
		if ve, ok := errors.AsType[*ValidationError](err); ok { // Go 1.26
			return "422 " + ve.Field
		}
		return "500"
	}
}
```

Fechar recurso sem perder erro de escrita (retorno nomeado + `Join`):

```go
func WriteFile(path string, data []byte) (err error) {
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer func() { err = errors.Join(err, f.Close()) }()
	_, err = f.Write(data)
	return err
}
```

## 3. Interfaces e structs

- **Defina a interface no consumidor**, com só os métodos que ele usa. Interface "preventiva" no produtor é ruído.
- **Aceite interface, retorne struct concreta** (facilita evolução e evita *nil interface* surpresa).
- Para teste, prefira **fakes** escritos à mão a gerar mocks; um fake de 5 linhas é mais legível.
- *Embedding* promove métodos e vaza API: use só para composição deliberada, nunca para "herdar" campos.
- **Não copie** tipos com `sync.Mutex`/`atomic`: o `go vet` (copylocks) acusa; passe ponteiro.
- **Options funcionais** só para API pública com muitos opcionais estáveis; para uso interno uma *config struct* é mais simples.

```go
type OrderStore interface { // declarada onde é consumida
	Get(ctx context.Context, id string) (Order, error)
}

type Service struct{ store OrderStore }

type Option func(*Server)

func WithTimeout(d time.Duration) Option { return func(s *Server) { s.timeout = d } }

func NewServer(addr string, opts ...Option) *Server {
	s := &Server{addr: addr, timeout: 10 * time.Second} // default seguro
	for _, o := range opts {
		o(s)
	}
	return s
}
```

## 4. Genéricos, iteradores e as novidades de linguagem

- **Quando usar generics:** algoritmo/contêiner idêntico para vários tipos (`Map`, `Filter`, `Set[T]`, pools). **Quando não:** regra de negócio, ou
  quando uma interface de 1 método resolve. Se você está escrevendo `[T any]` e só usa `any`, provavelmente não precisa.
- **Iteradores** (`iter.Seq[V]`, `iter.Seq2[K,V]`) tornam sequências preguiçosas e componíveis; implemente respeitando o retorno de `yield`.
  Coleções: `slices.Collect`, `slices.Sorted(maps.Keys(m))`, `slices.Values`, `maps.All`. Strings: `strings.SplitSeq`, `strings.Lines`.
- **Método genérico (1.27)** — para operações *do tipo concreto* que variam em outro tipo (`Box.Map[T]`). Não satisfaz interface.
- **Constraint auto-referente (1.26)** — `type Adder[A Adder[A]] interface{ Add(A) A }`.
- **`new(expr)` (1.26)** — `Patch{Name: new(name), Age: new(age)}` em vez de variável temporária + `&`.

```go
package idio

import (
	"cmp"
	"iter"
	"maps"
	"slices"
	"strings"
)

func Lines(s string) iter.Seq[string] { return strings.SplitSeq(s, "\n") }

func Filter[T any](seq iter.Seq[T], keep func(T) bool) iter.Seq[T] {
	return func(yield func(T) bool) {
		for v := range seq {
			if keep(v) && !yield(v) {
				return // sempre respeite o false do consumidor
			}
		}
	}
}

func SortedKeys(m map[string]int) []string { return slices.Sorted(maps.Keys(m)) }

type Box struct{ items []string }

func (b *Box) Map[T any](f func(string) T) []T { // Go 1.27
	out := make([]T, 0, len(b.items))
	for _, s := range b.items {
		out = append(out, f(s))
	}
	return out
}

func Port(env, flag int) int { return cmp.Or(flag, env, 8080) } // 1º valor não-zero
```

## 5. Slices, maps, strings

- Slice é (ponteiro, len, cap): **atribuir não copia**. Devolver campo interno expõe estado — use `slices.Clone`.
- `nil` slice ≠ slice vazio para `==nil`, mas ambos funcionam com `len`, `range`, `append`. Em JSON a v1 emite `null` e a v2 emite `[]`.
- Pré-dimensione quando conhece o tamanho: `make([]T, 0, n)`, `make(map[K]V, n)`, `strings.Builder` + `Grow`.
- Ordem de iteração de `map` é aleatória de propósito: ordene chaves (`slices.Sorted(maps.Keys(m))`) quando a saída importa (golden file, assinatura).
- `clear(m)` zera mapa/slice; `min`/`max` são builtins; `slices.SortFunc` com `cmp.Compare`; `slices.BinarySearch`.
- Concatenar em laço com `+=` é O(n²): use `strings.Builder`. Para `[]byte`→`string` sem cópia evite truques `unsafe` salvo prova por benchmark.

## 6. Contexto, tempo e cancelamento

- ctx sempre 1º parâmetro; **nunca** em struct de longa vida; **nunca** `nil` (use `context.TODO()` se ainda não decidiu).
- `context.WithTimeout` por chamada externa; `defer cancel()` sempre. `context.WithCancelCause` + `context.Cause` para dizer *por quê*.
- `context.WithoutCancel(ctx)` para trabalho que deve **sobreviver** ao request (auditoria, limpeza) mantendo os valores do ctx.
- Valores no ctx só para dados do *request* (trace id, usuário autenticado) — nunca dependências ou parâmetros opcionais.
- Receba `time.Duration` (não `int` de segundos); injete relógio (`func() time.Time`) ou use `synctest` para testar tempo.

## 7. Logging com `log/slog`

- Mensagem constante + atributos tipados: `log.LogAttrs(ctx, slog.LevelError, "falha ao processar", slog.String("order_id", id), slog.Any("err", err))`.
- Chaves estáveis em `snake_case`; **jamais** logue segredo/PII (token, senha, CPF, cartão) — implemente `LogValuer` para redigir.
- `slog.NewJSONHandler` em produção; `slog.NewMultiHandler` (1.26) para enviar a mais de um destino com níveis distintos.
- Logue na borda e use `slog.With` para anexar contexto (`request_id`) uma vez só.

## 8. Fronteiras seguras (cheque em todo código que toca entrada externa)

| Superfície | Prática |
|---|---|
| Caminho de arquivo vindo do usuário | `os.OpenRoot(dir)` e `root.Open(nome)` — traversal falha por construção; `filepath.Clean` **não** é defesa |
| SQL | Sempre parâmetros (`$1`/`?`); nunca `fmt.Sprintf` em query; `QueryContext` + `rows.Close()` + `rows.Err()` |
| Processo externo | `exec.CommandContext` com argumentos separados e `WaitDelay`; nunca `sh -c` com entrada de usuário |
| HTTP servidor | `ReadHeaderTimeout`, `ReadTimeout`, `WriteTimeout`, `IdleTimeout`; `http.MaxBytesReader`; `http.NewCrossOriginProtection()` |
| HTTP cliente | `http.Client{Timeout: ...}` reutilizado (pool de conexões); sempre `defer resp.Body.Close()` |
| Aleatório/segredo | `crypto/rand`; comparação com `subtle.ConstantTimeCompare`; hash de senha com `argon2`/`bcrypt`/`scrypt` |
| TLS | `MinVersion: tls.VersionTLS12` (ideal 1.3); nunca `InsecureSkipVerify` fora de teste local |
| Templates | `html/template` (escapa por contexto); nunca `text/template` para HTML |
| Desserialização | `json` com `DisallowUnknownFields` (v1) ou `json.RejectUnknownMembers(true)` (`encoding/json/v2`); limite de tamanho antes de decodificar |
| Dependências | `govulncheck ./...`, `go mod verify`, fixe versões, revise `go.sum` no PR |

## 9. JSON v2 em 30 segundos (Go 1.27)

```go
import "encoding/json/v2"

type Event struct {
	ID   string    `json:"id"`
	At   time.Time `json:"at"`
	Tags []string  `json:"tags,omitzero"` // omitzero: omite valor zero (inclui time.Time{})
}

err := json.UnmarshalRead(r.Body, &e, json.RejectUnknownMembers(true)) // estrito
out, err := json.Marshal(e, json.Deterministic(true))                   // ordem de chaves estável
```

Use `json.MarshalWrite`/`UnmarshalRead` para *streams*; `jsontext` para processar tokens sem alocar a árvore.

## 10. Checklist de revisão de código Go (use no PR)

- [ ] Toda goroutine tem dono, `ctx` e caminho de término?
- [ ] Todo `error` tratado uma vez, com `%w` e contexto?
- [ ] `Close`/`Shutdown`/`cancel` garantidos (`defer`) e erros de `Close` de escrita preservados?
- [ ] Timeouts em cliente e servidor HTTP; corpo limitado?
- [ ] Interface está no consumidor, pequena e com 2+ usos/fakes?
- [ ] Nenhum `init()` com efeito colateral, nenhum global mutável?
- [ ] Teste de tabela cobre o caminho feliz **e** os erros; `-race` limpo?
- [ ] `gofmt`, `go vet`, `staticcheck`, `govulncheck` sem achados novos?
