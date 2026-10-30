# Lente de clean code (`rev-clean`) — parte mecânica + checklist de leitura P1.CLEAN

> **Adicionado em 2026-10-28** (pedido do dono: levar técnicas de clean code às skills de Lambda e aos pipelines).
> Dono da doutrina geral de clean code: **`clean-code-craftsman`** (nomes, funções, smells, código gerado por IA).
> Esta reference só define **como o review aplica** essa doutrina: o que é medido por ferramenta, o que é lido por
> humano/agente e como cada achado vira veredito. Limiar é o mesmo do Sonar-First (`sonar-first-engineering`) — a
> squad tem **uma** régua, medida por várias ferramentas.

## 1. Por que uma lente própria

O motor Sonar-First mede `S3776`/`S1541`/`S107` onde ele roda; os linters da stack medem o mesmo no diff em
segundos, sem servidor e com 0 token. O review humano para de discutir "esta função está grande?" (o número
responde) e gasta atenção no que ferramenta nenhuma mede: intenção, nomes, fronteiras, mistura de mudança
estrutural com comportamental.

## 2. Parte mecânica (determinística, 0 token)

### 2.1 A régua (igual em todas as stacks)

| Medida | Teto (gate) | Equivalente Sonar | Alvo de escrita |
|---|---|---|---|
| Complexidade cognitiva por função | **≤ 15** | `S3776` | o menor possível; guard clauses primeiro |
| Complexidade ciclomática por função | **≤ 15** | `S1541` | — |
| Parâmetros por função | **≤ 7** | `S107` | ≤ 3–4; acima disso, um tipo (struct/dataclass) |
| Supressão inline (qualquer forma — ver §2.2) | **0** | (Fase C/D do Sonar-First) | exceção vai para a **configuração revisada**, com o porquê |

As três primeiras linhas e a última são iguais em todas as stacks. Tamanho e aninhamento dependem do que cada
ferramenta mede — não force um número que ela não calcula:

| Medida | Go (golangci-lint) | Python (ruff + complexipy) |
|---|---|---|
| Tamanho de função | `funlen`: 60 linhas / 40 instruções | `PLR0915` max-statements 50 (não há limite de linhas) |
| Aninhamento | `nestif` min-complexity 4: mede a complexidade do `if` aninhado e reporta **a partir de** 4 (não é "número de níveis") | sem regra própria: a cognitiva (que pesa aninhamento) cobre |

**Clean as You Code:** a régua vale para código **novo ou alterado** no diff. Código legado intocado não reprova o
PR (a dívida dele é da `ratchet-qualidade`); mexeu na função, ela passa a obedecer.

### 2.2 Comandos por stack

**Go** — configuração canônica: `../../golang-pro/references/clean-code-e-lint.md` §3 (golangci-lint v2; v2.8.0 é a
última que compila com Go 1.24, as v2 recentes para 1.26/1.27 aceitam a mesma config):

```bash
test -z "$(gofmt -l .)"
go vet ./...
go tool staticcheck ./...                                  # via diretiva tool do go.mod; ausente = MAJOR, nunca "se instalado"
golangci-lint run ./...                                    # gocognit 15 · gocyclo 15 · argument-limit 7 · funlen 60/40 · nestif
# zero supressão inline — inclui #nosec (gosec) e lint:ignore (staticcheck), que somem com o achado
rc=0; grep -rnE --include='*.go' -e '//[[:space:]]*nolint' -e '//[[:space:]]*lint:(file-)?ignore' -e '#nosec' -e 'NOSONAR' . || rc=$?; test "$rc" -eq 1
```

**Python** — configuração canônica: `../../aws-lambda-python/references/clean-code-python.md` §2 (blocos
`[tool.ruff.lint]` + `[tool.complexipy]` no `pyproject.toml`):

```bash
ruff check src tests                                       # C90 max-complexity 15 · PL max-args 7 · FBT/ERA/TRY/T20…
complexipy                                                 # cognitiva <= 15 (complexipy==8.3.0 no grupo dev)
# zero supressão inline — inclui as de arquivo inteiro (# ruff: noqa, # mypy: ignore-errors) e # complexipy: ignore
rc=0; grep -rniE '#[[:space:]]*(noqa|type:[[:space:]]*ignore|ruff:[[:space:]]*noqa|mypy:[[:space:]]*ignore|complexipy:[[:space:]]*ignore|pyright:[[:space:]]*ignore)|NOSONAR' src tests || rc=$?; test "$rc" -eq 1
```

Por que `rc=0; grep … || rc=$?; test "$rc" -eq 1` (verificado nos dois casos):
- **não** `! grep …`: se uma pasta não existe o `grep` sai 2 e o `!` transforma o erro em verde;
- **não** `grep …; test $? -eq 1`: com `bash -e` (o `run:` do GitHub Actions usa `-e`) o script morre no `grep` do caso limpo;
- `1` = nada achado (verde); `0` = achou e `2` = erro/pasta ausente (reprovam). Em `Makefile`, escreva `$$?` e `$$rc`.

**Java** — a régua já é medida pelo motor Sonar-First (`python -m scripts.sonar gate <arquivos>`); esta lente só
consolida o resultado no laudo.

**Medido nos exemplos das skills (2026-10-28):** Go — exemplo ruim 17 achados de 13 linters (gocognit 39, 8
parâmetros), lab 0; Python — exemplo ruim 13 achados no ruff + cognitiva 32 no complexipy (a ciclomática dele, 8,
passaria sozinha: por isso as duas medidas), lab 0.

### 2.3 Do número ao veredito

| Situação | Severidade | Veredito |
|---|---|---|
| Função nova/alterada acima de qualquer teto da §2.1 | 🟡 Necessário (MAJOR no `verificacao-loop`) | AGUARDANDO: refatorar, **ou** decisão escrita do dono no GATE 2 (vira card de dívida) |
| Supressão inline nova (qualquer forma da §2.2) | 🟡 Necessário (MAJOR) | AGUARDANDO: remover, ou mover a exceção para a configuração com motivo defensável revisado |
| Exceção nova na configuração do linter sem motivo escrito | 🟡 Necessário (MAJOR) | AGUARDANDO |
| Achado de segurança do linter (`gosec`, regras `S` do ruff) | segue a régua do `engenheiro-seguranca` | 🔴 se HIGH/crítico |
| Ferramenta ausente ou config ausente no projeto | MAJOR nomeado (nunca PASS silencioso) | `NAO_VERIFICADO` para a parte mecânica |
| Afrouxar teto na configuração **sem** ADR com medição | 🔴 (BLOCKER no `verificacao-loop`) — catraca | REQUER NOVO ROUND. Com ADR aprovado citando a medição, o teto novo vale |

Laudo: `.claude/pipeline/<slug>/05d-clean.md` — tabela `arquivo:linha · regra · medido · teto · severidade`, lista
de supressões e exceções conferidas, e a linha "Clean as You Code: N funções tocadas, M acima do teto".

## 3. Checklist de leitura P1.CLEAN (o que ferramenta não vê)

Arquivo por arquivo do diff — cada "não" é um achado com arquivo, linha e a alternativa concreta:

1. **Nomes** revelam intenção na linguagem do domínio (`pedido`, `reservar`), não na da implementação (`data`, `handle2`, `mgr`)? Escopo curto, nome curto; escopo longo, nome descritivo.
2. **Uma coisa por função**, num nível de abstração? O handler só adapta evento → domínio → resposta; regra de negócio fica em função pura testável sem mock.
3. **Efeitos colaterais nas bordas**: I/O (banco, fila, HTTP, relógio, aleatoriedade) entra por parâmetro/interface, não por global escondido; estado global mutável só para as dependências criadas na init.
4. **Erro tratado uma vez**: ou registra, ou propaga com contexto (`%w`, `raise … from`) — nunca "loga e relança"; exceção/erro genérico só na fronteira (lote, handler HTTP).
5. **Sem flag booleana de comportamento** (`processar(x, True)`): duas funções com nomes, ou um tipo/enum.
6. **Sem duplicação de conhecimento**: a mesma regra de negócio em dois lugares é bug esperando; duplicação acidental de 3 linhas parecidas não é.
7. **Sem abstração especulativa**: interface com uma implementação, parâmetro "para o futuro", camada que só repassa — resolva o problema de agora (critério de *over-engineering* do guia de review do Google).
8. **Tipos que impedem estado inválido**: valor validado vira tipo (dataclass `frozen`, `NewType`, struct com construtor que valida) em vez de `dict`/`map[string]any` circulando.
9. **Comentário explica o porquê** (decisão, restrição, link da fonte), nunca repete o código; código comentado é removido.
10. **Testes legíveis**: um comportamento por teste, nome que descreve o cenário, Arrange-Act-Assert, tabela/parametrização para variações; o teste prova o efeito (não só "não lançou").
11. **Código gerado por IA**: passe pelo roteiro de `../../clean-code-craftsman/references/codigo-gerado-por-ia.md` (classificar → travar comportamento com teste → passadas isoladas); quem gerou não aprova a própria limpeza.

## 4. Mudança estrutural × mudança de comportamento

Técnica que esta lente passa a exigir (preparatory refactoring / *tidy first*; guia de *small CLs* do Google):

- **Separe os dois tipos de mudança.** Refatoração (renomear, extrair função, guard clause, mover código, apagar
  código morto) vai num commit — idealmente num PR — **antes** da mudança de comportamento, com a suíte verde antes
  e depois. "Faça a mudança ficar fácil, depois faça a mudança fácil."
- **No review:** diff que mistura refatoração ampla com regra nova → 🟡 AGUARDANDO com o pedido de separação (ou de
  commits separados no mesmo PR). Limpeza pequena no código tocado (renomear uma variável local) pode ficar junto.
- **Tamanho:** ~100 linhas é um tamanho razoável de mudança e ~1000 é grande demais (heurística do Google); 200
  linhas num arquivo é diferente de 200 linhas em 50 arquivos. Exceções: apagar arquivo inteiro e refatoração
  feita por ferramenta automática confiável. Acima de 50 linhas ou 2 domínios, o review vira multi-dimensão
  (`review-multi-dimensao.md`).
- **Teste antes de refatorar:** código sem teste ganha teste de caracterização num commit próprio antes da limpeza.

## 5. Fontes (palavras próprias; nenhum texto copiado)

- Google Engineering Practices — *What to look for in a code review* e *Small CLs* (`google/eng-practices`, commit
  `3bb3ec25b3b0199f4940b1aa75f0ac5c5753301c`, CC-BY 3.0): critérios de complexidade/over-engineering, tamanho e
  separação de refatoração.
- Martin Fowler, *An example of preparatory refactoring* (martinfowler.com) — citando Kent Beck: *make the change
  easy, then make the easy change*.
- Régua: doutrina da squad (`sonar-first-engineering`, `squad-pipeline` §Sonar-First) — não é número novo.
- Técnicas por stack (Go/Python): `aws-lambda-go`, `golang-pro`, `aws-lambda-python` (ver §2.2).
