# Padrões de otimização em Go — I/O, rede, banco, serialização, concorrência

> Autoral (Squad AI). Aplique **depois** de medir (`profiling-e-benchmarks.md`). Cada item diz *quando vale* e *como provar*.

## 1. Serialização (JSON e afins)

- `encoding/json/v2` (estável no 1.27; o `encoding/json` v1 já roda sobre ele) tem `Unmarshal` **bem mais rápido** que o v1 e `Marshal` em paridade. Migrar costuma ser o ganho "grátis" mais alto em APIs JSON — com o cuidado de estrito/defaults (ver `golang-pro/references/go-1.27.md`).
- Streaming (import path `encoding/json/v2`; não existem na v1): `json.UnmarshalRead(r, &v)` / `json.MarshalWrite(w, v)` / `jsontext` evitam materializar o corpo inteiro; limite o tamanho de entrada (`http.MaxBytesReader`).
- Evite `map[string]any` em caminho quente: use structs tipadas (menos alocação, validação grátis).
- Protobuf/gRPC ou formatos binários só se o perfil mostrar JSON dominante **e** o contrato permitir (P1).
- Compressão: `gzip` custa CPU — vale para payload grande e rede lenta; meça (zstd via lib de terceiros só com auditoria).

## 2. HTTP cliente e servidor

| Ponto | Prática |
|---|---|
| Reuso de conexão | **Um** `http.Client`/`Transport` por destino (global ou injetado). `defer resp.Body.Close()` e **leia/descarte** o corpo (o 1.27 já drena um limite no `Close` do HTTP/1 para reaproveitar a conexão) |
| Pool | `Transport.MaxIdleConnsPerHost` (padrão 2) costuma ser baixo para um destino de alto tráfego — calibre; `MaxConnsPerHost` para proteger o destino |
| Timeouts | `Client.Timeout` total + `Transport.TLSHandshakeTimeout`, `ResponseHeaderTimeout`, `IdleConnTimeout`; sempre ctx por requisição |
| Servidor | `ReadHeaderTimeout` etc.; `http.MaxBytesReader`; evite alocar por requisição em middleware (`sync.Pool` só com medição) |
| HTTP/2 | Habilitado por padrão em TLS; vigie `MaxConcurrentStreams`; o 1.27 aceita prioridades (RFC 9218) |
| Compressão/respostas grandes | `io.Copy`/`http.ServeContent` (sem carregar em memória); `Content-Length` quando conhecido |
| Observabilidade barata | `otelhttp` com amostragem; **não** logue corpo; métricas por rota (cardinalidade controlada) |

## 3. Banco de dados (`database/sql`/pgx)

- Gargalo típico **não é o Go**: é N+1, falta de índice, transação longa, pool mal dimensionado. Use `EXPLAIN (ANALYZE)` antes de mexer no código.
- Pool: `db.SetMaxOpenConns(n)` (≤ conexões que o banco aguenta ÷ nº de réplicas), `SetMaxIdleConns`, `SetConnMaxLifetime`/`SetConnMaxIdleTime`. Exponha `db.Stats()` (`WaitCount`, `WaitDuration`) — espera alta = pool pequeno **ou** consultas lentas.
- Sempre `QueryContext` com ctx e timeout; fechar `Rows` (`defer rows.Close()`; checar `rows.Err()`).
- Lote: `INSERT` multi-linha/`COPY` (pgx `CopyFrom`) em vez de laço de `Exec`; *prepared statements* para consultas repetidas; `pgx` direto (sem `database/sql`) quando precisa de recursos nativos e menos overhead.
- Cache de leitura com expiração e invalidação **definida**; `singleflight` contra *stampede*.

## 4. I/O de arquivo e rede

- `bufio.Reader/Writer` para leituras/escritas pequenas e frequentes; `io.Copy` usa `ReaderFrom/WriterTo` (zero-copy quando possível: `sendfile` em Linux).
- `io.ReadAll` ficou ~2× mais rápido e usa ~50% menos memória (1.26), mas **continua** carregando tudo: prefira streaming para dados grandes.
- `os.ReadFile` para arquivos pequenos; `mmap` só com motivo (e cuidado com SIGBUS).
- Processamento por linha: `bufio.Scanner` (aumente `Buffer` se linhas grandes) ou `strings.Lines`/`bytes.Lines` (1.24, iteradores).

## 5. Strings, bytes e conversões

- `strings.Builder` (+ `Grow`) em vez de `+=` em laço; `strings.Cut`/`CutPrefix` e `CutLast` (1.27) fatiam sem alocar; `strings.SplitSeq`/`FieldsSeq` (1.24) iteram sem criar slice.
- `strconv.AppendInt(dst, n, 10)`, `time.Time.AppendFormat`, `fmt.Appendf` evitam strings intermediárias quando você já tem um `[]byte` destino.
- `bytes.Equal`/`strings.EqualFold` em vez de converter para comparar; `strings.Contains`/`Index` (implementação otimizada em assembly) antes de regex; `regexp` compile **uma vez** (var global) e evite em caminho quente.
- `[]byte`→`string` sem cópia exige `unsafe`: só com benchmark, e garantindo que o `[]byte` **nunca** mais muda.

## 6. Concorrência para desempenho (CPU-bound)

- Particione o trabalho em blocos grandes (granularidade ≥ dezenas de µs) — goroutine por item minúsculo perde para sequencial.
- `errgroup.SetLimit(runtime.GOMAXPROCS(0))`; evite compartilhar escrita: cada worker agrega localmente e um passo final combina (reduz contenção/false sharing).
- Meça escalabilidade com `go test -bench -cpu=1,2,4,8`: se não escala, procure lock/atomic compartilhado (perfil `mutex`) ou GC (muita alocação).
- Para I/O-bound, limite por **recurso externo** (conexões, taxa), não por CPU.

## 7. Compilação e binário

- `go build -trimpath -ldflags='-s -w'` reduz o binário (cold start e pull de imagem menores); mantenha uma build com símbolos para perfis.
- PGO (`default.pgo`) — ver `profiling-e-benchmarks.md`. `GOAMD64=v3` só se toda a frota é AVX2+; em AWS Lambda/Graviton use `GOARCH=arm64`.
- cgo: cada chamada tem custo fixo (~30% menor desde 1.26), mas ainda é caro em laço quente e quebra builds estáticos/cross-compile; isole e agrupe chamadas.
- Cold start de CLI/Lambda: evite `init()` pesado, carregue configuração preguiçosamente (`sync.OnceValue`), minimize dependências importadas (cada import inicializa).

## 8. Quando parar

Parou de aparecer no perfil? **Pare.** Ganho < 5% com aumento de complexidade? **Reverta.** Meta atingida e testes verdes? **Entregue** e documente o número. Otimização é um meio de cumprir requisito, não um hobby (P1 > P2).
