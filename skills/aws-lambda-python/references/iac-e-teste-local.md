# IaC e teste local — Python no AWS Lambda

> Estado de verificação (2026-10-28): o template SAM abaixo passou no `cfn-lint` 1.59.0 com `aws-sam-translator` 1.115.0 e foi
> **transformado** com o translator para conferir a role e a event source mapping geradas (**não** foi implantado). O teste de
> contrato rodou o handler no runtime **real** (`awslambdaric` 4.2.3) contra o Runtime API simulado. O mapa de Terraform da §5 **não**
> foi validado (sem `terraform` no ambiente).

## 1. Template SAM

`template.yaml`:

```yaml
AWSTemplateFormatVersion: "2010-09-09"
Transform: AWS::Serverless-2016-10-31
Description: Pedidos em Python 3.14 (arm64) - SQS com falha parcial + API HTTP + durable function

Parameters:
  TimeoutSegundos:
    Type: Number
    Default: 30
    MinValue: 3
    MaxValue: 900
  VisibilidadeSegundos:            # recomendação AWS: >= 6 x TimeoutSegundos; o CloudFormation não faz a conta
    Type: Number
    Default: 180
    MinValue: 18
    MaxValue: 43200

Globals:
  Function:
    Runtime: python3.14
    Architectures: [arm64]
    MemorySize: 256
    Timeout: !Ref TimeoutSegundos
    LoggingConfig:
      LogFormat: JSON               # habilita filtro por nível; logs do `logging` saem com requestId
      ApplicationLogLevel: INFO
      SystemLogLevel: WARN
    Environment:
      Variables:
        TABELA_PEDIDOS: !Ref TabelaPedidos
        POWERTOOLS_SERVICE_NAME: pedidos

Resources:
  TabelaPedidos:
    Type: AWS::DynamoDB::Table
    Properties:
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions: [{AttributeName: pk, AttributeType: S}]
      KeySchema: [{AttributeName: pk, KeyType: HASH}]
      PointInTimeRecoverySpecification: {PointInTimeRecoveryEnabled: true}
      SSESpecification: {SSEEnabled: true}

  TabelaIdempotencia:               # Powertools Idempotency: chave "id" + TTL no atributo "expiration"
    Type: AWS::DynamoDB::Table
    Properties:
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions: [{AttributeName: id, AttributeType: S}]
      KeySchema: [{AttributeName: id, KeyType: HASH}]
      TimeToLiveSpecification: {AttributeName: expiration, Enabled: true}
      SSESpecification: {SSEEnabled: true}

  FilaPedidosDlq:
    Type: AWS::SQS::Queue
    Properties:
      MessageRetentionPeriod: 1209600   # 14 dias para investigar e fazer redrive
      SqsManagedSseEnabled: true

  FilaPedidos:
    Type: AWS::SQS::Queue
    Properties:
      VisibilityTimeout: !Ref VisibilidadeSegundos
      SqsManagedSseEnabled: true
      RedrivePolicy:
        deadLetterTargetArn: !GetAtt FilaPedidosDlq.Arn
        maxReceiveCount: 5

  ProcessadorPedidos:
    Type: AWS::Serverless::Function
    Metadata:
      BuildMethod: makefile           # `make build-ProcessadorPedidos` (uv, wheels arm64)
    Properties:
      CodeUri: .
      Handler: pedidos.handler_sqs_pt.lambda_handler
      Environment:
        Variables:
          TABELA_IDEMPOTENCIA: !Ref TabelaIdempotencia
      Policies:
        - SQSPollerPolicy:
            QueueName: !GetAtt FilaPedidos.QueueName
        - DynamoDBWritePolicy:
            TableName: !Ref TabelaPedidos
        - DynamoDBCrudPolicy:           # Powertools Idempotency lê, grava, atualiza e apaga o registro
            TableName: !Ref TabelaIdempotencia
      Events:
        Pedidos:
          Type: SQS
          Properties:
            Queue: !GetAtt FilaPedidos.Arn
            BatchSize: 10
            FunctionResponseTypes: [ReportBatchItemFailures]
            ScalingConfig:
              MaximumConcurrency: 10

  ApiPedidos:
    Type: AWS::Serverless::Function
    Metadata:
      BuildMethod: makefile
    Properties:
      CodeUri: .
      Handler: pedidos.handler_http.lambda_handler
      AutoPublishAlias: vivo          # SnapStart só vale em versão publicada (nunca em $LATEST)
      SnapStart:
        ApplyOn: PublishedVersions    # Python 3.12+: cobra cache do snapshot (mín. 3 h) + cada restauração
      Policies:
        - DynamoDBReadPolicy:
            TableName: !Ref TabelaPedidos
        - DynamoDBWritePolicy:
            TableName: !Ref TabelaPedidos
      Events:
        Buscar:
          Type: HttpApi
          Properties: {Path: "/pedidos/{pedido_id}", Method: GET}
        Criar:
          Type: HttpApi
          Properties: {Path: /pedidos, Method: POST}

  FluxoPedido:
    Type: AWS::Serverless::Function
    Metadata:
      BuildMethod: makefile
    Properties:
      CodeUri: .
      Handler: pedidos.handler_durable.handler
      Runtime: python3.14             # durable: python3.13 ou python3.14
      AutoPublishAlias: vivo          # invoque pela versão/alias: execução em voo não muda de código
      DurableConfig:
        ExecutionTimeout: 3600
        RetentionPeriodInDays: 7

Outputs:
  UrlApi:
    Value: !Sub "https://${ServerlessHttpApi}.execute-api.${AWS::Region}.amazonaws.com"
```

Pontos que o template codifica:

- `Runtime: python3.14` + `Architectures: [arm64]` em `Globals`; o pacote precisa ter wheels `aarch64` (ver o `Makefile` em
  `references/empacotamento-e-cold-start.md`).
- `LoggingConfig` JSON com `ApplicationLogLevel`/`SystemLogLevel`: liga o filtro por nível e o `requestId` em cada linha do `logging`.
- Fila: `VisibilityTimeout` ≥ 6× o timeout (dois parâmetros revisados juntos — o CloudFormation não faz a conta), DLQ com
  `maxReceiveCount: 5` e retenção de 14 dias; `FunctionResponseTypes: [ReportBatchItemFailures]`; `ScalingConfig.MaximumConcurrency`
  entre 2 e 1000 (a soma das filas da função ≤ *reserved concurrency*).
- Tabela de idempotência com chave `id` e TTL em `expiration` (os nomes padrão do `DynamoDBPersistenceLayer`).
- API com `AutoPublishAlias` + `SnapStart` (só vale em versão publicada; para Python há cobrança de cache e de restauração). O
  `handler_http` não gera nada único na init, por isso não importa `pedidos.snapstart`; se a sua função gerar (id, token, semente),
  importe o módulo dos ganchos no arquivo do handler.
- `FluxoPedido`: `DurableConfig` (`ExecutionTimeout` até 31.622.400 s; retenção 1–90 dias) e alias para as execuções em voo.

## 2. O que a transformação do SAM gera (verificado com aws-sam-translator 1.115.0)

| Recurso | O que apareceu no template transformado | Implicação |
|---|---|---|
| Role do `ProcessadorPedidos` | `AWSLambdaBasicExecutionRole` **e** `AWSLambdaSQSQueueExecutionRole` (gerenciadas) + as 3 políticas inline pedidas | o evento SQS faz o SAM anexar uma política gerenciada de SQS **ampla** (não restrita à fila); se a sua política de segurança exige menor privilégio estrito, declare a `Role` explicitamente com as ações de polling só no ARN da fila |
| Event source mapping | `FunctionResponseTypes: [ReportBatchItemFailures]`, `ScalingConfig: {MaximumConcurrency: 10}`, `BatchSize: 10` | o que o handler espera |
| `ApiPedidos` | `SnapStart: {ApplyOn: PublishedVersions}` + versão/alias | invoque pelo alias |
| Role do `FluxoPedido` | `AWSLambdaBasicDurableExecutionRolePolicy` | permissões de checkpoint já anexadas |

Como reproduzir a conferência (sem conta AWS):

```python
# AWS_DEFAULT_REGION=sa-east-1 uv run --no-project --with aws-sam-translator==1.115.0 --with cfn-lint==1.59.0 python conferir.py
import json
from cfnlint.decode import decode
from samtranslator.translator.transform import transform

class SemPoliticas:  # o translator só precisa do mapa de políticas gerenciadas para nomes curtos
    def load(self):
        return {}

tpl, _ = decode("template.yaml")
for recurso in tpl["Resources"].values():
    if recurso["Type"] == "AWS::Serverless::Function":
        recurso["Properties"]["CodeUri"] = "s3://bucket/chave.zip"  # o translator exige URI S3
saida = transform(tpl, {}, SemPoliticas())
for nome, r in saida["Resources"].items():
    if r["Type"] == "AWS::IAM::Role":
        print(nome, json.dumps(r["Properties"].get("ManagedPolicyArns")))
```

## 3. O que o `cfn-lint` **não** pegou — e o teste que pega

Nos nossos testes, o `cfn-lint` 1.59.0 aprovou sem aviso um template com `Runtime: python3.99`, `MaximumConcurrency: 1` e
`FunctionResponseTypes: [X]` (ele pegou, por exemplo, propriedade com nome errado). Por isso as regras que evitam incidente viram
teste de invariantes, que roda no `pytest` junto com o resto (cada uma das quatro mutações acima, mais visibilidade < 6×, fez o
teste falhar):

`tests/test_template.py`:

```python
"""Invariantes do template que o cfn-lint NÃO pegou nos nossos testes (runtime inexistente, faixa de
MaximumConcurrency, FunctionResponseTypes inválido, regra dos 6x da visibilidade)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class _CfnLoader(yaml.SafeLoader):
    pass


def _tag(loader: yaml.SafeLoader, sufixo: str, no: yaml.Node) -> Any:
    if isinstance(no, yaml.ScalarNode):
        return {sufixo: loader.construct_scalar(no)}
    if isinstance(no, yaml.SequenceNode):
        return {sufixo: loader.construct_sequence(no)}
    if isinstance(no, yaml.MappingNode):
        return {sufixo: loader.construct_mapping(no)}
    raise TypeError(no)


_CfnLoader.add_multi_constructor("!", _tag)
_TEXTO = (Path(__file__).parents[1] / "template.yaml").read_text()
TPL: dict[str, Any] = _CfnLoader(
    _TEXTO
).get_single_data()  # _CfnLoader deriva do SafeLoader: sem objetos arbitrários
RUNTIMES_OK = {"python3.13", "python3.14"}  # revise com a tabela de runtimes da AWS


def _funcoes() -> dict[str, dict[str, Any]]:
    return {
        k: v["Properties"] for k, v in TPL["Resources"].items() if v["Type"] == "AWS::Serverless::Function"
    }


def test_runtime_e_arquitetura() -> None:
    glob = TPL["Globals"]["Function"]
    for nome, props in _funcoes().items():
        assert props.get("Runtime", glob["Runtime"]) in RUNTIMES_OK, nome
        assert props.get("Architectures", glob["Architectures"]) == ["arm64"], nome


def test_sqs_com_falha_parcial_e_concorrencia_limitada() -> None:
    eventos = [
        e["Properties"]
        for p in _funcoes().values()
        for e in p.get("Events", {}).values()
        if e["Type"] == "SQS"
    ]
    assert eventos
    for ev in eventos:
        assert ev["FunctionResponseTypes"] == ["ReportBatchItemFailures"]
        assert 2 <= ev["ScalingConfig"]["MaximumConcurrency"] <= 1000


def test_visibilidade_6x_timeout_e_dlq() -> None:
    p = TPL["Parameters"]
    assert p["VisibilidadeSegundos"]["Default"] >= 6 * p["TimeoutSegundos"]["Default"]
    fila = TPL["Resources"]["FilaPedidos"]["Properties"]
    assert fila["RedrivePolicy"]["maxReceiveCount"] >= 5
```

Rode também `cfn-lint template.yaml` (e `sam validate --lint`, se tiver o SAM CLI — não verificado aqui).

## 4. Teste de contrato com o runtime real (sem AWS, sem Docker)

O handler Python é chamado pelo **Runtime Interface Client** (`awslambdaric`, o mesmo que roda no Lambda), que conversa HTTP com o
endereço em `AWS_LAMBDA_RUNTIME_API`. Um servidor local que finge ser o Runtime API exercita o caminho completo: desserialização do
evento, chamada do handler, serialização da resposta e o formato de erro.

`contrato/fake_runtime_api.py` (idêntico ao das skills **aws-lambda-go** e **aws-lambda-go-rust**; `PORTA` e `PRAZO_MS` por variável de ambiente):

`contrato/fake_runtime_api.py`:

```python
#!/usr/bin/env python3
"""Runtime API do Lambda (simulado) — só para testes locais. Entrega eventos de um arquivo JSON
(lista) e imprime a resposta/erro de cada invocação. Uso:

  python3 fake_runtime_api.py eventos.json &        # escuta em 127.0.0.1:$PORTA (padrão 9001)
  AWS_LAMBDA_RUNTIME_API=127.0.0.1:9001 ./bootstrap  # o runtime do Lambda conversa com ele

Variáveis: PORTA (padrão 9001) e PRAZO_MS (padrão 30000) — prazo de cada invocação, enviado em
Lambda-Runtime-Deadline-Ms; rode com PRAZO_MS=300 para exercitar a margem de prazo do handler.
"""
import json, os, sys, time, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

EVENTOS = json.load(open(sys.argv[1]))
FILA = list(enumerate(EVENTOS, 1))
RESULTADOS = []
LOCK = threading.Lock()
PORTA = int(os.environ.get("PORTA", "9001"))
PRAZO_MS = int(os.environ.get("PRAZO_MS", "30000"))


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # silencia o log padrão
        pass

    def _send(self, code, body=b"", headers=None):
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.endswith("/runtime/invocation/next"):
            with LOCK:
                item = FILA.pop(0) if FILA else None
            if item is None:
                # sem mais eventos: o teste acabou; encerra o servidor (o runtime vê "connection refused" e sai)
                threading.Thread(target=lambda: (time.sleep(0.3), srv.shutdown()), daemon=True).start()
                time.sleep(1.0)  # segura a conexão: o runtime fica esperando, como no Lambda real
                self._send(204)
                return
            n, ev = item
            hdr = {
                "Lambda-Runtime-Aws-Request-Id": f"req-{n}",
                "Lambda-Runtime-Deadline-Ms": str(int(time.time() * 1000) + PRAZO_MS),
                "Lambda-Runtime-Invoked-Function-Arn": "arn:aws:lambda:sa-east-1:000000000000:function:teste",
                "Lambda-Runtime-Trace-Id": "Root=1-00000000-000000000000000000000001",
                "Content-Type": "application/json",
            }
            self._send(200, json.dumps(ev).encode(), hdr)
        else:
            self._send(404)

    def _corpo(self):
        """Lê o corpo com Content-Length OU Transfer-Encoding: chunked (o runtime do Go usa chunked)."""
        if "chunked" in self.headers.get("Transfer-Encoding", "").lower():
            partes = []
            while True:
                tam = int(self.rfile.readline().strip().split(b";")[0] or b"0", 16)
                if tam == 0:
                    self.rfile.readline()  # CRLF final
                    break
                partes.append(self.rfile.read(tam))
                self.rfile.readline()  # CRLF depois do chunk
            return b"".join(partes).decode(errors="replace")
        return self.rfile.read(int(self.headers.get("Content-Length", 0))).decode(errors="replace")

    def do_POST(self):
        corpo = self._corpo()
        tipo = "erro" if self.path.endswith("/error") else "resposta"
        req = self.path.split("/invocation/")[1].split("/")[0] if "/invocation/" in self.path else "?"
        ctype = self.headers.get("Content-Type", "")
        with LOCK:
            RESULTADOS.append((req, tipo, ctype, corpo))
        print(f"[{req}] {tipo} ({ctype}): {corpo!r}", flush=True)
        self._send(202, b"{}")


srv = ThreadingHTTPServer(("127.0.0.1", PORTA), H)
srv.serve_forever()
```

Handler de contrato (a lógica de lote real com efeito falso) e os eventos:

`tests/handler_contrato.py`:

```python
"""Handler de contrato: a lógica de lote real com um efeito falso (sem AWS). Só para o teste com o RIC."""

from __future__ import annotations

from typing import Any

from pedidos.lote import Resposta, processar_lote


def lambda_handler(event: dict[str, Any], context: Any) -> Resposta:
    return processar_lote(
        event.get("Records", []), lambda _pedido: None, context.get_remaining_time_in_millis
    )
```

`contrato/eventos_sqs.json`:

```json
[
  {"Records": [
    {"messageId": "ok1", "body": "{\"pedido_id\":\"a\",\"valor_centavos\":100}"},
    {"messageId": "json-ruim", "body": "{nao e json"},
    {"messageId": "valor-zero", "body": "{\"pedido_id\":\"b\",\"valor_centavos\":0}"},
    {"messageId": "ok2", "body": "{\"pedido_id\":\"c\",\"valor_centavos\":7}"}
  ]},
  {"Records": []},
  {"isto": "não é um evento SQS"}
]
```

Execução (verificada):

```bash
python3 contrato/fake_runtime_api.py contrato/eventos_sqs.json &      # PRAZO_MS=300 para o caso de prazo
AWS_LAMBDA_RUNTIME_API=127.0.0.1:9001 AWS_LAMBDA_FUNCTION_NAME=teste AWS_LAMBDA_FUNCTION_VERSION='$LATEST' \
AWS_LAMBDA_FUNCTION_MEMORY_SIZE=128 AWS_LAMBDA_LOG_GROUP_NAME=g AWS_LAMBDA_LOG_STREAM_NAME=s \
AWS_REGION=sa-east-1 AWS_DEFAULT_REGION=sa-east-1 PYTHONPATH=src:. \
uv run python -m awslambdaric tests.handler_contrato.lambda_handler
```

Respostas observadas:

| Caso | Resposta |
|---|---|
| lote com 2 inválidas em 4 | `{"batchItemFailures": [{"itemIdentifier": "json-ruim"}, {"itemIdentifier": "valor-zero"}]}` |
| `Records` vazio | `{"batchItemFailures": []}` |
| evento sem `Records` | `{"batchItemFailures": []}` — o handler trata como lote vazio; se a função puder ser invocada por outra origem, valide o formato do evento |
| `PRAZO_MS=300` (deadline curto) | todas as mensagens devolvidas à fila, sem processar |
| registro sem `messageId` | POST em `/error` com `errorType: KeyError` e `stackTrace` → o lote inteiro volta |
| variável obrigatória ausente na init | POST em `/runtime/init/error` com `errorType: KeyError` |

Ao fim dos eventos o servidor desliga e o `awslambdaric` sai com `RuntimeError: Failed to get next` — esperado no teste. Para CI,
asserte o JSON de resposta. O contrato **não** cobre IAM, SQS nem DynamoDB reais: para integração use um ambiente de teste na AWS
(ou LocalStack → **localstack-dev**).

## 5. Terraform — nomes equivalentes (NÃO validado)

Para quem usa Terraform (padrão de módulos, state e policy-as-code → **engenheiro-iac**), as propriedades acima correspondem a:

| SAM / CloudFormation | Terraform (`hashicorp/aws`) |
|---|---|
| `Runtime`, `Architectures`, `Handler` | `aws_lambda_function.runtime`, `.architectures`, `.handler` |
| `LoggingConfig` | bloco `logging_config { log_format, application_log_level, system_log_level }` |
| `SnapStart.ApplyOn` | bloco `snap_start { apply_on = "PublishedVersions" }` + `publish = true` |
| `FunctionResponseTypes`, `ScalingConfig.MaximumConcurrency` | `aws_lambda_event_source_mapping.function_response_types`, bloco `scaling_config { maximum_concurrency }` |
| `RedrivePolicy` | `aws_sqs_queue.redrive_policy` (`jsonencode`) |
| `DurableConfig` | confira o suporte na versão do provider antes de usar |

Rode `terraform validate`, `plan` revisado e Checkov/Trivy antes de qualquer `apply`.
