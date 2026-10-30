# Dados e AWS em serviços Go

> Autoral (Squad AI). Blocos com `package`/imports foram compilados com Go 1.27.1 contra pgx v5, AWS SDK for Go v2 e OpenTelemetry
> (versões da data da verificação: pgx 5.11, aws-sdk-go-v2 1.47, OTel 1.47 — **fixe as suas no `go.mod`** e atualize com revisão).

## 1. PostgreSQL com `pgx` (pool nativo)

```go
func NewPool(ctx context.Context, url string, maxConns int32) (*pgxpool.Pool, error) {
	cfg, err := pgxpool.ParseConfig(url)
	if err != nil {
		return nil, fmt.Errorf("config do banco: %w", err) // não inclua a URL (segredo) na mensagem
	}
	cfg.MaxConns = maxConns
	cfg.MaxConnLifetime = 30 * time.Minute // recicla (balanceadores, failover)
	cfg.MaxConnIdleTime = 5 * time.Minute
	cfg.HealthCheckPeriod = time.Minute
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		return nil, err
	}
	pctx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()
	if err := pool.Ping(pctx); err != nil {
		pool.Close()
		return nil, fmt.Errorf("ping do banco: %w", err)
	}
	return pool, nil
}
```

**Dimensionamento do pool:** `MaxConns × réplicas ≤ max_connections do banco − reserva` (admin, migrações, outros serviços). Muitos pods ⇒ use um *pooler* (PgBouncer/RDS Proxy) e menos conexões por pod.
Pool grande não acelera consulta lenta: se `pool.Stat().EmptyAcquireCount`/tempo de espera sobe, procure transação longa, consulta sem índice ou N+1 antes de aumentar.

Transação curta com rollback garantido e tratamento de erro **tipado** do driver:

```go
package ext3

import (
	"context"
	"errors"
	"fmt"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"
)

var ErrConflict = errors.New("conflito")

func WithTx(ctx context.Context, pool *pgxpool.Pool, fn func(pgx.Tx) error) (err error) {
	tx, err := pool.Begin(ctx)
	if err != nil {
		return fmt.Errorf("begin: %w", err)
	}
	defer func() {
		if err != nil {
			_ = tx.Rollback(context.WithoutCancel(ctx)) // rollback mesmo com ctx já cancelado
		}
	}()
	if err = fn(tx); err != nil {
		return err
	}
	return tx.Commit(ctx)
}

type User struct {
	ID   int64  `db:"id"`
	Name string `db:"name"`
}

func ListUsers(ctx context.Context, q pgx.Tx, minID int64) ([]User, error) {
	rows, err := q.Query(ctx, `SELECT id, name FROM users WHERE id >= $1 ORDER BY id`, minID)
	if err != nil {
		return nil, err
	}
	return pgx.CollectRows(rows, pgx.RowToStructByName[User]) // fecha rows e checa rows.Err()
}

func Insert(ctx context.Context, q pgx.Tx, name string) error {
	_, err := q.Exec(ctx, `INSERT INTO users(name) VALUES ($1)`, name)
	if pe, ok := errors.AsType[*pgconn.PgError](err); ok && pe.Code == "23505" { // unique_violation
		return fmt.Errorf("usuário %q: %w", name, ErrConflict)
	}
	return err
}
```

Práticas: SQL **sempre parametrizado**; `SELECT` de colunas explícitas (nada de `SELECT *`); transações curtas e **sem chamada de rede dentro** (use outbox para publicar eventos);
`context` com timeout por operação; `LIMIT`/paginação por chave (*keyset*) em listagens; índice para cada filtro/ordenação quente (`EXPLAIN (ANALYZE, BUFFERS)`);
migrações **versionadas e reversíveis** (goose, golang-migrate, Atlas…) rodando como *job* separado do deploy da aplicação; migração compatível com a versão anterior do código (expandir → migrar → contrair).
`database/sql` (quando necessário): `SetMaxOpenConns`, `SetMaxIdleConns`, `SetConnMaxLifetime`, `SetConnMaxIdleTime`; `QueryContext`; `defer rows.Close()`; `rows.Err()`; `db.Stats()` para métricas.

## 2. AWS SDK for Go v2

Princípios: **sem credenciais no código** (cadeia padrão: variáveis, perfil, IRSA/Pod Identity no EKS, role da task no ECS); **região e endpoint por ambiente**; ctx em toda chamada;
um cliente por serviço **reutilizado** (são concorrência-seguros); retry com teto; checar erros **tipados**.

```go
cfg, err := config.LoadDefaultConfig(ctx,
	config.WithRetryer(func() aws.Retryer {
		return retry.AddWithMaxBackoffDelay(
			retry.NewStandard(func(o *retry.StandardOptions) { o.MaxAttempts = 4 }), 5*time.Second)
	}),
)
sqsClient := sqs.NewFromConfig(cfg) // s3.NewFromConfig(cfg), dynamodb.NewFromConfig(cfg)…
```

- **LocalStack/testes:** defina `AWS_ENDPOINT_URL=http://localhost:4566` (e credenciais fictícias de teste) — o SDK v2 lê o endpoint do ambiente, sem mudar código (ver skill `localstack-dev`).
  S3 em LocalStack costuma exigir *path-style* (`s3.NewFromConfig(cfg, func(o *s3.Options){ o.UsePathStyle = true })`).
- **Erros:** use `errors.AsType[*types.NoSuchKey](err)` (Go 1.26) / `errors.As` com os tipos do pacote `.../types`, ou `smithy.APIError` (`ErrorCode()`) para códigos genéricos (`ThrottlingException`).
- **Throttling:** o retryer padrão já faz backoff; adicione *rate limiting* do lado do cliente se você mesmo gera a carga (`x/time/rate`).

### 2.1 Consumidor SQS (at-least-once)

```go
func Consume(ctx context.Context, log *slog.Logger, c *sqs.Client, queueURL string, workers int, h Handler) error {
	for ctx.Err() == nil {
		out, err := c.ReceiveMessage(ctx, &sqs.ReceiveMessageInput{
			QueueUrl: aws.String(queueURL), MaxNumberOfMessages: 10,
			WaitTimeSeconds: 20, // long polling: menos chamadas vazias (custo) e menor latência
			VisibilityTimeout: 60, // > tempo máximo de processar UMA mensagem
		})
		if err != nil { /* log + backoff com select em ctx.Done(); continue */ }
		g, gctx := errgroup.WithContext(ctx)
		g.SetLimit(workers)
		for _, m := range out.Messages {
			g.Go(func() error {
				if err := h(gctx, aws.ToString(m.Body)); err != nil {
					log.Error("processamento falhou", "msg_id", aws.ToString(m.MessageId), "err", err)
					return nil // NÃO apaga: reaparece após o visibility timeout e vai à DLQ após maxReceiveCount
				}
				_, derr := c.DeleteMessage(gctx, &sqs.DeleteMessageInput{QueueUrl: aws.String(queueURL), ReceiptHandle: m.ReceiptHandle})
				return derr
			})
		}
		_ = g.Wait()
	}
	return context.Cause(ctx)
}
```

Regras do consumidor: **idempotente** (a mesma mensagem pode chegar 2×); `VisibilityTimeout` > pior caso de processamento (ou estenda com `ChangeMessageVisibility` em tarefas longas);
**DLQ** com `maxReceiveCount` (3–5) e alarme em `ApproximateNumberOfMessagesVisible` da DLQ; mensagem venenosa não pode travar a fila; encerre limpo em SIGTERM (para de receber, termina as em voo, não apaga as não concluídas);
FIFO só quando a ordem for requisito (limita vazão); corpo da mensagem pequeno (grandes → S3 + ponteiro); valide e **limite o tamanho** do que chega (entrada externa = não confiável).

### 2.2 S3 e DynamoDB

```go
// S3: stream, nunca io.ReadAll em objeto grande; corpo sempre fechado.
out, err := c.GetObject(ctx, &s3.GetObjectInput{Bucket: aws.String(bucket), Key: aws.String(key)})
if err != nil { return 0, fmt.Errorf("s3 get %s/%s: %w", bucket, key, err) }
defer out.Body.Close()
n, err := io.Copy(dst, out.Body)

// DynamoDB: escrita condicional = idempotência/lock otimista; erro tipado.
_, err = c.PutItem(ctx, &dynamodb.PutItemInput{
	TableName: aws.String(table), Item: item,
	ConditionExpression: aws.String("attribute_not_exists(pk)"),
})
if _, ok := errors.AsType[*ddbtypes.ConditionalCheckFailedException](err); ok { return ErrDuplicate }
```

- Upload de objeto grande: *multipart* concorrente via `feature/s3/transfermanager` (ainda `v0.x` na verificação: fixe a versão e releia o changelog) — o antigo `feature/s3/manager` está marcado como **deprecado** (substituído pelo `transfermanager`) em vez de `PutObject` com buffer inteiro; URLs pré-assinadas para o cliente enviar direto ao S3.
- DynamoDB: modele pelo **padrão de acesso**; `Query` (não `Scan`) em caminho quente; chave de partição com alta cardinalidade; `TransactWriteItems` só quando necessário (custo 2×); capacidade on-demand até conhecer a carga.
- Segurança: **menor privilégio** por serviço (ação + recurso específicos), criptografia em repouso/trânsito, bucket privado com *Block Public Access*, sem `*` em IAM. Detalhes → **arquiteto-cloud-aws** / **engenheiro-seguranca**.

## 3. OpenTelemetry

```go
exp, err := otlptracehttp.New(ctx) // endpoint/headers via OTEL_EXPORTER_OTLP_ENDPOINT / OTEL_EXPORTER_OTLP_HEADERS
tp := sdktrace.NewTracerProvider(
	sdktrace.WithBatcher(exp),
	sdktrace.WithResource(resource.NewWithAttributes(semconv.SchemaURL,
		semconv.ServiceName("pedidos"), semconv.ServiceVersion(version))),
)
otel.SetTracerProvider(tp)
defer tp.Shutdown(ctx) // flush no shutdown (use um ctx com prazo, não o ctx já cancelado)
handler := otelhttp.NewHandler(mux, "http") // spans de servidor; para cliente: otelhttp.NewTransport
```

- Propague o contexto de trace (W3C `traceparent`) por HTTP/gRPC/mensagens (atributos da mensagem SQS) para correlacionar ponta a ponta; coloque `trace_id` nos logs.
- Amostragem: `ParentBased(TraceIDRatioBased(p))` em tráfego alto; 100% em erro via *tail sampling* no Collector.
- Cardinalidade: nome do span = **rota padrão** (`GET /items/{id}`), nunca a URL com ids; atributos sem PII.
- Custo/cold start: instrumente só o necessário; em Lambda prefira a extensão/collector enxuto (→ **aws-lambda-go**).

## 4. gRPC (quando faz sentido)

```go
s := grpc.NewServer(grpc.MaxRecvMsgSize(4<<20), grpc.ConnectionTimeout(10*time.Second))
h := health.NewServer()                       // protocolo grpc.health.v1
healthpb.RegisterHealthServer(s, h)           // probes do K8s com grpc probe nativo
// pb.RegisterXServer(s, impl)  — código gerado por protoc/buf
```

- **Deadline em toda chamada** (`ctx` com timeout no cliente); o servidor respeita `ctx.Done()`; propague o deadline para dependências.
- Interceptors para auth, logging, métricas, `recover`; erros com `status.Error(codes.X, msg)` (não vaze detalhes internos); `errdetails` para validação.
- Evolução de contrato: nunca reutilize número de campo; campos novos opcionais; `buf breaking` no CI.
- Shutdown: `s.GracefulStop()` com prazo (depois `s.Stop()`); marque `health` como `NOT_SERVING` antes.
- TLS/mTLS dentro da malha; keepalive configurado para atrás de balanceadores; balanceamento por **requisição** (não por conexão) em K8s (headless service/Envoy/xDS).
