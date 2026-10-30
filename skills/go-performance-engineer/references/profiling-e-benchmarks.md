# Profiling e benchmarks em Go — método e leitura de saída

> Autoral (Squad AI). Números e saídas abaixo foram **medidos** em Go 1.27.1 (VM de 2 vCPU, indicativo — meça no seu ambiente).

## 1. Benchmark confiável (`testing.B`)

```go
func BenchmarkSummarize(b *testing.B) {
	rows := loadRows()      // preparo FORA do laço: não entra na medição
	b.ReportAllocs()
	for b.Loop() {          // Go 1.24+: mede só o corpo; o resultado não é eliminado pelo compilador
		_ = Summarize(rows)
	}
}
```

- `b.Loop()` substitui `for i := 0; i < b.N; i++`: dispensa `b.ResetTimer()` e impede que o compilador apague o corpo.
- Sub-benchmarks por tamanho (`b.Run("n=1e3", ...)`) mostram a **forma da curva** (linear? quadrática?).
- Paralelo: `b.RunParallel(func(pb *testing.PB){ for pb.Next() { ... } })` para estruturas compartilhadas (cache, pool).
- Execute: `go test -run '^$' -bench . -benchmem -count=10 ./pkg | tee old.txt`. `-run '^$'` evita rodar os testes junto.
- Fixe o ambiente: máquina quieta, mesma CPU/frequência, sem outros processos; `-cpu=1,4` para ver escalabilidade.

### Comparar com `benchstat`

```bash
go install golang.org/x/perf/cmd/benchstat@latest   # fixe a versão no CI
benchstat old.txt new.txt
```

Saída real (função lenta → rápida, `-count=6`; para decisão real use ≥10):

```text
       │ old.txt │            new.txt            │
       │ sec/op  │   sec/op     vs base          │
Slow-2   524.40µ ± 22%   64.95µ ± 19%  -87.61% (p=0.002 n=6)

       │  B/op   │     B/op      vs base         │
Slow-2   113.981Ki ± 0%   5.305Ki ± 0%  -95.35% (p=0.002 n=6)

       │ allocs/op │  allocs/op  vs base          │
Slow-2   10211.00 ± 0%   55.00 ± 0%  -99.46% (p=0.002 n=6)
```

Leitura: `± 22%` é a variação entre execuções (alto = ruído; repita ou silencie a máquina); `p=0.002` → diferença estatisticamente significativa;
`n=6` amostras. **`~`** no lugar do percentual significa "sem diferença detectável" — não afirme ganho. Reporte as **três** tabelas (tempo, B/op, allocs/op).

## 2. Perfis com `pprof`

### Coletar

```bash
# em benchmark/teste
go test -run '^$' -bench Slow -benchtime=2000x -cpuprofile cpu.out -memprofile mem.out ./pkg
# em serviço (porta INTERNA): import _ "net/http/pprof" num http.Server separado em 127.0.0.1
go tool pprof -http=: 'http://127.0.0.1:6060/debug/pprof/profile?seconds=30'   # CPU
go tool pprof -http=: 'http://127.0.0.1:6060/debug/pprof/heap'                 # memória viva
go tool pprof -http=: 'http://127.0.0.1:6060/debug/pprof/allocs'               # alocações acumuladas
```

### Ler (saída real, `-top`)

```text
Showing nodes accounting for 520ms, 56.52% of 920ms total
      flat  flat%   sum%        cum   cum%
     140ms 15.22% 15.22%      160ms 17.39%  runtime.mallocgcTinySC2
      90ms  9.78% 25.00%      230ms 25.00%  runtime.mapassign_faststr
      50ms  5.43% 43.48%      150ms 16.30%  fmt.(*pp).doPrintf
```

Diagnóstico imediato: o topo é **alocador + mapa + fmt** ⇒ o custo está em alocação/formatação, não na lógica. Em `alloc_space` (`-sample_index=alloc_space -top mem.out`)
a função culpada aparece com a maior fatia (`SummarizeSlow` ≈ 85% dos bytes alocados).

Comandos úteis dentro do `pprof`: `top`, `top -cum`, `list NomeDaFunção` (linha a linha), `peek Func` (quem chama/é chamado), `web`/UI `-http` (o **flame graph** é a visão padrão desde o 1.26),
`-focus=regex`/`-ignore=regex`, **`-diff_base=antes.pb.gz`** (mostra só o que mudou entre dois perfis — ótimo para validar uma correção).

Tipos de perfil: `cpu` (onde roda), `heap`/`inuse_space` (o que está retido), `allocs`/`alloc_space|alloc_objects` (quem aloca), `goroutine`, `goroutineleak` (1.27), `mutex` (quem segura lock), `block` (onde espera), `threadcreate`.

### `go tool trace` e flight recorder

- `go tool trace trace.out` → linha do tempo por P, latência do escalonador, GC, rede. Use para "CPU baixa mas p99 alto" e para ver *stop-the-world*/assist.
- **Flight recorder (1.25)**: `trace.NewFlightRecorder(trace.FlightRecorderConfig{MinAge: 10*time.Second, MaxBytes: 4<<20})`, `fr.Start()`; ao detectar o evento (SLO estourado), `fr.WriteTo(file)` salva **os últimos segundos** — o trace do que acabou de acontecer, sem pagar o custo de rastrear tudo.
- `go tool trace -http=:PORTA` escuta só em *localhost* desde o 1.27 (use `0.0.0.0:PORTA` conscientemente).

## 3. PGO (Profile-Guided Optimization) — passo a passo verificado

1. Colete **CPU profile de produção** representativo (30–60 s, em várias instâncias/horários): `.../debug/pprof/profile?seconds=60`.
2. Mescle: `go tool pprof -proto p1.pprof p2.pprof p3.pprof > default.pgo`.
3. Coloque `default.pgo` **no diretório do pacote `main`** e faça commit (é pequeno). `go build` já usa `-pgo=auto` (padrão) e aplica *inlining*/devirtualização guiados pelo perfil.
4. Confirme: `go version -m ./bin/app | grep pgo` mostra `build -pgo=.../default.pgo`. Para comparar: `go build -pgo=off`.
5. **Meça** (benchmark/carga) — o ganho típico documentado é de 2–14%, mas depende do perfil e do código; em programas já sem chamadas quentes via interface/funções pequenas o ganho pode ser nulo (num teste sintético nosso, não houve diferença mensurável). Renove o perfil a cada mudança relevante de código.

Custos: build um pouco mais lento; o perfil pode "envelhecer" (refaça periodicamente). Nunca use perfil de um ambiente que não representa produção.

## 4. Telemetria contínua do runtime (`runtime/metrics`)

Métricas estáveis e baratas (leia com `metrics.Read`, exporte para Prometheus/OTel):

| Métrica | Uso |
|---|---|
| `/gc/heap/live:bytes` | heap vivo após o último GC — base para dimensionar `GOMEMLIMIT` |
| `/gc/gogc:percent`, `/gc/gomemlimit:bytes` | configuração efetiva do GC |
| `/cpu/classes/gc/total:cpu-seconds` | CPU gasta no GC (compare com CPU total) |
| `/sched/pauses/total/gc:seconds` | histograma de pausas de GC (`/gc/pauses:seconds` está deprecada) |
| `/sched/latencies:seconds` | tempo que goroutines esperam para rodar (saturação de CPU) |
| `/sched/goroutines:goroutines` (+ `/runnable`, `/waiting` no 1.26) | tendência = vazamento? |
| `/sched/gomaxprocs:threads`, `/memory/classes/total:bytes` | validação de container-awareness e RSS |

`GODEBUG=gctrace=1` imprime uma linha por ciclo, ex.: `gc 4 @0.023s 9%: 0.081+1.1+0.004 ms clock, ..., 3->4->1 MB, 4 MB goal, ... 2 P` —
`9%` = fração de CPU gasta em GC desde o início; `3->4->1 MB` = heap no início → no fim → vivo; `4 MB goal` = meta do próximo ciclo; `2 P` = processadores.

## 5. Checklist de uma investigação

- [ ] Meta e métrica definidas; medição-base salva (arquivo `old.txt` + perfil `.pb.gz`).
- [ ] Perfil de CPU **e** de alocação examinados; causa explicada em uma frase.
- [ ] Uma mudança por vez; `benchstat` (tempo, B/op, allocs/op) com `p<0.05`.
- [ ] Teste de equivalência + `-race`; carga ponta a ponta (p99, CPU, RSS).
- [ ] pprof só em interface interna; nenhum perfil com dados sensíveis commitado.
