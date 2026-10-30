# Política da AWS para testes de carga, eventos simulados e custo

> Reference de `testes-carga-desempenho-aws`. Base: Amazon EC2 Testing Policy (stress test), página de
> Penetration Testing / Simulated Events, DDoS Simulation Testing policy, COST03-BP05 e Cost Anomaly
> Detection. Políticas mudam: **releia as páginas antes de cada campanha** e registre a data da leitura
> no plano do teste.

## 1. Stress e load test legítimos

- A política de stress test cobre o envio de grande volume de tráfego **legítimo ou de teste** a uma
  aplicação que deve aguentá-lo — inclui stress, load e gameday tests.
- **Não exige aprovação prévia nem formulário** para stress test legítimo (a orientação antiga do
  PERF01-BP07, de 2023, mandava avisar o Support; a política atual não exige).
- Endpoints na AWS devem estar **na mesma região da origem do teste**.
- Pode haver traffic shaping acima de ~25 Gbps (ou 100 Gbps conforme caminho e região).
- **Inundação de pacotes/conexões e reflexão/amplificação não são stress test — são DDoS**:
  "Volumetric network-based DDoS simulations are explicitly prohibited from the Amazon EC2 platform".

## 2. O que exige formulário de Simulated Events

- **iPerf**, exercícios de red/blue/purple team com C2, phishing simulado, malware e "outros eventos
  simulados".
- Envio pelo console do Support **pelo menos 2 semanas antes**; resposta em até 2 dias úteis.
- **Request flooding** (login flooding, API flooding) é proibido como atividade de pentest.

## 3. Simulação de DDoS

- Só com **parceiro pré-aprovado** pela AWS e contra recurso protegido por **AWS Shield Advanced**.
- Limites publicados (ex.: 20 Gbps; 50.000 RPS) e **proibido originar o teste de recursos AWS**.
- Exceções exigem registro com antecedência (14 dias). Na prática da Squad: fora do escopo de times de
  produto — é decisão da segurança corporativa.

## 4. Regras do banco (valem junto com as da AWS)

- Carga só em pré-produção isolada; produção só com aprovação formal, janela e plano de abortar.
- Aviso prévio a operação, segurança e donos de dependências (inclusive APIs de terceiros: o teste pode
  violar o contrato de rate limit deles).
- Dados sintéticos; nenhuma credencial no script (variável de ambiente ou Secrets Manager).

## 5. Custo — o teste também tem orçamento

- **COST03-BP05**: Budgets por conta/workload (gasto real e previsto) e **Cost Anomaly Detection**
  (limiares absolutos ou percentuais; alertas via SNS).
- Antes do teste, estime: invocações e duração da Lambda (incluindo INIT, cobrado desde 08/2025),
  leitura/escrita no DynamoDB, NAT Gateway e transferência, logs (DEBUG sob carga é caro), Fargate do
  gerador, dashboards residuais da solução DLT.
- Defina condição de parada por custo (alarme de orçamento) além da condição por erro.
- Ambiente em escala de produção **sob demanda**: suba para o teste e destrua depois (PERF01-BP07).
- Não há serviço AWS nativo de "diferença de custo por PR"; ferramentas como Infracost são de terceiros.

## 6. Checklist de autorização do teste

- [ ] Política de stress test relida em DD/MM/AAAA; o teste não é volumétrico de rede.
- [ ] Nenhuma atividade que exija Simulated Events (ou formulário enviado ≥ 2 semanas antes).
- [ ] Origem e alvo na mesma região.
- [ ] Aprovação interna, janela e comunicação registradas.
- [ ] Budget e alarme de anomalia ativos; condição de parada por custo e por erro.

## Fontes

- https://aws.amazon.com/ec2/testing/
- https://aws.amazon.com/security/penetration-testing/
- https://aws.amazon.com/security/ddos-simulation-testing/
- https://docs.aws.amazon.com/wellarchitected/2023-04-10/framework/perf_performing_architecture_load_test.html
- https://docs.aws.amazon.com/de_de/wellarchitected/2025-02-25/framework/cost_monitor_usage_config_tools.html
- https://docs.aws.amazon.com/cost-management/latest/userguide/getting-started-ad.html
- https://aws.amazon.com/blogs/compute/aws-lambda-standardizes-billing-for-init-phase/
