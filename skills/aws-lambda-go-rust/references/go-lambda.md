# Go no AWS Lambda — movido

> Desde a **aws-lambda-go-rust v1.1.0** (2026-10-28) o conteúdo de Go em Lambda vive na skill dedicada **aws-lambda-go**:
> [`../../aws-lambda-go/references/go-lambda.md`](../../aws-lambda-go/references/go-lambda.md) (handlers SQS/FIFO/HTTP,
> idempotência, build e Windows), [`../../aws-lambda-go/references/fontes-de-eventos.md`](../../aws-lambda-go/references/fontes-de-eventos.md)
> (Kinesis, DynamoDB Streams, S3, EventBridge, streaming) e
> [`../../aws-lambda-go/references/iac-e-teste-local.md`](../../aws-lambda-go/references/iac-e-teste-local.md).
>
> Esta skill continua dona do **Rust** e da **comparação Go × Rust** (tabela no `SKILL.md`). Os números de Go da comparação
> foram medidos **junto** com os de Rust (2026-10-03, mesma máquina); a remedição só de Go (2026-10-28) está na aws-lambda-go
> (`go-lambda.md` §8 e `iac-e-teste-local.md` §4): pacote igual a menos de 0,1 MB e init com décimos de ms de diferença — ruído.
