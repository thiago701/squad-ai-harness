# Receitas de concorrência em Go (compiladas com Go 1.27.1, `-race`)

> Autoral (Squad AI). Todas as receitas com `package` passaram em `go vet` e `go test -race -count=3 -shuffle=on`.
> Dependências: `golang.org/x/sync` (errgroup, singleflight, semaphore) e `golang.org/x/time/rate`. Fixe versões no `go.mod`.

## 1. Fan-out com limite e cancelamento no 1º erro (`errgroup`)

```go
package conc

import (
	"context"
	"fmt"
	"runtime"

	"golang.org/x/sync/errgroup"
)

type Result struct{ URL string }

func FetchAll(ctx context.Context, urls []string) ([]Result, error) {
	g, ctx := errgroup.WithContext(ctx)
	g.SetLimit(runtime.GOMAXPROCS(0)) // CPU-bound: nº de CPUs (em contêiner só respeita o limit de CPU com `go ≥ 1.25` no go.mod; mín. 2); I/O-bound: calibre por medição
	out := make([]Result, len(urls))
	for i, u := range urls {
		g.Go(func() error {
			r, err := fetch(ctx, u)
			if err != nil {
				return fmt.Errorf("fetch %s: %w", u, err)
			}
			out[i] = r // cada goroutine escreve no seu índice: sem corrida, sem lock
			return nil
		})
	}
	if err := g.Wait(); err != nil {
		return nil, err
	}
	return out, nil
}
```

- `g.Go` **bloqueia** quando o limite é atingido (backpressure); `g.TryGo` retorna `false` em vez de bloquear.
- O ctx devolvido por `WithContext` é cancelado no 1º erro **e** quando `Wait` retorna — não o reutilize depois.
- Sem `errgroup` (stdlib pura): `sync.WaitGroup` + `wg.Go` (1.25).

## 2. Pool de workers com resultado e erro por job

```go
package rec

import (
	"context"
	"sync"
)

type Job struct{ ID int }
type Out struct {
	ID  int
	Err error
}

func Pool(ctx context.Context, n int, jobs []Job, do func(context.Context, Job) error) []Out {
	in := make(chan Job)
	out := make(chan Out)

	var wg sync.WaitGroup
	for range n {
		wg.Go(func() {
			for j := range in {
				out <- Out{ID: j.ID, Err: do(ctx, j)}
			}
		})
	}
	go func() { // único dono de `in`
		defer close(in)
		for _, j := range jobs {
			select {
			case in <- j:
			case <-ctx.Done():
				return
			}
		}
	}()
	go func() { wg.Wait(); close(out) }() // fecha `out` depois que TODOS os workers saem

	res := make([]Out, 0, len(jobs))
	for o := range out { // o consumidor lê até o fim → ninguém fica preso em `out <-`
		res = append(res, o)
	}
	return res
}
```

Armadilha clássica: **parar de ler `out` antes de ele fechar** deixa workers presos no envio (vazamento). Se precisar sair cedo, cancele o ctx **e** drene.

## 3. Pipeline genérico (produtor fecha, consumidor respeita `ctx`)

```go
func Generate[T any](ctx context.Context, in ...T) <-chan T {
	out := make(chan T)
	go func() {
		defer close(out) // quem envia fecha
		for _, v := range in {
			select {
			case out <- v:
			case <-ctx.Done():
				return
			}
		}
	}()
	return out
}

func Map[T, U any](ctx context.Context, in <-chan T, f func(T) U) <-chan U {
	out := make(chan U)
	go func() {
		defer close(out)
		for v := range in {
			select {
			case out <- f(v):
			case <-ctx.Done():
				return
			}
		}
	}()
	return out
}
```

Canal sem buffer entre etapas = **backpressure** (a etapa lenta freia as anteriores). Buffer só para suavizar rajadas, com tamanho justificado por medição.

## 4. "Primeiro que responder vence" sem vazar goroutines

```go
func FirstOf(ctx context.Context, fs ...func(context.Context) (string, error)) (string, error) {
	type res struct {
		v   string
		err error
	}
	ch := make(chan res, len(fs)) // buffer = nº de produtores → nenhum bloqueia no envio
	ctx, cancel := context.WithCancel(ctx)
	defer cancel() // cancela as perdedoras
	for _, f := range fs {
		go func() {
			v, err := f(ctx)
			ch <- res{v, err}
		}()
	}
	var errs []error
	for range fs {
		r := <-ch
		if r.err == nil {
			return r.v, nil
		}
		errs = append(errs, r.err)
	}
	return "", errors.Join(errs...)
}
```

## 5. Causa explícita de cancelamento e orçamento de tempo

```go
var ErrBudget = errors.New("orçamento de tempo esgotado")

func WithBudget(parent context.Context, d time.Duration) (context.Context, context.CancelFunc) {
	ctx, cancel := context.WithCancelCause(parent)
	t := time.AfterFunc(d, func() { cancel(ErrBudget) })
	return ctx, func() { t.Stop(); cancel(context.Canceled) }
}
// quem recebe ctx.Done() lê context.Cause(ctx) para saber o motivo (ErrBudget × cancelamento do chamador)
```

Outros: `context.WithTimeoutCause`, `context.AfterFunc(ctx, f)` (roda `f` ao cancelar, sem goroutine manual; devolve `stop`),
`context.WithoutCancel(ctx)` (trabalho que deve sobreviver ao request — auditoria/limpeza — mantendo os valores).

## 6. `singleflight` — colapsa chamadas idênticas (evita *cache stampede*)

```go
type Cache struct{ g singleflight.Group }

func (c *Cache) Load(ctx context.Context, key string, load func(context.Context) (string, error)) (string, error) {
	v, err, _ := c.g.Do(key, func() (any, error) { return load(ctx) })
	if err != nil {
		return "", err
	}
	return v.(string), nil
}
```

Cuidado: o `ctx` da **primeira** chamada governa a carga compartilhada; se ela cancelar, todas as esperas falham. Para cargas críticas use `DoChan` + ctx próprio ou `WithoutCancel`.

## 7. Semáforo ponderado e rate limit

```go
func Weighted(ctx context.Context, budget int64, costs []int64, do func(int64)) error {
	sem := semaphore.NewWeighted(budget)
	g, ctx := errgroup.WithContext(ctx)
	var acquireErr error
	for _, c := range costs {
		if err := sem.Acquire(ctx, c); err != nil {
			acquireErr = err // ctx cancelado: os itens restantes NÃO foram processados
			break
		}
		g.Go(func() error { defer sem.Release(c); do(c); return nil })
	}
	return errors.Join(acquireErr, g.Wait()) // não devolva só g.Wait(): esconderia o cancelamento
}

func Throttled(ctx context.Context, rps, n int, call func(int)) error {
	lim := rate.NewLimiter(rate.Limit(rps), 1)
	for i := range n {
		if err := lim.Wait(ctx); err != nil { // bloqueia respeitando ctx; sem busy loop
			return err
		}
		call(i)
	}
	return nil
}
```

## 8. Tarefa periódica e supervisão

```go
func Every(ctx context.Context, d time.Duration, tick func(context.Context) error) error {
	t := time.NewTicker(d)
	defer t.Stop() // sempre
	for {
		select {
		case <-ctx.Done():
			return context.Cause(ctx)
		case <-t.C:
			if err := tick(ctx); err != nil {
				return err
			}
		}
	}
}

func Supervise(ctx context.Context, tasks ...func(context.Context) error) error {
	g, ctx := errgroup.WithContext(ctx)
	for _, t := range tasks {
		g.Go(func() error { return t(ctx) })
	}
	if err := g.Wait(); !errors.Is(err, context.Canceled) {
		return err // parada solicitada (Canceled) não é falha
	}
	return nil
}
```

Os canais de `Ticker`/`Timer` são síncronos (sem buffer) em módulos com `go 1.23+`, e o Go 1.27 removeu o opt-out `asynctimerchan`: não espere "tick pendente" depois de `Stop`/`Reset`.

## 9. Estado compartilhado: mutex curto, atomic e troca de configuração

```go
type Cache[K comparable, V any] struct {
	mu sync.RWMutex
	m  map[K]V
}

func (c *Cache[K, V]) Get(k K) (V, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	v, ok := c.m[k]
	return v, ok
}

func (c *Cache[K, V]) Set(k K, v V) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.m == nil {
		c.m = make(map[K]V) // zero value útil
	}
	c.m[k] = v
}

type Live struct{ p atomic.Pointer[Cfg] } // leitura sem lock; troque a config inteira, não campos

func (l *Live) Load() *Cfg   { return l.p.Load() }
func (l *Live) Store(c *Cfg) { l.p.Store(c) }
```

- Prefira os **tipos** `atomic.Int64`, `atomic.Bool`, `atomic.Pointer[T]` (1.19+) às funções soltas (`go fix` com `atomictypes` converte).
- Seção crítica **curta**: nada de I/O, callback do usuário ou envio em canal sob lock. `RWMutex` só vale com leitura dominante e seção não trivial.
- `sync.OnceValue`/`OnceValues`/`OnceFunc` para inicialização preguiçosa; `sync.Pool` só para objetos temporários caros (ver `go-performance-engineer`).

## 10. Corrigindo o vazamento clássico (timeout + canal sem buffer)

Com bug (3 goroutines vazam; o perfil `goroutineleak` aponta a linha do envio):

```go
func search(timeout time.Duration) string {
	ch := make(chan string)        // sem buffer
	go func() { ch <- slow() }()   // trava para sempre se o timeout vencer
	select {
	case r := <-ch:
		return r
	case <-time.After(timeout):
		return "timeout"
	}
}
```

Corrigido — buffer 1 (único envio) e ctx para cancelar o trabalho:

```go
func search(ctx context.Context, timeout time.Duration) (string, error) {
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	ch := make(chan string, 1) // o único envio nunca bloqueia, mesmo sem receptor
	go func() { ch <- slow(ctx) }()
	select {
	case r := <-ch:
		return r, nil
	case <-ctx.Done():
		return "", context.Cause(ctx)
	}
}
```
