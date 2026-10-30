# Pacote, dependências e cold start — Python no AWS Lambda

> Estado de verificação (2026-10-28): build com **uv 0.11.32** para `python3.14` + `arm64` executado de verdade (wheels
> `manylinux2014_aarch64`, `.so` conferidas com `file`); tamanhos e tempos de import **medidos nesta entrega** numa máquina x86_64 de
> 2 vCPUs, sem microVM e sem download de pacote — são **indicativos**. Cold start real só vale medido **na AWS** (linha `REPORT`).

## 1. `pyproject.toml` (uv)

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

- Dependências de produção com teto de major (`<4`, `<2`): atualização major é decisão, não acidente.
- Ferramentas de linha de comando que **não** são importadas pelo código (ex.: `cfn-lint`) rodam com `uvx`, fora do lock de produção.
- `uv.lock` versionado e build com `--frozen`: o pacote de produção é o que foi testado.

## 2. Build reprodutível do `.zip` (verificado)

```bash
# 1) dependências de produção travadas, com hashes (sem dev, sem o próprio projeto)
uv export --frozen --no-dev --no-emit-project -o requirements.txt

# 2) wheels da PLATAFORMA da função (não da sua máquina) — só binários, nada de compilar sdist no host
uv pip install --no-installer-metadata --no-compile-bytecode --only-binary :all: \
  --python-platform aarch64-manylinux2014 --python 3.14 \
  --target build -r requirements.txt            # x86_64: --python-platform x86_64-manylinux2014

# 3) o seu código na raiz do pacote, sem __pycache__
cp -r src/pedidos build/
find build -name __pycache__ -prune -exec rm -rf {} +
(cd build && zip -qr9 ../function.zip . -x '*.pyc')

# 4) confira o artefato: as extensões nativas têm de ser aarch64 e da versão do runtime
file build/pydantic_core/*.so    # -> ELF 64-bit LSB shared object, ARM aarch64 (cpython-314-aarch64-linux-gnu)
```

Equivalente com `pip` (o que a documentação da AWS mostra):
`pip install --platform manylinux2014_aarch64 --target=package --implementation cp --python-version 3.14 --only-binary=:all: --upgrade <pacote>`.

O `Makefile` para o `sam build` (`BuildMethod: makefile`) faz exatamente esses passos:

`Makefile`:

```make
# SAM chama `make build-<IdLogico>` com ARTIFACTS_DIR = diretório do pacote. Requer uv e uv.lock commitado.
PY ?= 3.14
PLATAFORMA ?= aarch64-manylinux2014     # x86_64-manylinux2014 se a função for x86_64

define empacotar
	uv export --frozen --no-dev --no-emit-project $(1) -o "$(ARTIFACTS_DIR)/requirements.txt"
	uv pip install --no-installer-metadata --no-compile-bytecode --only-binary :all: \
	  --python-platform $(PLATAFORMA) --python $(PY) --target "$(ARTIFACTS_DIR)" -r "$(ARTIFACTS_DIR)/requirements.txt"
	cp -r src/pedidos "$(ARTIFACTS_DIR)/"
	rm -f "$(ARTIFACTS_DIR)/requirements.txt"
	find "$(ARTIFACTS_DIR)" -name __pycache__ -prune -exec rm -rf {} +
endef

build-ProcessadorPedidos build-ApiPedidos:
	$(call empacotar,)

build-FluxoPedido:
	$(call empacotar,--group durable)
```

Por que não `pip install -r requirements.txt` direto no Windows/macOS: o pip baixa o wheel **do host** (`win_amd64`, `macosx_arm64`)
e a função quebra na init com `ImportError` (o clássico "No module named 'pydantic_core._pydantic_core'"). Pacote só com dependência
pura não sofre disso — mas você não controla o que entra transitivamente.

Pacote com dependência que **só** existe como sdist (C/C++ sem wheel `manylinux`): compile em ambiente Amazon Linux 2023 da mesma
arquitetura (imagem `public.ecr.aws/lambda/python:3.14` ou `sam build --use-container`), ou troque por imagem de contêiner.

## 3. Tamanhos medidos (arm64, `zip -9`, Python 3.14)

| Conteúdo | `.zip` | descompactado |
|---|---|---|
| só o código `pedidos/` | 23 KB | — |
| `aws-lambda-powertools` 3.38.0 (sem extras) | 1,1 MB | 3,9 MB |
| `aws-lambda-powertools[parser]` (+ pydantic 2.14.1 / pydantic-core 2.50.1) | 3,6 MB | 10,7 MB |
| `boto3` 1.43.121 (+ botocore, s3transfer, urllib3…) | 17,1 MB | 23,1 MB |
| tudo acima (o pacote de `requirements.txt`) | 20,6 MB | 33 MB |

- O **botocore** sozinho tem ≈ 20 MB descompactado: é a maior parte do pacote. A AWS recomenda empacotá-lo mesmo assim (controle de
  versão); se o tamanho apertar (limite de 250 MB com layers), use **layer** própria versionada — nunca empacote `urllib3`/`botocore`
  soltos sem o `boto3` correspondente.
- Acima de 50 MB zipado não dá upload direto: o SAM/CloudFormation envia via S3 (o SAM faz sozinho até 250 MB descompactado).
- Imagem de contêiner (até 10 GB) para ML/dependência nativa grande — com o custo de você reconstruir a imagem a cada patch da base.

## 4. Layers

- O conteúdo da layer vai para `/opt/python` (ou `/opt/python/lib/python3.14/site-packages`); ordem de busca: **pacote da função >
  layers > runtime**. Até 5 layers; o limite de 250 MB vale para função + layers.
- Layer pública do Powertools: `arn:aws:lambda:<região>:017000801446:layer:AWSLambdaPowertoolsPythonV3-python314-arm64:<versão>` — a
  própria documentação do Powertools mostra versões diferentes em lugares diferentes da mesma página: **confira a versão por região**
  antes de fixar. Layer é dependência de supply chain como qualquer outra: fixe a versão (nunca "a última").
- Layer **não** substitui lock: com dependências no pacote, o que foi testado é o que roda.

## 5. Cold start: o que pesa e como medir

Tempo de import medido localmente (x86_64, Python 3.14.6, mediana de 15 processos novos, com `.pyc` em cache):

| Módulo do handler | Import (mediana) |
|---|---|
| `pedidos.lote` (stdlib: `json`, `logging`, `dataclasses`) | ≈ 31 ms |
| `pedidos.handler_sqs` (+ `boto3` + criação do cliente DynamoDB) | ≈ 253 ms |
| `pedidos.handler_http` (+ Powertools Event Handler + Pydantic) | ≈ 343 ms |
| `pedidos.handler_sqs_pt` (+ Batch, Parser, Idempotency, Logger) | ≈ 387 ms |

O que fazer com isso (P1 antes de P2):

1. **Não importe o que não usa** — cada import de topo é pago em toda init. Import tardio (dentro da função) só para dependência
   pesada e rara, e com medição: ele move o custo para a 1ª invocação que a usa.
2. Crie o cliente `boto3` **uma vez** na init (custo pago uma vez por ambiente); **não** crie no handler.
3. `arm64` (Graviton) + memória dimensionada medindo — CPU é proporcional à memória e o import é CPU-bound.
4. `.pyc`: a AWS recomenda **não** empacotar `__pycache__` (bytecode de outra versão do Python é ignorado ou incompatível).
   Medimos `handler_sqs_pt` com e sem `.pyc` pré-compilado e a diferença ficou **dentro do ruído** da máquina de teste — não adote
   bytecode pré-compilado sem medir na AWS, com a mesma versão exata do runtime.
5. Ainda não basta? SnapStart, Provisioned Concurrency ou Managed Instances (`references/modelos-de-execucao.md`).

Na AWS, a medida que vale está na linha `REPORT` (`Init Duration` só aparece na 1ª invocação do ambiente):

```text
fields @timestamp, @initDuration, @duration, @maxMemoryUsed
| filter @type = "REPORT" and ispresent(@initDuration)
| stats count() as frios, pct(@initDuration, 50) as p50, pct(@initDuration, 95) as p95, max(@maxMemoryUsed) as memoria
  by bin(1h)
```

Compare p95 **sob a carga real**, antes e depois de cada mudança; não copie número de blog como fato.

## 6. Migração de runtime (3.9/3.10/3.11 → 3.13/3.14)

- `python3.10` (AL2) é descontinuado em **2026-10-31** e `python3.11` (AL2) em 2027-06-30; depois da descontinuação não há patch nem
  suporte e o console deixa de permitir criar/editar; o bloqueio de **atualização** chega em 2027-08-31 — depois dele não dá para voltar
  ao runtime antigo.
- O que costuma quebrar: wheels nativos (reconstrua para `cp314`), dependências que fixavam `python_requires<3.12`, APIs removidas da
  stdlib (`distutils` saiu no 3.12; `asynchat`/`asyncore`/`imp` também), e o SO: AL2 → AL2023 muda `glibc` e bibliotecas do sistema
  (binário próprio compilado contra AL2 pode falhar).
- Caminho seguro: rode a suíte com a versão nova (`uv python install 3.14`), reconstrua o pacote, publique versão nova, desloque o
  tráfego do alias aos poucos (ponderado ou com CodeDeploy pelo SAM), acompanhe erros, `Init Duration` e `Max Memory Used`, e mantenha a
  versão anterior para rollback.
