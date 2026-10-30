# Testes em Go — estratégia, padrões e ferramentas

> Autoral (Squad AI). Blocos com `package` foram compilados e executados com Go 1.27.1 (`-race`, `-shuffle`, fuzz).

## Pirâmide recomendada

1. **Unitários de tabela** (maioria): rápidos, determinísticos, sem rede/disco real.
2. **Concorrência determinística** com `testing/synctest` (relógio virtual) — nunca `time.Sleep` real.
3. **Integração** atrás de *build tag* (`//go:build integration`): banco/fila reais via contêiner efêmero (testcontainers ou docker compose); rodam no CI, não no `go test ./...` local.
4. **Fuzz** em parsers/validadores/decodificadores (superfície de entrada externa).
5. **Benchmarks** só onde há requisito de desempenho (→ `go-performance-engineer`).

Regra: o teste descreve **comportamento observável**, não a implementação. Prefira *fakes* escritos à mão a mocks gerados.

## Teste de tabela + subtests + paralelismo

```go
package tst

import (
	"errors"
	"testing"
)

func TestSlug(t *testing.T) {
	tests := []struct {
		name    string
		in      string
		want    string
		wantErr error
	}{
		{"simples", "Olá Mundo", "olá-mundo", nil},
		{"espaços extras", "  a   b ", "a-b", nil},
		{"vazio", "   ", "", ErrEmpty},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel() // seguro desde o Go 1.22: tc é por iteração
			got, err := Slug(tc.in)
			if !errors.Is(err, tc.wantErr) || got != tc.want {
				t.Fatalf("Slug(%q) = %q, %v; quer %q, %v", tc.in, got, err, tc.want, tc.wantErr)
			}
		})
	}
}
```

- Mensagem de falha com **entrada, obtido e esperado**. Use `t.Helper()` em auxiliares; `t.Cleanup`, `t.TempDir()`, `t.Setenv` (não use com `t.Parallel`).
- `t.Context()` (1.24) devolve um ctx cancelado **antes** dos `Cleanup` — ótimo para goroutines do teste.
- Comparação de structs: `cmp.Diff` (`github.com/google/go-cmp`) dá diff legível; `reflect.DeepEqual` só para casos simples.
- `testing.T.Attr` (1.25) anexa metadados à saída; `T.ArtifactDir` (1.26) guarda artefatos (golden, dumps) por teste.

## Concorrência e tempo: `testing/synctest`

```go
func TestBudget(t *testing.T) {
	synctest.Test(t, func(t *testing.T) { // goroutines e timers vivem numa "bolha"
		ctx, cancel := WithBudget(context.Background(), 5*time.Second)
		defer cancel()
		synctest.Sleep(6 * time.Second) // 1.27: Sleep + Wait; 1.25/1.26: time.Sleep + synctest.Wait()
		if context.Cause(ctx) != ErrBudget {
			t.Fatalf("causa = %v", context.Cause(ctx))
		}
	})
}
```

- O relógio só avança quando **todas** as goroutines da bolha estão *durably blocked*. Isso expõe deadlock como **pânico** do teste (`deadlock: all goroutines in bubble are blocked`; ou `main bubble goroutine has exited but blocked goroutines remain` se sobrar goroutine bloqueada).
- Dentro da bolha: não use I/O de rede real; use `httptest.NewTestServer(t, h)` (1.27, rede em memória) ou `net.Pipe`.
- Tudo que a bolha cria deve terminar antes de `Test` retornar, senão há pânico — isso também é um **detector de vazamento**.

## Vazamento de goroutine

- **`go.uber.org/goleak`**: `TestMain` com `goleak.VerifyTestMain(m)` falha o pacote se sobrar goroutine; `goleak.VerifyNone(t)` por teste.
- **Perfil `goroutineleak`** (1.27, `runtime/pprof`): detecta em **produção/staging** (goroutine presa em primitiva inalcançável); complementa o goleak, que age em teste.
- Corrija a causa (ver `go-concurrency-expert`): sem dono de término, canal sem receptor, `ctx` ignorado (`Ticker` sem `Stop` só vaza com `go` < 1.23).

## Golden files

```go
var update = flag.Bool("update", false, "reescreve os golden files")

func TestGolden(t *testing.T) {
	got, _ := Slug("Golden File")
	path := filepath.Join("testdata", "slug.golden")
	if *update {
		_ = os.WriteFile(path, []byte(got), 0o644)
	}
	want, err := os.ReadFile(path)
	if err != nil { t.Fatal(err) }
	if string(want) != got { t.Fatalf("golden difere: %q != %q (rode com -update)", want, got) }
}
```

Saídas com mapas devem ser **determinísticas** (`json.Deterministic(true)` na v2, ou ordenar chaves). Revise o diff do golden no PR como se fosse código.

## Fuzzing

```go
func FuzzSlug(f *testing.F) {
	f.Add("Olá Mundo")
	f.Add("")
	f.Fuzz(func(t *testing.T, s string) {
		got, err := Slug(s)
		if err == nil && got == "" { // propriedade, não valor exato
			t.Fatalf("Slug(%q) retornou vazio sem erro", s)
		}
	})
}
```

Teste **propriedades** (idempotência, ida-e-volta `Unmarshal(Marshal(x)) == x`, nunca entra em pânico, invariantes). Rode `go test -fuzz=FuzzSlug -fuzztime=30s`;
entradas que quebram viram arquivos em `testdata/fuzz/` — **versionados**, viram regressão permanente.

## HTTP

- Handler: `httptest.NewRecorder()` + `httptest.NewRequest` — sem porta, sem rede.
- Cliente/ponta a ponta: `httptest.NewServer(h)`; com tempo virtual, `httptest.NewTestServer(t, h)` dentro de `synctest.Test`.
- Substitua dependências externas por `http.RoundTripper` falso no `http.Client` — não faça *monkey patching* de globals.

## Integração (build tag)

```go
//go:build integration

package store_test
```

`go test -tags=integration ./...`. Banco: use um contêiner por pacote (ou por suíte) e **transações com rollback** ou esquema por teste para isolar.
Nunca aponte teste de integração para um ambiente compartilhado ou de produção.

## Cobertura, race e flags úteis

| Objetivo | Comando |
|---|---|
| Rodar tudo com detector de corrida | `go test -race ./...` |
| Ordem aleatória (acha acoplamento entre testes) | `go test -shuffle=on ./...` |
| Sem cache | `go test -count=1 ./...` |
| Cobertura | `go test -coverprofile=c.out ./... && go tool cover -func=c.out` |
| Um teste | `go test -run '^TestSlug$/vazio' -v ./pkg` |
| Timeout curto de CI | `go test -timeout=2m ./...` |
| Saída para ferramenta | `go test -json ./...` |

Cobertura é **indicador**, não meta: 100% sem asserção não prova nada. Exija cobertura nos **caminhos de erro** e nas fronteiras.

## Anti-padrões

- `time.Sleep` para "esperar a goroutine" → `synctest`, canal de sincronização ou `sync.WaitGroup`.
- Testes que dependem de ordem, relógio real, `rand` sem semente fixa, rede externa ou variáveis globais mutáveis.
- *Mock* que repete a implementação linha a linha (teste frágil); `t.Fatal` dentro de goroutine que não é a do teste (use `t.Error` + canal, ou `errgroup`).
- Suprimir `-race` para "passar o CI". Corrida de dados é bug.
