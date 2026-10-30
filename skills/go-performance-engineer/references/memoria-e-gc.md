# Memória, alocação e GC em Go (1.26/1.27)

> Autoral (Squad AI). Saídas de `-gcflags=-m`, `gctrace` e `benchstat` foram capturadas no Go 1.27.1. Revalide ao trocar de versão: o compilador evolui rápido.

## 1. Como o GC do Go se comporta (modelo mental)

- Coletor **concorrente, não-moving**, baseado em marcação e varredura; as pausas *stop-the-world* são curtas (sub-milissegundo na prática); o custo real é a **CPU de marcação**
  e o *GC assist* (a própria goroutine ajudando quando aloca rápido demais).
- Custo do GC ≈ proporcional ao **heap vivo** (o que precisa ser percorrido), não ao lixo. Heap vivo grande + muita alocação ⇒ muitos ciclos caros.
- **Green Tea GC** (padrão desde 1.26): organiza a marcação por *spans* de memória, melhorando localidade de cache; reduz 10–40% do overhead de GC em cargas alocação-intensivas
  (e ~10% extra em CPUs com vetorização AVX-512/Zen 4+). Como todo ganho de GC, **depende da carga**: compare com `GOEXPERIMENT=nogreenteagc` no seu serviço.
- Alocação pequena ficou mais barata no 1.27 (rotinas especializadas por tamanho; <80 B até ~30% mais baratas; ~1% geral; binário +~60 KB).

## 2. Alavancas de configuração

| Variável | Efeito | Regra prática |
|---|---|---|
| `GOGC` (padrão 100) | Dispara GC quando o heap cresce `GOGC`% sobre o vivo | Subir (200–400) troca memória por CPU; só com folga de RAM |
| `GOMEMLIMIT` (1.19+) | Teto **suave** de memória total do runtime; GC fica mais agressivo perto do limite | Em contêiner, ~90% do limite do cgroup (80–95% conforme a memória fora do runtime). O runtime **não** deduz isto sozinho do cgroup |
| `GOGC=off` + `GOMEMLIMIT` | Só coleta ao chegar no limite | Apenas quando o heap vivo é pequeno e estável; teste de carga obrigatório |
| `GOMAXPROCS` | Nº de P | Já ciente de cgroup desde 1.25; fixar só com medição |
| `GODEBUG=gctrace=1` | Uma linha por ciclo | Diagnóstico pontual; não deixe ligado sem necessidade |

Dimensionamento: `limite do contêiner` ≥ `heap vivo (/gc/heap/live:bytes)` × (1 + GOGC/100) + pilhas + buffers de I/O + folga. Defina `GOMEMLIMIT` abaixo do limite para o GC reagir **antes** do *OOMKill*.
O limite considera o que o runtime gerencia (heap, pilhas, metadados), mas **não** vê memória de cgo/C nem `mmap` externo, e é suave (o limitador de CPU do GC impede espiral, então não garante contra OOMKill). O gc-guide sugere 5–10% de folga.

`gctrace` (linha real, comentada):

```text
gc 4 @0.023s 9%: 0.081+1.1+0.004 ms clock, 0.16+1.0/0.13/0+0.009 ms cpu, 3->4->1 MB, 4 MB goal, 0 MB stacks, 0 MB globals, 2 P
   │     │    │         └ pausa(STW)+marcação concorrente+pausa    └ heap: início→fim→vivo        └ meta do próximo ciclo
   │     │    └ 9% da CPU total do processo foi GC desde o início
   │     └ momento do ciclo
   └ nº do ciclo
```

Sinal de alerta: GC > ~10–25% da CPU com heap vivo pequeno ⇒ **taxa de alocação** alta (reduza alocações antes de mexer em `GOGC`).

## 3. Escape analysis — o que vai para o heap

```bash
go build -gcflags='-m' ./pkg 2>&1 | grep -E 'escapes|moved to heap|does not escape'
# -m=2 explica o porquê (cadeia de fluxo)
```

Saída real do Go 1.27.1 sobre um arquivo de teste:

```text
esc.go:9:19:  moved to heap: p                  ← ByPtr(): retorna &p; o dado sobrevive à função
esc.go:12:32: n escapes to heap                  ← Boxed(n): int convertido em `any` (boxing)
esc.go:16:11: make([]int, n) does not escape     ← Sum(n): slice local de tamanho dinâmico ficou na pilha
```

Lições: (1) **retornar ponteiro** para variável local, guardá-la em interface/closure que sobrevive, ou enviá-la a canal ⇒ heap; (2) conversão para `interface`/`any` costuma alocar (boxing);
(3) desde o 1.25/1.26 o compilador coloca na pilha **mais** `make([]T, n)` de tamanho dinâmico (abaixo de um limite pequeno) — **não presuma**, leia o `-m` da sua versão;
(4) valor pequeno passado **por valor** é frequentemente mais barato que ponteiro (sem alocação, melhor localidade); (5) `fmt.Sprintf`/`fmt.Println` fazem seus argumentos escaparem.
Não "otimize" um escape que não aparece no perfil de `alloc_space`.

## 4. Redução de alocação — receitas (com ganho medido)

Caso real (função que agrega 5.000 linhas), `benchstat -count=6` (indicativo; use ≥10):

| Versão | tempo/op | B/op | allocs/op |
|---|---|---|---|
| Lenta (`Sprintf` em laço, `map` sem tamanho, `+=` em string) | 524 µs | 114 KiB | 10.211 |
| Rápida (`strconv`/`Builder.Grow`, `make(map, n)`, `slices.Sort`) | 65 µs | 5,3 KiB | 55 |

Receitas, por ordem de custo/benefício:

1. **Pré-dimensione**: `make([]T, 0, n)`, `make(map[K]V, n)`, `strings.Builder` + `Grow(n)`, `bytes.Buffer` + `Grow`.
2. **Evite `fmt` no caminho quente**: `strconv.AppendInt`/`Itoa`, `Builder`, `append` de bytes; `fmt` fica para logs/erros.
3. **Reuse sem pool**: declare o buffer fora do laço e `buf = buf[:0]`; passe `dst []byte` para funções `AppendX` (padrão `strconv.Append*`, `time.AppendFormat`).
4. **Evite boxing**: não use `any` em contêiner quente; use genéricos ou tipo concreto.
5. **Interning**: `unique.Make(s)` (1.23) deduplica strings/valores repetidos (labels, nomes) e permite comparar por ponteiro.
6. **Referências fracas e limpeza** (1.24): `weak.Pointer[T]` para caches que não devem segurar o objeto; `runtime.AddCleanup(ptr, f, arg)` (substitui `SetFinalizer`, mais seguro) — **não** use para liberar recurso crítico (ordem/tempo não garantidos).
7. **`sync.Pool`** — só para objetos temporários **caros** e **homogêneos**, com `Reset` e sem reter dados sensíveis; o GC esvazia o pool; medir é obrigatório. Nunca devolva `buf.Bytes()` de um buffer que volta ao pool (copie, ex.: `b.String()`).
8. **Fatias que seguram arrays gigantes**: `s = s[:n]` mantém o array inteiro vivo; copie (`slices.Clone`) o trecho pequeno que precisa persistir.

## 5. Vazamentos "lógicos" de memória (heap vivo só cresce)

| Causa | Como achar | Correção |
|---|---|---|
| Goroutines presas (cada uma segura pilha + referências) | perfil `goroutineleak` / `goroutine` | ver **go-concurrency-expert** |
| Mapa/cache sem expiração | `heap` `inuse_space` apontando para o cache | limite de tamanho + TTL/LRU; `weak` se aplicável |
| `append` em slice global; subslice segurando array grande | `heap` + `list` | copiar o necessário; limpar com `clear`/`nil` |
| `time.After` em laço quente (alocação por iteração; vazamento só em `go` < 1.23) / `Ticker` sem `Stop` | `allocs`/`heap` mostram timers | `NewTimer` + `Stop`/`Reset`; `defer t.Stop()` |
| `http.Response.Body` sem `Close`; `sql.Rows` sem `Close` | `goroutine` com leitura de rede presa | `defer resp.Body.Close()` / `defer rows.Close()` |

Para provar vazamento: dois `heap` com minutos de diferença e `go tool pprof -diff_base=antes.pb.gz depois.pb.gz` — o que **cresceu** é o suspeito.

## 6. Layout de dados e CPU

- **Slice de structs** (AoS) com campos acessados juntos; **struct de slices** (SoA) quando o laço toca um campo só — melhor uso de cache.
- Ordene campos de struct do maior para o menor alinhamento para reduzir *padding*; o analisador `fieldalignment` (via `golang.org/x/tools`) sugere. Só vale em estruturas com milhões de instâncias.
- Evite falso compartilhamento: contadores `atomic` escritos por vários núcleos na **mesma linha de cache (64 B)** degradam — separe-os (padding) ou agregue por goroutine.
- Remova *bounds checks* só se o perfil mostrar; reescreva o laço (`for i := range s`, subslice prévio) antes de pensar em `-gcflags=-B`.
