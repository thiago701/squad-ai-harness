# Go no AWS Lambda — referência

> Código **compilado e testado** nesta skill em 2026-10-28 com o padrão da skill: `go 1.24.3` + `toolchain go1.24.13`,
> `aws-lambda-go` **v1.54.0** (a v1.55.x exige Go 1.26), `aws-sdk-go-v2` v1.47.5 (`service/dynamodb` v1.72.2). Verde em `gofmt`,
> `go vet`, `staticcheck` 2025.1.1 (v0.6.1), `golangci-lint` v2.8.0 com o `.golangci.yml` da Squad (0 achados) e `go test -race`;
> o `govulncheck` (v1.1.4) **reprova**: 28 vulnerabilidades da biblioteca padrão alcançáveis com a 1.24.13 em 2026-10-28 — o número
> só cresce (§13). Cobertura de `internal/` 99,2 %. Cada `bootstrap`
> foi executado contra o Runtime API simulado (`iac-e-teste-local.md` §3). Os trechos abaixo são
> os arquivos reais — copie e adapte; não reescreva de memória. Streams, S3, EventBridge e streaming de resposta:
> `fontes-de-eventos.md`.

## 1. Estrutura do projeto

```text
cmd/sqs/main.go       # lambda.Start(handler SQS) — main fino
cmd/sqsdyn/main.go    # variante com SDK v2 + idempotência (DynamoDB)
cmd/http/main.go      # lambda.Start(handler HTTP API v2)
cmd/kinesis/ cmd/ddbstream/ cmd/s3/ cmd/eventbridge/ cmd/streamurl/   # ver fontes-de-eventos.md
internal/batch/       # lógica PURA de lote SQS (testável sem Lambda): Handle (padrão) e HandleFIFO
internal/stream/      # lote ORDENADO de Kinesis/DynamoDB Streams (genérico)
internal/idem/        # guarda de idempotência com lease (DynamoDB)
internal/objetos/ internal/evb/                                        # S3 e EventBridge
Makefile              # build-<IdLógico> chamado pelo SAM
internal/resposta/ internal/tmpfs/                                     # corpo HTTP (omitzero) e /tmp com nome validado + os.Root
exemplos/ruim/ exemplos/bom/   # módulos à parte: o antes→depois do clean code (clean-code-go.md)
.golangci.yml         # gate de clean code (canônico em golang-pro)
go.mod                # go 1.24.3 · toolchain go1.24.13 · aws-lambda-go v1.54.0 · tool (staticcheck, govulncheck, build-lambda-zip)
```

Princípio (P1): `main` só liga as peças e chama `lambda.Start`; a regra de negócio mora em pacote interno e se testa com `testing`
comum. Um binário por função (um `cmd/` por Lambda) mantém o pacote pequeno.

## 2. Assinaturas de handler aceitas

A documentação lista nove: `func()`, `func() error`, `func() (TOut, error)`, `func(TIn) error`, `func(TIn) (TOut, error)`,
`func(context.Context) error`, `func(context.Context) (TOut, error)`, `func(context.Context, TIn) error` e
`func(context.Context, TIn) (TOut, error)` (`TIn`/`TOut` compatíveis com `encoding/json`). Use sempre
`func(context.Context, TIn) (TOut, error)`: o `ctx` traz o **deadline** da invocação.

## 3. SQS com falha parcial (fila padrão)

### Margem de prazo (`internal/prazo`) — o `ctx` do Lambda expira tarde demais

O `ctx` que o `aws-lambda-go` entrega expira **exatamente** no deadline da invocação (`lambda/invoke_loop.go`: `context.WithDeadline`
com o `Lambda-Runtime-Deadline-Ms`). Esperar por `ctx.Err()` significa perceber o fim do prazo quando a invocação **já** estourou: a
resposta parcial não chega, e o lote inteiro volta — inclusive o que deu certo. Por isso o trabalho roda num contexto que termina
`margem` (≈ 500 ms) **antes**, e cada mensagem roda num `Executa` que não espera além dele:

`internal/prazo/prazo.go`:

```go
// Package prazo reserva uma margem antes do deadline da invocação para o handler responder a tempo.
package prazo

import (
	"context"
	"fmt"
	"time"
)

// Margem padrão: tempo para montar e enviar a resposta (parcial) antes do fim da invocação.
const Margem = 500 * time.Millisecond

// ComMargem devolve um contexto que expira `margem` ANTES do deadline de ctx. O ctx do aws-lambda-go expira
// exatamente no deadline da invocação: esperar por ele é responder tarde demais (o lote inteiro volta).
func ComMargem(ctx context.Context, margem time.Duration) (context.Context, context.CancelFunc) {
	if dl, ok := ctx.Deadline(); ok {
		return context.WithDeadline(ctx, dl.Add(-margem))
	}
	return context.WithCancel(ctx)
}

// Executa roda fn isolando pânico e NÃO espera além do prazo de ctx: se o prazo vencer antes, devolve
// ctx.Err() e fn segue em segundo plano até terminar — por isso fn deve respeitar ctx.
func Executa(ctx context.Context, fn func() error) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	res := make(chan error, 1) // buffer 1: a goroutine nunca fica presa se ninguém mais ler
	go func() {
		defer func() {
			if rec := recover(); rec != nil {
				res <- fmt.Errorf("pânico: %v", rec)
			}
		}()
		res <- fn()
	}()
	select {
	case err := <-res:
		return err
	case <-ctx.Done():
		return ctx.Err()
	}
}
```

`Executa` devolve no prazo mesmo que `fn` ignore o `ctx`, mas a goroutine de `fn` continua viva até terminar — e um trabalho vivo
depois do `return` do handler congela com o ambiente e "acorda" na próxima invocação. A margem resolve a **resposta**; o que evita o
vazamento é `fn` respeitar o `ctx` (todo cliente do SDK v2 e `database/sql` aceitam `ctx`). Testes (`internal/prazo/prazo_test.go`):

```go
package prazo

import (
	"context"
	"errors"
	"testing"
	"time"
)

func TestComMargem_ExpiraAntesDoDeadline(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	dl, _ := ctx.Deadline()
	trabalho, c2 := ComMargem(ctx, 300*time.Millisecond)
	defer c2()
	got, _ := trabalho.Deadline()
	if d := dl.Sub(got); d != 300*time.Millisecond {
		t.Fatalf("margem = %v", d)
	}
}

func TestExecuta_NaoEsperaFnQueIgnoraOPrazo(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()
	ini := time.Now()
	err := Executa(ctx, func() error { time.Sleep(2 * time.Second); return nil })
	if !errors.Is(err, context.DeadlineExceeded) || time.Since(ini) > time.Second {
		t.Fatalf("err=%v em %v", err, time.Since(ini))
	}
}

func TestExecuta_PanicoViraErro(t *testing.T) {
	if err := Executa(context.Background(), func() error { panic("boom") }); err == nil {
		t.Fatal("pânico deveria virar erro")
	}
}

func TestComMargem_SemDeadlineSoCancela(t *testing.T) {
	ctx, cancel := ComMargem(context.Background(), Margem)
	if _, ok := ctx.Deadline(); ok {
		t.Fatal("sem deadline no pai não há margem a aplicar")
	}
	cancel()
	if ctx.Err() == nil {
		t.Fatal("cancel deveria encerrar o contexto")
	}
}

func TestExecuta_PrazoJaVencidoNemComeca(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	chamou := false
	if err := Executa(ctx, func() error { chamou = true; return nil }); !errors.Is(err, context.Canceled) || chamou {
		t.Fatalf("err=%v chamou=%v", err, chamou)
	}
}
```

`internal/batch/batch.go`:

```go
// Package batch processa mensagens SQS com falha parcial, concorrência limitada e margem de prazo.
package batch

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"sync"
	"time"

	"github.com/aws/aws-lambda-go/events"

	"example.com/glam/internal/prazo"
)

// Pedido é o corpo esperado de cada mensagem.
type Pedido struct {
	ID    string `json:"id"`
	Valor int64  `json:"valor"` // em centavos
}

// Processor trata um pedido. Deve ser idempotente (SQS entrega "pelo menos uma vez") e respeitar ctx.
type Processor func(ctx context.Context, p Pedido) error

// ErrInvalido marca mensagem que nunca vai passar (vai para a DLQ após maxReceiveCount).
var ErrInvalido = errors.New("mensagem inválida")

func decodifica(body string) (Pedido, error) {
	var p Pedido
	if err := json.Unmarshal([]byte(body), &p); err != nil {
		return Pedido{}, fmt.Errorf("%w: %w", ErrInvalido, err)
	}
	if p.ID == "" || p.Valor <= 0 {
		return Pedido{}, fmt.Errorf("%w: id/valor", ErrInvalido)
	}
	return p, nil
}

// trata decodifica e processa UMA mensagem dentro do prazo de trabalho (pânico vira erro em prazo.Executa).
func trata(ctx context.Context, r events.SQSMessage, proc Processor) error {
	return prazo.Executa(ctx, func() error {
		p, err := decodifica(r.Body)
		if err != nil {
			return err
		}
		return proc(ctx, p)
	})
}

// Handle processa o lote (fila PADRÃO) e devolve SÓ os itens que falharam (partial batch response).
// Requer `ReportBatchItemFailures` na event source mapping. Concorrência máxima = limite. O trabalho para
// `margem` antes do deadline da invocação; o que não terminou até lá volta à fila.
func Handle(ctx context.Context, ev events.SQSEvent, limite int, margem time.Duration, proc Processor) events.SQSEventResponse {
	trabalho, cancel := prazo.ComMargem(ctx, margem)
	defer cancel()
	var (
		mu    sync.Mutex
		falha = []events.SQSBatchItemFailure{}
		wg    sync.WaitGroup
		sem   = make(chan struct{}, max(limite, 1))
	)
	marca := func(id string) {
		mu.Lock()
		falha = append(falha, events.SQSBatchItemFailure{ItemIdentifier: id})
		mu.Unlock()
	}
	for _, r := range ev.Records {
		if trabalho.Err() != nil { // sem tempo: não inicia trabalho novo, devolve à fila
			marca(r.MessageId)
			continue
		}
		select {
		case sem <- struct{}{}:
		case <-trabalho.Done():
			marca(r.MessageId)
			continue
		}
		wg.Add(1)
		go func() {
			defer func() { <-sem; wg.Done() }()
			if trata(trabalho, r, proc) != nil { // volta no máximo no fim do prazo de trabalho
				marca(r.MessageId)
			}
		}()
	}
	wg.Wait() // cada goroutine retorna até o fim do prazo de trabalho (prazo.Executa)
	return events.SQSEventResponse{BatchItemFailures: falha}
}

// HandleFIFO processa EM ORDEM e PARA na 1ª falha: devolve a que falhou e todas as seguintes,
// preservando a ordem do grupo (exigência da AWS para filas FIFO com resposta parcial).
func HandleFIFO(ctx context.Context, ev events.SQSEvent, margem time.Duration, proc Processor) events.SQSEventResponse {
	trabalho, cancel := prazo.ComMargem(ctx, margem)
	defer cancel()
	falha := []events.SQSBatchItemFailure{}
	for i, r := range ev.Records {
		if trata(trabalho, r, proc) != nil { // erro, pânico, mensagem inválida ou prazo esgotado
			for _, resto := range ev.Records[i:] {
				falha = append(falha, events.SQSBatchItemFailure{ItemIdentifier: resto.MessageId})
			}
			break
		}
	}
	return events.SQSEventResponse{BatchItemFailures: falha}
}
```

Por que é assim:

- **Resposta só com os `messageId` que falharam.** Com `ReportBatchItemFailures` na event source mapping, o Lambda apaga as demais
  mensagens e devolve só as falhas à fila. Lista vazia (ou nula) = sucesso total.
- **O handler devolve `error == nil` mesmo com falhas de mensagem.** Devolver erro faz o lote **inteiro** voltar; também voltam
  inteiros: JSON de resposta inválido, `itemIdentifier` vazio/nulo/inexistente ou chave com nome errado. Só devolva `error` para falha
  que atinge o lote todo (ex.: configuração inválida).
- **`falha` nasce como slice vazio** (`[]events.SQSBatchItemFailure{}`): serializa `[]` explícito — a AWS aceita `null`, mas a lista
  vazia é inequívoca e fica coberta por teste.
- **Concorrência limitada** por semáforo (`make(chan struct{}, n)`); `max(limite, 1)` evita travar com configuração zerada.
- **Prazo:** o trabalho roda em `prazo.ComMargem(ctx, prazo.Margem)` (≈ 500 ms antes do deadline); sem tempo, não inicia
  mensagem nova e a devolve à fila, e uma mensagem em andamento que não termina até o fim do prazo de trabalho também volta — a
  resposta parcial sai **antes** do timeout da função (verificado com `PRAZO_MS=300` no Runtime API simulado: as 4 mensagens voltam).
- **Pânico por mensagem** é capturado em `trata` (`recover`) e vira falha só daquela mensagem.
- **Mensagem inválida** (`ErrInvalido`) falha de propósito: nunca vai passar e segue para a DLQ após `maxReceiveCount`.
- O laço captura `r` por iteração (semântica do Go ≥ 1.22) — sem `r := r`.

Testes (`internal/batch/batch_test.go`) — falha parcial com pânico, prazo estourado, lote vazio, e a ordem FIFO:

```go
package batch

import (
	"context"
	"errors"
	"slices"
	"testing"
	"time"

	"example.com/glam/internal/prazo"
	"github.com/aws/aws-lambda-go/events"
)

func rec(id, body string) events.SQSMessage { return events.SQSMessage{MessageId: id, Body: body} }

func ids(r events.SQSEventResponse) []string {
	var out []string
	for _, f := range r.BatchItemFailures {
		out = append(out, f.ItemIdentifier)
	}
	slices.Sort(out)
	return out
}

func TestHandle_FalhasParciais(t *testing.T) {
	ev := events.SQSEvent{Records: []events.SQSMessage{
		rec("ok1", `{"id":"a","valor":100}`),
		rec("json-ruim", `{nao é json`),
		rec("sem-valor", `{"id":"b","valor":0}`),
		rec("erro-negocio", `{"id":"falha","valor":5}`),
		rec("panico", `{"id":"panico","valor":5}`),
		rec("ok2", `{"id":"c","valor":7}`),
	}}
	proc := func(_ context.Context, p Pedido) error {
		switch p.ID {
		case "falha":
			return errors.New("dependência fora do ar")
		case "panico":
			panic("boom")
		}
		return nil
	}
	got := ids(Handle(context.Background(), ev, 3, 0, proc))
	want := []string{"erro-negocio", "json-ruim", "panico", "sem-valor"}
	if !slices.Equal(got, want) {
		t.Fatalf("falhas = %v, quer %v", got, want)
	}
}

func TestHandle_SemTempoDevolveTudoOQueNaoIniciou(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel() // deadline já estourou
	ev := events.SQSEvent{Records: []events.SQSMessage{rec("x", `{"id":"a","valor":1}`), rec("y", `{"id":"b","valor":1}`)}}
	got := ids(Handle(ctx, ev, 2, 0, func(context.Context, Pedido) error { return nil }))
	if !slices.Equal(got, []string{"x", "y"}) {
		t.Fatalf("falhas = %v", got)
	}
}

func TestHandle_LoteVazioNaoDevolveNil(t *testing.T) {
	r := Handle(context.Background(), events.SQSEvent{}, 1, 0, nil)
	if r.BatchItemFailures == nil {
		t.Fatal("BatchItemFailures deve ser slice vazio (serializa como []), não nil")
	}
}

func TestHandleFIFO_ParaNaPrimeiraFalhaEDevolveOResto(t *testing.T) {
	ev := events.SQSEvent{Records: []events.SQSMessage{
		rec("1", `{"id":"a","valor":1}`),
		rec("2", `{"id":"falha","valor":1}`),
		rec("3", `{"id":"c","valor":1}`), // válida, mas vem DEPOIS da falha: não pode ser processada
		rec("4", `{"id":"d","valor":1}`),
	}}
	var vistos []string
	proc := func(_ context.Context, p Pedido) error {
		vistos = append(vistos, p.ID)
		if p.ID == "falha" {
			return errors.New("fora do ar")
		}
		return nil
	}
	got := ids(HandleFIFO(context.Background(), ev, 0, proc))
	if !slices.Equal(got, []string{"2", "3", "4"}) {
		t.Fatalf("falhas = %v, quer [2 3 4]", got)
	}
	if !slices.Equal(vistos, []string{"a", "falha"}) {
		t.Fatalf("processadas = %v: nada depois da 1ª falha pode rodar", vistos)
	}
}

func TestHandleFIFO_PanicoEPoisonMessageTambemParam(t *testing.T) {
	ev := events.SQSEvent{Records: []events.SQSMessage{rec("1", `{nao é json`), rec("2", `{"id":"b","valor":1}`)}}
	got := ids(HandleFIFO(context.Background(), ev, 0, func(context.Context, Pedido) error { return nil }))
	if !slices.Equal(got, []string{"1", "2"}) {
		t.Fatalf("falhas = %v", got)
	}
	ev = events.SQSEvent{Records: []events.SQSMessage{rec("1", `{"id":"a","valor":1}`)}}
	got = ids(HandleFIFO(context.Background(), ev, 0, func(context.Context, Pedido) error { panic("boom") }))
	if !slices.Equal(got, []string{"1"}) {
		t.Fatalf("falhas = %v", got)
	}
}

// Deadline REAL (não só cancel): 1 s de invocação, 500 ms de margem → 500 ms de trabalho.
// Cada mensagem leva 200 ms respeitando o ctx; com concorrência 1 cabem 2 e as outras voltam à fila —
// e a resposta sai ANTES do deadline (se esperasse o deadline, o lote inteiro voltaria).
func TestHandle_MargemAntesDoDeadlineReal(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	ev := events.SQSEvent{Records: []events.SQSMessage{
		rec("1", `{"id":"a","valor":1}`), rec("2", `{"id":"b","valor":1}`),
		rec("3", `{"id":"c","valor":1}`), rec("4", `{"id":"d","valor":1}`),
	}}
	proc := func(ctx context.Context, _ Pedido) error {
		select {
		case <-time.After(200 * time.Millisecond):
			return nil
		case <-ctx.Done():
			return ctx.Err()
		}
	}
	ini := time.Now()
	got := ids(Handle(ctx, ev, 1, 500*time.Millisecond, proc))
	if dur := time.Since(ini); dur > 800*time.Millisecond {
		t.Fatalf("respondeu em %v: tarde demais (deadline em 1 s)", dur)
	}
	if !slices.Equal(got, []string{"3", "4"}) {
		t.Fatalf("falhas = %v, quer [3 4]", got)
	}
}

// Processor que IGNORA o ctx não pode segurar a resposta além do prazo de trabalho.
func TestHandle_ProcessorQueIgnoraOCtxNaoAtrasaAResposta(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	ev := events.SQSEvent{Records: []events.SQSMessage{rec("lento", `{"id":"a","valor":1}`)}}
	ini := time.Now()
	got := ids(Handle(ctx, ev, 1, 500*time.Millisecond, func(context.Context, Pedido) error {
		time.Sleep(3 * time.Second)
		return nil
	}))
	if dur := time.Since(ini); dur > 800*time.Millisecond || !slices.Equal(got, []string{"lento"}) {
		t.Fatalf("falhas = %v em %v", got, dur)
	}
}

func TestHandleFIFO_MargemDevolveOResto(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 700*time.Millisecond)
	defer cancel()
	ev := events.SQSEvent{Records: []events.SQSMessage{rec("1", `{"id":"a","valor":1}`), rec("2", `{"id":"b","valor":1}`)}}
	got := ids(HandleFIFO(ctx, ev, 500*time.Millisecond, func(ctx context.Context, _ Pedido) error {
		select {
		case <-time.After(150 * time.Millisecond):
			return nil
		case <-ctx.Done():
			return ctx.Err()
		}
	}))
	if !slices.Equal(got, []string{"2"}) {
		t.Fatalf("falhas = %v, quer [2]", got)
	}
}

// Go 1.24: b.Loop() substitui o laço com b.N — o setup fora do laço não entra na medição e o
// compilador não elimina a chamada medida.
func BenchmarkHandle(b *testing.B) {
	ev := events.SQSEvent{Records: []events.SQSMessage{
		{MessageId: "1", Body: `{"id":"a","valor":1}`},
		{MessageId: "2", Body: `{nao e json`},
	}}
	proc := func(context.Context, Pedido) error { return nil }
	for b.Loop() {
		Handle(context.Background(), ev, 5, prazo.Margem, proc)
	}
}
```

## 4. Fila FIFO

`HandleFIFO` (no mesmo arquivo) processa **em ordem** e **para na primeira falha**, devolvendo a que falhou e todas as seguintes —
exigência da AWS para preservar a ordem do grupo. Limite de lote da FIFO: 10. Uma *poison message* bloqueia o grupo até a DLQ
(`maxReceiveCount`): mantenha a validação cedo e a DLQ monitorada. Fila FIFO só quando a ordem é requisito.

## 5. Ponto de entrada SQS

`cmd/sqs/main.go`:

```go
package main

import (
	"context"
	"log/slog"
	"os"
	"strconv"

	"github.com/aws/aws-lambda-go/events"
	"github.com/aws/aws-lambda-go/lambda"

	"example.com/glam/internal/batch"
	"example.com/glam/internal/prazo"
)

var (
	log    = slog.New(slog.NewJSONHandler(os.Stdout, nil)) // JSON no stdout → CloudWatch Logs
	limite = envInt("CONCORRENCIA", 5)
)

func envInt(k string, def int) int {
	if v, err := strconv.Atoi(os.Getenv(k)); err == nil && v > 0 {
		return v
	}
	return def
}

func processa(ctx context.Context, p batch.Pedido) error {
	// aqui entram os clientes criados NA INICIALIZAÇÃO (SDK, pool de banco): reutilizados entre invocações
	log.InfoContext(ctx, "pedido processado", "id", p.ID, "valor", p.Valor)
	return nil
}

func handler(ctx context.Context, ev events.SQSEvent) (events.SQSEventResponse, error) {
	r := batch.Handle(ctx, ev, limite, prazo.Margem, processa)
	log.InfoContext(ctx, "lote concluído", "recebidas", len(ev.Records), "falhas", len(r.BatchItemFailures))
	return r, nil
}

func main() { lambda.Start(handler) }
```

- `log` e `limite` são variáveis de pacote: inicializadas **uma vez** por ambiente de execução.
- Logs JSON no stdout vão para o CloudWatch Logs. Registre contagens e ids; **não** o corpo da mensagem nem o evento inteiro.

## 6. Inicialização reaproveitável + idempotência (SDK v2, DynamoDB)

SQS entrega *pelo menos uma vez*: o handler tem de tolerar duplicata. `internal/idem/idem.go` reserva a chave com **lease**
(`EM_ANDAMENTO` + prazo) por escrita condicional e marca `CONCLUIDO` ao final; um processamento que morreu no meio é retomado quando o
lease expira:

```go
// Package idem implementa idempotência por chave com "lease" no DynamoDB.
//
// Fluxo por mensagem: Reservar → processar → Concluir.
//   - 1ª entrega: reserva a chave (estado EM_ANDAMENTO, com lease) e processa;
//   - entrega duplicada enquanto outra invocação processa: Reservar devolve false (não repete);
//   - invocação que morreu no meio: o lease expira e a próxima entrega reserva de novo;
//   - já concluída: Reservar devolve false (descarta a duplicata com sucesso).
package idem

import (
	"context"
	"errors"
	"strconv"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb/types"
)

// Guarda faz a idempotência por chave com lease no DynamoDB (escrita condicional).
type Guarda struct {
	DB     *dynamodb.Client
	Tabela string        // chave de partição: "pk" (S); habilite TTL no atributo "expira"
	Lease  time.Duration // > pior caso de processamento de 1 mensagem
	Reter  time.Duration // por quanto tempo lembrar de chaves concluídas (cobre a janela de reentrega)
	Agora  func() time.Time
}

func (g Guarda) agora() time.Time {
	if g.Agora != nil {
		return g.Agora()
	}
	return time.Now()
}

func n(v int64) types.AttributeValue {
	return &types.AttributeValueMemberN{Value: strconv.FormatInt(v, 10)}
}

// Reservar devolve true se ESTA invocação deve processar a chave.
func (g Guarda) Reservar(ctx context.Context, chave string) (bool, error) {
	agora := g.agora()
	_, err := g.DB.PutItem(ctx, &dynamodb.PutItemInput{
		TableName: aws.String(g.Tabela),
		Item: map[string]types.AttributeValue{
			"pk":     &types.AttributeValueMemberS{Value: chave},
			"estado": &types.AttributeValueMemberS{Value: "EM_ANDAMENTO"},
			"lease":  n(agora.Add(g.Lease).Unix()),
			"expira": n(agora.Add(g.Reter).Unix()),
		},
		ConditionExpression: aws.String("attribute_not_exists(pk) OR (estado = :andamento AND lease < :agora)"),
		ExpressionAttributeValues: map[string]types.AttributeValue{
			":andamento": &types.AttributeValueMemberS{Value: "EM_ANDAMENTO"},
			":agora":     n(agora.Unix()),
		},
	})
	var dup *types.ConditionalCheckFailedException
	switch {
	case err == nil:
		return true, nil
	case errors.As(err, &dup):
		return false, nil
	default:
		return false, err
	}
}

// Concluir marca a chave como processada (mantida até "expira").
func (g Guarda) Concluir(ctx context.Context, chave string) error {
	_, err := g.DB.UpdateItem(ctx, &dynamodb.UpdateItemInput{
		TableName:        aws.String(g.Tabela),
		Key:              map[string]types.AttributeValue{"pk": &types.AttributeValueMemberS{Value: chave}},
		UpdateExpression: aws.String("SET estado = :ok"),
		ExpressionAttributeValues: map[string]types.AttributeValue{
			":ok": &types.AttributeValueMemberS{Value: "CONCLUIDO"},
		},
	})
	return err
}
```

Teste sem AWS (o SDK aceita um `HTTPClient` falso; o erro condicional vira `false`, e erro de infraestrutura **não** vira "duplicata"):

```go
package idem

import (
	"context"
	"io"
	"net/http"
	"strings"
	"testing"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/credentials"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb"
)

// fakeDynamo responde com o que o DynamoDB real devolveria; assim o teste roda sem rede nem AWS.
type fakeDynamo struct {
	respostas []func() *http.Response
	corpos    []string
}

func (f *fakeDynamo) Do(r *http.Request) (*http.Response, error) {
	b, _ := io.ReadAll(r.Body)
	f.corpos = append(f.corpos, string(b))
	i := len(f.corpos) - 1
	return f.respostas[i](), nil
}

func ok() *http.Response {
	return &http.Response{StatusCode: http.StatusOK, Header: http.Header{"Content-Type": {"application/x-amz-json-1.0"}}, Body: io.NopCloser(strings.NewReader("{}"))}
}

func condicaoFalhou() *http.Response {
	return &http.Response{
		StatusCode: http.StatusBadRequest,
		Header:     http.Header{"Content-Type": {"application/x-amz-json-1.0"}, "X-Amzn-Errortype": {"ConditionalCheckFailedException"}},
		Body: io.NopCloser(strings.NewReader(
			`{"__type":"com.amazonaws.dynamodb.v20120810#ConditionalCheckFailedException","message":"The conditional request failed"}`)),
	}
}

func guarda(f *fakeDynamo) Guarda {
	db := dynamodb.New(dynamodb.Options{
		Region:           "sa-east-1",
		Credentials:      credentials.NewStaticCredentialsProvider("teste", "teste", ""), // valores de teste, nunca reais
		HTTPClient:       f,
		BaseEndpoint:     aws.String("http://dynamo.invalid"),
		RetryMaxAttempts: 1,
	})
	return Guarda{
		DB: db, Tabela: "idem", Lease: time.Minute, Reter: 24 * time.Hour,
		Agora: func() time.Time { return time.Unix(1_800_000_000, 0) },
	}
}

func TestReservar(t *testing.T) {
	f := &fakeDynamo{respostas: []func() *http.Response{ok, condicaoFalhou}}
	g := guarda(f)

	if v, err := g.Reservar(context.Background(), "msg-1"); err != nil || !v {
		t.Fatalf("1ª entrega: v=%v err=%v", v, err)
	}
	if v, err := g.Reservar(context.Background(), "msg-1"); err != nil || v {
		t.Fatalf("duplicata deve devolver false sem erro: v=%v err=%v", v, err)
	}
	if !strings.Contains(f.corpos[0], "attribute_not_exists(pk) OR (estado = :andamento AND lease < :agora)") {
		t.Fatalf("condição ausente no pedido: %s", f.corpos[0])
	}
}

func TestReservar_ErroDeInfraPropaga(t *testing.T) {
	falha := func() *http.Response {
		return &http.Response{StatusCode: http.StatusInternalServerError, Header: http.Header{"X-Amzn-Errortype": {"InternalServerError"}}, Body: io.NopCloser(strings.NewReader(`{"__type":"InternalServerError","message":"x"}`))}
	}
	g := guarda(&fakeDynamo{respostas: []func() *http.Response{falha}})
	if v, err := g.Reservar(context.Background(), "k"); err == nil || v {
		t.Fatalf("erro de infraestrutura NÃO pode virar 'duplicata': v=%v err=%v", v, err)
	}
}

func TestConcluir(t *testing.T) {
	f := &fakeDynamo{respostas: []func() *http.Response{ok}}
	if err := guarda(f).Concluir(context.Background(), "msg-1"); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(f.corpos[0], `"SET estado = :ok"`) || !strings.Contains(f.corpos[0], "CONCLUIDO") {
		t.Fatalf("pedido inesperado: %s", f.corpos[0])
	}
}

func TestAgora_SemRelogioInjetadoUsaOAtual(t *testing.T) {
	antes := time.Now()
	if got := (Guarda{}).agora(); got.Before(antes) || time.Since(got) > time.Second {
		t.Fatalf("agora() = %v", got)
	}
}
```

Ponto de entrada com clientes criados na **inicialização** (`cmd/sqsdyn/main.go`):

```go
package main

import (
	"context"
	"log/slog"
	"os"
	"strconv"
	"time"

	"github.com/aws/aws-lambda-go/events"
	"github.com/aws/aws-lambda-go/lambda"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb"

	"example.com/glam/internal/batch"
	"example.com/glam/internal/idem"
	"example.com/glam/internal/prazo"
)

var (
	log    = slog.New(slog.NewJSONHandler(os.Stdout, nil))
	limite = envInt("CONCORRENCIA", 5)
)

func envInt(k string, def int) int {
	if v, err := strconv.Atoi(os.Getenv(k)); err == nil && v > 0 {
		return v
	}
	return def
}

type app struct{ guarda idem.Guarda }

// processa: reserva a chave → efeito IDEMPOTENTE → conclui.
func (a *app) processa(ctx context.Context, p batch.Pedido) error {
	chave := "pedido:" + p.ID
	primeira, err := a.guarda.Reservar(ctx, chave)
	if err != nil {
		return err // infraestrutura: devolve à fila (tenta de novo)
	}
	if !primeira {
		return nil // duplicata (ou em andamento): sucesso, descarta
	}
	// ... efeito colateral IDEMPOTENTE aqui (UPSERT, escrita condicional) ...
	return a.guarda.Concluir(ctx, chave)
}

func (a *app) handler(ctx context.Context, ev events.SQSEvent) (events.SQSEventResponse, error) {
	r := batch.Handle(ctx, ev, limite, prazo.Margem, a.processa)
	log.InfoContext(ctx, "lote concluído", "recebidas", len(ev.Records), "falhas", len(r.BatchItemFailures))
	return r, nil
}

func main() {
	// Inicialização: roda UMA vez por ambiente de execução; o handler reaproveita os clientes.
	cfg, err := config.LoadDefaultConfig(context.Background()) // credenciais, região e endpoint do ambiente
	if err != nil {
		log.Error("config AWS", "erro", err)
		os.Exit(1) // falha de init: visível no CloudWatch como Init error
	}
	tabela := os.Getenv("TABELA_IDEM")
	if tabela == "" {
		log.Error("variável TABELA_IDEM ausente") // configuração errada: falha na init, não por mensagem
		os.Exit(1)
	}
	a := &app{guarda: idem.Guarda{
		DB:     dynamodb.NewFromConfig(cfg),
		Tabela: tabela,
		Lease:  2 * time.Minute,
		Reter:  24 * time.Hour,
	}}
	lambda.Start(a.handler)
}
```

Observações:

- A chave de idempotência **reduz** duplicatas, mas só um **efeito idempotente** (UPSERT, escrita condicional) garante o resultado:
  se `Concluir` falhar depois do efeito, a reentrega após o lease reexecuta.
- Habilite **TTL** no atributo `expira` da tabela, senão ela cresce para sempre. `ttl` é palavra reservada no DynamoDB — por isso o nome.
- `lease` > pior caso de processar **uma** mensagem; `reter` ≥ janela em que o SQS pode reentregar (cobre a retenção da fila).
- Nesta skill o código com DynamoDB foi verificado com **cliente HTTP falso** (compila, passa em teste); não foi executado contra o
  DynamoDB real nem contra LocalStack — faça o teste de integração no seu ambiente.
- Credenciais, região e endpoint (LocalStack: `AWS_ENDPOINT_URL`) vêm do ambiente via `config.LoadDefaultConfig`; nunca no código.

## 7. API Gateway HTTP API (payload v2)

`cmd/http/main.go`:

```go
package main

import (
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"strings"

	"github.com/aws/aws-lambda-go/events"
	"github.com/aws/aws-lambda-go/lambda"
)

func resp(status int, v any) (events.APIGatewayV2HTTPResponse, error) {
	b, err := json.Marshal(v)
	if err != nil {
		// Erro de programação (tipo não serializável): registra e responde 500 em vez de 502 do API Gateway.
		slog.Error("serializar resposta", "erro", err)
		return events.APIGatewayV2HTTPResponse{StatusCode: http.StatusInternalServerError, Body: `{"erro":"interno"}`}, nil
	}
	return events.APIGatewayV2HTTPResponse{
		StatusCode: status,
		Headers:    map[string]string{"Content-Type": "application/json", "X-Content-Type-Options": "nosniff"},
		Body:       string(b),
	}, nil
}

// handler atende HTTP API (payload v2): GET /pedidos/{id}
func handler(_ context.Context, req events.APIGatewayV2HTTPRequest) (events.APIGatewayV2HTTPResponse, error) {
	if req.RequestContext.HTTP.Method != http.MethodGet || !strings.HasPrefix(req.RawPath, "/pedidos/") {
		return resp(http.StatusNotFound, map[string]string{"erro": "não encontrado"})
	}
	id := req.PathParameters["id"]
	if id == "" || len(id) > 64 { // entrada externa: valide sempre
		return resp(http.StatusBadRequest, map[string]string{"erro": "id inválido"})
	}
	return resp(http.StatusOK, map[string]any{"id": id, "status": "pago"})
}

func main() { lambda.Start(handler) }
```

- Valide **toda** entrada (`PathParameters`, query, corpo): tamanho, formato, lista de valores aceitos. Corpo pode vir em base64
  (`IsBase64Encoded`) — decodifique antes de interpretar.
- Responda erro de negócio como **resposta** com status 4xx (como acima), não como `error` — um `error` não tratado vira 5xx genérico
  e perde a mensagem.
- Cabeçalhos de segurança mínimos (`X-Content-Type-Options`); não devolva detalhes internos de erro ao cliente; autenticação no
  próprio API Gateway (JWT/IAM) em vez de código próprio.
- Roteamento simples por `RouteKey`/método; só adote roteador se houver muitas rotas (P1).

## 8. Build e tamanho do pacote

```bash
CGO_ENABLED=0 GOOS=linux GOARCH=arm64 \
  go build -tags lambda.norpc -trimpath -ldflags="-s -w" -o bootstrap ./cmd/sqs
file bootstrap                      # ELF 64-bit ... ARM aarch64 ... statically linked
zip bootstrap.zip bootstrap         # o executável chama-se "bootstrap" e fica na RAIZ do zip
```

Passe `-tags`, `-trimpath` e `-ldflags` na linha de comando (valores com espaço em `GOFLAGS` quebram o build).

Medido no handler SQS de exemplo (sem SDK de serviço), Go 1.24.13, `aws-lambda-go` v1.54.0, 2026-10-28 (MB = 10⁶ bytes):

| Variante | Tamanho |
|---|---|
| padrão (RPC embutido, com símbolos) — x86_64 | 11,81 MB |
| `-tags lambda.norpc` — x86_64 | 9,04 MB |
| `-tags lambda.norpc` + `-s -w` — x86_64 | 6,10 MB |
| **igual à anterior, `GOARCH=arm64`** | **5,70 MB** (2,33 MB zipado) |
| `cmd/sqsdyn` (com `aws-sdk-go-v2` + DynamoDB), arm64, `norpc`, `-s -w` | 9,24 MB (3,42 MB zipado) |
| `cmd/sqsdyn` com `GOFIPS140=v1.0.0` (módulo criptográfico FIPS 140-3, §12) | 9,31 MB |
| `cmd/http`, `cmd/streamurl`, `cmd/kinesis` (arm64, `norpc`, `-s -w`) | 5,70 / 5,64 / 5,77 MB |

Com o mesmo código, os binários do Go 1.27.3 + `aws-lambda-go` v1.55.1 mediram 6,36 MB (`sqs`) e 9,90 MB (`sqsdyn`): a versão
mais nova **não** deixa o pacote menor — o que pesa é o SDK de serviço que você importa.

Importe só os clientes que usa; cada serviço do SDK soma ao binário. `-ldflags` com `-s -w` remove símbolos/DWARF (stack traces
continuam com nomes de função).

## 9. Prazo, memória e armadilhas

- **Deadline:** o `ctx` do `aws-lambda-go` expira **exatamente** no prazo da invocação — quando `ctx.Err()` aparece, já é tarde
  para responder. Trabalhe em `prazo.ComMargem(ctx, prazo.Margem)` (≈ 500 ms antes) e propague esse contexto a toda chamada externa
  (SDK, banco, HTTP); a margem é o tempo de montar e enviar a resposta (parcial).
- **Ambiente congelado:** goroutines em segundo plano **param** quando a invocação retorna e retomam (ou somem) na próxima. Termine
  o trabalho antes de devolver; não use "fire and forget".
- **`init` e `main`:** falha na inicialização (`os.Exit(1)`, pânico) aparece como erro de **Init** (e o tempo de init é cobrado); faça trabalho caro
  (credenciais, TLS, pool) ali **uma vez**, não por invocação — mas sem bloquear em dependência lenta sem timeout.
- **Memória do Go:** o GC reage à pressão; se `Max Memory Used` (linha `REPORT`) encostar no limite, avalie `GOMEMLIMIT` — **meça antes**,
  não há valor mágico (→ **go-performance-engineer**).
- **`/tmp`:** persiste entre invocações do mesmo ambiente; trate como cache descartável e limpe o que criar.
- **Segredos:** leia do Secrets Manager/SSM na inicialização (com cache e expiração), não de variável de ambiente em claro; nunca logue.
- **Evite:** `log.Fatal`/`os.Exit` dentro do handler; estado global mutável sem sincronização (o ambiente atende uma invocação por
  vez, mas as goroutines do seu lote não); cliente criado por invocação.

## 10. Build no Windows (PowerShell)

O `bootstrap` precisa chegar ao Lambda como **executável Unix**. Um `.zip` feito no Windows (ex.: `Compress-Archive`) não
grava o bit de execução — a função falha na inicialização. A documentação da AWS indica o `build-lambda-zip`, do próprio
`aws-lambda-go`; conferido no fonte (v1.54.0 e v1.55.1): ele grava o arquivo com atributos Unix e permissão `0777`, e, se o executável tiver
outro nome, acrescenta um link simbólico `bootstrap` apontando para ele (verificado inspecionando o zip gerado).

```powershell
# build-lambda-zip já é ferramenta do módulo (diretiva `tool` do Go 1.24): versão travada no go.sum, sem go install
$env:GOOS = "linux"; $env:GOARCH = "arm64"; $env:CGO_ENABLED = "0"
go build -tags lambda.norpc -trimpath -ldflags="-s -w" -o bootstrap ./cmd/sqs
Remove-Item Env:GOOS, Env:GOARCH, Env:CGO_ENABLED   # a ferramenta roda no Windows; e o próximo `go test` não compila para Linux
go tool build-lambda-zip -o sqs.zip bootstrap
```

- No `cmd.exe` o equivalente é `set GOOS=linux` etc. (mesma sequência). As variáveis valem para a sessão inteira — limpe-as.
- `sam build` com `BuildMethod: makefile` exige `make` no PATH; no Windows a alternativa é `BuildMethod: go1.x` (a doc da AWS a mostra
  para `provided.al2023`) ou rodar o build no WSL/CI Linux. O PowerShell acima **não** foi executado aqui (só o `build-lambda-zip`, no
  Linux); confirme no seu Windows.
- Testes locais (`go test`, Runtime API simulado) rodam com o `GOOS` do host — compile o `bootstrap` de teste **sem** `GOOS=linux`.

## 11. Gates

Ordem barata → cara; o script roda com `bash -e` (como o `run` do GitHub Actions) e cada linha precisa sair 0 — exceto o
`govulncheck`, que com Go 1.24 reprova (§13). Verificado no lab em 2026-10-28: tudo verde até o `govulncheck` (saída 3, 28 achados).
Critérios e a explicação de cada comando: `clean-code-go.md` §5.

```bash
set -euo pipefail
export GOTOOLCHAIN=go1.24.13                 # FIXO: o `toolchain` do go.mod é mínimo; `auto` usaria um Go mais novo instalado
test "$(go env GOVERSION)" = go1.24.13
test -z "$(gofmt -l .)"                      # formatação
go vet ./...
go tool staticcheck ./...                    # obrigatório: staticcheck 2025.1.1 travado no go.mod (diretiva tool)
golangci-lint run ./...                      # binário oficial v2 mais recente + .golangci.yml canônico (S3776/S1541/S107)
rc=0; grep -rnE --include='*.go' -e '//[[:space:]]*nolint' -e '//[[:space:]]*lint:(file-)?ignore' -e '#nosec' -e 'NOSONAR' . || rc=$?; test "$rc" -eq 1
go test -race -count=1 ./...
go test -count=1 -coverprofile=cover.out ./internal/...
go tool cover -func=cover.out | awk '/^total:/ { sub("%", "", $3); exit !($3 + 0 >= 97) }'   # regra de negócio ≥ 97 %
GOEXPERIMENT=synctest go test -count=1 ./internal/prazo   # o teste com relógio falso só compila com o experimento
D=$(mktemp -d) && make -s build-ProcessadorPedidos ARTIFACTS_DIR="$D" && file "$D/bootstrap" | grep -q 'ARM aarch64'
go tool govulncheck ./...                    # com Go 1.24 REPROVA: ver §13 — não silencie
```

## 12. Go 1.24 na prática (cada item compilado e testado no lab)

O padrão desta skill é `go 1.24.3` no `go.mod` com `toolchain go1.24.13`. Atenção ao que `toolchain` significa: é o **mínimo**.
Com Go 1.24.x mais antigo instalado, `GOTOOLCHAIN=auto` (o padrão) baixa o 1.24.13; mas com um Go **mais novo** instalado (1.26,
1.27) o `auto` usa o mais novo — e aí um `sync.WaitGroup.Go` (1.25+) **compila** num módulo `go 1.24.3` (só o `go vet` acusa:
"requires go1.25 or later") e o `govulncheck` v1.1.4 quebra. Verificado: com `go1.27.3` o build passou; com `go1.24.13`,
`wg.Go undefined`. Por isso o build, o CI e o `Makefile` **fixam** o toolchain:

```bash
export GOTOOLCHAIN=go1.24.13                       # fixo: nunca o Go mais novo da máquina
test "$(go env GOVERSION)" = go1.24.13             # guarda no CI: falha se alguém mudar o ambiente
```

**Não** use nada do 1.25+ (`sync.WaitGroup.Go`, `synctest.Test`, `GOMAXPROCS` ciente de cgroup, `errors.AsType`, `new(expr)`) —
com o toolchain fixo o build quebra, que é o que se quer.

**Ferramentas como dependência do módulo (`tool`).** Versão travada no `go.sum`, a mesma para todo o time e para o CI:

```text
go get -tool honnef.co/go/tools/cmd/staticcheck@v0.6.1       # staticcheck 2025.1.1 (a v0.7+ exige Go 1.25)
go get -tool golang.org/x/vuln/cmd/govulncheck@v1.1.4        # a v1.2+ exige Go 1.25
go get -tool github.com/aws/aws-lambda-go/cmd/build-lambda-zip@v1.54.0
go tool staticcheck ./...  ·  go tool govulncheck ./...  ·  go tool build-lambda-zip -o f.zip bootstrap
```

O `golangci-lint` fica **fora** do `tool` (a documentação dele desaconselha: as dependências do linter entrariam no grafo do seu
módulo). Use o **binário oficial da v2 mais recente** (verificado: v2.15.0 analisa este lab em Go 1.24 com o mesmo resultado — 0
achados no lab, 17 no exemplo ruim). Só se você precisa **compilar** o linter com Go 1.24, use
`go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@v2.8.0` (a v2.9+ exige 1.25 para compilar).

**`/tmp` com nome hostil: validar o nome **e** usar `os.Root`.** No Go 1.24 o `os.Root` **não é fronteira de segurança**: o
`govulncheck` acha alcançáveis neste lab a **GO-2026-4970** (escape da raiz por link simbólico + barra final — corrigida só no
1.25.12) e a **GO-2026-4602** (`FileInfo` escapa — corrigida no 1.25.8). Reproduzido: com `go1.24.13`, `root.Open("atalho/")`
(onde `atalho` é link para fora) **abriu e listou** o diretório de fora; com `go1.27.3`, "path escapes from parent". Então o nome é
validado **antes** — um único componente local, sem nenhuma `/` (`nome == filepath.Base(nome) && filepath.IsLocal(nome)`) — e o
`os.Root` fica como segunda camada (barra `../`, absoluto e link para fora):

`internal/tmpfs/tmpfs.go`:

```go
// Package tmpfs grava arquivos temporários num diretório sem deixar o nome escapar dele.
//
// Nome vindo do evento (chave S3, id) é entrada hostil. Duas camadas, porque no Go 1.24 o os.Root
// NÃO é fronteira de segurança: GO-2026-4970 (escape por link simbólico + barra final, corrigida só no
// 1.25.12) e GO-2026-4602 (FileInfo escapa, corrigida no 1.25.8) seguem abertas em toda a linha 1.24.
//  1. o nome é validado ANTES: um componente só, local, sem nenhuma "/" (nem final);
//  2. o os.Root ainda recusa "../", caminho absoluto e link para fora — defesa extra, não a única.
package tmpfs

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// ErrNomeInvalido marca nome que não é um único componente local (barra, "..", absoluto, vazio).
var ErrNomeInvalido = errors.New("nome de arquivo inválido")

// Grava cria (ou trunca) dir/nome com dados, sem sair de dir.
func Grava(dir, nome string, dados []byte) error {
	if !nomeSeguro(nome) {
		return fmt.Errorf("%w: %q", ErrNomeInvalido, nome)
	}
	raiz, err := os.OpenRoot(dir)
	if err != nil {
		return fmt.Errorf("abrir raiz %q: %w", dir, err)
	}
	defer func() { _ = raiz.Close() }() // o que importa é o Close do arquivo, conferido abaixo

	f, err := raiz.Create(nome)
	if err != nil {
		return fmt.Errorf("criar %q: %w", nome, err)
	}
	_, errEscrita := f.Write(dados)
	if err := errors.Join(errEscrita, f.Close()); err != nil { // fecha sempre; devolve os dois erros, se houver
		return fmt.Errorf("gravar %q: %w", nome, err)
	}
	return nil
}

// nomeSeguro aceita só um componente local: "a.csv" sim; "a/", "x/y", "../a", "/a", "" não.
func nomeSeguro(nome string) bool {
	return nome == filepath.Base(nome) && filepath.IsLocal(nome) && !strings.ContainsRune(nome, '/')
}
```

`internal/tmpfs/tmpfs_test.go`:

```go
package tmpfs

import (
	"errors"
	"os"
	"path/filepath"
	"testing"
)

func TestGrava(t *testing.T) {
	dir := t.TempDir()
	fora := t.TempDir()
	if err := os.Symlink(fora, filepath.Join(dir, "atalho")); err != nil {
		t.Fatal(err)
	}
	casos := []struct {
		nome      string
		aceito    bool
		validacao bool // recusado já pela validação do nome (e não só pelo os.Root)
	}{
		{"relatorio.csv", true, false},
		{"../fora.csv", false, true}, // sobe de diretório
		{"/etc/passwd", false, true}, // caminho absoluto
		{"atalho/", false, true},     // link + barra final: no Go 1.24 o os.Root deixa escapar (GO-2026-4970)
		{"sub/arquivo", false, true}, // mais de um componente
		{"", false, true},            // vazio
		{"atalho", false, false},     // link para fora: barrado pelo os.Root
	}
	for _, c := range casos {
		t.Run(c.nome, func(t *testing.T) {
			err := Grava(dir, c.nome, []byte("x"))
			if (err == nil) != c.aceito {
				t.Fatalf("Grava(%q) err=%v, aceito esperado=%v", c.nome, err, c.aceito)
			}
			if c.validacao && !errors.Is(err, ErrNomeInvalido) {
				t.Fatalf("Grava(%q) deveria ser barrado pela validação do nome: %v", c.nome, err)
			}
		})
	}
	if entradas, _ := os.ReadDir(fora); len(entradas) != 0 {
		t.Fatalf("a escrita escapou da raiz: %v", entradas)
	}
}

func TestGrava_ErrosDeSistemaDeArquivos(t *testing.T) {
	if err := Grava(filepath.Join(t.TempDir(), "nao-existe"), "a.csv", nil); err == nil {
		t.Fatal("diretório inexistente deveria falhar")
	}
	dir := t.TempDir()
	if err := os.Mkdir(filepath.Join(dir, "pasta"), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := Grava(dir, "pasta", []byte("x")); err == nil || errors.Is(err, ErrNomeInvalido) {
		t.Fatalf("criar arquivo por cima de diretório deveria falhar no sistema de arquivos: %v", err)
	}
}
```

O caso `{"atalho/", false}` do teste é o da GO-2026-4970: sem a validação, ele passaria pelo `os.Root` do 1.24. (No 1.24 o `os.Root`
tem `Create`, `Open`, `OpenFile`, `Mkdir`, `Remove`, `Stat`; `WriteFile`/`ReadFile` no `Root` só chegam no 1.25.)

**`omitzero` e alias genérico.** `omitempty` não omite `time.Time{}` nem struct vazia; `omitzero` omite o valor zero do tipo:

`internal/resposta/resposta.go`:

```go
// Package resposta define o corpo das respostas HTTP. Go 1.24: a tag `omitzero` omite o valor ZERO do tipo
// (inclusive time.Time{} e structs), o que `omitempty` não faz.
package resposta

import "time"

// Pedido é a resposta de GET /pedidos/{id}.
type Pedido struct {
	ID     string    `json:"id"`
	Valor  int64     `json:"valor"`
	PagoEm time.Time `json:"pagoEm,omitzero"` // ausente enquanto não pago (omitempty mandaria "0001-01-01T00:00:00Z")
}

// Conjunto é um alias genérico (Go 1.24): mesmo tipo que map[K]struct{}, com nome que diz a intenção.
type Conjunto[K comparable] = map[K]struct{}
```

`internal/resposta/resposta_test.go`:

```go
package resposta

import (
	"encoding/json"
	"testing"
	"time"
)

func TestPedido_OmitZero(t *testing.T) {
	casos := []struct {
		nome string
		p    Pedido
		quer string
	}{
		{"não pago", Pedido{ID: "a", Valor: 100}, `{"id":"a","valor":100}`},
		{
			"pago",
			Pedido{ID: "a", Valor: 100, PagoEm: time.Date(2026, 10, 28, 12, 0, 0, 0, time.UTC)},
			`{"id":"a","valor":100,"pagoEm":"2026-10-28T12:00:00Z"}`,
		},
	}
	for _, c := range casos {
		t.Run(c.nome, func(t *testing.T) {
			b, err := json.Marshal(c.p)
			if err != nil {
				t.Fatal(err)
			}
			if string(b) != c.quer {
				t.Fatalf("got %s, want %s", b, c.quer)
			}
		})
	}
}

func TestConjunto_EhUmMap(t *testing.T) {
	vistos := Conjunto[string]{"m1": {}}
	if tamanho(vistos) != 1 { // alias: passa onde se espera o map, sem conversão
		t.Fatal("alias deveria ser o próprio map")
	}
}

func tamanho(m map[string]struct{}) int { return len(m) }
```

**`b.Loop()` em benchmark** (no fim de `internal/batch/batch_test.go`, acima): o setup antes do laço não entra na medida e a chamada
não é eliminada pelo compilador. Medido: `BenchmarkHandle` ≈ 11,3 µs/op, 2.272 B/op, 42 allocs/op (x86_64, 2 vCPUs; indicativo).

**`testing/synctest` (experimental no 1.24).** Só compila com `GOEXPERIMENT=synctest`; dentro de `synctest.Run`, `time.Sleep` e
timers usam relógio falso — o teste de prazo de 2 s roda em 0,00 s. No 1.25 a API muda (`synctest.Test`): por isso o arquivo tem
build tag e o CI comum continua verde sem o experimento.

`internal/prazo/prazo_synctest_test.go`:

```go
//go:build goexperiment.synctest

// Go 1.24: testing/synctest é EXPERIMENTAL — só compila com GOEXPERIMENT=synctest (no 1.25 a API muda para
// synctest.Test). Dentro da "bolha", time.Sleep e timers usam um relógio falso: o teste de prazo de 2 s roda
// em microssegundos e sem flakiness.
package prazo

import (
	"context"
	"errors"
	"testing"
	"testing/synctest"
	"time"
)

func TestExecuta_PrazoComRelogioFalso(t *testing.T) {
	synctest.Run(func() {
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		defer cancel()
		trabalho, c2 := ComMargem(ctx, Margem)
		defer c2()
		ini := time.Now()
		err := Executa(trabalho, func() error { time.Sleep(time.Hour); return nil })
		if !errors.Is(err, context.DeadlineExceeded) {
			t.Fatalf("err = %v", err)
		}
		if d := time.Since(ini); d != 2*time.Second-Margem {
			t.Fatalf("respondeu em %v (relógio falso), queria %v", d, 2*time.Second-Margem)
		}
	})
}
```

```bash
GOEXPERIMENT=synctest go test -count=1 ./internal/prazo   # roda TAMBÉM no gate (§11): sem o experimento o arquivo nem compila
```

**FIPS 140-3 (`GOFIPS140`).** Ambiente regulado (banco, governo) que exige módulo criptográfico FIPS: compile com
`GOFIPS140=v1.0.0` — o binário passa a usar o Go Cryptographic Module v1.0.0 e já sai com `DefaultGODEBUG=fips140=on`
(verificado com `go version -m`); o pacote cresce ≈ 70 KB (9,24 → 9,31 MB no `sqsdyn`). A situação da validação CMVP do módulo
deve ser conferida no NIST antes de afirmar conformidade; a decisão é de **engenheiro-seguranca**.

**Ganho grátis do 1.24** (sem mudar código): mapas com Swiss Tables e alocação de objetos pequenos mais eficiente, segundo as notas
de versão — meça o seu caso (`REPORT`, `pprof`) antes de prometer número.

## 13. Fim de suporte e vulnerabilidades — leia antes de entregar

- O Go mantém as **duas** últimas versões principais. Em 2026-10-28 são a **1.27** (1.27.3) e a **1.26**; a 1.24 está **fora de
  suporte** desde o lançamento da 1.26 — não recebe mais correção de segurança.
- `govulncheck` no código deste lab, medido em 2026-10-28: **44** vulnerabilidades da biblioteca padrão **alcançáveis** com
  `go1.24.3` e **28** com `go1.24.13` — **o número só cresce** (horas antes, no mesmo dia, eram 42 e 26): cada correção nova sai só
  para 1.26/1.27. O último patch reduz, não zera: o resto foi corrigido em 1.25.x/1.26.x — `net/http`, `crypto/tls`, `crypto/x509`,
  `net/url`, `encoding/xml` e o próprio `os.Root` (**GO-2026-4970**, **GO-2026-4602**). Por isso `toolchain go1.24.13` é o mínimo
  aceitável dentro da linha 1.24.
- O gate **não** é silenciado: com Go 1.24 o `govulncheck` reprova (código de saída 3). Entregar assim exige **aceite de risco explícito do dono**
  (registrado, com prazo) e revisão do **engenheiro-seguranca** — o risco é maior em função exposta a HTTP/TLS.
- Como subir quando o projeto permitir (uma mudança, testada):
  1. `go mod edit -go=1.26 -toolchain=go1.27.3` (ou `-go=1.27`), `go get github.com/aws/aws-lambda-go@v1.55.1`, `go mod tidy`, e
     troque o `GOTOOLCHAIN` fixo (Makefile e CI) pela versão nova;
  2. atualize as ferramentas (`go get -tool honnef.co/go/tools/cmd/staticcheck@latest golang.org/x/vuln/cmd/govulncheck@latest`) e o
     `golangci-lint` para a última v2;
  3. rode os gates (§11) — o `govulncheck` deve sair limpo; publique versão nova e desloque o alias aos poucos.
- O que a v1.55 do `aws-lambda-go` traz e a v1.54 não tem (conferido no diff do fonte): o cliente do Runtime/Extensions API passa a
  **ignorar `HTTP_PROXY`/`HTTPS_PROXY`** do ambiente (na v1.54 o transporte padrão respeita essas variáveis; o Go já não usa proxy
  para `127.0.0.1`, o endereço do Runtime API no Lambda, mas se você define proxy na função, inclua `NO_PROXY=127.0.0.1`); o campo
  `UserNotFound` nos eventos de gatilho do Cognito; e a troca de `io/ioutil` por `io`/`os`. Nada mais do que esta skill usa mudou.
