# Fontes de eventos além de SQS/HTTP — Go no AWS Lambda

> Verificado em 2026-10-28 com o padrão da skill (`go 1.24.3` + `toolchain go1.24.13`, `aws-lambda-go` v1.54.0): os pacotes abaixo
> passam em `go vet`, `staticcheck`, `golangci-lint` (gate da Squad, 0 achados), `go test -race`, e cada `bootstrap` foi executado contra o Runtime API simulado (`iac-e-teste-local.md` §3) com os eventos de
> exemplo — as respostas citadas são as **observadas**. Semântica de cada fonte conferida na documentação da AWS (datas na skill).

## 1. Kinesis Data Streams e DynamoDB Streams — falha parcial **ordenada**

Diferente do SQS: em stream o Lambda faz *checkpoint* por número de sequência. Com `ReportBatchItemFailures`, se a lista tiver vários
itens o Lambda usa o **menor** número de sequência como checkpoint e reprocessa **tudo a partir dele**. Logo, processe **em ordem** e
**pare na primeira falha**, devolvendo só o `sequenceNumber` dela. Lista vazia/nula = sucesso total; `itemIdentifier` vazio/nulo ou chave
com nome errado = falha do lote inteiro. Os tipos de resposta estão no pacote `events` (`streams.go`): `KinesisEventResponse` /
`KinesisBatchItemFailure` e `DynamoDBEventResponse` / `DynamoDBBatchItemFailure`.

`internal/stream/stream.go` (genérico — o mesmo laço serve às duas fontes):

```go
// Package stream processa lotes de Kinesis Data Streams e DynamoDB Streams EM ORDEM, com falha parcial.
//
// Em streams o Lambda faz checkpoint pelo número de sequência: com ReportBatchItemFailures ele usa o MENOR
// número devolvido como checkpoint e reprocessa tudo a partir dele. Por isso processamos em ordem e paramos
// na 1ª falha, devolvendo só o número de sequência dela (o que vem depois será reentregue de qualquer forma).
package stream

import (
	"context"
	"time"

	"github.com/aws/aws-lambda-go/events"

	"example.com/glam/internal/prazo"
)

// Ordenado processa regs em ordem e devolve o número de sequência do 1º que falhou ("" = todos ok).
// Erro, pânico e prazo esgotado (margem antes do deadline da invocação) contam como falha daquele registro.
func Ordenado[T any](ctx context.Context, regs []T, margem time.Duration, seq func(T) string, proc func(context.Context, T) error) string {
	trabalho, cancel := prazo.ComMargem(ctx, margem)
	defer cancel()
	for _, r := range regs {
		if prazo.Executa(trabalho, func() error { return proc(trabalho, r) }) != nil {
			return seq(r)
		}
	}
	return ""
}

// HandleKinesis devolve a resposta parcial do Kinesis (lista vazia = sucesso total).
func HandleKinesis(ctx context.Context, ev events.KinesisEvent, margem time.Duration, proc func(context.Context, events.KinesisEventRecord) error) events.KinesisEventResponse {
	falha := []events.KinesisBatchItemFailure{}
	if s := Ordenado(ctx, ev.Records, margem, func(r events.KinesisEventRecord) string { return r.Kinesis.SequenceNumber }, proc); s != "" {
		falha = append(falha, events.KinesisBatchItemFailure{ItemIdentifier: s})
	}
	return events.KinesisEventResponse{BatchItemFailures: falha}
}

// HandleDynamoDB devolve a resposta parcial do DynamoDB Streams (lista vazia = sucesso total).
func HandleDynamoDB(ctx context.Context, ev events.DynamoDBEvent, margem time.Duration, proc func(context.Context, events.DynamoDBEventRecord) error) events.DynamoDBEventResponse {
	falha := []events.DynamoDBBatchItemFailure{}
	if s := Ordenado(ctx, ev.Records, margem, func(r events.DynamoDBEventRecord) string { return r.Change.SequenceNumber }, proc); s != "" {
		falha = append(falha, events.DynamoDBBatchItemFailure{ItemIdentifier: s})
	}
	return events.DynamoDBEventResponse{BatchItemFailures: falha}
}
```

Testes (`internal/stream/stream_test.go`) — o evento Kinesis é desserializado de JSON real, com `data` em base64 (o pacote `events`
já entrega `Kinesis.Data` decodificado como `[]byte`):

```go
package stream

import (
	"context"
	"encoding/json"
	"errors"
	"testing"
	"time"

	"github.com/aws/aws-lambda-go/events"
)

// kinesis monta o evento a partir de JSON real (data em base64), como o Lambda entrega.
func kinesis(t *testing.T) events.KinesisEvent {
	t.Helper()
	raw := `{"Records":[
	 {"kinesis":{"sequenceNumber":"100","partitionKey":"p","data":"eyJpZCI6ImEifQ=="}},
	 {"kinesis":{"sequenceNumber":"101","partitionKey":"p","data":"eyJpZCI6ImZhbGhhIn0="}},
	 {"kinesis":{"sequenceNumber":"102","partitionKey":"p","data":"eyJpZCI6ImMifQ=="}}]}`
	var ev events.KinesisEvent
	if err := json.Unmarshal([]byte(raw), &ev); err != nil {
		t.Fatal(err)
	}
	return ev
}

func TestHandleKinesis_ParaNaPrimeiraFalhaEDevolveSoEla(t *testing.T) {
	var vistos []string
	proc := func(_ context.Context, r events.KinesisEventRecord) error {
		var p struct{ ID string }
		if err := json.Unmarshal(r.Kinesis.Data, &p); err != nil { // Data já vem decodificado do base64
			return err
		}
		vistos = append(vistos, p.ID)
		if p.ID == "falha" {
			return errors.New("fora do ar")
		}
		return nil
	}
	resp := HandleKinesis(context.Background(), kinesis(t), 0, proc)
	if len(resp.BatchItemFailures) != 1 || resp.BatchItemFailures[0].ItemIdentifier != "101" {
		t.Fatalf("resposta = %+v, quer só o 101", resp)
	}
	if len(vistos) != 2 {
		t.Fatalf("processados = %v: nada depois da falha pode rodar", vistos)
	}
}

func TestHandleKinesis_SucessoSerializaListaVazia(t *testing.T) {
	resp := HandleKinesis(context.Background(), kinesis(t), 0, func(context.Context, events.KinesisEventRecord) error { return nil })
	b, _ := json.Marshal(resp)
	if string(b) != `{"batchItemFailures":[]}` {
		t.Fatalf("json = %s", b)
	}
}

func TestHandleDynamoDB_PanicoEPrazo(t *testing.T) {
	ev := events.DynamoDBEvent{Records: []events.DynamoDBEventRecord{
		{Change: events.DynamoDBStreamRecord{SequenceNumber: "1"}},
		{Change: events.DynamoDBStreamRecord{SequenceNumber: "2"}},
	}}
	resp := HandleDynamoDB(context.Background(), ev, 0, func(_ context.Context, r events.DynamoDBEventRecord) error {
		if r.Change.SequenceNumber == "2" {
			panic("boom")
		}
		return nil
	})
	if got := resp.BatchItemFailures; len(got) != 1 || got[0].ItemIdentifier != "2" {
		t.Fatalf("pânico: %+v", got)
	}
	// Deadline real de 600 ms com margem de 500 ms: 100 ms de trabalho; cada registro leva 80 ms.
	ctx, cancel := context.WithTimeout(context.Background(), 600*time.Millisecond)
	defer cancel()
	resp = HandleDynamoDB(ctx, ev, 500*time.Millisecond, func(ctx context.Context, _ events.DynamoDBEventRecord) error {
		select {
		case <-time.After(80 * time.Millisecond):
			return nil
		case <-ctx.Done():
			return ctx.Err()
		}
	})
	if got := resp.BatchItemFailures; len(got) != 1 || got[0].ItemIdentifier != "2" {
		t.Fatalf("sem tempo para o 2º: %+v", got)
	}
}
```

Pontos de entrada (`cmd/kinesis/main.go` e `cmd/ddbstream/main.go`):

```go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"

	"github.com/aws/aws-lambda-go/events"
	"github.com/aws/aws-lambda-go/lambda"

	"example.com/glam/internal/prazo"
	"example.com/glam/internal/stream"
)

var log = slog.New(slog.NewJSONHandler(os.Stdout, nil))

type leitura struct {
	Sensor string  `json:"sensor"`
	Valor  float64 `json:"valor"`
}

func processa(ctx context.Context, r events.KinesisEventRecord) error {
	var l leitura
	if err := json.Unmarshal(r.Kinesis.Data, &l); err != nil || l.Sensor == "" {
		// Atenção: em stream, um registro que NUNCA passa trava o shard até MaximumRecordAgeInSeconds /
		// MaximumRetryAttempts mandarem o lote para o destino de falha. Valide cedo e configure os dois limites.
		return fmt.Errorf("registro inválido (seq %s)", r.Kinesis.SequenceNumber)
	}
	log.InfoContext(ctx, "leitura", "sensor", l.Sensor)
	return nil
}

func handler(ctx context.Context, ev events.KinesisEvent) (events.KinesisEventResponse, error) {
	return stream.HandleKinesis(ctx, ev, prazo.Margem, processa), nil
}

func main() { lambda.Start(handler) }
```

```go
package main

import (
	"context"
	"fmt"
	"log/slog"
	"os"

	"github.com/aws/aws-lambda-go/events"
	"github.com/aws/aws-lambda-go/lambda"

	"example.com/glam/internal/prazo"
	"example.com/glam/internal/stream"
)

var log = slog.New(slog.NewJSONHandler(os.Stdout, nil))

func processa(ctx context.Context, r events.DynamoDBEventRecord) error {
	// r.EventName: INSERT | MODIFY | REMOVE. NewImage/OldImage só vêm conforme o StreamViewType da tabela.
	// String() entra em pânico se o atributo não for do tipo S: confira o tipo antes.
	av, ok := r.Change.Keys["pk"]
	if !ok || av.DataType() != events.DataTypeString {
		return fmt.Errorf("chave pk ausente ou não-string (seq %s)", r.Change.SequenceNumber)
	}
	log.InfoContext(ctx, "mudança", "evento", r.EventName, "pk", av.String())
	return nil
}

func handler(ctx context.Context, ev events.DynamoDBEvent) (events.DynamoDBEventResponse, error) {
	return stream.HandleDynamoDB(ctx, ev, prazo.Margem, processa), nil
}

func main() { lambda.Start(handler) }
```

Observado no simulador: Kinesis com o 2º registro inválido → `{"batchItemFailures":[{"itemIdentifier":"4960"}]}` (o 3º não é
processado); DynamoDB com `pk` numérica no 2º registro → `{"batchItemFailures":[{"itemIdentifier":"112"}]}`.

Configuração que acompanha (na event source mapping; padrões conferidos na referência da API `CreateEventSourceMapping`):

- `MaximumRetryAttempts` e `MaximumRecordAgeInSeconds` têm padrão **-1 (infinito)**: um registro que nunca passa **trava o shard** até
  expirar na origem. Defina os dois (a idade mínima válida é 60 s) e um destino `OnFailure` (SQS/SNS/S3) para o que for descartado.
- `BisectBatchOnFunctionError: true` divide o lote quando a função **devolve erro**; com resposta parcial + bissecção, o Lambda divide no
  número de sequência devolvido e retenta só o restante.
- `ParallelizationFactor` (1–10, padrão 1) processa vários lotes por shard em paralelo — a ordem continua garantida **por chave de
  partição**, não no shard inteiro.
- Janela de agrupamento: a regra "`BatchSize` > 10 exige `MaximumBatchingWindowInSeconds` ≥ 1" é do **SQS** (referência do
  CloudFormation). A referência da API `CreateEventSourceMapping` também cita Kinesis e DynamoDB, mas o padrão do Kinesis é `BatchSize`
  100 com janela 0 (`services-kinesis-parameters`) — em stream, a janela é escolha de custo × latência, não obrigação.
- Concorrência por semáforo **não** se aplica aqui: paralelizar dentro do lote quebra a ordem. Para mais vazão, use
  `ParallelizationFactor` ou mais shards.
- Idempotência continua obrigatória (uma retentativa reprocessa registros que já tinham passado).

## 2. S3 — chave URL-encoded, entrega assíncrona

A documentação do S3: "o valor do nome da chave do objeto é URL-encoded" — `red flower.jpg` chega como `red+flower.jpg`. O
`aws-lambda-go` decodifica para você no `UnmarshalJSON` de `S3Object` (via `url.QueryUnescape`) e expõe o resultado em
`Object.URLDecodedKey`: use esse campo, não `Object.Key`.

```go
// Package objetos extrai e valida os objetos de um evento do S3.
package objetos

import (
	"errors"
	"fmt"
	"strings"

	"github.com/aws/aws-lambda-go/events"
)

// Objeto é o que o handler precisa: bucket, chave JÁ decodificada e o sequencer (ordem por chave).
type Objeto struct {
	Bucket, Chave, VersionID, Sequencer string
	Tamanho                             int64
}

// ErrForaDoPrefixo marca chave fora do prefixo esperado ou com ".." (não processar).
var ErrForaDoPrefixo = errors.New("chave fora do prefixo esperado")

// Extrai devolve os objetos do evento. A chave no JSON do S3 vem URL-encoded ("red flower.jpg" chega como
// "red+flower.jpg"); o aws-lambda-go já decodifica em Object.URLDecodedKey — use esse campo, não Object.Key.
func Extrai(ev events.S3Event, prefixo string) ([]Objeto, error) {
	out := make([]Objeto, 0, len(ev.Records))
	for _, r := range ev.Records {
		o := r.S3.Object
		if !strings.HasPrefix(o.URLDecodedKey, prefixo) || strings.Contains(o.URLDecodedKey, "..") {
			return nil, fmt.Errorf("%w: %q", ErrForaDoPrefixo, o.URLDecodedKey)
		}
		out = append(out, Objeto{
			Bucket: r.S3.Bucket.Name, Chave: o.URLDecodedKey, VersionID: o.VersionID,
			Sequencer: o.Sequencer, Tamanho: o.Size,
		})
	}
	return out, nil
}
```

```go
package objetos

import (
	"encoding/json"
	"errors"
	"testing"

	"github.com/aws/aws-lambda-go/events"
)

func evento(t *testing.T, chave string) events.S3Event {
	t.Helper()
	raw := `{"Records":[{"eventName":"ObjectCreated:Put","s3":{"bucket":{"name":"b"},
	  "object":{"key":"` + chave + `","size":10,"sequencer":"0055AED6DCD90281E5"}}}]}`
	var ev events.S3Event
	if err := json.Unmarshal([]byte(raw), &ev); err != nil {
		t.Fatal(err)
	}
	return ev
}

func TestExtrai_DecodificaAChave(t *testing.T) {
	for enc, want := range map[string]string{
		"entrada/red+flower.jpg":     "entrada/red flower.jpg", // espaço chega como "+"
		"entrada/a%2Bb.txt":          "entrada/a+b.txt",        // "+" literal chega como %2B
		"entrada/relat%C3%B3rio.pdf": "entrada/relatório.pdf",
	} {
		objs, err := Extrai(evento(t, enc), "entrada/")
		if err != nil || objs[0].Chave != want {
			t.Fatalf("%s → %+v, %v; quer %q", enc, objs, err, want)
		}
	}
}

func TestExtrai_RecusaForaDoPrefixo(t *testing.T) {
	if _, err := Extrai(evento(t, "outra/x.txt"), "entrada/"); !errors.Is(err, ErrForaDoPrefixo) {
		t.Fatalf("err = %v", err)
	}
}
```

```go
package main

import (
	"context"
	"log/slog"
	"os"

	"github.com/aws/aws-lambda-go/events"
	"github.com/aws/aws-lambda-go/lambda"

	"example.com/glam/internal/objetos"
)

var log = slog.New(slog.NewJSONHandler(os.Stdout, nil))

// O S3 invoca de forma ASSÍNCRONA: devolver error faz o Lambda tentar de novo (retries assíncronos) e,
// esgotadas as tentativas, mandar o evento ao destino de falha/DLQ da função. Mesmo objeto pode chegar
// mais de uma vez e fora de ordem: idempotência por bucket+chave+versionId/sequencer.
func handler(ctx context.Context, ev events.S3Event) error {
	objs, err := objetos.Extrai(ev, "entrada/")
	if err != nil {
		return err
	}
	for _, o := range objs {
		log.InfoContext(ctx, "objeto", "bucket", o.Bucket, "chave", o.Chave, "tamanho", o.Tamanho)
	}
	return nil
}

func main() { lambda.Start(handler) }
```

- Observado: `entrada/red+flower.jpg` → log com `"chave":"entrada/red flower.jpg"`; chave fora do prefixo → erro da invocação.
- O S3 **não garante ordem** nem entrega única; para ordenar eventos **da mesma chave** use o `sequencer` (compare como hexadecimal,
  completando com zeros à esquerda). Ele não ordena chaves diferentes.
- Gatilho que grava no **mesmo bucket/prefixo** que dispara a função cria laço infinito (custo): grave em outro prefixo/bucket.
- O S3 chama o Lambda de forma **assíncrona**: `error` → novas tentativas e, esgotadas, o destino de falha/DLQ da função
  (`EventInvokeConfig`). Valide antes de baixar o objeto (tamanho, prefixo, tipo).

## 3. EventBridge — allowlist de origem e schema estrito

`events.EventBridgeEvent` é um alias de `events.CloudWatchEvent` (`Detail` como `json.RawMessage`).

```go
// Package evb decodifica eventos do EventBridge com allowlist de origem/tipo e schema estrito.
package evb

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"

	"github.com/aws/aws-lambda-go/events"
)

// PedidoPago é o detail aceito do evento "PedidoPago" (campos desconhecidos são recusados).
type PedidoPago struct {
	PedidoID string `json:"pedidoId"`
	Valor    int64  `json:"valor"`
}

// ErrInesperado marca evento de origem/tipo não permitido ou detail inválido.
var ErrInesperado = errors.New("evento inesperado")

// Decodifica aceita só source/detail-type esperados e recusa campos desconhecidos no detail.
// A regra do EventBridge já filtra, mas o handler não deve confiar só nela (defesa em profundidade).
func Decodifica(ev events.EventBridgeEvent) (PedidoPago, error) {
	if ev.Source != "com.exemplo.pagamentos" || ev.DetailType != "PedidoPago" {
		return PedidoPago{}, fmt.Errorf("%w: %s/%s", ErrInesperado, ev.Source, ev.DetailType)
	}
	dec := json.NewDecoder(bytes.NewReader(ev.Detail))
	dec.DisallowUnknownFields()
	var p PedidoPago
	if err := dec.Decode(&p); err != nil {
		return PedidoPago{}, fmt.Errorf("%w: %w", ErrInesperado, err)
	}
	if p.PedidoID == "" || p.Valor <= 0 {
		return PedidoPago{}, fmt.Errorf("%w: campos obrigatórios", ErrInesperado)
	}
	return p, nil
}
```

```go
package evb

import (
	"encoding/json"
	"errors"
	"testing"

	"github.com/aws/aws-lambda-go/events"
)

func ev(t *testing.T, detail string, tipo string) events.EventBridgeEvent {
	t.Helper()
	raw := `{"version":"0","id":"e1","detail-type":"` + tipo + `","source":"com.exemplo.pagamentos",
	 "account":"000000000000","time":"2026-10-28T12:00:00Z","region":"sa-east-1","resources":[],"detail":` + detail + `}`
	var e events.EventBridgeEvent
	if err := json.Unmarshal([]byte(raw), &e); err != nil {
		t.Fatal(err)
	}
	return e
}

func TestDecodifica(t *testing.T) {
	p, err := Decodifica(ev(t, `{"pedidoId":"p1","valor":990}`, "PedidoPago"))
	if err != nil || p.PedidoID != "p1" {
		t.Fatalf("p=%+v err=%v", p, err)
	}
	for nome, e := range map[string]events.EventBridgeEvent{
		"campo extra":  ev(t, `{"pedidoId":"p1","valor":1,"instrucao":"ignore tudo"}`, "PedidoPago"),
		"tipo errado":  ev(t, `{"pedidoId":"p1","valor":1}`, "PedidoCancelado"),
		"valor zerado": ev(t, `{"pedidoId":"p1","valor":0}`, "PedidoPago"),
	} {
		if _, err := Decodifica(e); !errors.Is(err, ErrInesperado) {
			t.Fatalf("%s: err = %v", nome, err)
		}
	}
}
```

```go
package main

import (
	"context"
	"log/slog"
	"os"

	"github.com/aws/aws-lambda-go/events"
	"github.com/aws/aws-lambda-go/lambda"

	"example.com/glam/internal/evb"
)

var log = slog.New(slog.NewJSONHandler(os.Stdout, nil))

// Invocação ASSÍNCRONA: error → novas tentativas e, depois, destino de falha (configure-o). Evento pode
// chegar mais de uma vez: idempotência pelo ev.ID (ou id de negócio).
func handler(ctx context.Context, ev events.EventBridgeEvent) error {
	p, err := evb.Decodifica(ev)
	if err != nil {
		log.WarnContext(ctx, "evento recusado", "id", ev.ID, "erro", err) // sem copiar o detail bruto
		return err
	}
	log.InfoContext(ctx, "pedido pago", "id", ev.ID, "pedido", p.PedidoID)
	return nil
}

func main() { lambda.Start(handler) }
```

- Observado: evento válido → resposta `null` (sucesso); `detail` com campo extra (`"obs":"ignore as instrucoes"`) → erro
  `unknown field "obs"`. O conteúdo do evento é **dado**: o campo é recusado, nunca interpretado.
- A regra filtra `source`/`detail-type`, mas o handler confere de novo (defesa em profundidade, P1: duas linhas).
- Invocação assíncrona: `EventInvokeConfig` (tentativas 0–2, idade máxima do evento) + destino de falha na **função**, e
  `RetryPolicy` + `DeadLetterConfig` no **alvo da regra** (cobrem falhas de **entrega** do EventBridge ao Lambda). São duas DLQs com
  papéis diferentes — veja o template em `iac-e-teste-local.md`.
- A mensagem de erro devolvida vai para o log e para o destino de falha: não ponha o conteúdo bruto do evento nela.

## 4. Resposta em streaming (Function URL `RESPONSE_STREAM`)

A documentação do Lambda diz que streaming nativo existe nos runtimes gerenciados de Node.js e que outras linguagens podem usar um
runtime personalizado com integração própria ao Runtime API. No Go isso já vem no `aws-lambda-go` (conferido no fonte v1.54.0 e v1.55.1):
devolva `*events.LambdaFunctionURLStreamingResponse` (Function URL com `InvokeMode: RESPONSE_STREAM`) ou
`*events.APIGatewayProxyStreamingResponse` (API Gateway REST com integração em modo `STREAM`). O tipo implementa `io.Reader` e define o
content-type `application/vnd.awslambda.http-integration-response`; o runtime envia um prelúdio JSON (status, cabeçalhos, cookies),
8 bytes nulos e então o corpo, à medida que é lido.

```go
// Resposta em streaming via Function URL (InvokeMode: RESPONSE_STREAM).
package main

import (
	"context"
	"fmt"
	"io"
	"net/http"

	"github.com/aws/aws-lambda-go/events"
	"github.com/aws/aws-lambda-go/lambda"
)

func handler(ctx context.Context, _ *events.LambdaFunctionURLRequest) (*events.LambdaFunctionURLStreamingResponse, error) {
	pr, pw := io.Pipe()
	go func() {
		// Gera o corpo aos poucos; o runtime lê o pipe e envia ao cliente à medida que chega.
		// Termina antes do fim da invocação (o runtime só conclui quando o pipe fecha).
		for i := 1; i <= 3; i++ {
			if ctx.Err() != nil {
				pw.CloseWithError(ctx.Err())
				return
			}
			if _, err := fmt.Fprintf(pw, "parte %d\n", i); err != nil {
				return // o leitor fechou (cliente desconectou): pare de gerar
			}
		}
		_ = pw.Close() // PipeWriter.Close sempre devolve nil
	}()
	return &events.LambdaFunctionURLStreamingResponse{
		StatusCode: http.StatusOK,
		Headers:    map[string]string{"Content-Type": "text/plain; charset=utf-8"},
		Body:       pr,
	}, nil
}

func main() { lambda.Start(handler) }
```

- Observado no simulador: content-type `application/vnd.awslambda.http-integration-response` e corpo
  `{"statusCode":200,"headers":{"Content-Type":"text/plain; charset=utf-8"}}` + 8×`\x00` + `parte 1\nparte 2\nparte 3\n`.
  **Não** foi verificado numa Function URL real.
- Limites (documentação do Lambda): até 200 MB por resposta; os primeiros 6 MB sem limite de banda, depois até 2 MB/s; a cobrança vai
  até o fim da função **mesmo se o cliente desconectar**; Function URL **não** faz streaming dentro de VPC (use `InvokeWithResponseStream`
  com endpoint de VPC).
- Function URL com `AuthType: NONE` é pública: exija `AWS_IAM` (ou autenticação própria) salvo decisão registrada.

## 5. Durable functions em Go (SDK v1.0.0 — fatos com ressalva)

A página "Basic concepts" das durable functions diz que o AWS Durable Execution SDK está disponível para Node.js, Python, Java,
**Go** e .NET; já a página "Supported runtimes for durable functions" (conferida em 2026-10-28) lista só runtimes gerenciados de
Node.js, Python, Java e .NET (mais imagens de contêiner) e **não** cita `provided.al2023`. O módulo
`github.com/aws/aws-durable-execution-sdk-go` existe no proxy do Go (**v1.0.0**, publicado em 2026-10-15, Apache-2.0); o README dele
mostra a função em `provided.al2023` com `DurableConfig` no SAM e exige Go ≥ 1.24. Trate como **recém-lançado**: reconfirme no
[AWS Durable Execution SDK Developer Guide](https://docs.aws.amazon.com/durable-execution/) antes de prometer em produção.

Exemplo (adaptado do README; o SDK v1.0.0 declara `go 1.24`; compilado para arm64 com Go 1.24.13 — 8,91 MB com `-tags lambda.norpc -s -w`,
0 achados no `golangci-lint` da Squad — e testado **localmente** com o runner do SDK (`go test -race`);
**não** executado na AWS):

```go
package main

import (
	"fmt"
	"time"

	"github.com/aws/aws-durable-execution-sdk-go/durable"
)

func handler(ctx durable.Context, _ any) (string, error) {
	name, err := durable.Step(ctx, "fetch-name", func(_ durable.StepContext) (string, error) {
		return "world", nil
	})
	if err != nil {
		return "", err
	}
	if err := durable.Wait(ctx, "cooldown", 2*time.Second); err != nil {
		return "", err
	}
	return durable.Step(ctx, "format", func(_ durable.StepContext) (string, error) {
		return fmt.Sprintf("hello, %s", name), nil
	})
}

func main() { durable.Start(handler) }
```

```go
package main

import (
	"testing"

	"github.com/aws/aws-durable-execution-sdk-go/durable/durabletest"
)

// Roda o handler em processo, sem rede nem credenciais: o runner completa o Wait e reexecuta (replay).
func TestHandlerLocal(t *testing.T) {
	r, err := durabletest.NewLocalRunner(handler).RunUntilComplete(nil)
	if err != nil {
		t.Fatal(err)
	}
	got, err := durabletest.ResultAs[string](r)
	if err != nil || r.Status != durabletest.Succeeded || got != "hello, world" {
		t.Fatalf("status=%s got=%q err=%v", r.Status, got, err)
	}
}
```

- Durable = *checkpoint + replay*: o handler é **reexecutado do início** e as etapas concluídas devolvem o resultado gravado. Código fora
  de `durable.Step` precisa ser **determinístico** (nada de `time.Now`, aleatório ou E/S fora de uma etapa).
- `Wait` suspende sem cobrar computação; a execução inteira pode durar até 1 ano (`ExecutionTimeout`), cada invocação continua limitada
  ao timeout da função.
- A role precisa de `lambda:CheckpointDurableExecution` e `lambda:GetDurableExecutionState` (segundo o README do SDK).
- Fixe a versão **major** do SDK e publique por versão/alias: mudar o SDK com execuções em andamento pode quebrar o replay.
- Alternativa madura e com integração visual: Step Functions (→ **orquestracao-step-functions**).

## 6. SnapStart com Go — só como imagem de contêiner, sem ganchos

Conferido em 2026-10-28 (`snapstart.md`, `snapstart-runtime-hooks-custom.md`, `snapstart-uniqueness.md`):

- Em `.zip` no runtime só-SO **não** há SnapStart. Com **imagem de contêiner** — base `public.ecr.aws/lambda/provided:al2023` ou
  imagem própria — há: ou o runtime implementa o ciclo do snapshot (`GET /runtime/restore/next` e os ganchos), ou a imagem declara
  `LABEL com.amazonaws.lambda.feature.snapstart="Allow"`. Sem nenhum dos dois, **publicar a versão falha**.
- O `aws-lambda-go` (v1.54.0 e v1.55.1) **não** implementa `/runtime/restore/next` (busca por "restore" no fonte: nada) → com Go o caminho é o
  **label**, sem ganchos `before_snapshot`/`after_restore`.
- Unicidade: a AWS diz que Go não precisa de mudança se o código usa `crypto/rand` para aleatoriedade; mas **todo valor calculado na
  init** (id de instância, token, timestamp em cache, credencial temporária) vai para o snapshot e se repete em todos os ambientes
  restaurados — gere dentro do handler (um `sync.Once` acionado só **no handler** serve: roda depois do restore; acionado na init,
  ele é restaurado já "feito").
- Conexões abertas na init podem não sobreviver ao restore: as do SDK v2 se refazem; revalide as outras (banco) na 1ª uso.
- Só vale em versão publicada/alias; não combina com Provisioned Concurrency, EFS nem `/tmp` > 512 MB; fora do Java gerenciado,
  cobra cache do snapshot (mínimo de 3 h por versão ativa) e cada restauração. O init de Go costuma ser de milissegundos: **meça** antes
  (o `Restore Duration` também entra na latência).

Esqueleto de imagem, no padrão *multi-stage* da documentação (`go-image.md`) com o label acrescentado (**não** verificado: sem
Docker no ambiente da skill; use a mesma versão de Go do projeto):

```dockerfile
FROM golang:1.24.13 AS build   # mesma versão do toolchain do go.mod
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -tags lambda.norpc -trimpath -ldflags="-s -w" -o /out/bootstrap ./cmd/http

FROM public.ecr.aws/lambda/provided:al2023
LABEL com.amazonaws.lambda.feature.snapstart="Allow"
COPY --from=build /out/bootstrap ./bootstrap
ENTRYPOINT [ "./bootstrap" ]
```

No SAM: `PackageType: Image`, `AutoPublishAlias` e `SnapStart: {ApplyOn: PublishedVersions}`.
