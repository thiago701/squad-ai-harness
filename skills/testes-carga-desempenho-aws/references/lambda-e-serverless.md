# Desempenho de Lambda e serverless — medir antes de otimizar

> Reference de `testes-carga-desempenho-aws`. Base: docs do Lambda (modelo de recursos, SnapStart,
> concorrência e quotas), blogs AWS Compute sobre cold start e cobrança do INIT, Lambda Power Tuning
> (open source, citado pela doc do Lambda), CodeGuru Profiler. Decisão SnapStart × GraalVM × CRaC em
> Java: `lambda-java-cold-start`.

## 1. Memória e CPU

- Memória de **128 MB a 10.240 MB**, em incrementos de 1 MB; CPU proporcional — **1.769 MB = 1 vCPU**.
- **AWS Lambda Power Tuning**: máquina de estados do Step Functions que invoca a função em várias
  memórias, analisa os logs e recomenda o ponto de **custo**, **velocidade** ou **equilíbrio**.
  Entradas: `lambdaARN`, `powerValues`, `num`, `payload`. Pode entrar no CI/CD.
- **Atenção:** a função executa de verdade — chamadas HTTP, SDK e **efeitos colaterais**. Use payload
  realista e conta de teste.
- Compute Optimizer também recomenda memória (só x86_64, exige opt-in).

## 2. Cold start

- Afeta **menos de 1%** das invocações; varia de **< 100 ms a > 1 s**. Causas: scaling, rebalanceamento
  entre AZs, atualização da função, reciclagem de ambientes ociosos.
- Medição: `Init Duration` na linha REPORT do log; métrica `init_duration` do Lambda Insights.
- A AWS **não recomenda warmers** (pings agendados) em produção.
- **Cobrança do INIT desde 01/08/2025** (ZIP + runtime gerenciado + on-demand): INIT entra no Billed
  Duration — reduzir pacote, SDK e init virou também redução de custo. A AWS publicou query de Logs
  Insights (`BilledGBs`, `UnbilledInitGBs`, `UnbilledInitRatio`) para medir.
- **SnapStart**: snapshot do ambiente inicializado ao **publicar versão**; Java 11+, Python 3.12+, .NET 8+.
  Incompatível com provisioned concurrency, EFS, ephemeral storage > 512 MB e `$LATEST`. Cuidados:
  unicidade (IDs/segredos/entropia gerados no init se repetem), reconexão de rede, dados temporários.
  Java sem custo extra; demais runtimes pagam cache (mínimo 3 h) e restauração.
- **Provisioned Concurrency** para latência garantida; tende a compensar com utilização sustentada
  acima de ~60%.

## 3. Concorrência e escalonamento (o que o spike testa)

- Concorrência padrão **1.000 por região** (ajustável; contas novas começam com quota menor).
- Escalonamento por função: **+1.000 ambientes a cada 10 s** (ou 10.000 RPS a cada 10 s).
- Excedeu → **429 (throttling)**. Concorrência reservada limita uma função e protege dependências.
- Payload síncrono 6 MB; timeout máximo 900 s.

## 4. Onde o gargalo costuma estar

| componente | sintoma sob carga | o que medir |
|---|---|---|
| API Gateway | 429 no Gateway | throttle da conta/estágio/método; burst |
| Lambda | 429, `Throttles`, `ConcurrentExecutions` no teto | concorrência, init, duração p99 |
| DynamoDB | `ThrottledRequests`, hot partition | capacidade, chave de partição, retries |
| RDS/Aurora | conexões esgotadas | RDS Proxy, pool, `DatabaseConnections` |
| SQS/EventBridge | backlog crescente | `ApproximateAgeOfOldestMessage`, taxa de consumo |
| API externa | rate limit | erros da dependência, circuit breaker |

## 5. Observabilidade durante o teste

- CloudWatch: `Duration` (p50/p95/p99), `Errors`, `Throttles`, `ConcurrentExecutions`, `IteratorAge`,
  métricas do Gateway (`Latency`, `IntegrationLatency`, `4XXError`, `5XXError`).
- X-Ray/ADOT para localizar o segmento lento; Logs Insights para cold start e custo.
- CodeGuru Profiler (amostra 1×/s, agrega em 5 min, dados em até 15 min; ativação pelo console em Java)
  para código caro. Verifique o status atual do serviço antes de adotar.
- Latência: percentis e **trimmed mean**; Apdex para traduzir em experiência.
- A AWS não publica um p99 universal: a meta vem do SLO do negócio (REL12-BP03).

## 6. Práticas

1. Linha de base medida (memória, init, p99, custo/1.000 requisições) antes de qualquer otimização.
2. Power Tuning com payload realista; repetir a cada mudança relevante de código ou dependência.
3. SnapStart avaliado para APIs sensíveis a latência; provisioned concurrency quando a meta exigir.
4. Regressão de desempenho no pipeline comparando com o histórico (QA.NT.2; PERF01-BP07).
5. Depois do deploy, revisar com dados reais (Trusted Advisor, Compute Optimizer).

## Fontes

- https://docs.aws.amazon.com/lambda/latest/dg/resource-model.html
- https://docs.aws.amazon.com/en_gb/lambda/latest/dg/snapstart.html
- https://docs.aws.amazon.com/lambda/latest/dg/burst-concurrency.html
- https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html
- https://aws.amazon.com/blogs/compute/understanding-and-remediating-cold-starts-an-aws-lambda-perspective
- https://aws.amazon.com/blogs/compute/operating-lambda-performance-optimization-part-1/
- https://aws.amazon.com/blogs/compute/aws-lambda-standardizes-billing-for-init-phase/
- https://github.com/alexcasalboni/aws-lambda-power-tuning
- https://docs.aws.amazon.com/codeguru/latest/profiler-ug/setting-up-lambda.html
- https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/qa.nt.2-validate-system-reliability-with-performance-testing.html
