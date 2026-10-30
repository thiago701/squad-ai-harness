# Clean code em Python para Lambda — técnicas e gate verificável

> Estado de verificação (2026-10-28): gate executado de verdade no projeto de exemplo — `ruff` 0.17.3 (regras abaixo) e
> `complexipy` 8.3.0 (complexidade cognitiva) com **0 achados** em `src/` e `tests/`, `mypy --strict` limpo em `src` **e** `tests`,
> 20 testes verdes, contrato com o `awslambdaric` inalterado; o gate de supressão inline passou na prova de mutação (§3). O exemplo ruim deliberado (§4) dispara 13 achados de `ruff` e
> cognitiva 32 no `complexipy`. Princípios gerais (nomes, funções, comentários, smells, testes limpos) → **clean-code-craftsman**;
> aqui fica o que é **específico de Python em Lambda** e o que dá para **checar por máquina**.

## 1. Os limiares da squad (iguais aos do Sonar) e onde cada um é medido

| Limiar | Regra Sonar | Ferramenta em Python | Configuração |
|---|---|---|---|
| Complexidade **cognitiva** ≤ 15 por função | **S3776** | `complexipy` | `[tool.complexipy] max-complexity-allowed = 15` |
| Complexidade **ciclomática** ≤ 15 por função | **S1541** | `ruff` `C901` (mccabe) | `[tool.ruff.lint.mccabe] max-complexity = 15` |
| Parâmetros ≤ 7 por função (gate; mire em ≤ 3–4) | **S107** | `ruff` `PLR0913` | `[tool.ruff.lint.pylint] max-args = 7` |
| Posicionais ≤ 3 (o resto keyword-only, `*`) | — | `ruff` `PLR0917` | `max-positional-args = 3` |
| Ramos ≤ 12, retornos ≤ 6 por função | — | `ruff` `PLR0912`/`PLR0911` | `max-branches`, `max-returns` |
| Tamanho da função: ≤ 50 **instruções** (não há limite de **linhas** no gate) | — | `ruff` `PLR0915` | `max-statements = 50` |
| Aninhamento: **sem regra própria** no gate (o `PLR1702` do ruff é *preview*) — a cognitiva pune cada nível | S3776 | `complexipy` | — |
| **Zero supressão inline** (`# noqa`, `# ruff: noqa`, `# type: ignore`, `# mypy: ignore-errors`, `# complexipy: ignore`, `# pyright: ignore`, `NOSONAR`) | doutrina Sonar-First | `grep` no gate (§3) | exceção só em `per-file-ignores`, por caminho e com o porquê |

Por que medir as **duas** complexidades: no exemplo ruim da §4, a ciclomática da função é **8** (passa no `C901`) e a cognitiva é
**32** (reprova no `complexipy`). A ciclomática conta caminhos; a cognitiva pune **aninhamento** — exatamente o que torna um handler
difícil de ler. Sem o `complexipy`, o pior trecho passaria no gate.

## 2. Configuração canônica (a do projeto, verificada)

`pyproject.toml`:

```toml
[project]
name = "pedidos"
version = "0.1.0"
requires-python = ">=3.14"
dependencies = [
    "aws-lambda-powertools[parser]>=3.38,<4",
    "boto3>=1.43,<2",
]

[dependency-groups]
dev = [
    "pytest>=9", "moto[dynamodb]>=5.2", "ruff>=0.17", "mypy>=2.4", "boto3-stubs[dynamodb]",
    "aws-durable-execution-sdk-python-testing>=1.4", "awslambdaric>=4.2", "pyyaml>=6", "types-PyYAML", "complexipy==8.3.0",
]
durable = ["aws-durable-execution-sdk-python>=3,<4"]

[build-system]
requires = ["uv_build>=0.11,<0.12"]
build-backend = "uv_build"

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 110
target-version = "py314"

[tool.ruff.lint]
# Gate de clean code da squad: limiares alinhados ao Sonar (S3776 cognitiva <= 15, S1541 ciclomática <= 15).
select = [
    "E", "W", "F", "I", "UP", "B", "S", "BLE", "SIM", "RUF",  # base: erros, imports, modernização, bugs, segurança
    "C90",                                                   # complexidade ciclomática (mccabe)
    "PL",                                                    # pylint: tamanho de função, argumentos, ramos, retornos
    "N",                                                     # nomes PEP 8
    "RET", "PIE", "C4", "PERF",                              # retorno, redundância, comprehensions, desempenho
    "ERA",                                                   # código comentado
    "FBT",                                                   # flag booleana como parâmetro
    "ARG",                                                   # argumento não usado
    "TRY",                                                   # tratamento de exceção
    "T20",                                                   # print() esquecido
    "PT",                                                    # estilo de pytest
]
ignore = [
    "N818",  # exceções de domínio em PT-BR (MensagemInvalida): o N818 só aceita o sufixo inglês "Error"
]

[tool.ruff.lint.mccabe]
max-complexity = 15  # Sonar S1541 (ciclomática)

[tool.ruff.lint.pylint]
max-args = 7  # Sonar S107 (gate); mire em <= 3-4
max-positional-args = 3
max-branches = 12
max-returns = 6
max-statements = 50

[tool.ruff.lint.per-file-ignores]
# Supressão é decisão de configuração revisada, nunca comentário no código (zero noqa/type: ignore inline).
"tests/**" = [
    "S101",     # assert é a linguagem do pytest (em src continua proibido)
    "PLR2004",  # número na asserção é o próprio dado esperado
    "S106",     # credenciais FALSAS exigidas pelo moto (os.environ.update em conftest.py)
    "TRY003",   # mensagem de erro em dublê de teste é o próprio dado
]

[tool.complexipy]
paths = ["src", "tests"]
max-complexity-allowed = 15  # Sonar S3776 (cognitiva)

[tool.mypy]
strict = true
# Powertools e snapshot_restore_py expõem decorators sem tipo; o resto continua estrito.
disallow_untyped_decorators = false

[[tool.mypy.overrides]]
module = ["snapshot_restore_py"]
ignore_missing_imports = true
```

Decisões registradas na própria configuração (é ali que se revisa, não no código):

- `N818` desligado: exceções de domínio em PT-BR (`MensagemInvalida`) — a regra só aceita o sufixo inglês `Error`.
- `tests/**`: `S101` (`assert` é a linguagem do pytest), `PLR2004` (o número na asserção é o dado esperado), `S106`
  (credenciais **falsas** do `moto`) e `TRY003` (mensagem de dublê de teste). Nada além disso: em `src`, `assert` continua
  proibido (some com `python -O`) e não há exceção.
- `complexipy` mede `src` **e** `tests` (teste ilegível também é dívida).
- Ferramentas de lint/tipos no grupo `dev`, com `complexipy` **fixado** (`==8.3.0`): mudar a versão muda a nota — atualize de propósito.

## 3. Gate (os comandos que o pipeline roda)

```bash
uv run ruff format --check src tests
uv run ruff check src tests                 # inclui C901 (S1541), PLR0913 (S107), FBT, ERA, T20, TRY...
uv run complexipy                           # S3776: lê [tool.complexipy] (src e tests, teto 15); sai 1 se algo passar
uv run mypy src tests                       # --strict pelo pyproject
bash exemplos/gate_supressao.sh src tests   # zero supressão inline (abaixo)
uv run pytest -q
```

Cada comando sai com código ≠ 0 quando reprova (conferido: `complexipy` no exemplo ruim → 1; em `src`/`tests` → 0).

O gate de supressão precisa pegar também as formas **de arquivo inteiro** — `# ruff: noqa` no topo cala o ruff no arquivo todo e
`# complexipy: ignore` esconde a cognitiva (os dois conferidos no controle abaixo):

`exemplos/gate_supressao.sh`:

```bash
#!/usr/bin/env bash
# Gate de supressão inline. grep sai 0 = achou (reprova), 1 = nada (passa), 2 = erro (reprova).
# Por que não `! grep ...`: o bash ignora `set -e` em comando negado — a linha nunca derruba o script.
# Por que não `grep ...; test $? -eq 1`: com `set -e` (o padrão do `run:` no GitHub Actions) o script
# morre no próprio grep quando ele sai 1 — o caso LIMPO — antes do test rodar.
set -euo pipefail
rc=0
grep -rniE '#[[:space:]]*(noqa|type:[[:space:]]*ignore|ruff:[[:space:]]*noqa|mypy:[[:space:]]*ignore|complexipy:[[:space:]]*ignore|pyright:[[:space:]]*ignore)|NOSONAR' "$@" || rc=$?
test "$rc" -eq 1
```

Por que essa forma e não as óbvias (conferido com `bash -e`):

- `! grep ...` — no meio de um script com `set -e`, o bash **ignora** falha de comando negado: o grep acha a supressão e o script
  segue (só reprovaria se fosse a última linha, o que é frágil).
- `grep ...; test $? -eq 1` — com `set -e` (o padrão do `run:` do GitHub Actions) o script morre **no próprio grep** quando ele sai
  1, que é justamente o caso **limpo**: o gate reprova código bom.
- `rc=0; grep ... || rc=$?; test "$rc" -eq 1` — 1 (nada achado) passa; 0 (achou) e 2 (pasta ausente, erro) reprovam. Em
  `Makefile`, escreva `$$?` e `$$rc`.

Prova de mutação (cada forma de supressão injetada no exemplo ruim faz o gate reprovar; o limpo passa; pasta ausente reprova):

`exemplos/mutacao_supressao.sh`:

```bash
#!/usr/bin/env bash
# Prova de mutação do gate de supressão: cada forma de supressão (1) cala a ferramenta e (2) reprova o gate.
set -euo pipefail
cd "$(dirname "$0")/.."
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
falhou=0
checa() {  # $1 = rótulo, $2 = arquivo mutante
    if bash exemplos/gate_supressao.sh "$2" >/dev/null 2>&1; then echo "FALHA: gate deixou passar $1"; falhou=1
    else echo "ok: gate reprova $1"; fi
}
# ruim.py: 13 achados do ruff e cognitiva 32 — cada supressão esconde a sua parte
for forma in "# ruff: noqa" "# complexipy: ignore" "# mypy: ignore-errors" "NOSONAR"; do
    m="$TMP/m$RANDOM.py"; { echo "$forma"; cat exemplos/ruim.py; } > "$m"; checa "'$forma' no topo" "$m"
done
for forma in "# noqa" "# noqa: PLR0913" "# type: ignore" "# pyright: ignore[reportGeneralTypeIssues]" "#NoQA"; do
    m="$TMP/m$RANDOM.py"; sed "9s|\$|  $forma|" exemplos/ruim.py > "$m"; checa "'$forma' na linha" "$m"
done
# controle: as supressões de fato calam as ferramentas (por isso o grep é obrigatório)
m="$TMP/ctrl_ruff.py"; { echo "# ruff: noqa"; cat exemplos/ruim.py; } > "$m"
uv run -q ruff check --no-cache "$m" >/dev/null && echo "controle: '# ruff: noqa' calou o ruff"
m="$TMP/ctrl_cx.py"; sed 's|^def processar(|def processar(  # complexipy: ignore\n    |' exemplos/ruim.py > "$m"
uv run -q complexipy "$m" >/dev/null 2>&1 && echo "controle: '# complexipy: ignore' escondeu a cognitiva 32"
# limpo passa, pasta ausente reprova
bash exemplos/gate_supressao.sh src tests && echo "ok: src e tests limpos passam"
if bash exemplos/gate_supressao.sh pasta_inexistente 2>/dev/null; then echo "FALHA: pasta ausente passou"; falhou=1
else echo "ok: pasta ausente reprova"; fi
exit "$falhou"
```

Saída observada: as 9 formas reprovadas (`# ruff: noqa`, `# complexipy: ignore`, `# mypy: ignore-errors` e `NOSONAR` no topo;
`# noqa`, `# noqa: PLR0913`, `# type: ignore`, `# pyright: ignore[...]` e `#NoQA` na linha), os dois controles confirmados
("`# ruff: noqa` calou o ruff", "`# complexipy: ignore` escondeu a cognitiva 32"), `src tests` limpos passam, pasta ausente
reprova — saída 0 do script.

## 4. Exemplo ruim deliberado → o que o gate aponta → a versão limpa

`exemplos/ruim.py` (fora do pacote; existe só para provar o gate):

`exemplos/ruim.py`:

```python
"""Exemplo DELIBERADAMENTE ruim (fora do pacote): cada trecho dispara uma regra do gate."""

import logging

logger = logging.getLogger(__name__)
CACHE = {}


def processar(registros, tabela, regiao, tentativas, timeout, cliente, debug: bool, dry_run: bool):
    falhas = []
    for r in registros:
        if r.get("body"):
            if r["body"].startswith("{"):
                if "pedido_id" in r["body"]:
                    if len(r["body"]) < 65536:
                        try:
                            if not dry_run:
                                cliente.put_item(TableName=tabela, Item={"pk": {"S": r["body"]}})
                                CACHE[r["messageId"]] = True
                            else:
                                print("dry run", r["messageId"])
                        except Exception:
                            pass
                    else:
                        falhas.append(r["messageId"])
                else:
                    falhas.append(r["messageId"])
            else:
                falhas.append(r["messageId"])
        # if debug:
        #     logger.info(r)
    return {"batchItemFailures": [{"itemIdentifier": f} for f in falhas]}
```

Achados reais (`ruff check exemplos/ruim.py --statistics` + `complexipy exemplos/ruim.py`):

| Regra | Quantidade | O que denuncia |
|---|---|---|
| `complexipy` (S3776) | cognitiva **32** > 15 | seis níveis de `if`/`try` aninhados |
| `PLR0913` (S107) / `PLR0917` | 8 > 7 / 8 > 3 | lista de parâmetros que é configuração disfarçada |
| `ARG001` | 4 | parâmetros que ninguém usa (`regiao`, `tentativas`, `timeout`, `debug`) |
| `FBT001` | 2 | `debug: bool`, `dry_run: bool` — flag que divide a função em duas |
| `S110` + `BLE001` | 1 + 1 | `except Exception: pass` — engole a falha e a mensagem some sem rastro |
| `T201` | 1 | `print` no lugar de log |
| `ERA001` | 1 | código comentado |
| `PLR2004` | 1 | `65536` sem nome |
| `C901` (S1541) | **não** dispara | ciclomática 8 — por isso a cognitiva é obrigatória |

`exemplos/bom.py` — mesma intenção, cognitiva 3 e 2, 0 achados, `mypy --strict` limpo:

`exemplos/bom.py`:

```python
"""A mesma intenção do ruim.py, limpa: validação pura, efeito injetado, uma fronteira de erro."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from pedidos.dominio import MensagemInvalida, Pedido, ler_pedido

logger = logging.getLogger(__name__)

Gravar = Callable[[Pedido], None]


def processar(registros: Sequence[Mapping[str, Any]], gravar: Gravar) -> dict[str, list[dict[str, str]]]:
    falhas = [r["messageId"] for r in registros if not _tentar(r, gravar)]
    return {"batchItemFailures": [{"itemIdentifier": f} for f in falhas]}


def _tentar(registro: Mapping[str, Any], gravar: Gravar) -> bool:
    try:
        gravar(ler_pedido(registro["body"]))
    except MensagemInvalida as exc:
        logger.warning(
            "mensagem inválida", extra={"message_id": registro["messageId"], "motivo": exc.motivo.name}
        )
        return False
    except Exception:  # fronteira do lote: a falha fica nesta mensagem
        logger.exception("falha ao gravar", extra={"message_id": registro["messageId"]})
        return False
    return True
```

O que mudou, técnica por técnica: validação extraída para a função pura `ler_pedido` (reaproveitada e testada sozinha); o efeito
(`gravar`) **injetado por parâmetro** em vez de cliente + tabela + região soltos; a flag `dry_run` vira **outra função de efeito**
(um `gravar` que não grava), não um `if` dentro do handler; um único `try` na **fronteira** de cada mensagem, que registra e
devolve `False`; nenhum estado global mutável (`CACHE` some).

## 5. Pares antes → depois aplicados neste projeto (o gate obrigou)

**Mensagem de erro em string → motivo como tipo fechado** (`TRY003`, e o log deixa de carregar texto livre):

```python
# antes
if not isinstance(pedido_id, str) or not 1 <= len(pedido_id) <= 64:
    raise MensagemInvalida("pedido_id inválido")
```

```python
# depois
class Motivo(StrEnum):
    PEDIDO_ID = "pedido_id inválido"
    ...

class MensagemInvalida(ValueError):
    def __init__(self, motivo: Motivo) -> None:
        super().__init__(motivo.value)
        self.motivo = motivo

if not isinstance(pedido_id, str) or not 1 <= len(pedido_id) <= MAX_PEDIDO_ID:
    raise MensagemInvalida(Motivo.PEDIDO_ID)
```

O conjunto de motivos fica **fechado** (não dá para inventar um sexto sem mudar o tipo), o log grava `motivo.name` (seguro para
métrica, sem dado do cliente) e o `64` ganhou nome (`PLR2004`).

**`raise` dentro do próprio `try` para desviar o fluxo → cláusula de guarda** (`TRY301`):

```python
# antes
for pos, reg in enumerate(registros):
    try:
        if restante_ms() < MARGEM_MS:
            raise TimeoutError("prazo esgotado")
        processar(ler_pedido(reg["body"]))
    except Exception:
        ...
        return _resposta(r["messageId"] for r in registros[pos:])
```

```python
# depois
for pos, reg in enumerate(registros):
    pendentes = registros[pos:]
    if restante_ms() < MARGEM_MS:
        logger.warning("FIFO sem prazo; devolvendo à fila", extra={"devolvidas": len(pendentes)})
        return _resposta(r["messageId"] for r in pendentes)
    try:
        processar(ler_pedido(reg["body"]))
    except Exception:  # fronteira do lote: qualquer falha para a fila, preservando a ordem
        ...
        return _resposta(r["messageId"] for r in pendentes)
```

Exceção não é `goto`: falta de prazo é um caso **esperado**, tratado antes, com log próprio — e o `except` passa a significar só "a
mensagem falhou".

**`logger.error` para entrada inválida esperada → `warning` sem stack trace** (`TRY400` apontou): mensagem inválida não é falha do
sistema; ela vira métrica/DLQ. `logger.exception` fica para o inesperado.

**Supressão inline → configuração revisada ou código que não dispara:** `# noqa: S506` no `yaml.load` dos testes virou
`_CfnLoader(texto).get_single_data()` (o loader deriva do `SafeLoader`); os `# type: ignore[arg-type]` dos testes sumiram tipando o
evento de teste (`dict[str, list[dict[str, Any]]]`); `# noqa: S106` virou entrada justificada em `per-file-ignores`.

## 6. Técnicas para handlers Python (o que a máquina não mede sozinha)

- **Handler é adaptador:** traduz `event`/`context` → chamada de função pura e o resultado → resposta. Regra prática: se o handler
  tem `if` de negócio, a lógica está no lugar errado.
- **Dependência por parâmetro, não framework:** o efeito entra como `Callable` (`processar`, `gravar`) ou objeto pequeno; o cliente
  `boto3` é criado na init e passado. Teste troca o efeito por uma função — sem `patch` de módulo.
- **Estado inválido irrepresentável:** `@dataclass(frozen=True, slots=True)` para valores, `StrEnum`/`Literal` para conjuntos
  fechados, `NewType` para ids que não podem ser trocados (`PedidoId` × `ClienteId`). Valide **uma vez** na entrada; dali em diante
  o tipo garante.
- **Erros:** exceção de domínio específica (`MensagemInvalida`) com dado estruturado; `raise ... from exc` para preservar a causa;
  `except Exception` **só** na fronteira do lote/requisição, sempre com `logger.exception`; nunca `except: pass`.
- **Sem flag booleana como parâmetro:** duas funções, ou o comportamento injetado (§4). `*` torna argumentos de configuração
  keyword-only (`PLR0917`).
- **Retorno antecipado** e cláusulas de guarda em vez de pirâmide; uma função = um nível de abstração.
- **Nomes do domínio** (PT-BR, como no restante do código); constantes nomeadas no topo do módulo (`MARGEM_MS`, `MAX_PEDIDO_ID`).
- **Global só para o que é da init** (clientes, configuração lida uma vez). Nada de cache mutável em módulo para dado de cliente —
  ambientes são reaproveitados entre invocações e entre chamadores.
- **Testes:** Arrange-Act-Assert visível, `pytest.mark.parametrize` para variações de entrada hostil, um comportamento por teste,
  asserção do **efeito** (o que foi gravado), não da implementação. Teste também tipado e lintado (o gate inclui `tests`).

## 7. Fontes (reescritas em palavras próprias)

PEP 8 e PEP 20 (domínio público); Google Python Style Guide (CC BY 3.0); documentação das regras do `ruff` (MIT) e do `complexipy`
(MIT); o conceito de complexidade cognitiva segue o artigo da SonarSource que define a S3776 — só o conceito, sem texto copiado.
