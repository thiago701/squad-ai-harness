# Referência — Lambda Durable Functions (workflows longos dentro da Lambda)

> Parte da skill `arquiteto-cloud-aws`. Carregue sob demanda quando a tarefa pedir workflow multi-passo,
> espera longa, aprovação humana ou saga **dentro de uma Lambda**. Hub: `../SKILL.md`.
> Proveniência: técnica reescrita a partir de `awslabs/agent-plugins` (Apache-2.0), skill
> `aws-lambda-durable-functions`. Nenhum trecho copiado — ver `docs/ATTRIBUTIONS.md`.

## Quando escolher (e quando não)

| Situação | Escolha | Por quê |
|---|---|---|
| Fluxo de poucos passos, código já em Lambda, esperas de minutos a dias, callback humano | **Durable Functions** | A orquestração é código normal; sem DSL separada, sem segundo serviço para versionar |
| Fluxo visual, auditável por não-devs, integrações nativas (200+ serviços) sem código | Step Functions | Console/ASL e integrações diretas valem mais que "tudo em código" |
| Evento único, sem estado entre passos | Lambda simples + SQS/EventBridge | Durabilidade seria custo sem ganho (P1-Simplicidade) |
| Tarefa >15 min de CPU contínua | ECS Fargate / Batch | Durable não torna um passo mais longo que o timeout da função |

Regra de bolso: se o workflow cabe numa função, tem dono único e precisa esperar ou compensar, comece por
durable; migre para Step Functions quando a visibilidade operacional ou o número de integrações crescer.

## Modelo mental: checkpoint + replay

A função **reexecuta do início** a cada retomada. Passos já concluídos devolvem o resultado gravado sem rodar de
novo; o código fora de passos roda outra vez. Daí as quatro regras que causam quase todos os bugs:

1. **Tudo que é não determinístico vai dentro de um passo**: relógio, aleatório, UUID, chamada HTTP, consulta a
   banco, leitura de variável mutável. Fora de passo, o valor muda a cada replay e quebra a execução.
2. **Operação durável não aninha dentro de passo** (passo dentro de passo, espera dentro de passo, invocação
   dentro de passo). Para agrupar, use um *child context*.
3. **Mutação de variável de closure se perde no replay.** Passos devolvem valores; o estado vive no retorno.
4. **Efeito colateral fora de passo se repete.** Log deve usar o logger do contexto (consciente de replay).

Dê **nome descritivo a todo passo**: é o nome que identifica o passo no histórico e nos testes.

## Blocos de construção

- **Passo (step):** unidade atômica com retry próprio; resultado é gravado. Idempotência continua sendo sua
  responsabilidade quando o passo chama sistema externo (chave de idempotência no pedido).
- **Espera (wait):** pausa sem custo de computação; a função é descarregada e retomada depois.
- **Callback:** a execução gera um token, entrega a um sistema/pessoa e suspende até alguém reportar sucesso ou
  falha com esse token. Use *heartbeat* e timeout para não esperar para sempre. Serve a aprovação humana,
  webhook de terceiro e job assíncrono.
- **Wait-for-condition:** polling declarativo com estratégia de intervalo, no lugar de loop com sleep.
- **Map / Parallel:** concorrência controlada com política de conclusão (mínimo de sucessos, falhas toleradas em
  número ou percentual) e limite de concorrência. Defina a política *antes* de escrever o corpo.
- **Invocação durável:** chamar outra função durável como parte do fluxo, com o resultado gravado.

## Erros, retry e saga

- Classifique: erro **transitório** (re-tenta com backoff e teto de tentativas) × **permanente** (falha
  imediata, sem retry). Retry sem teto e sem classificação é a causa típica de execução presa.
- Saga: cada passo que muda estado registra sua **compensação**; ao falhar, rode as compensações em ordem
  inversa, cada uma também como passo (logo, idempotente).
- O erro que o código lança deve ser **determinístico** entre replays; não embuta timestamp ou id aleatório na
  mensagem fora de passo.

## Operação e segurança

- **Invocação exige ARN qualificado** (versão, alias ou `$LATEST`); ARN sem qualificador falha. Em produção,
  invoque por alias.
- Papel de execução: política gerenciada de execução durável (checkpoint + leitura de estado + logs). Quem
  responde callbacks externos precisa apenas das permissões de sucesso/falha de callback — menor privilégio,
  nunca credencial ampla.
- Dados gravados em checkpoint ficam no histórico da execução: **não coloque segredo nem PII em retorno de
  passo**; guarde referência (ARN do Secrets Manager, chave S3) e resolva dentro do passo.
- Pré-requisitos a conferir antes de gerar código: versão mínima do AWS CLI/SAM/CDK com suporte ao recurso e
  runtime com o SDK durável disponível (confirme na documentação AWS vigente — muda rápido).
- Disponibilidade por linguagem: SDKs oficiais para JavaScript/TypeScript e Python; para **Java**, o SDK é
  separado e mais novo (ver `docs/research/notes/java-aws-notes.md`) — valide maturidade antes de adotar.

## Testes

- Teste local com o runner de testes do SDK; teste na nuvem só para o que o local não cobre.
- Busque operações **pelo nome**, nunca por índice (a ordem muda quando o fluxo evolui).
- Teste o replay de verdade: execute com mais de uma invocação (espera + retomada) e afirme que passos
  concluídos não reexecutam.
- Use relógio falso para esperas longas; para callbacks, aguarde o callback ser registrado antes de respondê-lo.
- Cubra os caminhos de erro: transitório que recupera, permanente que compensa, timeout de callback.

## Troubleshooting de execução presa/falha

Leia o histórico da execução (ID da execução) antes de mexer no código: veja o último passo concluído, o próximo
esperado, se há callback pendente (token nunca respondido) e se o erro é de replay não determinístico. Causa
mais comum: valor não determinístico fora de passo introduzido num deploy novo enquanto havia execuções em voo —
**versione por alias e não altere a ordem/nome de passos de um fluxo com execuções ativas**.

## Anti-padrões

- Usar durable para um passo único ("Lambda com checkpoint de enfeite").
- Loop de `sleep` em vez de espera/condição.
- Segredo no retorno de passo; callback sem timeout; saga sem compensação idempotente.
- Mudar nome/ordem de passos com execuções em voo.
