# Distributed Load Testing on AWS e geradores de carga

> Reference de `testes-carga-desempenho-aws`. Base: página e guia da solução Distributed Load Testing on
> AWS (DLT), Prescriptive Guidance "Load testing applications", blog AWS DevOps de load test no CI/CD,
> PERF01-BP07 e REL12-BP03. Scripts k6/Locust/Gatling prontos: `especialista-qualidade`
> (`performance-tests.md`).

## 1. Tipos de teste segundo o Prescriptive Guidance (por pergunta)

| pergunta | tipo | como |
|---|---|---|
| quanto aguenta? | stress/capacidade | degraus até um limite definido |
| aguenta X? | load | a duração importa: back pressure só aparece com o tempo |
| escala para cima e para baixo? | elasticidade | cada degrau **mais longo que o período do gatilho de scaling** (ex.: CPU > 70% por 5 min → degraus > 5 min); comece com mais de uma instância; teste também o scale-down |
| degrada com o tempo? | soak | **taxa constante**; meça latência e erros (não o req/s alcançado); rastreie com X-Ray e IDs de correlação |
| está funcionando? | smoke em produção | carga baixa, horário de pouco tráfego |

REL12-BP03: a suíte cobre **uso médio, picos, spikes e carga alta sustentada**, excede a carga esperada
para achar o ponto de ruptura e sobe em incrementos para achar os limites de escala.

## 2. A solução DLT

- Executa **JMeter, k6 e Locust** **(terceiros)** sem modificação, ou um endpoint HTTP simples.
- Roda em **ECS on Fargate**, implantada por CloudFormation (o repositório também tem CDK); simula
  dezenas de milhares de usuários, em várias regiões, com testes paralelos.
- Agendamento imediato, futuro ou recorrente (recorrência exige data de expiração; intervalo maior que
  a duração do teste).
- Modos: **Standard** (a solução controla tasks × concorrência, ramp-up e hold, via Taurus) e
  **Native** (o script define a carga; ex.: k6 com 200 VUs em 5 tasks = 1.000 VUs; "safety duration"
  de até 24 h).
- Métricas agregadas por segundo; dashboard por minuto; dashboards do CloudWatch por cenário e região
  **persistem e custam** até apagar o cenário (apagar a stack não remove).
- Só HTTP/HTTPS; implantação apenas em regiões com Cognito; custo de referência da infraestrutura da
  solução em torno de US$ 31/mês em us-east-1 (fora a carga gerada e o sistema sob teste).

## 3. DLT como gate no pipeline (blog AWS DevOps)

```
Source → Build → Deploy Dev → Load Test (DLT) → [passou?] → Deploy Prod
```

- Critérios versionados em arquivo junto do código (ex.: tempo médio ≤ 1 s, erros ≤ 1).
- Ambiente espelho de produção, contas separadas.
- No banco/sem CI novo: o mesmo teste roda pelo harness local apontando para a pré-produção, e o
  resultado (JSON) é comparado com a linha de base versionada.

## 4. Geradores e dimensionamento

- Ferramentas simples (hey, ab, wrk, Vegeta — **terceiros**) testam uma URI; fluxo transacional exige
  JMeter ou k6.
- O gerador também tem limite: dimensione (CPU/rede) e distribua quando necessário; gerador fora da
  conta/VPC do sistema sob teste.
- PERF01-BP07: gerar carga com Spot, dados **sintéticos ou sanitizados**, ambiente por CloudFormation,
  e observar com Synthetics e RUM.

## 5. Roteiro mínimo de um teste

1. Meta (SLO, pico × margem) e critério de aprovação versionados.
2. Quotas conferidas e aumentadas (`quotas-e-limites.md`).
3. Ambiente: tamanho documentado (se menor que produção, registre a extrapolação e lembre que rede entre
   serviços também é gargalo).
4. Dados sintéticos em volume realista; endpoints sem efeito colateral nos testes de scaling.
5. Rampa → patamar → pico → recuperação; repetir pelo menos 2× para checar estabilidade.
6. Coleta: métricas do gerador **e** da AWS (throttles, erros, concorrência, duração, consumo do banco).
7. Relatório com gargalo evidenciado e nova linha de base; nunca sobrescrever resultados anteriores.

## Antipadrões (REL12-BP03, PERF01-BP07, PG)

Teste único fora do CI; ambiente diferente de produção sem documentar; sem metas; carga irreal (sem picos
nem sustentação); não exceder a carga esperada; monitoramento insuficiente; gerador subdimensionado;
sobrescrever resultados; testar produção em escala sem considerar o usuário.

## Fontes

- https://aws.amazon.com/solutions/implementations/distributed-load-testing-on-aws/
- https://docs.aws.amazon.com/solutions/latest/distributed-load-testing-on-aws/solution-overview.html
- https://docs.aws.amazon.com/solutions/latest/distributed-load-testing-on-aws/design-considerations.html
- https://docs.aws.amazon.com/prescriptive-guidance/latest/load-testing/test-types.html
- https://docs.aws.amazon.com/prescriptive-guidance/latest/load-testing/foundation.html
- https://aws.amazon.com/blogs/devops/load-test-applications-in-cicd-pipeline/
- https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_testing_resiliency_test_non_functional.html
- https://docs.aws.amazon.com/wellarchitected/2023-04-10/framework/perf_performing_architecture_load_test.html
