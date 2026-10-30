# Comandos por stack — cadeia de gates (11 executáveis, 12 etapas nomeadas)

> Carregado sob demanda pelo `verificacao-loop`. Ambiente padrão: Windows 11 / PowerShell;
> os comandos Maven/npm/python rodam igual no Linux — ajuste só o separador de path.

## Java 25 + Maven

| Gate | Comando | Critério |
|---|---|---|
| TOOLCHAIN | `mvn -v` × `<maven.compiler.release>` do pom | versões iguais |
| BUILD | `mvn -B clean compile` | exit 0 |
| STATIC | `mvn -B spotbugs:check` (com `findsecbugs-plugin`) | sem achado HIGH |
| UNIT + INTEGRATION | `mvn -B verify` | suíte verde |
| COVERAGE | JaCoCo ≥ 0.8.15 (Java 25) — `jacoco:check` no `verify` | linhas ≥ 97 %, branches ≥ 90 % |
| MUTATION | `mvn org.pitest:pitest-maven:mutationCoverage` (pitest ≥ 1.20, `pitest-junit5-plugin` ≥ 1.2.3) | score ≥ `score_min` **e** sobreviventes ≤ `sobreviventes_max` |

> **Por que dois tetos e não um:** numa base de 44 mutações, 2 mutantes vivos dão 95,5 % e passam
> tranquilos num piso de 85 %. Foi exatamente assim que um afrouxamento de assertion escapou no
> experimento A/B de 2026-09-14. O percentual protege base grande; o **teto absoluto** protege as
> pequenas — que é onde vive a maior parte do código de regra de negócio.
| ARCHITECTURE | `archunit-junit5` ≥ 1.4 dentro do `verify` | regras de camada OK |

> **Armadilha de versão (medida em 2026-09-14):** JaCoCo 0.8.12 e PIT 1.17 **não leem bytecode
> Java 25** (class file 69) e explodem com `IllegalArgumentException` no `ClassReader`. Mínimos:
> **JaCoCo 0.8.15**, **pitest-maven 1.20.x**, **pitest-junit5-plugin 1.2.3**.

### `jacoco:check` com o teto do budget

```xml
<rule><element>BUNDLE</element><limits>
  <limit><counter>LINE</counter><value>COVEREDRATIO</value><minimum>0.97</minimum></limit>
  <limit><counter>BRANCH</counter><value>COVEREDRATIO</value><minimum>0.90</minimum></limit>
</limits></rule>
```

O número tem de estar **no `pom.xml`**, não só no relatório: gate que não quebra o `mvn verify`
é relatório, não gate.

## Python 3.13 (FastAPI / Django)

| Gate | Comando | Critério |
|---|---|---|
| STATIC | `ruff check .` · `ruff format --check .` · `mypy .` | sem erro |
| STATIC · clean code | `ruff check src tests` com o bloco canônico (`C90` max-complexity 15 = S1541, `PL` max-args 7 = S107, `FBT`/`ERA`/`TRY`/`T20`…) · `complexipy` (cognitiva ≤ 15 = S3776, `complexipy==8.3.0` no grupo dev) · `rc=0; grep -rniE '#[[:space:]]*(noqa\|type:[[:space:]]*ignore\|ruff:[[:space:]]*noqa\|mypy:[[:space:]]*ignore\|complexipy:[[:space:]]*ignore\|pyright:[[:space:]]*ignore)\|NOSONAR' src tests \|\| rc=$?; test "$rc" -eq 1` (rc 1 = limpo) | 0 achado no código tocado; achado = MAJOR; teto afrouxado sem ADR = BLOCKER. Config: `skills/aws-lambda-python/references/clean-code-python.md` |
| UNIT + COVERAGE | `pytest --cov --cov-report=xml --cov-fail-under=97` | verde + ≥ 97 % |
| MUTATION | `mutmut run` ou `cosmic-ray` nos módulos de regra | score ≥ teto |
| SECURITY | `bandit -r src/` · `pip-audit` | sem HIGH, sem CVE Critical/High |
| PROPERTY-BASED | `hypothesis` nos invariantes do domínio | propriedades não falseadas |

## Angular 21+ / TypeScript

| Gate | Comando | Critério |
|---|---|---|
| STATIC | `ng lint` · `tsc --noEmit` | sem erro |
| UNIT + COVERAGE | `ng test --watch=false --code-coverage` | ≥ 97 % |
| E2E | `npx playwright test` | cenários verdes |
| SECURITY | `npm audit --omit=dev` | sem `high`/`critical` |

## Go 1.27 (Lambda: Go 1.24)

> Dentro de tabela Markdown o `|` aparece escapado (`\|`); no terminal o comando é sem a barra — a forma canônica,
> copiável, está em `../../tech-lead-review/references/lente-clean-code.md` §2.2.

> Projetos da `aws-lambda-go` usam `go 1.24.3` + `toolchain go1.24.13` por decisão do dono (Go 1.24 fora de suporte):
> o TOOLCHAIN compara com essa linha, e o `govulncheck` reprova até haver aceite de risco escrito ou upgrade. Fixe
> `GOTOOLCHAIN=go1.24.13` no gate: a diretiva `toolchain` é um **mínimo** — com Go mais novo instalado, `auto` usa o novo.


| Gate | Comando | Critério |
|---|---|---|
| TOOLCHAIN | `go version` × `go` do `go.mod` | mesma linha maior (ex.: 1.27) |
| BUILD | `go build ./...` | exit 0 |
| STATIC | `go vet ./...` · `go tool staticcheck ./...` (versão travada pela diretiva `tool` do `go.mod`) · `test -z "$(gofmt -l .)"` | sem achado; staticcheck ausente = MAJOR, nunca "se instalado" |
| STATIC · clean code | `golangci-lint run ./...` com a config canônica (`skills/golang-pro/references/clean-code-e-lint.md` §3; v2.8.0 para Go 1.24) · `rc=0; grep -rnE --include='*.go' -e '//[[:space:]]*nolint' -e '//[[:space:]]*lint:(file-)?ignore' -e '#nosec' -e 'NOSONAR' . \|\| rc=$?; test "$rc" -eq 1` | 0 issues no código tocado — cognitiva ≤ 15 (S3776), ciclomática ≤ 15 (S1541), parâmetros ≤ 7 (S107), funlen 60/40, nestif; zero supressão inline, inclusive `#nosec` e `lint:ignore` (rc 1 = limpo). Achado = MAJOR; teto afrouxado sem ADR = BLOCKER |
| UNIT + COVERAGE | `go test ./... -race -coverprofile=cover.out` · `go tool cover -func=cover.out` | verde; total ≥ 97 % (regra de negócio), `-race` limpo |
| IMPACTADOS (tier ≤ standard) | `go test -run '<regex do preflight>' ./<pacotes tocados>/...` | verde |
| SECURITY | `govulncheck ./...` · `gitleaks dir .` | 0 vulnerabilidade alcançável, 0 segredo |
| PERFORMANCE | `go test -bench=. -benchmem ./<pacote>` comparado ao budget | dentro dos tetos |

## Rust 1.99 (edição 2024)

| Gate | Comando | Critério |
|---|---|---|
| TOOLCHAIN | `rustc --version` × `rust-version` do `Cargo.toml` | igual ou maior |
| BUILD | `cargo build --locked` | exit 0 |
| STATIC | `cargo fmt --check` · `cargo clippy --all-targets --all-features -- -D warnings` | sem warning |
| UNIT + INTEGRATION | `cargo test --locked` | verde (unit + `tests/` + doctests) |
| COVERAGE | `cargo llvm-cov --fail-under-lines 97` (se instalado) | ≥ 97 % |
| IMPACTADOS (tier ≤ standard) | `cargo test -p <crate tocado> <filtro do preflight>` | verde |
| SECURITY | `cargo audit` · `cargo deny check` · `gitleaks dir .` | 0 advisories, licenças OK, 0 segredo |
| UNSAFE | `cargo miri test` nos módulos com `unsafe` (quando houver) | sem UB detectado |
| PERFORMANCE | `cargo bench` (criterion/divan) comparado ao budget | dentro dos tetos |

> Os dois blocos vieram com as skills `golang-pro`/`rust-pro` (patch de 03/10, aplicado em 11/10);
> ferramentas marcadas "se instalado" degradam para MAJOR (gate que não rodou), nunca PASS silencioso.

## Transversal — segurança (todas as stacks)

```bash
# CVE de dependência — OSV cobre Maven, PyPI, npm, Go, Cargo…
osv-scanner scan source -r . --format json

# Segredos versionados
gitleaks dir . --no-banner --redact --report-format json --report-path reports/gitleaks.json

# SBOM CycloneDX — o inventário do que foi realmente entregue
syft scan dir:. -o cyclonedx-json=reports/sbom.cyclonedx.json

# IaC (Terraform / CloudFormation / Kubernetes)
tfsec .            # ou: checkov -d . --compact
trivy config .     # misconfiguração em IaC e Dockerfile

# Imagem de contêiner
trivy image --severity HIGH,CRITICAL --exit-code 1 <imagem>:<tag>
```

### Por que SBOM é gate e não documentação

Sem inventário assinável não há resposta para *"esta versão contém a lib X vulnerável?"* no dia
em que a CVE sai. O SBOM é gerado **no mesmo build que produz o artefato** e versionado junto —
gerado depois, a partir do repositório, ele descreve outra coisa.

## Transversal — cadeia de suprimentos

| Verificação | Comando | Por quê |
|---|---|---|
| Actions pinadas por SHA | `grep -rn "uses:.*@v[0-9]" .github/workflows/` | tag é mutável; SHA não |
| Hooks `pre-commit` por SHA | `grep -n "rev:" .pre-commit-config.yaml` | mesma razão |
| Assinatura de artefato | `cosign sign-blob` / `cosign verify-blob` | prova de origem do binário |
| Proveniência de build | SLSA provenance no pipeline de release | responde "quem construiu, de qual commit" |

## Fallback portátil de scan de segredos (PowerShell)

Quando `gitleaks` não estiver disponível — e **registre isso como MAJOR**, não como PASS:

```powershell
git diff --cached | Select-String -Pattern `
  'AKIA[0-9A-Z]{16}', `
  '-----BEGIN.*PRIVATE KEY-----', `
  '(?i)(secret|token|passwd|password|api[_-]?key)\s*[:=]\s*["''][^"'']{8,}'
```

Qualquer match = BLOCKER.

## Performance — harness mínimo reprodutível

```bash
python bench/medir.py --repeticoes-cold 25 --repeticoes-quente 300000 \
                      --saida reports/bench-consolidado.json
python scripts/quality/gate_runner.py --projeto . --budget quality-budget.yaml
```

Regras não negociáveis do número publicado:

1. **≥ 3 rodadas independentes**, mediana + coeficiente de variação. Rodada única não vira teto.
2. **Cold start é wall clock externo** do processo — relógio que começa dentro do `main` mede
   inicialização de objeto, não cold start (erro medido: subestimava 300×).
3. **O `-march` do build entra no relatório.** Binário compilado com `x86-64-v2` não roda em
   Lambda `arm64`; o número medido só vale para a arquitetura em que foi medido.
4. **`fonte` obrigatória no budget** — teto sem medição de origem o runner recusa.
