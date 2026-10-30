# Clean code e lint em Go — o gate da Squad (arquivo canônico)

> **Canônico:** este arquivo e o `.golangci.yml` abaixo são a fonte única do gate de clean code em Go da Squad. A **aws-lambda-go**
> (`references/clean-code-go.md`) e os pipelines (`squad-pipeline`, `verificacao-loop`, `tech-lead-review`) **apontam** para cá —
> não copie o arquivo para outro lugar da Squad (duas cópias divergem).
> Estado de verificação (2026-10-28): config validada com `golangci-lint config verify` no **v2.8.0** (construído com Go 1.24.13 —
> a última v2 que compila com 1.24) e no **v2.15.0** (Go 1.27.3); no lab da aws-lambda-go: **0 achados** no código real e **17**
> no exemplo deliberadamente ruim (13 linters diferentes). Princípios gerais de clean code (nomes, funções, smells) →
> **clean-code-craftsman**; este arquivo traz o que é **específico de Go** e o que é **verificável por máquina**.

## 1. Limiares — alinhados à doutrina Sonar-First da Squad

| Regra | Limite (gate) | Sonar | Linter |
|---|---|---|---|
| Complexidade cognitiva por função | ≤ 15 | **S3776** | `gocognit` (`min-complexity: 15`) |
| Complexidade ciclomática por função | ≤ 15 | **S1541** | `gocyclo` (`min-complexity: 15`) |
| Parâmetros por função | ≤ 7 (mire em ≤ 3–4) | **S107** | `revive` `argument-limit` `[7]` |
| Tamanho de função | ≤ 60 linhas / 40 instruções | — | `funlen` |
| Aninhamento de `if` | `nestif` reporta a partir de complexidade **4** (`min-complexity: 4`) — a pontuação soma o peso de cada `if`/`else` aninhado dentro do `if` de fora (no exemplo ruim: 29); não é "número de níveis" | — | `nestif` |
| Duplicação | blocos ≥ 120 tokens | — | `dupl` |
| Supressão inline | **zero** (`//nolint`, `//lint:ignore`, `#nosec`, `NOSONAR`) | Fase C/D | `grep` no gate (§4) |

A complexidade **cognitiva** é a que mais pega: no exemplo ruim do lab, a pirâmide de `if` mediu **39** de cognitiva e ficou **abaixo**
de 15 na ciclomática (o número de caminhos é baixo; o que dói é o aninhamento) — por isso os dois limites coexistem.

## 2. O que é clean code **em Go** (além do geral)

1. **`gofmt` não se discute** e `gofumpt`/`goimports` padronizam o resto — estilo nunca é assunto de revisão.
2. **Nomes curtos no escopo curto, descritivos no escopo longo:** `r` num laço de 3 linhas, `pedidoPendente` num campo de pacote.
   Sem gagueira (`pedido.PedidoID` → `pedido.ID`); siglas inteiras (`ID`, `URL`, `HTTP`); receptor de 1–2 letras, sempre o mesmo.
3. **Retorno antecipado:** trate o erro e saia; o caminho feliz fica à esquerda, sem `else` depois de `return` (`indent-error-flow`).
4. **Erros são valores com contexto:** `fmt.Errorf("salvar pedido %s: %w", id, err)`; sentinela `ErrX` para decisão do chamador
   (`errors.Is`), tipo `XError` para dados (`errors.As`); **nunca** comparar com `==` nem pelo texto. Mensagem minúscula, sem ponto.
   Desde o Go 1.20 dá para embrulhar dois: `fmt.Errorf("%w: %w", ErrInvalido, err)`.
5. **Trate o erro uma vez:** ou registra, ou devolve — logar **e** devolver duplica o log em cada camada. Quem loga é a borda
   (handler/`main`).
6. **`context.Context` é o 1º parâmetro** de quem faz I/O; nunca guardado em struct; propague o prazo.
7. **Interfaces pequenas, declaradas no consumidor**, só quando há mais de uma implementação ou fronteira de teste. Aceite interface,
   devolva tipo concreto.
8. **Zero value útil** e construtor só com invariante a proteger; parâmetros que andam juntos viram struct (resolve S107 sem esconder
   acoplamento).
9. **Sem global mutável.** Dependências criadas uma vez (logger, clientes) vivem em `main`/composição e descem por parâmetro ou
   struct; o resto, nunca. `x.(T)` sempre com `, ok` (`forcetypeassert`).
10. **Teste de tabela** com `t.Run` por caso e mensagem que diga o que veio e o que se queria (`got %v, want %v`).
11. **Comentário de documentação em todo exportado**, começando pelo nome (`revive` `exported`); comentário de linha explica o
    **porquê**, não o quê.
12. **Biblioteca padrão primeiro; constantes nomeadas** para literal repetido (`goconst`) e as constantes da stdlib
    (`http.StatusOK`, `http.MethodPost` — `usestdlibvars`).

## 3. `.golangci.yml` (golangci-lint v2)

`.golangci.yml`:

```yaml
# golangci-lint v2 — gate de clean code da Squad para Go (canônico: skills/golang-pro/references/clean-code-e-lint.md).
# Limiares = doutrina Sonar-First da Squad: S3776 (cognitiva) <= 15, S1541 (ciclomática) <= 15, S107 (parâmetros) <= 7.
# Zero supressão inline: nada de //nolint, //lint:ignore, #nosec ou NOSONAR no código; exceção só aqui, em exclusions, com o porquê.
version: "2"

run:
  timeout: 5m
  tests: true

linters:
  default: none
  enable:
    # correção e erros
    - govet
    - staticcheck
    - errcheck
    - errorlint        # errors.Is/As e %w, nunca err == / type switch em erro embrulhado
    - nilerr
    - ineffassign
    - unused
    - unparam
    # recursos e contexto
    - bodyclose
    - noctx
    - contextcheck
    - gosec
    # tamanho e complexidade (limiares abaixo)
    - gocognit         # S3776
    - gocyclo          # S1541
    - funlen
    - nestif
    - revive           # argument-limit = S107
    # duplicação e legibilidade
    - dupl
    - goconst
    # misspell fora: o código e os comentários da Squad são em PT-BR (falso positivo em "clientes", "devolvendo")
    - errname
    - copyloopvar
    - intrange
    - usestdlibvars
    - forcetypeassert  # x.(T) sem ", ok" derruba a invocação com pânico
    - gochecknoglobals # global mutável; dependências da init ficam em main (ver exclusions)
  settings:
    gocognit:
      min-complexity: 15   # Sonar S3776
    gocyclo:
      min-complexity: 15   # Sonar S1541
    funlen:
      lines: 60
      statements: 40
      ignore-comments: true
    nestif:
      min-complexity: 4    # reporta if cuja complexidade de aninhamento (soma dos if/else internos) chega a 4
    dupl:
      threshold: 120
    goconst:
      min-len: 3
      min-occurrences: 3
    revive:
      rules:
        - name: argument-limit       # Sonar S107
          arguments: [7]
        - name: context-as-argument  # ctx é o 1º parâmetro
        - name: error-return         # error é o último retorno
        - name: error-strings        # mensagem de erro minúscula, sem ponto final
        - name: errorf
        - name: early-return
        - name: indent-error-flow    # sem else depois de return
        - name: superfluous-else
        - name: unused-parameter
        - name: var-naming
        - name: receiver-naming
        - name: exported
        - name: blank-imports
        - name: unexported-return
  exclusions:
    rules:
      # main de cada Lambda guarda as dependências criadas UMA vez na init (logger, clientes SDK, config lida
      # do ambiente) — é o ciclo de vida do Lambda, não estado mutável de negócio. Fora de cmd/, global continua proibida.
      - path: ^cmd/
        linters: [gochecknoglobals]
      # testes de tabela são longos por natureza; a complexidade continua valendo
      - path: _test\.go
        linters: [funlen, dupl, goconst]

issues:
  # mostra TUDO: o padrão esconde achados repetidos e mais de um achado por linha
  max-issues-per-linter: 0
  max-same-issues: 0
  uniq-by-line: false

formatters:
  enable:
    - gofumpt
    - goimports
```

Notas de decisão (cada uma veio de um achado real no lab):

- `default: none` + lista explícita: o time sabe exatamente o que barra; linter novo entra por decisão, não por atualização.
- `misspell` **fora**: dicionário em inglês; o código da Squad é em PT-BR ("clientes", "devolvendo" viraram falso positivo).
- `issues` com `max-same-issues: 0` e `uniq-by-line: false`: o padrão do golangci-lint **esconde** achados (só um por linha e três
  iguais) — com ele, o exemplo ruim mostrava 11 achados em vez de 17 (medido) e o `argument-limit` sumia atrás do `gocognit`.
- Exceção por **caminho**, nunca inline: `gochecknoglobals` liberado em `cmd/` (dependências da init do Lambda) e
  `funlen`/`dupl`/`goconst` liberados em `_test.go` — cada uma com o porquê no próprio arquivo.
- `gocognit` + `gocyclo` + `nestif` + `funlen` medem coisas diferentes; deixar só um esconde o problema que os outros veem.

## 4. Zero supressão inline

Nada de supressão no código. Quatro formas calam um achado e todas são proibidas: `//nolint` (golangci-lint), `//lint:ignore` e
`//lint:file-ignore` (staticcheck isolado — verificado: `//lint:ignore S1003` some com o S1003), `#nosec` (gosec — verificado:
`// #nosec G107` some com o G107, e o golangci-lint respeita) e `NOSONAR`. Se uma exceção for inevitável, ela vai para
`linters.exclusions` do `.golangci.yml`, por **caminho e linter**, com comentário do porquê — revisável num lugar só. O gate:

```bash
rc=0; grep -rnE --include='*.go' -e '//[[:space:]]*nolint' -e '//[[:space:]]*lint:(file-)?ignore' -e '#nosec' -e 'NOSONAR' . || rc=$?; test "$rc" -eq 1
```

Por que exatamente assim (o `grep` sai **1** quando não acha nada, **0** quando acha, **2** em erro, ex.: pasta inexistente):

- `! grep ... pasta1 pasta2` fica **verde** se uma pasta não existir (sai 2 e o `!` inverte) — falso verde;
- `grep ...; test $? -eq 1` **morre** sob `bash -e` (o `run` do GitHub Actions usa `-e`): o `grep` limpo sai 1 e mata o script
  antes do `test`;
- `rc=0; grep ... || rc=$?; test "$rc" -eq 1`: o `||` protege do `-e`, e só o 1 passa. Verificado com `bash -e`: pasta limpa →
  verde; arquivo com `#nosec` → vermelho; pasta inexistente → vermelho.
- Num `Makefile`, dobre o `$`: `rc=0; grep ... || rc=$$?; test "$$rc" -eq 1` (numa linha só da receita).

## 5. Gate completo (ordem barata → cara)

```bash
set -euo pipefail
export GOTOOLCHAIN=go1.27.3                  # FIXE a versão do projeto (`toolchain` no go.mod é só o mínimo; `auto` usaria um Go mais novo)
test "$(go env GOVERSION)" = "$GOTOOLCHAIN"
test -z "$(gofmt -l .)"
go vet ./...
go tool staticcheck ./...                    # obrigatório; versão travada pela diretiva tool (Go 1.24+)
golangci-lint run ./...                      # .golangci.yml desta reference
rc=0; grep -rnE --include='*.go' -e '//[[:space:]]*nolint' -e '//[[:space:]]*lint:(file-)?ignore' -e '#nosec' -e 'NOSONAR' . || rc=$?; test "$rc" -eq 1
go test -race -count=1 ./...
go test -count=1 -coverprofile=cover.out ./internal/...
go tool cover -func=cover.out | awk '/^total:/ { sub("%", "", $3); exit !($3 + 0 >= 97) }'
go tool govulncheck ./...
```

**Cobertura:** o critério da Squad (`verificacao-loop`) é **≥ 97 % de linhas** na regra de negócio. Em Go o `go tool cover` mede
**instruções** (não ramos — os ≥ 90 % de branches do verificacao-loop não têm medida nativa em Go; cubra os ramos com testes de
tabela e revisão). A regra de negócio mora em `internal/` (ou no pacote de domínio do projeto); `cmd/` (só `main` com a init e o
`Start`) fica fora da métrica e é coberto por teste de contrato/integração. Na aws-lambda-go: `internal/` 99,2 %, total 58,4 %.

**`golangci-lint`:** use o **binário oficial da v2 mais recente** (verificado: v2.15.0, inclusive analisando código Go 1.24 — mesmo
resultado que a v2.8.0). Só quem precisa **compilar** o linter com Go 1.24 fica na **v2.8.0** (`go install
github.com/golangci/golangci-lint/v2/cmd/golangci-lint@v2.8.0`; a v2.9+ exige 1.25). **Não** como `tool` do módulo (a documentação
do golangci-lint desaconselha: as dependências do linter entram no grafo do seu módulo).

## Fontes (reescritas em PT-BR com palavras próprias; nenhum trecho copiado)

- *Effective Go* e *Go Code Review Comments* (go.dev / Go Wiki) — conteúdo sob **CC BY 4.0** (código sob BSD).
- *Google Go Style Guide* (guide, decisions, best practices) — **CC BY 3.0**.
- *Uber Go Style Guide* (`uber-go/guide`) — **Apache-2.0**.
- Documentação do golangci-lint v2 (configuração e linters) — fatos de configuração citados; o projeto é **GPL-3.0** e não é
  redistribuído.
- Limiares: doutrina Sonar-First da Squad (`sonar-first-engineering`, `clean-code-craftsman`: S3776, S1541, S107).
