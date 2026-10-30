# SnapStart, Managed Instances, durable functions e streaming — Python no AWS Lambda

> Estado de verificação (2026-10-28): fatos conferidos na documentação do Lambda nesta data. O código de SnapStart e de durable
> function roda **localmente** (`snapshot_restore_py` 1.0.0; `aws-durable-execution-sdk-python` 3.0.0 com o runner local
> `aws-durable-execution-sdk-python-testing` 1.4.0); o template SAM correspondente foi validado com `cfn-lint` 1.59.0 e transformado
> com `aws-sam-translator` 1.115.0. **Nada foi implantado**: snapshot real, restauração e cobrança não foram medidos.

## 1. Qual modelo usar

| Necessidade | Escolha | Custo/risco que vem junto |
|---|---|---|
| Nenhum requisito duro de latência | padrão (sob demanda) | cold start ocasional |
| Init pesada (Pydantic, SDKs, modelos) em API sensível a latência | **SnapStart** (Python 3.12+) | cobra cache do snapshot (mín. 3 h por versão ativa) + cada restauração; cuidado com unicidade |
| Latência previsível de dois dígitos de ms | **Provisioned Concurrency** | custo fixo por hora; não combina com SnapStart |
| Tráfego alto e estável, quer instância EC2 (Savings Plans/RI) | **Managed Instances** (Python 3.13+) | memória × processos; `/tmp` compartilhado; capacidade a gerenciar |
| Workflow de vários passos, esperas longas, até 1 ano | **durable functions** (`python3.13`/`3.14`) | determinismo no replay; SDK fixado por major |
| Resposta grande/progressiva (SSE, arquivos) | **Lambda Web Adapter** ou runtime customizado | streaming não é nativo no Python gerenciado |

## 2. SnapStart (Python 3.12+)

Como funciona: ao **publicar uma versão**, o Lambda roda a init, tira um snapshot (memória + disco) do microVM e restaura dele os
ambientes novos. Consequências práticas:

- Só vale em **versão publicada ou alias** (nunca em `$LATEST`) → `AutoPublishAlias` no SAM.
- Não combina com Provisioned Concurrency, EFS, S3 Files nem `/tmp` > 512 MB.
- Na criação do snapshot a init pode levar até o maior entre 130 s e o timeout da função (máx. 900 s), e os ganchos
  `before_snapshot` contam nesse tempo; na restauração, runtime + ganchos `after_restore` têm **10 s** (senão `SnapStartTimeoutException`).
- **Unicidade:** tudo gerado na init vai para o snapshot e é **igual em todos os ambientes restaurados** — id de ambiente, semente do
  `random`, token, timestamp em cache. Gere no handler ou num gancho `after_restore`; para aleatoriedade use `random.SystemRandom`
  ou `secrets` (leem `/dev/urandom` e continuam únicos depois do restore).
- Conexões abertas na init podem não sobreviver ao restore: as do SDK da AWS se refazem sozinhas; para outras (banco), revalide no
  `after_restore` ou na 1ª uso.
- Ganchos só rodam se o módulo que os registra for **importado** pelo arquivo do handler. Ordem: `before_snapshot` em ordem inversa
  de registro; `after_restore` na ordem de registro.

`src/pedidos/snapstart.py`:

```python
"""Ganchos de SnapStart (Python 3.12+).

Importe este módulo no arquivo do handler; módulo não importado = ganchos ignorados.
"""

from __future__ import annotations

import random
import secrets
from typing import Any

from snapshot_restore_py import register_after_restore, register_before_snapshot

_rng = random.SystemRandom()  # CSPRNG: continua único depois do restore (random.random() NÃO)
_estado: dict[str, Any] = {"id_ambiente": None, "segredo": None}


@register_before_snapshot
def _antes_do_snapshot() -> None:
    # Nada que precise ser único ou expirar pode ir para o snapshot.
    _estado["segredo"] = None


@register_after_restore
def _depois_do_restore() -> None:
    # Roda em cada ambiente restaurado (prazo total de restore: 10 s). Regenere o que é único.
    _estado["id_ambiente"] = secrets.token_hex(8)


def id_ambiente() -> str:
    if _estado["id_ambiente"] is None:  # sem SnapStart (ou em teste) o gancho não roda
        _estado["id_ambiente"] = secrets.token_hex(8)
    return str(_estado["id_ambiente"])


def numero_aleatorio() -> float:
    return _rng.random()
```

No template: `AutoPublishAlias` + `SnapStart: {ApplyOn: PublishedVersions}` (ver `references/iac-e-teste-local.md`). Monitore a
restauração na linha `REPORT` (`Restore Duration`) e apague versões antigas — cada versão ativa com SnapStart continua sendo cobrada.

## 3. Lambda Managed Instances (Python 3.13+)

- O runtime Python usa **vários processos**: cada requisição concorrente roda num processo separado, um por vez, de forma síncrona.
  Não há memória compartilhada entre requisições — globais e caches de módulo são por processo, então o código **não** precisa de
  cuidados de thread-safety.
- `PerExecutionEnvironmentMaxConcurrency`: padrão de **16 requisições por vCPU** para Python, que também define quantos processos
  existem. **Cada processo faz a sua init**: memória total ≈ memória de um processo × número de processos. Com bibliotecas grandes,
  reduza a concorrência ou ajuste a razão CPU/memória; acompanhe a métrica `MemoryUtilization`.
- `/tmp` é **compartilhado** entre todos os processos: nomes de arquivo únicos por requisição (ou trava de arquivo) e limpeza.
- Logs sempre em JSON estruturado com `requestId` (o `logging` da stdlib inclui sozinho); entradas de requisições diferentes se
  intercalam — filtre por `requestId`.
- Prazo: `context.get_remaining_time_in_millis()` antes de cada unidade de trabalho e timeout do cliente downstream derivado do
  tempo restante (o `boto3` não aceita timeout por chamada num cliente já criado: ou cria um cliente com o timeout, ou fixa um timeout
  razoável na init — avalie o custo de criar cliente em alto volume).
- Encerramento: só com extensão registrada o ambiente recebe `SIGTERM` antes de desligar — sem extensão, não conte com hook de saída.
- Powertools for AWS Lambda (Python) **≥ 3.23.0**.

## 4. Durable functions (`python3.13` / `python3.14`)

Uma durable function é uma função Lambda comum que recebe um `DurableContext`: cada `step` grava checkpoint, `wait` suspende sem
cobrar computação, e depois de uma pausa ou falha o Lambda **re-invoca a função do começo** e repõe o resultado dos passos já
concluídos (replay). Daí as regras:

- **Determinismo fora dos passos:** código fora de `step` roda de novo a cada replay — nada de `datetime.now()`, `random`, `uuid4`
  ou I/O fora de um passo.
- **Passo pode repetir** (retry): o efeito colateral dentro dele continua precisando ser idempotente.
- Execução total até **1 ano**: `ExecutionTimeout` aceita 1 a 31.622.400 s no SAM/CloudFormation, mas o guia de durable fala em 60 a
  31.536.000 s (padrão 86.400 no console) — use ≥ 60 s e ≤ 365 dias para caber nas duas; histórico retido de 1 a 90 dias
  (`RetentionPeriodInDays`, padrão 14). O timeout da **função** continua limitando cada invocação.
- Fixe o SDK por **major** (`aws-durable-execution-sdk-python>=3,<4`) e empacote-o (o runtime traz uma cópia só para teste); invoque
  por **versão/alias**, nunca `$LATEST`: uma execução em voo precisa continuar com o mesmo código.
- O SAM anexa a política gerenciada `AWSLambdaBasicDurableExecutionRolePolicy` à role da função quando há `DurableConfig`
  (verificado na transformação com `aws-sam-translator` 1.115.0).
- O SDK 3.x grava o resultado de cada passo num envelope tipado (serdes próprio) — não leia o checkpoint esperando JSON puro.

`src/pedidos/handler_durable.py`:

```python
"""Durable function (python3.13+): passos com checkpoint + espera sem pagar computação.

Handler: pedidos.handler_durable.handler  (função criada com DurableConfig; invoque por versão/alias)
"""

from __future__ import annotations

from typing import Any

from aws_durable_execution_sdk_python import DurableContext, StepContext, durable_execution, durable_step
from aws_durable_execution_sdk_python.config import Duration


@durable_step
def reservar_estoque(step_ctx: StepContext, pedido_id: str) -> dict[str, Any]:
    # Um passo é re-executado em retry: o efeito colateral dele precisa ser idempotente.
    step_ctx.logger.info("reservando", extra={"pedido_id": pedido_id})
    return {"pedido_id": pedido_id, "reservado": True}


@durable_step
def cobrar(_step_ctx: StepContext, pedido_id: str, valor_centavos: int) -> dict[str, Any]:
    return {"pedido_id": pedido_id, "cobrado": valor_centavos}


@durable_execution
def handler(event: dict[str, Any], context: DurableContext) -> dict[str, Any]:
    # Código FORA de step roda de novo a cada replay: mantenha-o determinístico (sem now(), random, I/O).
    pedido_id = str(event["pedido_id"])
    reserva = context.step(reservar_estoque(pedido_id), name="reservar")
    if not reserva["reservado"]:
        return {"status": "sem-estoque", "pedido_id": pedido_id}
    context.wait(duration=Duration.from_seconds(2), name="janela-de-cancelamento")
    cobranca = context.step(cobrar(pedido_id, int(event["valor_centavos"])), name="cobrar")
    return {"status": "concluido", **cobranca}
```

Teste local com o runner do SDK (sem AWS) — inclui o `wait`:

`tests/test_durable_e_snapstart.py`:

```python
from __future__ import annotations

import json

from aws_durable_execution_sdk_python.lambda_service import InvocationStatus
from aws_durable_execution_sdk_python_testing.runner import DurableFunctionTestRunner

from pedidos import snapstart
from pedidos.handler_durable import handler


def test_durable_fluxo_completo() -> None:
    with DurableFunctionTestRunner(handler=handler) as runner:
        r = runner.run(input=json.dumps({"pedido_id": "a", "valor_centavos": 5}), execution_timeout=30)
    assert r.status is InvocationStatus.SUCCEEDED
    assert json.loads(r.result) == {"status": "concluido", "pedido_id": "a", "cobrado": 5}
    # o checkpoint de cada passo é gravado num envelope tipado (serdes do SDK 3.x), não como JSON puro
    assert r.get_step("reservar").status.value == "SUCCEEDED"
    assert r.get_wait("janela-de-cancelamento") is not None


def test_snapstart_ganchos_regeneram_unicidade() -> None:
    snapstart._depois_do_restore()
    a = snapstart.id_ambiente()
    snapstart._depois_do_restore()
    assert snapstart.id_ambiente() != a
    assert 0.0 <= snapstart.numero_aleatorio() < 1.0
```

Durable × Step Functions: código Python com tipos e testes unitários (durable) × diagrama ASL, integrações diretas com 200+ serviços e
observabilidade visual (Step Functions) → **orquestracao-step-functions**.

## 5. Streaming de resposta e funções web

- O runtime Python gerenciado **não** faz streaming de resposta nativo (só Node.js). Para Python: **Lambda Web Adapter** (o app ASGI/WSGI
  roda atrás dele) ou runtime customizado com a integração de streaming do Runtime API. Streaming permite até 200 MB de resposta (os
  primeiros 6 MB sem limite de banda, depois 2 MB/s), cobra a duração inteira mesmo se o cliente desconectar e **não** funciona por
  Function URL dentro de VPC.
- **Lambda Web Functions** (servidor HTTP próprio escutando em `AWS_LAMBDA_HTTP_ENDPOINT`) hoje suportam **só Node.js** — não
  prometa para Python.
