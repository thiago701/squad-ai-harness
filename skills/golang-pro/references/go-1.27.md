# Go 1.27 — fatos de versão (verificado out/2026)

> Fontes: go.dev/doc/go1.27 · go.dev/doc/go1.26 · go.dev/doc/go1.25 · go.dev/doc/devel/release ·
> toolchain 1.27.1 real (cada trecho de código desta página foi compilado/executado).
> Texto reescrito pela Squad AI; nenhuma passagem copiada. Revalide a cada release menor.

## Linha do tempo e suporte

| Release | Data | Último patch (out/2026) | Situação |
|---|---|---|---|
| Go 1.27 | 2026-08-19 | 1.27.1 | **Atual** — recomendada para código novo |
| Go 1.26 | 2026-02-10 | 1.26.8 | Suportada (segunda major mais recente) |
| Go 1.25 | 2025-08 | 1.25.14 | **Fora da janela** — sem novas correções de segurança; recomende subir |

O Go mantém correções de segurança para as **duas** últimas majors, com cadência semestral
(fev/ago). Não há LTS formal; a linha de produção segura é "a major atual ou a anterior".
`go.mod` com `go 1.27` e `toolchain go1.27.1` faz o `go` baixar o compilador certo sozinho.

## Go 1.27 — o que muda a forma de escrever

**Linguagem**
- **Métodos genéricos:** um método pode declarar os próprios type parameters
  (`func (b *Box) Map[T any](f func(string) T) []T`). Limites: métodos de **interface** não podem ser
  genéricos e um método genérico não satisfaz interface. Já usado em `(*rand.Rand).N` (`math/rand/v2`).
- **Chaves de struct literal** podem ser qualquer *field selector* válido, não só o campo de 1º nível.
- **Inferência de tipo generalizada** ao atribuir/converter função genérica para tipo função.

**Biblioteca padrão**
- **`encoding/json/v2` estável** (+ `encoding/json/jsontext`). `encoding/json` (v1) passa a ser
  *implementado sobre* a v2; APIs v2 (import path `encoding/json/v2`; `MarshalWrite`/`UnmarshalRead`/`RejectUnknownMembers` não existem na v1): `Marshal`, `MarshalWrite`, `MarshalEncode`, `Unmarshal`,
  `UnmarshalRead`, `UnmarshalDecode`, todas com `...Options`. Padrões mais estritos que a v1:
  rejeita UTF-8 inválido e **nomes duplicados** em objeto. `Unmarshal` bem mais rápido; `Marshal` em paridade.
  `GOEXPERIMENT=nojsonv2` restaura a implementação v1 original (e remove o pacote `encoding/json/v2` do build): serve só para isolar incompatibilidades do `encoding/json` v1, não para código que já importa a v2. Removidos durante o experimento: opções de tag
  `format` e `unknown`, `DiscardUnknownMembers`, `SkipFunc`; `inline` virou `embed`.
- **`uuid`** — pacote novo na stdlib (import path `uuid`; `uuid.New()`, `uuid.NewV7()`, parse/format).
- **`crypto/mldsa`** (ML-DSA, FIPS 204, pós-quântico), integrado a `crypto/x509` e TLS 1.3;
  `MLKEM1024` em `crypto/tls`. `tls.Config.Rand` ficou *deprecated* (use `testing/cryptotest.SetGlobalRandom`).
- **Testes:** `testing/synctest.Sleep` (= `time.Sleep` + `synctest.Wait`), `httptest.NewTestServer`
  (servidor numa rede **em memória**, ideal dentro de bolha `synctest`), `go test` roda o vet
  `stdversion` por padrão (acusa símbolo da stdlib mais novo que a versão do `go.mod`).
- `net/http`: `Server.MaxHeaderValueCount`; HTTP/2 aceita sinais de prioridade (RFC 9218; desligue com
  `Server.DisableClientPriority`); `Response.Body` HTTP/1 **drena o restante no `Close`** (até um limite)
  para reaproveitar conexão.
- Pequenas: `strings.CutLast`/`bytes.CutLast`, `net/url.URL.Clone`/`Values.Clone`, `math/big.Int.Divide`,
  `hash/maphash.Hasher`/`ComparableHasher`, `database/sql.ConvertAssign`, `unicode` 17.
- **Experimentais** (não use em produção): `simd`, `simd/archsimd` (`GOEXPERIMENT=simd`).

**Runtime / ferramentas**
- **Perfil `goroutineleak`** estável: `pprof.Lookup("goroutineleak")` e `/debug/pprof/goroutineleak`.
  Usa o GC para achar goroutines bloqueadas em primitivas inalcançáveis (canal, `Mutex`, `Cond`…).
  Limite: pode não achar vazamento preso a variável global.
- **Tracebacks incluem labels de `runtime/pprof`** no cabeçalho da goroutine (módulos com `go 1.27+`;
  desligue com `GODEBUG=tracebacklabels=0`).
- **Alocação mais barata:** rotinas especializadas por tamanho (<80 B até ~30% mais baratas; ~1% geral;
  +~60 KB de binário; `GOEXPERIMENT=nosizespecializedmalloc`).
- `go fix` ganhou modernizadores `atomictypes`, `embedlit`, `slicesbackward`, `unsafefuncs`; `waitgroup`
  foi renomeado `waitgroupgo`. `go mod tidy` com `go 1.27+` consolida em no máximo 2 blocos `require`.
- `go vet` (printf): acusa `%w` com `*E` quando `E` implementa `error`. `go tool trace -http=:PORTA`
  agora escuta só em *localhost*. `go doc pkg@versão` e `go doc -ex`.
- **GODEBUG removidos:** `asynctimerchan` (canais de `time` sempre síncronos/sem buffer), `gotypesalias`,
  `tlsunsafeekm`, `tlsrsakex`, `tls3des`, `tls10server`, `x509keypairleaf`. Se o `go.mod` ainda os fixa
  num valor antigo, o `go` falha: remova a linha.
- Portes: **macOS 13+** obrigatório; `ppc64` Linux passa a ELFv2.

## Go 1.26 (fev/2026) — já estável

- **Green Tea GC por padrão**: ~10–40% menos overhead de GC em cargas alocação-intensivas (+~10% em CPUs
  com vetores AVX-512/Zen 4+). Desligue com `GOEXPERIMENT=nogreenteagc` só para comparar.
- **`new(expr)`**: `Age: new(yearsSince(born))` — ponteiro opcional sem variável auxiliar.
- **Constraints auto-referentes**: `type Adder[A Adder[A]] interface{ Add(A) A }`.
- **`errors.AsType[T](err)`**: versão genérica e tipada de `errors.As` (sem ponteiro-para-ponteiro).
- **`go fix` reescrito** como conjunto de *modernizers* (rode após subir a versão do `go.mod`).
- `log/slog.NewMultiHandler`; `bytes.Buffer.Peek`; `io.ReadAll` ~2× mais rápido; `os/signal.NotifyContext`
  cancela com *cause* (`context.Cause` mostra o sinal); `testing`: `T.ArtifactDir`; `reflect` com
  iteradores (`Type.Fields`, `Value.Methods`…); cgo ~30% mais barato; mais backing stores de slice na pilha.
- Cripto: `crypto/hpke` (RFC 9180), `crypto/mlkem/mlkemtest`, híbrido pós-quântico `X25519MLKEM768` **ligado por padrão** no TLS desde o 1.24 (o 1.26 acrescentou `SecP256r1MLKEM768` e `SecP384r1MLKEM1024`).
- `go mod init` agora grava `go 1.(N-1).0` (de propósito: compatibilidade). Em módulo novo, **suba para a versão atual**.
- Experimentais: `runtime/secret` (apagamento de temporários criptográficos), `simd/archsimd`.

## Go 1.25 (ago/2025) — base do que se usa hoje

- **`GOMAXPROCS` ciente de cgroup** (limite de CPU do contêiner) e reajustado dinamicamente; `runtime.NumCPU()`
  continua vendo os cores do nó.
- **`testing/synctest`** estável: `synctest.Test(t, func(t *testing.T){ ... synctest.Wait() })`, relógio virtual por bolha.
- **`sync.WaitGroup.Go(f)`**, `runtime/trace.FlightRecorder`, `http.CrossOriginProtection` (defesa CSRF por
  `Sec-Fetch-Site`/`Origin`), `slog.GroupAttrs`, `os.Root` ampliado, `testing.T.Attr`.
- Vet novos: `waitgroup` (Add dentro da goroutine) e `hostport` (`fmt.Sprintf("%s:%d")` para endereço → use `net.JoinHostPort`).
- Green Tea e `json/v2` entraram como **experimentos** (hoje já estáveis/padrão).

## Armadilhas de migração

| Risco | Como tratar |
|---|---|
| `json/v2` é mais estrito (nomes duplicados, UTF-8 inválido) e tem outros defaults (`nil` slice → `[]`) | Rode a suíte de contrato/golden; ajuste com opções/tags (`omitempty`/`omitzero`); para o `encoding/json` v1 já sobre a v2, `GOEXPERIMENT=nojsonv2` isola regressões **temporariamente** (não ajuda quem importa a v2) |
| Green Tea muda o perfil de pausa do GC | Re-benchmarke p99/p999 antes de afirmar ganho; compare com `GOEXPERIMENT=nogreenteagc` |
| `asynctimerchan` removido | Módulos com `go` < 1.23 ainda tinham canais de `Timer`/`Ticker` com buffer; agora são sempre síncronos. Código que drenava o canal após `Stop`/`Reset` deixa de precisar disso — revise esperas baseadas em `len(t.C)` |
| Método genérico não satisfaz interface | Não migre interfaces para genéricos "porque dá": mantenha a interface concreta |
| `go.mod` fixa `godebug` removido | Delete a entrada/`//go:debug` correspondente |
| `go test` falha no vet `stdversion` | Eleve `go` no `go.mod` **ou** troque a API (não suprima o vet) |
| Cripto pós-quântica nova | Nunca implemente o seu: use `crypto/mlkem`, `crypto/mldsa`, `crypto/hpke` |

## Verificação rápida da instalação

```bash
go version                         # go1.27.1 ou superior
go env GOTOOLCHAIN GOFLAGS         # confirme que o toolchain automático está ativo
go list -m -versions go | tr ' ' '\n' | tail -3
```
