# Handlers, lote SQS, HTTP e idempotência — Python no AWS Lambda

> Estado de verificação (2026-10-28): todo o código abaixo roda em **Python 3.14.6** (e a suíte também passa em 3.13.18) com `aws-lambda-powertools` 3.38.0,
> `boto3` 1.43.121, `pydantic` 2.14.1 e `moto` 5.2.5 — **20 testes `pytest` passando**, `ruff check`/`ruff format --check`
> limpos, `complexipy` 8.3.0 (cognitiva ≤ 15) sem achado e `mypy --strict` sem erro em `src` e `tests`. Nada aqui foi implantado na AWS: o comportamento de nuvem (latência, cold start) não foi medido.

## 1. Estrutura do projeto

```text
pedidos/
├── pyproject.toml          # dependências de produção + grupos dev/durable (uv)
├── uv.lock                 # versionado: o build usa --frozen
├── template.yaml           # SAM (references/iac-e-teste-local.md)
├── Makefile                # build do pacote com uv (references/empacotamento-e-cold-start.md)
├── src/pedidos/
│   ├── dominio.py          # validação e modelo — puro, sem AWS
│   ├── lote.py             # falha parcial padrão e FIFO — stdlib
│   ├── handler_sqs.py      # entrada SQS só com stdlib + boto3
│   ├── modelos.py          # Pydantic (Powertools Parser)
│   ├── handler_sqs_pt.py   # entrada SQS com Powertools
│   ├── handler_http.py     # HTTP API v2 com Powertools Event Handler
│   ├── snapstart.py        # ganchos de SnapStart (references/modelos-de-execucao.md)
│   └── handler_durable.py  # durable function (references/modelos-de-execucao.md)
└── tests/                  # pytest + moto + contrato com o runtime real
```

Regra que organiza tudo: **o handler só adapta**. Validação (`dominio`) e o algoritmo do lote (`lote`) são funções puras,
testadas sem mock; o handler injeta o efeito (`gravar`) e o relógio (`context.get_remaining_time_in_millis`).

## 2. Validação da entrada (código puro)

A mensagem é dado não confiável: tamanho, JSON, conjunto **exato** de campos e tipos são checados **antes** de qualquer efeito.
`MensagemInvalida` sinaliza "reprocessar não adianta" — a mensagem falha, volta à fila e, depois de `maxReceiveCount`, vai para a DLQ.

`src/pedidos/dominio.py`:

```python
"""Modelo e validação do pedido — código puro, sem AWS (testável sem mock)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum

MAX_CORPO_BYTES = 64 * 1024
MAX_PEDIDO_ID = 64
CAMPOS = frozenset({"pedido_id", "valor_centavos"})


class Motivo(StrEnum):
    """Por que a mensagem foi recusada — conjunto fechado, seguro para log e métrica."""

    CORPO_GRANDE = "corpo acima do limite"
    JSON_INVALIDO = "JSON inválido"
    CAMPOS = "campos ausentes ou desconhecidos"
    PEDIDO_ID = "pedido_id inválido"
    VALOR = "valor_centavos inválido"


class MensagemInvalida(ValueError):
    """Entrada que nunca vai passar: reprocessar não adianta (segue para a DLQ)."""

    def __init__(self, motivo: Motivo) -> None:
        super().__init__(motivo.value)
        self.motivo = motivo


@dataclass(frozen=True, slots=True)
class Pedido:
    pedido_id: str
    valor_centavos: int


def ler_pedido(corpo: str) -> Pedido:
    """Valida tamanho, formato e campos ANTES de qualquer efeito colateral."""
    if len(corpo.encode()) > MAX_CORPO_BYTES:
        raise MensagemInvalida(Motivo.CORPO_GRANDE)
    try:
        dados = json.loads(corpo)
    except json.JSONDecodeError as exc:
        raise MensagemInvalida(Motivo.JSON_INVALIDO) from exc
    if not isinstance(dados, dict) or set(dados) != CAMPOS:
        raise MensagemInvalida(Motivo.CAMPOS)
    pedido_id, valor = dados["pedido_id"], dados["valor_centavos"]
    if not isinstance(pedido_id, str) or not 1 <= len(pedido_id) <= MAX_PEDIDO_ID:
        raise MensagemInvalida(Motivo.PEDIDO_ID)
    if type(valor) is not int or valor <= 0:  # bool é subclasse de int: rejeitado de propósito
        raise MensagemInvalida(Motivo.VALOR)
    return Pedido(pedido_id, valor)
```

Detalhe que os testes pegam: `type(valor) is not int` rejeita `true` (em Python, `bool` é subclasse de `int`; `isinstance` aceitaria).

## 3. Lote SQS com falha parcial (biblioteca padrão)

`src/pedidos/lote.py`:

```python
"""Lote SQS com falha parcial (ReportBatchItemFailures) — biblioteca padrão apenas."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

from pedidos.dominio import MensagemInvalida, Pedido, ler_pedido

logger = logging.getLogger(__name__)

MARGEM_MS = 500  # folga para responder antes do timeout da função

Registro = Mapping[str, Any]
Resposta = dict[str, list[dict[str, str]]]


def _resposta(ids: Iterable[str]) -> Resposta:
    # Lista vazia = sucesso total. Nunca devolva itemIdentifier vazio/inexistente: o LOTE INTEIRO volta.
    return {"batchItemFailures": [{"itemIdentifier": i} for i in ids]}


def processar_lote(
    registros: Sequence[Registro],
    processar: Callable[[Pedido], None],
    restante_ms: Callable[[], int],
) -> Resposta:
    """Fila padrão: cada mensagem falha sozinha; o que não couber no prazo volta para a fila."""
    falhas: list[str] = []
    for pos, reg in enumerate(registros):
        if restante_ms() < MARGEM_MS:
            falhas.extend(r["messageId"] for r in registros[pos:])
            logger.warning("prazo esgotado; devolvendo à fila", extra={"pendentes": len(registros) - pos})
            break
        mid = reg["messageId"]
        try:
            processar(ler_pedido(reg["body"]))
        except MensagemInvalida as exc:  # esperado: entrada ruim, sem stack trace no log
            logger.warning("mensagem inválida", extra={"message_id": mid, "motivo": exc.motivo.name})
            falhas.append(mid)
        except Exception:  # uma mensagem nunca derruba o lote
            logger.exception("falha ao processar", extra={"message_id": mid})
            falhas.append(mid)
    return _resposta(falhas)


def processar_lote_fifo(
    registros: Sequence[Registro],
    processar: Callable[[Pedido], None],
    restante_ms: Callable[[], int],
) -> Resposta:
    """FIFO: em ordem; na 1ª falha (ou sem prazo) devolve ela e TODAS as seguintes, sem processá-las."""
    for pos, reg in enumerate(registros):
        pendentes = registros[pos:]
        if restante_ms() < MARGEM_MS:
            logger.warning("FIFO sem prazo; devolvendo à fila", extra={"devolvidas": len(pendentes)})
            return _resposta(r["messageId"] for r in pendentes)
        try:
            processar(ler_pedido(reg["body"]))
        except Exception:  # fronteira do lote: qualquer falha para a fila, preservando a ordem
            logger.exception(
                "FIFO parou", extra={"message_id": reg["messageId"], "devolvidas": len(pendentes)}
            )
            return _resposta(r["messageId"] for r in pendentes)
    return _resposta([])
```

O que este código garante (cada item tem teste em `tests/test_lote.py`):

- **falha parcial:** só os `messageId` que falharam voltam; erro de **uma** mensagem nunca escapa do handler (se escapar, o lote inteiro volta);
- **lote vazio:** `{"batchItemFailures": []}` (lista vazia = sucesso total);
- **prazo:** sem tempo para a próxima, devolve ela e as seguintes **sem processar**;
- **FIFO:** na 1ª falha devolve ela e **todas** as seguintes, preservando a ordem do grupo.

Concorrência dentro do lote: o padrão é **sequencial** (P1). Se o trabalho for I/O e o volume exigir, prefira aumentar
`MaximumConcurrency` da event source mapping (mais invocações) a abrir threads no handler; se usar `ThreadPoolExecutor`, limite os
workers, dê timeout a cada chamada downstream menor que o tempo restante e **espere todas** antes de retornar — thread viva depois do
`return` congela com o ambiente e "vaza" para a próxima invocação. `async def` não é aceito como handler; `asyncio.run(...)` dentro do
handler funciona, mas raramente compensa a complexidade.

## 4. Ponto de entrada SQS + idempotência com escrita condicional

`src/pedidos/handler_sqs.py`:

```python
"""Entrada SQS sem Powertools. Handler: pedidos.handler_sqs.lambda_handler"""

from __future__ import annotations

import logging
import os
from typing import Any

import boto3
from botocore.config import Config

from pedidos.dominio import Pedido
from pedidos.lote import Resposta, processar_lote

logger = logging.getLogger(__name__)

# INIT: roda uma vez por ambiente de execução e é reaproveitado entre invocações.
_CONFIG = Config(connect_timeout=2, read_timeout=5, retries={"mode": "standard", "max_attempts": 3})
_DDB = boto3.client("dynamodb", config=_CONFIG)
_TABELA = os.environ["TABELA_PEDIDOS"]  # falha na init, visível no log, se faltar


def gravar(pedido: Pedido) -> None:
    """Efeito idempotente: escrita condicional — a 2ª entrega do mesmo pedido vira no-op."""
    try:
        _DDB.put_item(
            TableName=_TABELA,
            Item={"pk": {"S": pedido.pedido_id}, "valor_centavos": {"N": str(pedido.valor_centavos)}},
            ConditionExpression="attribute_not_exists(pk)",
        )
    except _DDB.exceptions.ConditionalCheckFailedException:
        logger.info("pedido já gravado (entrega duplicada)", extra={"pedido_id": pedido.pedido_id})


def lambda_handler(event: dict[str, Any], context: Any) -> Resposta:
    return processar_lote(event.get("Records", []), gravar, context.get_remaining_time_in_millis)
```

- `boto3.client` sem `Config` usa timeout de conexão e de leitura de **60 s** — maior que o timeout de muitas funções. Sempre configure.
- A escrita condicional (`attribute_not_exists(pk)`) torna a reentrega do mesmo pedido um no-op: SQS é *at-least-once*. O teste
  manda o mesmo pedido com outro valor e confere que o 1º valor ficou — contar itens não prova nada, porque `put_item` na mesma chave
  sobrescreve (um mutante sem a condição passava num teste assim).
- A variável obrigatória lida no import falha a **init** de forma visível — o runtime reporta `KeyError: 'TABELA_PEDIDOS'` como erro
  de init (verificado com `awslambdaric` contra o Runtime API simulado) — em vez de falhar mensagem a mensagem.
- Teste local: o `botocore` lê a região de `AWS_DEFAULT_REGION` (só `AWS_REGION` dá `NoRegionError`, verificado); no Lambda as duas
  variáveis já vêm definidas.

## 5. A mesma coisa com Powertools (Batch + Parser + Idempotency + Logger)

`src/pedidos/modelos.py`:

```python
"""Modelos Pydantic (Powertools Parser): validação estrita da entrada não confiável."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PedidoIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)  # campo desconhecido = inválido

    pedido_id: str = Field(min_length=1, max_length=64)
    valor_centavos: int = Field(gt=0)
```

`src/pedidos/handler_sqs_pt.py`:

```python
"""Entrada SQS com Powertools (Batch + Parser + Idempotency + Logger).

Handler: pedidos.handler_sqs_pt.lambda_handler
"""

from __future__ import annotations

import os
from typing import Any

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.batch import BatchProcessor, EventType, process_partial_response
from aws_lambda_powertools.utilities.batch.types import PartialItemFailureResponse
from aws_lambda_powertools.utilities.data_classes.sqs_event import SQSRecord
from aws_lambda_powertools.utilities.idempotency import (
    DynamoDBPersistenceLayer,
    IdempotencyConfig,
    idempotent_function,
)
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.config import Config

from pedidos.modelos import PedidoIn

logger = (
    Logger()
)  # JSON no stdout; nível via POWERTOOLS_LOG_LEVEL (ou o ApplicationLogLevel do LoggingConfig)

_CONFIG = Config(connect_timeout=2, read_timeout=5, retries={"mode": "standard", "max_attempts": 3})
_DDB = boto3.client("dynamodb", config=_CONFIG)
_TABELA = os.environ["TABELA_PEDIDOS"]

processor = BatchProcessor(event_type=EventType.SQS)
_idem_config = IdempotencyConfig(
    event_key_jmespath="pedido_id",
    payload_validation_jmespath="valor_centavos",  # mesmo pedido com valor diferente = erro, não "já feito"
    raise_on_no_idempotency_key=True,  # padrão é False: sem a chave, a idempotência é PULADA em silêncio
    expires_after_seconds=24 * 3600,
)
_persistencia = DynamoDBPersistenceLayer(table_name=os.environ["TABELA_IDEMPOTENCIA"], boto_config=_CONFIG)


@idempotent_function(data_keyword_argument="pedido", config=_idem_config, persistence_store=_persistencia)
def gravar(pedido: PedidoIn) -> dict[str, str]:
    _DDB.put_item(
        TableName=_TABELA,
        Item={"pk": {"S": pedido.pedido_id}, "valor_centavos": {"N": str(pedido.valor_centavos)}},
    )
    return {"pedido_id": pedido.pedido_id}


def record_handler(record: SQSRecord) -> None:
    pedido = PedidoIn.model_validate_json(record.body)  # ValidationError -> falha SÓ desta mensagem
    gravar(pedido=pedido)


@logger.inject_lambda_context(clear_state=True)  # log_event=False (padrão): nunca logar o evento inteiro
def lambda_handler(event: dict[str, Any], context: LambdaContext) -> PartialItemFailureResponse:
    _idem_config.register_lambda_context(context)  # obrigatório com idempotent_function: usa o prazo restante
    return process_partial_response(
        event=event, record_handler=record_handler, processor=processor, context=context
    )
```

Comportamentos do Powertools 3.38.0 **verificados nos testes** (`tests/test_handlers.py`) — conheça-os antes de adotar:

| Situação | O que acontece |
|---|---|
| Algumas mensagens falham | resposta com só os `messageId` que falharam (igual à versão stdlib) |
| **Todas** falham | `process_partial_response` **levanta** `BatchProcessingError` (o lote inteiro volta, com o backoff da fila). Para devolver a lista completa em vez de levantar: `BatchProcessor(..., raise_on_entire_batch_failure=False)` |
| `Records` vazio (evento de teste) | **levanta** `UnexpectedBatchTypeError` — o SQS não entrega lote vazio, mas o seu teste de fumaça pode |
| Campo extra / tipo errado | `ValidationError` do Pydantic → falha só daquela mensagem (`extra="forbid"`, `strict=True`) |
| Reentrega do mesmo `pedido_id` (no mesmo lote ou em outra invocação) | Idempotency devolve o resultado salvo e o `put_item` roda **uma** vez só (o teste espiona as chamadas; tabela com chave `id` e TTL em `expiration`, os padrões do `DynamoDBPersistenceLayer`) |
| Mesmo `pedido_id` com **valor diferente** | com `payload_validation_jmespath` vira `IdempotencyValidationError` → falha daquela mensagem (conflito vai para a DLQ, não é tratado como "já feito") |
| Chave de idempotência ausente | com o padrão `raise_on_no_idempotency_key=False` a idempotência é **pulada em silêncio** → use `True` |

- `register_lambda_context(context)` é obrigatório com `idempotent_function`: o Powertools usa o tempo restante para expirar o
  registro "em andamento" se a função morrer no meio.
- FIFO: `SqsFifoPartialProcessor()` para na 1ª falha; `skip_group_on_error=True` só continua os **outros** `MessageGroupId` — use
  apenas se os grupos forem realmente independentes.
- `Logger(log_event=False)` é o padrão: **não** ligue `log_event` em produção (o evento tem dado do cliente).

## 6. API Gateway HTTP API (payload v2)

`src/pedidos/handler_http.py`:

```python
"""API Gateway HTTP API (payload v2) com Powertools Event Handler e validação Pydantic.

Handler: pedidos.handler_http.lambda_handler
"""

from __future__ import annotations

import os
from http import HTTPStatus
from typing import Annotated, Any

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver, Response, content_types
from aws_lambda_powertools.event_handler.openapi.params import Path
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.config import Config

from pedidos.modelos import PedidoIn

logger = Logger()
app = APIGatewayHttpResolver(enable_validation=True)  # corpo/parâmetros inválidos -> 422 sem tocar no handler

_DDB = boto3.client(
    "dynamodb", config=Config(connect_timeout=2, read_timeout=3, retries={"mode": "standard"})
)
_TABELA = os.environ["TABELA_PEDIDOS"]


@app.get("/pedidos/<pedido_id>")
def buscar(pedido_id: Annotated[str, Path(min_length=1, max_length=64)]) -> Response[dict[str, Any]]:
    item = _DDB.get_item(TableName=_TABELA, Key={"pk": {"S": pedido_id}}).get("Item")
    if item is None:
        return Response(HTTPStatus.NOT_FOUND, content_types.APPLICATION_JSON, {"erro": "não encontrado"})
    return Response(
        HTTPStatus.OK,
        content_types.APPLICATION_JSON,
        {"pedido_id": pedido_id, "valor_centavos": int(item["valor_centavos"]["N"])},
    )


@app.post("/pedidos")
def criar(pedido: PedidoIn) -> Response[dict[str, str]]:
    _DDB.put_item(
        TableName=_TABELA,
        Item={"pk": {"S": pedido.pedido_id}, "valor_centavos": {"N": str(pedido.valor_centavos)}},
        ConditionExpression="attribute_not_exists(pk)",
    )
    return Response(HTTPStatus.CREATED, content_types.APPLICATION_JSON, {"pedido_id": pedido.pedido_id})


@app.exception_handler(_DDB.exceptions.ConditionalCheckFailedException)
def ja_existe(_: Exception) -> Response[dict[str, str]]:
    return Response(HTTPStatus.CONFLICT, content_types.APPLICATION_JSON, {"erro": "pedido já existe"})


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_HTTP, clear_state=True)
def lambda_handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    return app.resolve(event, context)
```

Verificado em `tests/test_http.py`: `POST` válido → 201; repetido → 409 (escrita condicional); `GET` existente → 200; inexistente
→ 404; corpo com campo extra ou tipo errado → **422** sem chegar ao handler (`enable_validation=True`; o corpo da resposta traz só
`loc` e `type`, não ecoa a entrada); rota inexistente → 404.

- O payload **v2** (HTTP API) difere do v1 (REST API): use `APIGatewayHttpResolver` para v2 e `APIGatewayRestResolver` para v1.
- Autenticação (JWT authorizer, IAM, Cognito) fica no API Gateway, não no handler → **engenheiro-seguranca**.
- FastAPI/Django: rode com o **Lambda Web Adapter** (o mesmo app roda local e no Lambda), aceitando init maior — meça.

## 7. Testes

`tests/conftest.py`:

```python
from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import boto3
import pytest
from moto import mock_aws

os.environ.update(
    AWS_DEFAULT_REGION="sa-east-1",
    AWS_ACCESS_KEY_ID="teste",
    AWS_SECRET_ACCESS_KEY="teste",
    TABELA_PEDIDOS="pedidos",
    TABELA_IDEMPOTENCIA="idempotencia",
    POWERTOOLS_SERVICE_NAME="pedidos",
)


@dataclass
class ContextoFalso:
    restante_ms: int = 30_000
    function_name: str = "teste"
    memory_limit_in_mb: int = 256
    invoked_function_arn: str = "arn:aws:lambda:sa-east-1:000000000000:function:teste"
    aws_request_id: str = "req-1"

    def get_remaining_time_in_millis(self) -> int:
        return self.restante_ms


@pytest.fixture
def contexto() -> ContextoFalso:
    return ContextoFalso()


@pytest.fixture
def aws() -> Iterator[None]:
    with mock_aws():
        ddb = boto3.client("dynamodb")
        for nome, chave in (("pedidos", "pk"), ("idempotencia", "id")):
            ddb.create_table(
                TableName=nome,
                KeySchema=[{"AttributeName": chave, "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": chave, "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST",
            )
        yield


def sqs(*corpos: tuple[str, str]) -> dict[str, list[dict[str, Any]]]:
    return {
        "Records": [
            {
                "messageId": mid,
                "receiptHandle": "rh",
                "body": corpo,
                "attributes": {},
                "messageAttributes": {},
                "md5OfBody": "",
                "eventSource": "aws:sqs",
                "eventSourceARN": "arn:aws:sqs:sa-east-1:0:fila",
                "awsRegion": "sa-east-1",
            }
            for mid, corpo in corpos
        ]
    }
```

`tests/test_lote.py`:

```python
from __future__ import annotations

import pytest

from pedidos.dominio import MensagemInvalida, Pedido, ler_pedido
from pedidos.lote import processar_lote, processar_lote_fifo
from tests.conftest import sqs

OK = '{"pedido_id":"a","valor_centavos":100}'


@pytest.mark.parametrize(
    "corpo",
    [
        "{nao e json",
        '{"pedido_id":"a"}',
        '{"pedido_id":"a","valor_centavos":true}',
        '{"pedido_id":"a","valor_centavos":1,"x":1}',
        '{"pedido_id":"","valor_centavos":1}',
        "x" * 70_000,
    ],
)
def test_entrada_hostil_e_rejeitada(corpo: str) -> None:
    with pytest.raises(MensagemInvalida):
        ler_pedido(corpo)


def test_falha_parcial_so_com_as_que_falharam() -> None:
    vistos: list[str] = []

    def processar(p: Pedido) -> None:
        if p.pedido_id == "explode":
            raise RuntimeError("downstream fora")
        vistos.append(p.pedido_id)

    ev = sqs(
        ("m1", OK),
        ("m2", "{ruim"),
        ("m3", '{"pedido_id":"explode","valor_centavos":1}'),
        ("m4", '{"pedido_id":"b","valor_centavos":7}'),
    )
    r = processar_lote(ev["Records"], processar, lambda: 30_000)
    assert r == {"batchItemFailures": [{"itemIdentifier": "m2"}, {"itemIdentifier": "m3"}]}
    assert vistos == ["a", "b"]


def test_lote_vazio_e_sucesso_total() -> None:
    assert processar_lote([], lambda _p: None, lambda: 30_000) == {"batchItemFailures": []}


def test_prazo_esgotado_devolve_o_resto() -> None:
    tempos = iter([30_000, 100, 100])
    ev = sqs(("m1", OK), ("m2", OK), ("m3", OK))
    r = processar_lote(ev["Records"], lambda _p: None, lambda: next(tempos))
    assert r == {"batchItemFailures": [{"itemIdentifier": "m2"}, {"itemIdentifier": "m3"}]}


def test_fifo_para_na_primeira_falha() -> None:
    vistos: list[str] = []
    ev = sqs(("m1", OK), ("m2", "{ruim"), ("m3", OK), ("m4", OK))
    r = processar_lote_fifo(ev["Records"], lambda p: vistos.append(p.pedido_id), lambda: 30_000)
    assert r == {"batchItemFailures": [{"itemIdentifier": m} for m in ("m2", "m3", "m4")]}
    assert vistos == ["a"]  # nada depois da falha foi processado
```

`tests/test_handlers.py`:

```python
from __future__ import annotations

import importlib
from typing import Any

import boto3
import pytest
from aws_lambda_powertools.utilities.batch.exceptions import BatchProcessingError, UnexpectedBatchTypeError

from tests.conftest import ContextoFalso, sqs

OK = '{"pedido_id":"a","valor_centavos":100}'


def _itens() -> int:
    return boto3.client("dynamodb").scan(TableName="pedidos")["Count"]


def _valor(pedido_id: str) -> int:
    item = boto3.client("dynamodb").get_item(TableName="pedidos", Key={"pk": {"S": pedido_id}})["Item"]
    return int(item["valor_centavos"]["N"])


@pytest.mark.usefixtures("aws")
def test_stdlib_duplicada_nao_regrava(contexto: ContextoFalso) -> None:
    h = importlib.reload(importlib.import_module("pedidos.handler_sqs"))
    outro_valor = '{"pedido_id":"a","valor_centavos":999}'
    ev = sqs(("m1", OK), ("m2", outro_valor), ("m3", "{ruim"))
    assert h.lambda_handler(ev, contexto) == {"batchItemFailures": [{"itemIdentifier": "m3"}]}
    # a 2ª entrega NÃO sobrescreveu: sem a escrita condicional, o valor seria 999
    assert _valor("a") == 100


@pytest.mark.usefixtures("aws")
def test_powertools_falha_parcial_e_idempotencia(
    contexto: ContextoFalso, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = importlib.reload(importlib.import_module("pedidos.handler_sqs_pt"))
    ev = sqs(("m1", OK), ("m2", '{"pedido_id":"a","valor_centavos":1,"extra":1}'), ("m3", OK))
    chamadas: list[str] = []
    put_original = h._DDB.put_item

    def espia(**kwargs: Any) -> Any:
        chamadas.append(kwargs["Item"]["pk"]["S"])
        return put_original(**kwargs)

    monkeypatch.setattr(h._DDB, "put_item", espia)
    r = h.lambda_handler(ev, contexto)
    assert r == {"batchItemFailures": [{"itemIdentifier": "m2"}]}
    assert chamadas == ["a"]  # m1 e m3 são o mesmo pedido: um único efeito
    # reentrega em outra invocação: resultado salvo devolvido, sem novo put_item
    assert h.lambda_handler(sqs(("m9", OK)), contexto) == {"batchItemFailures": []}
    assert chamadas == ["a"]
    # mesmo pedido_id com valor diferente: conflito vira falha (não "já processado")
    conflito = sqs(
        ("m10", '{"pedido_id":"a","valor_centavos":1}'), ("m11", '{"pedido_id":"b","valor_centavos":2}')
    )
    assert h.lambda_handler(conflito, contexto) == {"batchItemFailures": [{"itemIdentifier": "m10"}]}
    assert _itens() == 2


@pytest.mark.usefixtures("aws")
def test_powertools_lote_todo_falho_levanta_excecao(contexto: ContextoFalso) -> None:
    h = importlib.reload(importlib.import_module("pedidos.handler_sqs_pt"))
    with pytest.raises(BatchProcessingError):
        h.lambda_handler(sqs(("m1", "{ruim"), ("m2", "{ruim")), contexto)


@pytest.mark.usefixtures("aws")
def test_powertools_lote_vazio_levanta(contexto: ContextoFalso) -> None:
    # O SQS não entrega lote vazio; num evento de teste vazio o Powertools LEVANTA (não devolve lista vazia).
    h = importlib.reload(importlib.import_module("pedidos.handler_sqs_pt"))
    with pytest.raises(UnexpectedBatchTypeError):
        h.lambda_handler({"Records": []}, contexto)
```

`tests/test_http.py`:

```python
from __future__ import annotations

import importlib
import json
from typing import Any

import pytest

from tests.conftest import ContextoFalso


def _ev(metodo: str, caminho: str, corpo: str | None = None) -> dict[str, Any]:
    return {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": caminho,
        "rawQueryString": "",
        "headers": {"content-type": "application/json"},
        "isBase64Encoded": False,
        "body": corpo,
        "requestContext": {
            "http": {
                "method": metodo,
                "path": caminho,
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "pytest",
            },
            "requestId": "r1",
            "routeKey": "$default",
            "stage": "$default",
        },
    }


@pytest.mark.usefixtures("aws")
def test_fluxo_http(contexto: ContextoFalso) -> None:
    h = importlib.reload(importlib.import_module("pedidos.handler_http"))
    criar = h.lambda_handler(_ev("POST", "/pedidos", '{"pedido_id":"a","valor_centavos":5}'), contexto)
    assert criar["statusCode"] == 201
    assert (
        h.lambda_handler(_ev("POST", "/pedidos", '{"pedido_id":"a","valor_centavos":5}'), contexto)[
            "statusCode"
        ]
        == 409
    )
    achou = h.lambda_handler(_ev("GET", "/pedidos/a"), contexto)
    assert achou["statusCode"] == 200
    assert json.loads(achou["body"])["valor_centavos"] == 5
    assert h.lambda_handler(_ev("GET", "/pedidos/zz"), contexto)["statusCode"] == 404
    invalido = _ev("POST", "/pedidos", '{"pedido_id":"b","valor_centavos":"5","x":1}')
    assert h.lambda_handler(invalido, contexto)["statusCode"] == 422
    assert h.lambda_handler(_ev("DELETE", "/pedidos/a"), contexto)["statusCode"] == 404  # rota inexistente
```

Os testes de durable/SnapStart estão em `references/modelos-de-execucao.md`; o de invariantes do template e o de contrato com o
runtime, em `references/iac-e-teste-local.md`. Rode tudo com:

```bash
uv sync --all-groups && uv run ruff format --check src tests && uv run ruff check src tests \
  && uv run complexipy && uv run mypy src tests && uv run pytest -q    # gate completo: references/clean-code-python.md
```

## 8. Outras fontes de evento (resumo)

- **Kinesis / DynamoDB Streams:** a mesma resposta `batchItemFailures`, mas o `itemIdentifier` é o **número de sequência** e o
  checkpoint volta para o **menor** número que falhou — tudo depois dele é reentregue, inclusive o que deu certo. O `BatchProcessor` do
  Powertools (`EventType.KinesisDataStreams` / `DynamoDBStreams`) continua processando depois de uma falha e informa todas; então ou o
  efeito é **idempotente**, ou processe em ordem e pare na 1ª falha (como no FIFO). Um registro que nunca passa segura o shard até
  esgotar `MaximumRetryAttempts`/`MaximumRecordAgeInSeconds` (o padrão é -1, infinito): defina limites, `BisectBatchOnFunctionError` e
  destino `OnFailure`. Em Go, o mesmo padrão em ordem está na **aws-lambda-go**.
- **S3:** a chave do objeto chega **URL-encoded** → `urllib.parse.unquote_plus(record["s3"]["object"]["key"])`; evite gravar no
  mesmo bucket/prefixo que dispara a função (laço de invocação).
- **EventBridge / agendamento:** invocação assíncrona — configure `MaximumRetryAttempts`, `MaximumEventAgeInSeconds` e destino de
  falha (ou DLQ); idempotência continua obrigatória.
- Arquitetura com SNS/EventBridge/Pipes → **aws-serverless-eda**.
