# Diagnóstico e testes de código concorrente em Go

> Autoral (Squad AI). As saídas abaixo foram **capturadas de execuções reais** com Go 1.27.1 (caminhos abreviados).
> O comportamento do `synctest` foi conferido com `go doc testing/synctest` do mesmo toolchain.

## 1. Lendo um relatório do race detector (`-race`)

```text
==================
WARNING: DATA RACE
Read at 0x00c00011e0f0 by goroutine 9:
  runtime.mapaccess2_faststr()
  ...
Previous write at 0x00c00011e0f0 by goroutine 8:
  runtime.mapassign_faststr()
  main.main.func1()
      main.go:14 +0x8c

Goroutine 9 (running) created at:
  sync.(*WaitGroup).Go()
Goroutine 8 (finished) created at:
  sync.(*WaitGroup).Go()
==================
Found 1 data race(s)
exit status 66
```

Como ler: (1) **dois acessos ao mesmo endereço**, ao menos um é escrita, sem *happens-before* entre eles; (2) as pilhas dizem **onde**
(`main.go:14`); (3) "created at" mostra **quem criou** cada goroutine — o ponto onde o dono deveria ter sincronizado.
Aqui: duas goroutines escrevendo no mesmo `map` (`counts[k]++`). Correções, da mais simples à mais cara:
cada goroutine devolve seu resultado (índice/canal) e uma só agrega; `sync.Mutex` com seção curta; `atomic` para contadores.

- `-race` custa ~5–10× de memória e ~2–20× de tempo de execução (doc oficial do race detector): rode em **todos** os testes e em staging com carga; em produção só em canário.
- Código que "passa" sem `-race` não está correto — ausência de falha ≠ ausência de corrida.
- Leitura/escrita concorrente de `map` sem `-race` vira `fatal error: concurrent map writes` (não é recuperável com `recover`).
- Modelo de memória: só há garantia de visibilidade entre goroutines via **sincronização** (canal, mutex, atomic, `WaitGroup`, `Once`). `bool` "flag" sem atomic é corrida.

## 2. Vazamento de goroutine

**Sinais:** `runtime.NumGoroutine()` (ou a métrica `/sched/goroutines:goroutines` de `runtime/metrics`) cresce sem estabilizar; memória sobe; shutdown não termina.

**Perfil `goroutineleak` (Go 1.27):** o GC encontra goroutines bloqueadas em primitivas (canal, `Mutex`, `Cond`…) que **nenhuma outra goroutine alcançável** pode destravar.

```go
runtime.GC()
pprof.Lookup("goroutineleak").WriteTo(os.Stdout, 1)
// em serviço: GET /debug/pprof/goroutineleak  (porta interna!)
```

Saída real do exemplo (3 chamadas com timeout vencido e canal sem buffer):

```text
goroutineleak profile: total 3
3 @ 0x47f06a 0x41421c 0x413e17 0x4e06d6 0x484ec1
#	0x4e06d5	main.search.func1+0x35	main.go:15
```

`3 @` = três goroutines idênticas presas; a linha `#` aponta o **envio** `ch <- "resultado"` (linha 15). Limites: pode **não** detectar vazamento
preso a variável global ou a goroutine ainda "runnable". Em caso de dúvida, compare dois perfis `goroutine` (`/debug/pprof/goroutine?debug=1`) separados por minutos: o grupo que cresce é o suspeito.

**`?debug=2`** imprime cada goroutine com estado e **tempo bloqueada** (`[chan send, 12 minutes]`) — vazamento aparece como centenas de iguais com minutos de espera.
No 1.27 as pilhas incluem os *labels* do `pprof` (módulos `go 1.27+`): rotule goroutines de fundo com `pprof.Do(ctx, pprof.Labels("job","reindex"), f)`.

**Causas, por frequência:** (1) envio num canal sem receptor após timeout/cancelamento; (2) `range` sobre canal que ninguém fecha; (3) `ctx` ignorado em laço/`select`;
(4) `Ticker` ainda referenciado sem `Stop` (a partir de `go 1.23`, `Timer`/`Ticker` sem referência são coletados mesmo sem `Stop`; antes disso, vazavam); (5) `wg.Wait()` com `Add` sem `Done` (erro em ramo de saída antecipada); (6) `http.Response.Body` sem fechar; (7) goroutine esperando `Mutex`/`Cond` de quem já saiu.

**Em testes:** `goleak.VerifyTestMain(m)` (por pacote) ou `goleak.VerifyNone(t)`; dentro de `synctest.Test`, goroutine remanescente bloqueada quando a função retorna **dá pânico** (`deadlock: main bubble goroutine has exited but blocked goroutines remain`).

## 3. Deadlock

- O runtime só declara `fatal error: all goroutines are asleep - deadlock!` quando **todas** as goroutines estão bloqueadas — num servidor com outras goroutinas ativas isso **nunca** dispara.
  Num serviço "pendurado", tire um dump: `kill -QUIT <pid>` (imprime todas as pilhas e encerra) ou `/debug/pprof/goroutine?debug=2`.
- Leia os estados: `chan receive` / `chan send` (par ausente), `select` (nenhum case pode andar), `sync.Mutex.Lock`/`semacquire` (lock preso por outra goroutine), `sync.WaitGroup.Wait` (falta `Done`),
  `sync.Cond.Wait` (falta `Signal`). Monte o **grafo de espera**: A espera B espera A?
- Causas clássicas: lock não reentrante chamado de dentro de si mesmo; ordem de locks invertida entre dois caminhos; `wg.Add` depois de `Wait`; canal sem buffer enviado e recebido pela **mesma** goroutine;
  callback do usuário chamado sob lock que tenta adquirir o mesmo lock.
- Prevenção: ordem global de locks documentada; nunca chamar código externo sob lock; `TryLock` só em casos excepcionais; `context` com prazo em toda espera de recurso.

## 4. Contenção e latência (CPU baixa, p99 alto)

```go
runtime.SetMutexProfileFraction(5) // 1 em 5 eventos de contenção de mutex
runtime.SetBlockProfileRate(1_000_000) // amostra em média 1 evento a cada 1 ms (10^6 ns) bloqueado — não é limiar
```

```bash
go tool pprof -http=:0 http://127.0.0.1:6060/debug/pprof/mutex
go tool pprof -http=:0 http://127.0.0.1:6060/debug/pprof/block
curl -o trace.out 'http://127.0.0.1:6060/debug/pprof/trace?seconds=5' && go tool trace trace.out
```

- `mutex` mostra **quem segurou** o lock por muito tempo; `block` mostra **onde se esperou** (canal, lock, `Cond`).
- `go tool trace` mostra a linha do tempo por P: lacunas = espera; "GC assist" = alocação demais (→ `go-performance-engineer`).
- **Flight recorder** (1.25, `runtime/trace.FlightRecorder`): mantém uma janela deslizante do trace em memória e grava só quando algo acontece (ex.: p99 estourou) — ideal para o "e agora?" em produção.
- Remédios: encolher a seção crítica, fatiar o lock (*sharding* por chave), trocar por `atomic`, ler mais do que escrever (`RWMutex`), cópia-na-escrita com `atomic.Pointer`, ou tirar o trabalho de sob o lock.

## 5. Testes determinísticos com `testing/synctest`

Regras-chave (do pacote oficial):

- `synctest.Test(t, f)` roda `f` numa **bolha**; goroutines iniciadas nela fazem parte dela. O relógio é **falso** (começa em 2000-01-01 UTC) e só avança quando **todas** as goroutines estão *durably blocked*.
- Bloqueios *duráveis*: envio/recebimento em canal **criado na bolha**, `select` só com canais da bolha, `sync.Cond.Wait`, `sync.WaitGroup.Wait` (com `Add`/`Go` dentro da bolha), `time.Sleep`.
- **Não** são duráveis (podem ser destravados de fora): `sync.Mutex`/`RWMutex`, I/O de rede, *syscalls*. Evite-os na bolha; use rede falsa (`net.Pipe`, `httptest.NewTestServer`, 1.27).
- `synctest.Wait()` bloqueia até todas as **outras** goroutines estarem durably blocked (use para "deixe tudo assentar antes de afirmar"); `synctest.Sleep(d)` (1.27) = `Sleep` + `Wait`.
- Se todas bloqueiam e nada pode avançar o tempo, **`Test` entra em pânico** (deadlock detectado). Timers/tickers/canais da bolha não podem ser usados de fora (pânico).
- Um `sync.WaitGroup` **variável de pacote** (`var wg sync.WaitGroup`) não associa à bolha; use `new(sync.WaitGroup)` ou campo.

```go
// Código sob teste: backoff exponencial; a espera respeita ctx.
func Retry(ctx context.Context, attempts int, base time.Duration, f func() error) error {
	var errs []error
	delay := base
	for i := range attempts {
		err := f()
		if err == nil {
			return nil
		}
		errs = append(errs, fmt.Errorf("tentativa %d: %w", i+1, err))
		if i == attempts-1 {
			break
		}
		t := time.NewTimer(delay)
		select {
		case <-t.C:
		case <-ctx.Done():
			t.Stop()
			return errors.Join(append(errs, context.Cause(ctx))...)
		}
		delay *= 2
	}
	return errors.Join(errs...)
}

func TestRetryBackoff(t *testing.T) {
	synctest.Test(t, func(t *testing.T) {
		var tries []time.Duration
		start := time.Now()
		err := Retry(t.Context(), 3, time.Second, func() error {
			tries = append(tries, time.Since(start))
			return errors.New("falha")
		})
		// backoff 1s, 2s — o teste leva microssegundos reais
		want := []time.Duration{0, time.Second, 3 * time.Second}
		if err == nil || !slices.Equal(tries, want) {
			t.Fatalf("tentativas = %v, erro = %v", tries, err)
		}
	})
}
```

Testes que **não** cabem na bolha (I/O real, processos): `-race -count=N`, timeouts curtos, `t.Context()` e sincronização explícita por canal (nunca `Sleep`).

## 6. Receita de caça a flaky concorrente

```bash
go test -race -count=200 -shuffle=on -cpu=1,2,8 -failfast ./pkg/...
GOMAXPROCS=1 go test -race -count=50 ./pkg/...   # expõe suposições de ordem
go test -run '^TestFlaky$' -count=1000 -race ./pkg  # isola o suspeito
```

1. Reproduza e **registre a taxa de falha** (ex.: 3/200). 2. Leia o relatório de `-race`/dump. 3. Hipótese de causa (propriedade/término/ordem). 4. Corrija a causa.
5. Prove: o mesmo comando com contagem maior fica limpo; o teste de regressão determinístico (`synctest`) falha sem a correção.

## 7. Checklist de revisão de PR com concorrência

- [ ] Cada `go` tem dono do término, `ctx` e erro propagado?
- [ ] Quem envia fecha? Há receptor garantido para todo envio (ou buffer/`select` com `ctx.Done()`)?
- [ ] Concorrência limitada (`SetLimit`, semáforo, pool)? Nada de `go` por item ilimitado?
- [ ] Estado compartilhado protegido (mutex/atomic/dono único)? Locks curtos, sem I/O sob lock, ordem consistente?
- [ ] `Ticker`/`Timer`/`Body`/`Rows` fechados com `defer`?
- [ ] Teste determinístico (`synctest`) e `-race -count>1` no CI? `goleak` no `TestMain`?
