# IaC, teste local e medição — Lambda em Go

> Estado de verificação (2026-10-28): o **template SAM** foi validado com `cfn-lint` **1.59.0** (**não** foi implantado) e o
> `Makefile` foi executado alvo a alvo (`file bootstrap` → ELF aarch64 estático); o **Terraform** **não** foi validado (sem
> `terraform` no ambiente); o **Runtime API simulado** rodou de verdade contra os oito `bootstrap` de exemplo. Cold start e custo só
> valem se **medidos na AWS**. Para Rust, o equivalente está em `../../aws-lambda-go-rust/references/iac-e-teste-local.md`.

## 1. Template SAM (validado com cfn-lint)

`template.yaml` — SQS com DLQ e falha parcial, HTTP API, Kinesis com destino de falha, EventBridge com as duas DLQs e Function URL com
streaming:

```yaml
AWSTemplateFormatVersion: "2010-09-09"
Transform: AWS::Serverless-2016-10-31
Description: Funções Lambda em Go (provided.al2023, arm64) — SQS, HTTP API, Kinesis, EventBridge e Function URL com streaming

Parameters:
  TimeoutSegundos:
    Type: Number
    Default: 30
    MinValue: 3
    MaxValue: 900
  VisibilidadeSegundos:               # recomendação da AWS: >= 6 x TimeoutSegundos (o mínimo válido é timeout <= visibilidade)
    Type: Number
    Default: 180
    MinValue: 18
    MaxValue: 43200

Globals:
  Function:
    Runtime: provided.al2023
    Architectures: [arm64]
    Handler: bootstrap            # o nome do Handler é livre; o obrigatório é o executável `bootstrap` na RAIZ do pacote
    MemorySize: 256
    Timeout: !Ref TimeoutSegundos
    LoggingConfig:
      LogFormat: JSON
    Environment:
      Variables:
        CONCORRENCIA: "5"

Resources:
  FilaPedidosDlq:
    Type: AWS::SQS::Queue
    Properties:
      MessageRetentionPeriod: 1209600
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
      BuildMethod: makefile
    Properties:
      CodeUri: .
      Policies:
        - SQSPollerPolicy:
            QueueName: !GetAtt FilaPedidos.QueueName
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
      MemorySize: 128
      Events:
        Buscar:
          Type: HttpApi
          Properties:
            Path: /pedidos/{id}
            Method: GET

  Leituras:
    Type: AWS::Kinesis::Stream
    Properties:
      StreamModeDetails:
        StreamMode: ON_DEMAND
      StreamEncryption:
        EncryptionType: KMS
        KeyId: alias/aws/kinesis

  FalhasLeiturasDlq:
    Type: AWS::SQS::Queue
    Properties:
      MessageRetentionPeriod: 1209600
      SqsManagedSseEnabled: true

  ConsumidorLeituras:
    Type: AWS::Serverless::Function
    Metadata:
      BuildMethod: makefile
    Properties:
      CodeUri: .
      Policies:
        - KinesisStreamReadPolicy:
            StreamName: !Ref Leituras
        - SQSSendMessagePolicy:
            QueueName: !GetAtt FalhasLeiturasDlq.QueueName
      Events:
        Stream:
          Type: Kinesis
          Properties:
            Stream: !GetAtt Leituras.Arn
            StartingPosition: LATEST
            BatchSize: 100
            MaximumBatchingWindowInSeconds: 1   # junta registros por até 1 s (no SQS, BatchSize > 10 exige >= 1)
            FunctionResponseTypes: [ReportBatchItemFailures]  # checkpoint no MENOR sequenceNumber devolvido
            BisectBatchOnFunctionError: true
            MaximumRetryAttempts: 5            # sem limite (-1, o padrão) um registro ruim trava o shard até expirar
            MaximumRecordAgeInSeconds: 3600
            DestinationConfig:
              OnFailure:
                Destination: !GetAtt FalhasLeiturasDlq.Arn   # recebe os METADADOS do lote que falhou (não os dados)

  FalhasEventosDlq:
    Type: AWS::SQS::Queue
    Properties:
      MessageRetentionPeriod: 1209600
      SqsManagedSseEnabled: true

  PedidoPago:
    Type: AWS::Serverless::Function
    Metadata:
      BuildMethod: makefile
    Properties:
      CodeUri: .
      EventInvokeConfig:                  # invocação ASSÍNCRONA (EventBridge): tentativas e destino de falha da função
        MaximumRetryAttempts: 2
        MaximumEventAgeInSeconds: 3600
        DestinationConfig:
          OnFailure:
            Type: SQS
            Destination: !GetAtt FalhasEventosDlq.Arn
      Events:
        Pago:
          Type: EventBridgeRule
          Properties:
            Pattern:
              source: [com.exemplo.pagamentos]
              detail-type: [PedidoPago]
            RetryPolicy:
              MaximumRetryAttempts: 5
              MaximumEventAgeInSeconds: 3600
            DeadLetterConfig:
              Type: SQS                     # eventos que o EventBridge não conseguiu ENTREGAR ao Lambda

  Relatorio:
    Type: AWS::Serverless::Function
    Metadata:
      BuildMethod: makefile
    Properties:
      CodeUri: .
      FunctionUrlConfig:
        AuthType: AWS_IAM                   # nunca NONE sem um motivo registrado
        InvokeMode: RESPONSE_STREAM         # o handler devolve *events.LambdaFunctionURLStreamingResponse

Outputs:
  UrlApi:
    Value: !Sub "https://${ServerlessHttpApi}.execute-api.${AWS::Region}.amazonaws.com/pedidos/{id}"
  UrlRelatorio:
    Value: !GetAtt RelatorioUrl.FunctionUrl
```

`Makefile` (o SAM chama `make build-<IdLógico>` com `ARTIFACTS_DIR`):

```make
# SAM chama `make build-<IdLogico>` com ARTIFACTS_DIR apontando para o diretorio do pacote.
# Toolchain FIXO: `toolchain` no go.mod e minimo — com um Go mais novo instalado, GOTOOLCHAIN=auto usaria o novo.
export GOTOOLCHAIN := go1.24.13

GOBUILD = CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -tags lambda.norpc -trimpath -ldflags="-s -w"

build-ProcessadorPedidos:
	$(GOBUILD) -o "$(ARTIFACTS_DIR)/bootstrap" ./cmd/sqs

build-ApiPedidos:
	$(GOBUILD) -o "$(ARTIFACTS_DIR)/bootstrap" ./cmd/http

build-ConsumidorLeituras:
	$(GOBUILD) -o "$(ARTIFACTS_DIR)/bootstrap" ./cmd/kinesis

build-PedidoPago:
	$(GOBUILD) -o "$(ARTIFACTS_DIR)/bootstrap" ./cmd/eventbridge

build-Relatorio:
	$(GOBUILD) -o "$(ARTIFACTS_DIR)/bootstrap" ./cmd/streamurl
```

Pontos que o template codifica (cada um evita um incidente típico):

- `FunctionResponseTypes: [ReportBatchItemFailures]` em **SQS e Kinesis** — sem isto, a resposta parcial do handler é **ignorada**.
- SQS: `VisibilityTimeout` — a AWS **recomenda** ≥ **6×** o timeout da função (+ `MaximumBatchingWindowInSeconds`); o mínimo **válido** é
  timeout ≤ visibilidade. O CloudFormation não faz a conta — por isso os dois parâmetros; revise-os juntos. `maxReceiveCount: 5`
  (recomendação: ≥ 5) e DLQ com retenção de 14 dias.
- SQS: `ScalingConfig.MaximumConcurrency` (2–1000; a **soma** dos máximos das filas da função ≤ *reserved concurrency*, senão há
  *throttling*) protege o banco/downstream. Não combina com o *Provisioned Mode* da event source mapping.
- Kinesis: `MaximumRetryAttempts` e `MaximumRecordAgeInSeconds` explícitos (o padrão -1 = infinito trava o shard num registro ruim),
  `BisectBatchOnFunctionError` e `DestinationConfig.OnFailure`. A janela de 1 s com `BatchSize` 100 é escolha (junta registros), não
  obrigação: a exigência "`BatchSize` > 10 → `MaximumBatchingWindowInSeconds` ≥ 1" é do **SQS** segundo a referência do
  CloudFormation (a referência da API `CreateEventSourceMapping` a estende a Kinesis/DynamoDB, mas o padrão do Kinesis é 100 com janela 0).
- EventBridge: `EventInvokeConfig` (tentativas e destino de falha **da função**, para erros do handler) **e** `RetryPolicy` +
  `DeadLetterConfig` **no alvo da regra** (para falhas de entrega do EventBridge). Papéis diferentes; os dois são baratos.
- Function URL: `InvokeMode: RESPONSE_STREAM` casa com `*events.LambdaFunctionURLStreamingResponse`; `AuthType: AWS_IAM`.
- Políticas do SAM por recurso (`SQSPollerPolicy`, `KinesisStreamReadPolicy`, `SQSSendMessagePolicy`) — e **confira a role gerada**: na
  transformação (`aws-sam-translator` 1.115.0, verificado) o SAM anexa sozinho políticas gerenciadas **amplas** aos eventos de fila e de
  stream, além das que você pediu:

  | Role | Políticas gerenciadas anexadas |
  |---|---|
  | `ProcessadorPedidosRole` (evento SQS) | `AWSLambdaBasicExecutionRole` + `AWSLambdaSQSQueueExecutionRole` |
  | `ConsumidorLeiturasRole` (evento Kinesis) | `AWSLambdaBasicExecutionRole` + `AWSLambdaKinesisExecutionRole` |
  | `ApiPedidosRole`, `PedidoPagoRole`, `RelatorioRole` | `AWSLambdaBasicExecutionRole` |

  Para menor privilégio estrito, declare a `Role` explicitamente com as ações de polling só no ARN da fila/stream. Conferência sem conta
  AWS: o script `conferir.py` da **aws-lambda-python** (`references/iac-e-teste-local.md` §2) serve igual para este template.
- `LoggingConfig.LogFormat: JSON` estrutura os logs **do sistema**; os da aplicação são os que o `slog` escreve (o Lambda não recodifica
  uma linha que já é JSON).
- No Windows sem `make`: `BuildMethod: go1.x` (a doc da AWS o mostra com `provided.al2023`, `Handler: bootstrap` e `CodeUri` apontando
  para a pasta do `main`) — **não** verificado aqui.
- Validar: `cfn-lint template.yaml` (e `sam validate --lint` se tiver o SAM CLI — não verificado aqui).

## 2. Terraform (esqueleto — NÃO validado)

```hcl
resource "aws_sqs_queue" "dlq" {
  name                      = "pedidos-dlq"
  message_retention_seconds = 1209600 # 14 dias
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "fila" {
  name                       = "pedidos"
  visibility_timeout_seconds = 180 # >= 6 x timeout da função (30 s)
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 5
  })
}

resource "aws_lambda_function" "processador" {
  function_name    = "processador-pedidos"
  role             = aws_iam_role.lambda.arn # menor privilégio: só esta fila/tabela
  runtime          = "provided.al2023"
  architectures    = ["arm64"]
  handler          = "bootstrap"
  filename         = "bootstrap.zip"
  source_code_hash = filebase64sha256("bootstrap.zip")
  memory_size      = 256
  timeout          = 30

  logging_config {
    log_format = "JSON"
  }
}

resource "aws_lambda_event_source_mapping" "sqs" {
  event_source_arn        = aws_sqs_queue.fila.arn
  function_name           = aws_lambda_function.processador.arn
  batch_size              = 10
  function_response_types = ["ReportBatchItemFailures"]

  scaling_config {
    maximum_concurrency = 10
  }
}
```

Sem versão do *provider* fixada no esqueleto: fixe-a (`required_providers`). Argumentos conferidos na documentação do provider
(`function_response_types`, `scaling_config.maximum_concurrency` ≥ 2, `logging_config.log_format`, `sqs_managed_sse_enabled`), **sem** `terraform validate`.
Gate: `terraform fmt -check && terraform validate && terraform plan` (→ **engenheiro-iac**).

## 3. Teste local sem AWS: Runtime API simulado

O `bootstrap` não sabe nada de AWS: ele conversa HTTP com o endereço em `AWS_LAMBDA_RUNTIME_API` (`GET .../invocation/next` para pegar
um evento; `POST .../invocation/<id>/response` ou `/error` para devolver o resultado). Um servidor de ~90 linhas exercita o binário
**real** com eventos reais, sem Docker, sem credenciais e sem rede.

`fake_runtime_api.py` (o runtime do Go envia o corpo em `Transfer-Encoding: chunked`, tratado abaixo; o content-type é impresso para
conferir o streaming):

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

Uso (compile para o **host**; um binário arm64 só roda em arm64 ou sob emulação):

```bash
CGO_ENABLED=0 go build -tags lambda.norpc -o bootstrap ./cmd/sqs
python3 fake_runtime_api.py eventos_sqs.json &
AWS_LAMBDA_RUNTIME_API=127.0.0.1:9001 AWS_LAMBDA_FUNCTION_NAME=teste \
AWS_LAMBDA_FUNCTION_VERSION='$LATEST' AWS_LAMBDA_FUNCTION_MEMORY_SIZE=128 \
AWS_LAMBDA_LOG_GROUP_NAME=g AWS_LAMBDA_LOG_STREAM_NAME=s AWS_REGION=sa-east-1 _HANDLER=bootstrap \
./bootstrap
```

Eventos usados e respostas **observadas**:

| Binário | Evento | Resposta observada |
|---|---|---|
| `cmd/sqs` | `eventos_sqs.json` (abaixo) | `{"batchItemFailures":[{"itemIdentifier":"json-ruim"},{"itemIdentifier":"sem-valor"}]}`; lote vazio → `{"batchItemFailures":[]}` |
| `cmd/sqs` com `PRAZO_MS=300` (menos que a margem de 500 ms) | `eventos_sqs.json` | as **4** mensagens devolvidas (nenhuma iniciada) — a resposta sai antes do deadline |
| `cmd/sqsdyn` sem `TABELA_IDEM` | qualquer | log `variável TABELA_IDEM ausente` e saída 1 **na init**, antes de pedir evento (no Lambda: `Runtime.ExitError` na init) |
| `cmd/http` | `eventos_http.json` (abaixo) | `GET /pedidos/42` → 200; `/pedidos/` → 400; `POST /outra` → 404 |
| `cmd/kinesis` | 3 registros, o 2º com `data` que não é JSON | `{"batchItemFailures":[{"itemIdentifier":"4960"}]}` |
| `cmd/ddbstream` | 2 registros, o 2º com `pk` numérica | `{"batchItemFailures":[{"itemIdentifier":"112"}]}` |
| `cmd/s3` | chave `entrada/red+flower.jpg`; depois `outra/x.txt` | sucesso (log com a chave decodificada); depois `/error` |
| `cmd/eventbridge` | `detail` válido; depois com campo extra | `null`; depois `/error` com `unknown field "obs"` |
| `cmd/streamurl` | Function URL | content-type `application/vnd.awslambda.http-integration-response`, prelúdio + 8 bytes nulos + corpo |

`eventos_sqs.json`:

```json
[{"Records":[{"messageId":"ok1","body":"{\"id\":\"a\",\"valor\":100}"},{"messageId":"json-ruim","body":"{nao e json"},{"messageId":"sem-valor","body":"{\"id\":\"b\",\"valor\":0}"},{"messageId":"ok2","body":"{\"id\":\"c\",\"valor\":7}"}]},{"Records":[]}]
```

`eventos_http.json`:

```json
[{"version":"2.0","routeKey":"GET /pedidos/{id}","rawPath":"/pedidos/42","pathParameters":{"id":"42"},"requestContext":{"http":{"method":"GET","path":"/pedidos/42"}}},
 {"version":"2.0","rawPath":"/pedidos/","pathParameters":{},"requestContext":{"http":{"method":"GET","path":"/pedidos/"}}},
 {"version":"2.0","rawPath":"/outra","requestContext":{"http":{"method":"POST","path":"/outra"}}}]
```

`eventos_kinesis.json` (o `data` é base64):

```json
[{"Records":[
 {"eventSource":"aws:kinesis","kinesis":{"sequenceNumber":"4959","partitionKey":"p","data":"eyJzZW5zb3IiOiJzMSIsInZhbG9yIjoxLjV9"}},
 {"eventSource":"aws:kinesis","kinesis":{"sequenceNumber":"4960","partitionKey":"p","data":"bmFvIGUganNvbg=="}},
 {"eventSource":"aws:kinesis","kinesis":{"sequenceNumber":"4961","partitionKey":"p","data":"eyJzZW5zb3IiOiJzMiIsInZhbG9yIjoyfQ=="}}]}]
```

Para o teste ser útil em CI: escreva a asserção (compare o JSON de resposta com o esperado) e inclua o caso de **erro** (`/error`), de
**prazo** (rode o servidor com `PRAZO_MS=300`) e de **corpo grande**. Integração com SQS/Kinesis/DynamoDB reais: ambiente de teste na
AWS ou LocalStack (→ **localstack-dev**) — **não verificado nesta skill**; o simulador cobre só o contrato do runtime.

## 4. Medição de init local (indicativa) e na AWS (a que vale)

Local — compara binários entre si, **não** é cold start (sem microVM, sem download do pacote, sem rede):

```python
#!/usr/bin/env python3
"""Mede, LOCALMENTE, o tempo até o runtime pedir a 1ª invocação (init) e até responder a ela — 1 amostra por execução.
NÃO é cold start do Lambda (sem microVM, sem download do pacote): serve só para comparar binários entre si.
Uso:  for i in $(seq 25); do python3 medir_init.py eventos_sqs.json ./bootstrap; done"""
import json, os, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

EVENTO = json.load(open(sys.argv[1]))[0]
BIN = sys.argv[2]
t = {}


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def do_GET(self):
        t.setdefault("t_next", time.perf_counter())
        if t.get("servido"):
            time.sleep(5)  # sem mais eventos: segura a conexão, como o Lambda real
            return
        t["servido"] = True
        b = json.dumps(EVENTO).encode()
        self.send_response(200)
        for k, v in {"Lambda-Runtime-Aws-Request-Id": "r1",
                     "Lambda-Runtime-Deadline-Ms": str(int(time.time() * 1000) + 30000),
                     "Lambda-Runtime-Invoked-Function-Arn": "arn:aws:lambda:sa-east-1:0:function:t",
                     "Lambda-Runtime-Trace-Id": "Root=1-00000000-000000000000000000000001",
                     "Content-Type": "application/json"}.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        if "chunked" in self.headers.get("Transfer-Encoding", "").lower():  # o runtime do Go envia chunked
            while True:
                n = int(self.rfile.readline().strip() or b"0", 16)
                if n == 0:
                    self.rfile.readline()
                    break
                self.rfile.read(n)
                self.rfile.readline()
        else:
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
        t["t_resp"] = time.perf_counter()
        self.send_response(202)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"{}")


class S(ThreadingHTTPServer):
    def handle_error(self, *a):  # matar o bootstrap derruba a conexão: ruído esperado
        pass


srv = S(("127.0.0.1", 9002), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
env = dict(os.environ, AWS_LAMBDA_RUNTIME_API="127.0.0.1:9002", AWS_LAMBDA_FUNCTION_NAME="t",
           AWS_LAMBDA_FUNCTION_VERSION="$LATEST", AWS_LAMBDA_FUNCTION_MEMORY_SIZE="128",
           AWS_LAMBDA_LOG_GROUP_NAME="g", AWS_LAMBDA_LOG_STREAM_NAME="s", AWS_REGION="sa-east-1", _HANDLER="bootstrap")
t0 = time.perf_counter()
p = subprocess.Popen([BIN], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
while "t_resp" not in t and time.perf_counter() - t0 < 5:
    time.sleep(0.0005)
p.kill()
p.wait()
if "t_resp" not in t:
    sys.exit("sem resposta em 5 s")
print(f"init {(t['t_next'] - t0) * 1000:.1f} ms | 1a resposta {(t['t_resp'] - t0) * 1000:.1f} ms")
srv.shutdown()
```

```bash
for i in $(seq 25); do python3 medir_init.py eventos_sqs.json ./bootstrap; done   # mediana das 25 amostras
```

Resultado (2026-10-28, Go 1.24.13 + `aws-lambda-go` v1.54.0, host x86_64 com 2 CPUs, 25 amostras por binário, handler SQS trivial;
medianas): `norpc` + `-s -w` → init ≈ 2,8 ms e 1ª resposta ≈ 3,8 ms; padrão (com RPC, sem `-s -w`) → ≈ 3,3 ms e ≈ 4,5 ms (com Go
1.27.3 + v1.55.1 foram ≈ 3,4/4,4 e 4,1/5,3 ms). A diferença (< 1 ms) está no
nível do ruído de uma máquina compartilhada. Conclusão honesta: um handler Go trivial começa em poucos milissegundos; o cold start real
vem de **pacote, init do SDK/TLS/credenciais, VPC e memória** — meça na AWS. (Comparação Go × Rust: **aws-lambda-go-rust**.)

Na AWS — a linha `REPORT` de cada invocação traz `Duration`, `Billed Duration`, `Memory Size`, `Max Memory Used` e, na invocação fria,
`Init Duration`. Consulta de exemplo no CloudWatch Logs Insights (não validada aqui):

```text
filter @type = "REPORT"
| stats count() as invocacoes, count(@initDuration) as frias, avg(@initDuration) as init_medio,
        pct(@duration, 95) as p95_ms, max(@maxMemoryUsed / 1000 / 1000) as pico_mb by bin(1h)
```

Dimensione memória/timeout por medição (CPU é proporcional à memória; mais memória pode **reduzir** o custo total se a duração cair
mais que o preço sobe) e compare `x86_64` × `arm64` com a sua carga — não assuma.

## 5. Migrar de `provided.al2` / `go1.x` para `provided.al2023`

1. **Prazos:** `provided.al2` foi descontinuado em 2026-07-31 — sem patches nem suporte da AWS; a criação de funções é bloqueada em
   2027-07-29 e a atualização em 2027-08-31 (até lá, CLI, SAM e CloudFormation ainda criam/atualizam; as invocações continuam). `go1.x` já
   foi descontinuado (2024-01-08). Reconfirme as datas na documentação antes de comunicar.
2. **De `go1.x`:** a página de Go do Lambda ainda cita `provided.al2` como destino — não use: ele já foi descontinuado. O handler vira executável: compile `bootstrap` (`GOOS=linux`, `-tags lambda.norpc`) e coloque-o na **raiz** do zip,
   troque `Runtime` para `provided.al2023` (o campo `Handler` é exigido no zip mas o nome é livre; mantenha `bootstrap` por convenção); o
   código do handler (`lambda.Start`) permanece.
3. **Binário estático** (`CGO_ENABLED=0`) não depende da libc do SO. Binário **dinâmico** (glibc) precisa ter sido
   compilado contra uma glibc não mais nova que a do AL2023.
4. **arm64:** troque a arquitetura **e** recompile para `arm64` na mesma mudança (artefato amd64 em função arm64 falha na inicialização).
5. **Implante com alias/versão** e desloque o tráfego em etapas (ponderado), acompanhando erros, `Init Duration` e `Max Memory Used`; mantenha
   a versão anterior para rollback.
