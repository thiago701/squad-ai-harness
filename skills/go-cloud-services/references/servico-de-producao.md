# Esqueleto de serviço Go de produção

> Autoral (Squad AI). Os blocos com `package` foram compilados e testados (`-race`) com Go 1.27.1.
> Estrutura sugerida: `cmd/app/main.go` (wiring) · `internal/config` · `internal/httpapi` · `internal/store` · `internal/<domínio>`.

## 1. Configuração 12-factor, fail-fast e imutável

```go
package svc

import (
	"errors"
	"fmt"
	"strconv"
	"time"
)

// Config: carregada UMA vez no main, validada, imutável depois.
type Config struct {
	Addr            string
	DatabaseURL     string        // segredo: nunca logar
	ShutdownTimeout time.Duration // menor que terminationGracePeriodSeconds do pod
	MaxConns        int32
}

func LoadConfig(getenv func(string) string) (Config, error) { // getenv injetável = testável sem mexer no ambiente
	c := Config{Addr: or(getenv("ADDR"), ":8080"), DatabaseURL: getenv("DATABASE_URL"), ShutdownTimeout: 20 * time.Second, MaxConns: 10}
	var errs []error
	if c.DatabaseURL == "" {
		errs = append(errs, errors.New("DATABASE_URL é obrigatório"))
	}
	if v := getenv("SHUTDOWN_TIMEOUT"); v != "" {
		d, err := time.ParseDuration(v)
		if err != nil || d <= 0 {
			errs = append(errs, fmt.Errorf("SHUTDOWN_TIMEOUT inválido %q", v))
		} else {
			c.ShutdownTimeout = d
		}
	}
	if v := getenv("DB_MAX_CONNS"); v != "" {
		n, err := strconv.ParseInt(v, 10, 32)
		if err != nil || n < 1 {
			errs = append(errs, fmt.Errorf("DB_MAX_CONNS inválido %q", v))
		} else {
			c.MaxConns = int32(n)
		}
	}
	return c, errors.Join(errs...) // reporta TODOS os problemas de uma vez
}

func or(v, def string) string {
	if v == "" {
		return def
	}
	return v
}
```

Regras: o `main` chama `LoadConfig(os.Getenv)`; erro ⇒ log (sem valores secretos) e `exit 1` **antes** de abrir qualquer porta. Segredos via variável de ambiente injetada por
*secret manager* (K8s Secret montado/External Secrets, AWS Secrets Manager/SSM) — nunca no repositório, na imagem ou em `ARG`. Não use pacote global de configuração mutável.

## 2. Servidor: saúde, readiness e shutdown em 4 passos

```go
type App struct {
	Log   *slog.Logger
	Ready atomic.Bool // readiness: vira false ao iniciar o shutdown
	Ping  func(context.Context) error
}

func (a *App) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /livez", func(w http.ResponseWriter, _ *http.Request) { w.WriteHeader(http.StatusNoContent) }) // vivo: sem dependências
	mux.HandleFunc("GET /readyz", func(w http.ResponseWriter, r *http.Request) {
		if !a.Ready.Load() {
			http.Error(w, "encerrando", http.StatusServiceUnavailable)
			return
		}
		ctx, cancel := context.WithTimeout(r.Context(), time.Second)
		defer cancel()
		if err := a.Ping(ctx); err != nil { // só dependência CRÍTICA, com timeout curto
			http.Error(w, "dependência indisponível", http.StatusServiceUnavailable)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	})
	return mux
}

// Serve: sobe, espera o sinal (ctx), tira do balanceador e drena as conexões em voo.
func (a *App) Serve(ctx context.Context, srv *http.Server, drain, shutdown time.Duration) error {
	errc := make(chan error, 1)
	go func() { errc <- srv.ListenAndServe() }()
	a.Ready.Store(true)

	select {
	case err := <-errc:
		return err
	case <-ctx.Done():
	}
	a.Log.Info("encerrando", "cause", context.Cause(ctx))
	a.Ready.Store(false) // 1) readiness falha → o balanceador para de enviar tráfego
	time.Sleep(drain)    // 2) janela de propagação (≈ período do probe); 0 se o pod usa preStop
	sctx, cancel := context.WithTimeout(context.WithoutCancel(ctx), shutdown)
	defer cancel()
	if err := srv.Shutdown(sctx); err != nil { // 3) espera as requisições em voo
		_ = srv.Close() // 4) estourou o prazo: força
		return err
	}
	if err := <-errc; !errors.Is(err, http.ErrServerClosed) {
		return err
	}
	return nil
}
```

`main` (resumo): `ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)` → carrega config → abre pool/clients **com ctx** →
monta `http.Server{ReadHeaderTimeout: 5s, ReadTimeout: 15s, WriteTimeout: 30s, IdleTimeout: 60s, Handler: Instrument(app.Handler())}` → `app.Serve(...)` →
`defer` fecha pool/clients e `tp.Shutdown` (flush de traces) **depois** do `Serve` retornar. Em teste, cancele o ctx para provar o shutdown (como no teste do esqueleto).

**Por que `/livez` e `/readyz` separados:** liveness que checa banco reinicia pods por falha de dependência (piora o incidente). Readiness decide **só** se este pod deve receber tráfego agora.

## 3. Erros de API: formato único e sem vazamento

- Mapeie erros de domínio (`errors.Is`/`AsType`) para status **na borda** (um `func writeError(w, r, err)`). Corpo padronizado — `application/problem+json` (RFC 9457): `type`, `title`, `status`, `detail`, `instance`/`trace_id`.
- Nunca devolva `err.Error()` de erro interno (SQL, caminhos, stack) ao cliente; logue a causa completa com `trace_id` e responda mensagem genérica.
- 4xx = culpa do cliente (validação, auth, não encontrado, conflito); 5xx = nossa (logar `ERROR`). 429/503 com `Retry-After` para *load shedding*.
- Validação na borda: tamanho máximo, tipos, enumerações; rejeite campos desconhecidos (`json.RejectUnknownMembers(true)` com `encoding/json/v2` / `DisallowUnknownFields` na v1).

## 4. Middlewares essenciais (ordem: externo → interno)

1. **recover** (converte `panic` em 500 e loga com stack; nunca derruba o processo); 2. **request id / trace** (`otelhttp.NewHandler`); 3. **log de acesso** (`slog`: método, rota *padrão*, status, duração — não a URL com ids/segredos);
4. **timeout por requisição** (`http.TimeoutHandler` ou ctx com prazo); 5. **limites** (tamanho de corpo, concorrência, *rate limit* por cliente);
6. **auth** (JWT/mTLS; validar `iss`/`aud`/`exp`, chaves por JWKS com cache); 7. **CORS/CSRF** (`http.NewCrossOriginProtection()` em rotas mutáveis acessadas por navegador).

## 5. Resiliência (cliente de outras APIs)

| Mecanismo | Regra |
|---|---|
| Timeout | **Toda** chamada externa tem prazo (ctx) e o `http.Client` tem `Timeout` total; prazo da cadeia < prazo do chamador |
| Retry | Só operações idempotentes (GET/PUT/DELETE ou POST com chave de idempotência); backoff exponencial + **jitter** + teto de tentativas; respeite `Retry-After`; nunca retry em 4xx (exceto 408/429) |
| Bulkhead | Semáforo/pool **por dependência** — a lenta não consome todas as goroutines/conexões |
| Circuit breaker | Por destino, com janela e *half-open*; abre em falha de **sistema** (5xx/timeout), não de negócio |
| Load shedding | Ao saturar, rejeite cedo (503) em vez de enfileirar sem limite |
| Idempotência | `Idempotency-Key` + armazenamento (chave → resposta) com TTL; consumidor de fila deduplica por id de mensagem |
| Transação + evento | **Outbox**: grave o evento na mesma transação do dado e publique em outro processo (evita "gravou mas não publicou") |

Backoff com jitter (cheio) — exemplo de cálculo: `sleep = rand(0, min(teto, base * 2^tentativa))`; use `math/rand/v2` (não é segredo) e `time.NewTimer` + `select` em `ctx.Done()`.

## 6. Observabilidade

- **Logs:** `slog.NewJSONHandler(os.Stdout, ...)`; atributos estáveis (`trace_id`, `span_id`, `route`, `status`, `duration_ms`); níveis com critério (ERROR = acionável); nunca PII/segredos.
- **Traces:** OpenTelemetry — `otelhttp` (servidor e cliente), `otelgrpc` (via `grpc.StatsHandler(otelgrpc.NewServerHandler())`; os interceptors estão deprecados), `otelsql`/instrumentação do pgx; exporte OTLP para um Collector; amostragem (`ParentBased(TraceIDRatioBased)`); **flush no shutdown**.
- **Métricas:** RED por rota/dependência (taxa, erros, duração em histograma), saturação (goroutines, pool de conexões `db.Stats()`, heap vivo). Rótulos de **baixa cardinalidade** (rota padrão, não URL; nunca user id).
- **Perfis:** `net/http/pprof` em listener separado em `127.0.0.1` (ou autenticado, rede interna); flight recorder para incidentes (`go-performance-engineer`).
- **SLOs:** defina disponibilidade e latência alvo por rota crítica e alerte por *burn rate*, não por limiar instantâneo.
