# Catálogo de erros Go — mensagem → causa → checagem → correção

> Autoral (Squad AI). As mensagens abaixo foram **capturadas do toolchain Go 1.27.1** (caminhos abreviados). Wording pode variar um pouco entre versões — compare com a sua saída.
> Use junto com o protocolo do `error-investigator`: classifique, **colete evidência**, diagnostique, só então corrija.

## 1. Erros de compilação (`go build` / `go vet`)

```text
./main.go:5:2: "os" imported and not used
./main.go:9:2: declared and not used: x
./main.go:10:17: cannot use 10 (untyped int constant) as string value in variable declaration
./main.go:11:14: undefined: undefinedVar
```

| Mensagem | Causa provável | Correção |
|---|---|---|
| `"pkg" imported and not used` / `declared and not used: x` | O compilador Go **proíbe** import e variável sem uso | Remova; se o uso é temporário, `_ = x` com comentário (e remova depois). `goimports` automatiza |
| `undefined: strings` | Falta o `import` (ou o símbolo está em outro pacote/arquivo com build tag) | Adicione o import; confira `//go:build` e sufixos `_linux.go`/`_test.go` |
| `assignment mismatch: 1 variable but f returns 2 values` | Ignorou o retorno `error` | `x, err := f(); if err != nil { ... }` — **nunca** `x, _ :=` sem motivo |
| `cannot use T{} (value of struct type T) as Stringer value ...: T does not implement Stringer (method String has pointer receiver)` | Método com receptor **ponteiro**; o valor `T` não o tem no conjunto de métodos | Use `&T{}` (ou mude o receptor se for consistente com os demais métodos) |
| `cannot use x (variable of type int) as float64 value` | Go não faz conversão numérica implícita | Converta explicitamente `float64(x)` — atenção a perda de precisão |
| `missing return` | Algum ramo termina sem `return` | Retorne em todos os ramos; `panic` só para o inatingível |
| `invalid operation: mismatched types` | Operandos de tipos nomeados diferentes (`time.Duration` × `int`) | Converta: `time.Duration(n) * time.Second` |
| `generic method requires go1.27 or later (-lang was set to go1.24; check go.mod)` · `new(len("abc")) requires go1.26 or later (...)` | Recurso novo com a diretiva `go` do módulo mais antiga | Suba `go` (e o toolchain) **ou** use a alternativa compatível (função genérica de pacote; variável + `&`). `method must have no type parameters` indica ferramenta/`gofmt` antigo lendo código 1.27 |
| `errors.AsType requires go1.26 or later (module is go1.24)` (vem do `go vet`, vet `stdversion`) | API da stdlib mais nova que o módulo | Suba o `go` do módulo ou use `errors.As` |
| `use of internal package ... not allowed` | Import de `internal/` fora da árvore do módulo | Mova o código para dentro da árvore ou exponha uma API pública |

Vários erros de uma vez? Corrija **o primeiro** e recompile: ele costuma gerar os seguintes. `go build -gcflags=-e` mostra **todos** os erros (padrão limita a 10).

### `go vet` (saída real)

```text
main.go:10:12: use passes lock by value: e/v1.S contains sync.Mutex
main.go:14:6: call of use copies lock value: e/v1.S contains sync.Mutex
main.go:15:14: fmt.Printf format %d has arg "texto" of wrong type string
```

`copylocks` (copiou `Mutex`/`WaitGroup`: passe ponteiro), `printf` (formato × argumento), `loopclosure` (antes do 1.22), `waitgroup` (`Add` dentro da goroutine), `hostport` (`Sprintf` para endereço → `net.JoinHostPort`),
`stdversion` (símbolo da stdlib mais novo que o `go` do módulo), `lostcancel` (`cancel` de `WithTimeout` não chamado). **Nunca** desligue o vet para "passar".

## 2. Módulos, toolchain e dependências

```text
go: go.mod requires go >= 1.99 (running go 1.24.7; GOTOOLCHAIN=local)
main.go:2:8: missing go.sum entry for module providing package golang.org/x/sync/errgroup (imported by e/m2); to add:
        go get e/m2
main.go:2:8: no required module provides package github.com/google/uuid; to add it:
        go get github.com/google/uuid
package e/m4
        imports e/m4/a from main.go
        imports e/m4/b from a.go
        imports e/m4/a from b.go: import cycle not allowed
go: warning: "./..." matched no packages          (build constraint `//go:build windows` num build em Linux)
main.go:2:8: package nao/existe/pkg is not in std (...)
```

| Mensagem | Causa provável | Checagem | Correção |
|---|---|---|---|
| `go.mod requires go >= X (running go Y; GOTOOLCHAIN=local)` | Toolchain instalado é mais antigo que o `go` do módulo e o download automático está desligado | `go version`, `go env GOTOOLCHAIN` | Atualize o Go da imagem/CI **ou** deixe `GOTOOLCHAIN=auto`; alinhe a imagem `golang:X` ao `go.mod` |
| `missing go.sum entry for module providing package …` | `go.sum` sem o hash (clone parcial, merge) | `git diff go.sum` | `go mod download` / `go mod tidy`; **commite** `go.sum` |
| `no required module provides package P` | Import sem `require` no `go.mod` | `go list -m all \| grep …` | `go get P@versão` (confirme o módulo e a versão: typosquatting!) |
| `package P is not in std` | Caminho sem domínio (parece stdlib) ou typo | conferir o import | Use o caminho completo do módulo |
| `updates to go.mod needed` | `go.mod` inconsistente com os imports (modo `-mod=readonly`) | `go mod tidy -diff` | `go mod tidy` e revise o diff |
| `import cycle not allowed` | A→B→A | `go list -deps` | Extraia o tipo compartilhado p/ pacote C, ou inverta por interface **no consumidor** |
| `build constraints exclude all Go files in …` / `matched no packages` | `//go:build`/sufixo de arquivo/`GOOS`/`GOARCH`/`CGO_ENABLED` excluem tudo | `go list -f '{{.GoFiles}} {{.IgnoredGoFiles}}'` | Ajuste a tag/GOOS ou adicione arquivo para a plataforma |
| `verifying module: checksum mismatch` / `SECURITY ERROR` | Conteúdo do módulo difere do registro público (sumdb) | `go mod verify`; compare proxy/versão | **Não contorne** (`GONOSUMDB`, `GOINSECURE`): investigue adulteração, troque a versão, reporte |
| `go: finding module for package` demora/falha | Proxy/rede/GOPRIVATE | `go env GOPROXY GOPRIVATE GONOSUMDB`; `curl` ao proxy interno | Configure `GOPRIVATE=git.empresa/*`, credenciais (`.netrc`/token), proxy acessível |
| `ambiguous import: found package P in multiple modules` | Dois módulos fornecem o mesmo caminho | `go mod graph \| grep P` | Remova/atualize um deles; `replace` só em dev local |
| `invalid version: unknown revision` / `404 Not Found` | Tag inexistente/repositório privado/rename | `git ls-remote`; `go list -m -versions M` | Versão correta; autenticação; `GOPRIVATE` |
| `gcc: executable file not found` / `cgo: C compiler "gcc" not found` | cgo habilitado sem toolchain C | `go env CGO_ENABLED CC` | Instale `gcc` na imagem de build **ou** `CGO_ENABLED=0` com alternativa pura em Go |

Regras de higiene ao mexer em módulos: mostre o `git diff go.mod go.sum` antes de seguir; **não** use `replace` permanente; **não** rode `go get -u ./...` como "conserto"; rode `govulncheck ./...` depois de mudar dependências.

## 3. Panics e `fatal error` em execução

| Saída (real) | O que significa | Causa típica → correção |
|---|---|---|
| `panic: assignment to entry in nil map` | Escrita em `map` nil | `m := make(map[K]V)` no construtor/zero-value útil |
| `panic: runtime error: invalid memory address or nil pointer dereference` + `[signal SIGSEGV ...]` | Desreferência de ponteiro/interface nil | Erro ignorado antes (`x, _ :=`)? Campo/`struct` não inicializado? Dependência nil injetada? Cheque o 1º frame do **seu** código |
| `panic: runtime error: index out of range [5] with length 3` | Índice fora do slice | Valide o tamanho; `for range`; cuidado com `len` vs `cap` e fatias de fatias |
| `panic: runtime error: slice bounds out of range [:n] with capacity m` | Fatiamento inválido | Valide `0 ≤ low ≤ high ≤ cap` |
| `panic: interface conversion: interface {} is string, not int` | Type assertion sem `, ok` | `v, ok := x.(int)` ou `switch x := x.(type)` |
| `panic: sync: negative WaitGroup counter` | `Done` chamado mais vezes que `Add` (ex.: `Done` duplicado no ramo de erro e no `defer`) | `wg.Go` (1.25) ou `Add` antes do `go` |
| `panic: close of closed channel` / `send on closed channel` | Dono do canal errado | Só o produtor fecha, uma vez (`sync.Once`/estrutura) |
| `fatal error: all goroutines are asleep - deadlock!` + `goroutine 1 [chan send]` | Todas bloqueadas (aqui: envio sem receptor) | Receptor ausente, `Wait` sem `Done`, lock cíclico → grafo de espera (**go-concurrency-expert**) |
| `fatal error: concurrent map writes` | Escritas concorrentes em `map` (não recuperável) | `Mutex`/`sync.Map`/dono único; **rode `-race`** |
| `runtime: goroutine stack exceeds 1000000000-byte limit` + `fatal error: stack overflow` | Recursão sem caso-base/ciclo | Caso-base; iteração; detectar ciclos (grafos) |
| `panic: test timed out after 2s` + `running tests: TestHang (2s)` | Teste pendurado (deadlock/espera sem timeout) | Leia as goroutines `[chan receive]`/`[select]`; **não** aumente o `-timeout` — ache o bloqueio |
| `fatal error: unexpected signal`/`SIGSEGV` com cgo/`unsafe` | Memória corrompida | Revise `unsafe`/cgo; `-race`; `cgocheck=1` já é o padrão — a checagem completa exige recompilar com `GOEXPERIMENT=cgocheck2`; isole |
| `signal: killed` / `exit status 137` | OOMKill | `GOMEMLIMIT`, vazamento, limites (**go-performance-engineer**) |

**Anatomia da pilha (real):**

```text
panic: runtime error: index out of range [5] with length 3

goroutine 1 [running]:
main.main()
	/.../p3/main.go:6 +0x9
exit status 2
```

`goroutine 1 [running]` = a goroutine que entrou em pânico; a 1ª linha `arquivo:linha` fora de `runtime`/stdlib é o ponto no **seu** código. `exit status 2` = pânico não tratado. `goroutine N [chan receive, 12 minutes]` em dumps mostra espera longa (vazamento/deadlock).

### Armadilhas clássicas que parecem outro erro

- **`error` nil que não é nil:** `func f() error { var e *MyErr; return e }` devolve interface **não nula** (tipo `*MyErr`, valor nil) — `if err != nil` dispara. Retorne `nil` literal.
- **Sombreamento (`:=` em escopo interno):** `err` declarado de novo dentro do `if`/`for` esconde o externo; o erro "some". o analisador `shadow` (x/tools, via `go vet -vettool` ou `golangci-lint` `govet: shadow`) ajuda; o staticcheck não tem check de sombreamento.
- **`defer` em laço:** acumula até a função retornar (descritores/locks abertos) — extraia função por iteração.
- **Fatia compartilhada:** `append` em subslice sobrescreve o array original. Copie com `slices.Clone`.
- **Closure e variável de laço:** corrigido no Go 1.22+ (por iteração) — em módulo com `go < 1.22` o bug **existe**; confira o `go.mod`.
- **`time.After` em laço / `Ticker` sem `Stop`:** só vaza em módulo com `go` < 1.23 (ou `Ticker` ainda referenciado); em `go ≥ 1.23` o timer sem referência é coletado e resta o custo de alocação por iteração. `defer t.Stop()` continua sendo boa prática.
- **`http.Response.Body` não fechado/ não lido:** conexões não reutilizadas, descritores esgotados.
- **`json` não preenche campo:** campo não exportado (minúscula) ou tag errada (`json:"name"`); `omitempty` x `omitzero`.

## 4. Falhas de teste (receitas)

| Sintoma | Investigue | Ação |
|---|---|---|
| Passa local, falha no CI | `go version`, `-race`, `-count`, `-shuffle`, variáveis de ambiente, fuso/locale, relógio, paralelismo da máquina, dependência de ordem | Reproduza com o **comando exato do CI** (`-race -shuffle=on -count=1`) |
| Falha 1 em N execuções | corrida, tempo real, `Sleep`, porta fixa, estado global | `go test -race -count=200 -shuffle=on -cpu=1,2,8`; `synctest` |
| `(cached)` esconde problema | cache de resultado | `-count=1` |
| `WARNING: DATA RACE` | leitura+escrita sem sincronização | ver **go-concurrency-expert** §1 |
| Falta teste de integração | `-tags=integration` não passado | rode com a tag; documente |
| Golden diferente | mudança legítima? ordem de mapa? | `-update` + revisar o diff; saída determinística |
| `TestMain` falha por goroutine vazada (`goleak`) | goroutine sem término | corrija a causa (não `IgnoreTopFunction` por reflexo) |

## 5. Heurísticas (seed — acrescente as recorrentes do seu projeto)

1. Erro de compilação em cascata ⇒ olhe **só o 1º**.
2. "Funciona local, falha no CI" ⇒ versão do Go/`GOFLAGS`/`GOTOOLCHAIN`/`go.work`/cache diferentes.
3. `nil pointer` logo após uma chamada ⇒ procure o `err` ignorado na linha anterior.
4. Goroutine/memória crescendo ⇒ vazamento: `goroutineleak` + `pprof goroutine`.
5. Latência alta com CPU baixa ⇒ espera (lock/canal/I-O): perfis `block`/`mutex`/`trace`.
6. `context deadline exceeded` ⇒ identifique **qual** prazo venceu (cliente, servidor, dependência) antes de aumentar timeouts.
7. Erro só em contêiner ⇒ CA/tzdata ausentes (`scratch`), usuário não-root, FS somente leitura, limites de memória/CPU, DNS.
8. Muda o resultado após `go get -u` ⇒ `go mod graph`/diff de `go.sum`; fixe a versão e abra issue.
