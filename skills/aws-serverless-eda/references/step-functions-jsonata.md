# Referência — Step Functions com JSONata (estado, erro, Map distribuído e padrões)

> Parte da skill `aws-serverless-eda`. Carregue sob demanda ao **escrever ou revisar uma state machine**
> (ASL). Hub: `../SKILL.md` (seções "Orchestrate with State Machines" e "Saga Pattern").
> Proveniência: técnicas reescritas a partir de `awslabs/agent-plugins` (Apache-2.0), skill
> `aws-serverless/aws-step-functions`. Nenhum trecho copiado — ver `docs/ATTRIBUTIONS.md`.
> Limites e preços mudam: confirme nas páginas oficiais antes de decisão cara.

## 1. Standard ou Express?

| Critério | Standard | Express |
|---|---|---|
| Duração máxima | até 1 ano | até 5 minutos |
| Semântica | exatamente uma vez | ao menos uma vez (assíncrono) / no máximo uma (síncrono) |
| Histórico | consultável por API (retenção limitada) | só CloudWatch Logs |
| `.sync` e `.waitForTaskToken` | suportados | **não** suportados |
| Cobrança | por transição de estado | por execução + duração |
| Use para | pagamento, pedido, compliance, tudo que **não pode** rodar duas vezes | ingestão de alto volume, transformação curta, passos idempotentes |

Combinação comum: Express na borda (alto volume, rápido) que dispara uma execução Standard para a
cauda longa (espera, aprovação humana). Express exige passos **idempotentes** (ver §5).

## 2. JSONata em vez de JSONPath (para state machines novas)

- Declare `"QueryLanguage": "JSONata"` no topo da máquina; dá para migrar estado a estado, pois
  JSONPath continua válido e é o padrão quando o campo é omitido.
- Os cinco campos de E/S do JSONPath (`InputPath`, `Parameters`, `ResultSelector`, `ResultPath`,
  `OutputPath`) viram dois: **`Arguments`** (entrada da tarefa) e **`Output`** (saída do estado).
- Toda expressão fica entre `{% ... %}`. Sem os delimitadores o texto é literal, sem erro nenhum.
- Dentro da expressão não se usa `$`/`$$` solto: o dado vem de `$states.input`, `$states.result`,
  `$states.errorOutput` e `$states.context` (metadados da execução, do estado e do item do Map).
- **Não misture** campos JSONPath e JSONata no mesmo estado.
- Toda expressão precisa produzir valor definido: acessar campo inexistente lança
  `States.QueryEvaluationError`. Proteja com `$exists()` antes de ler campo dinâmico e com `$type()`
  antes de aritmética. Cuidado com filtros: um único acerto volta como **objeto**, não array de um
  elemento, e nenhum acerto volta como indefinido — normalize para array antes de iterar.

## 3. Variáveis (`Assign`) e saída enxuta

- Guarde em `Assign` o que **estados posteriores** precisam (ID da cobrança, quantidade reservada) em
  vez de empurrar tudo pelo `Output`. Variáveis valem em qualquer estado seguinte do mesmo escopo.
- `Assign` e `Output` do mesmo estado são avaliados **em paralelo** com os valores de entrada: o que
  você atribui agora só existe no **próximo** estado. Por isso trocar `x` e `y` funciona sem variável
  temporária — e por isso ler no `Output` o que acabou de atribuir dá o valor antigo.
- Não se atribui a subcaminho de variável; reatribua o objeto inteiro.
- Em `Choice`, cada regra pode ter seu `Assign`; se nenhuma casa, vale o `Assign` do estado.
- Mantenha `Output` mínimo (só o que o próximo estado consome): payload grande custa e esbarra no
  limite de tamanho de estado. Em Map e Parallel, observe o escopo: o que é atribuído dentro de uma
  iteração não vaza para fora.

## 4. Erros: Retry, Catch e as armadilhas

- `Retry` e `Catch` existem em **Task, Parallel e Map**. Retentativas vêm antes; o `Catch` só atua
  quando elas se esgotam.
- Retrier: `IntervalSeconds`, `MaxAttempts` (0 = nunca), `BackoffRate` (≥ 1), `MaxDelaySeconds` (teto)
  e `JitterStrategy: FULL`. **Sempre use jitter e teto** em chamada a serviço compartilhado, para não
  sincronizar rajadas de retry.
- `States.ALL` fica sozinho no `ErrorEquals` e no **último** retrier/catcher. Erros próprios não
  podem começar com `States.`.
- Erros embutidos que mais importam: `States.Timeout`, `States.HeartbeatTimeout`, `States.TaskFailed`,
  `States.Permissions`, `States.QueryEvaluationError`, `States.BranchFailed` (Parallel),
  `States.NoChoiceMatched` (Choice sem `Default`) e `States.ExceedToleratedFailureThreshold` (Map).
- **Não retente** `States.QueryEvaluationError` (`MaxAttempts: 0`): é bug da expressão, repetir só
  gasta transições.
- No `Catch`, `$states.errorOutput` traz `Error` e `Cause`. Se o catcher casa, o `Assign` de **nível
  de estado não roda** — só o do catcher. Sem `Output` no catcher, a saída é o objeto de erro cru.
- Padrão de falha amigável: retry com backoff → `Catch` de `States.ALL` guarda o erro em variável →
  estado `Fail` cuja `Cause` é montada com `$exists()` (o caminho do catch pode não ter ocorrido).
- Em `Parallel`, um ramo falho derruba o estado inteiro (`States.BranchFailed`). Em `Map`, tolere
  falhas com `ToleratedFailurePercentage`/`ToleratedFailureCount`.

## 5. Integrações de serviço

| Sufixo do `Resource` | Comportamento | Quando |
|---|---|---|
| (nenhum) | chama a API e segue | disparar sem esperar |
| `.sync` | espera o job terminar | precisa do resultado (ex.: filha, job de ETL) |
| `.waitForTaskToken` | pausa até alguém devolver o token | aprovação humana, sistema externo, fila |
| `aws-sdk:servico:acao` | qualquer API do SDK | quando não há integração otimizada |

- Prefira a integração **otimizada** quando existir (ex.: `lambda:invoke`) à via SDK.
- Execução filha com `startExecution.sync:2` devolve a saída como **string JSON**; use `$parse()`.
- `.sync` e `.waitForTaskToken` só em Standard. O token vem de `$states.context.Task.Token`;
  combine com `TimeoutSeconds` (e `HeartbeatSeconds` quando houver) — sem timeout a espera é eterna.

## 6. Map: inline ou distribuído

- **Inline**: itens vêm do estado de entrada; roda dentro da própria execução. Bom para listas
  pequenas. `MaxConcurrency` 1 = sequencial; 0 = sem limite (cuidado com o serviço a jusante).
- **Distribuído** (`Mode: DISTRIBUTED`): cada iteração é uma **execução filha**. Use para milhares de
  itens, leitura direta de S3 (`ItemReader`: CSV, JSON, lista de objetos) e histórico por iteração.
- `ItemBatcher` agrupa itens em sub-listas (um lote por iteração) — reduz transições e chamadas;
  `ResultWriter` grava resultados no S3 em vez de estourar o limite de payload do estado.
- `ItemSelector` remodela cada item antes da iteração (e dá acesso ao contexto do Map).
- Dimensione `MaxConcurrency` pelo **gargalo a jusante** (limite de DynamoDB, API de terceiro), não
  pela vazão máxima do Step Functions.

## 7. Padrões prontos (quando aplicar)

| Padrão | Ideia | Cuidado |
|---|---|---|
| Polling (Wait → status → Choice) | espera inicial estimada, consulta, laço curto | limite o nº de voltas; senão a execução nunca termina |
| Saga / compensação | cada passo tem `Catch` que registra **qual** falhou e entra na cadeia de desfazer em ordem inversa | a compensação usa variáveis do passo direto (`chargeId`, `qtdReservada`) e também precisa de retry |
| Scatter-gather parcial | Map com tolerância 100% e filtro por `$exists(Error)` separa sucessos de falhas | normalize resultados filtrados para array |
| Semáforo / lock | escrita condicional no DynamoDB (`attribute_not_exists` + expiração) | `Catch` sempre libera o lock; TTL cobre execução que morreu |
| Humano no laço | `.waitForTaskToken` encadeado com `States.Timeout` → escalonar → rejeitar | cada elo com timeout próprio |
| Express → Standard | Express ingere em volume, Standard cuida da cauda longa | passos do Express idempotentes |

## 8. Testar e validar antes de publicar

- Salve definições como `*.asl.json`, valide a sintaxe/ASL antes do deploy e rode a API `TestState`
  para exercitar **um estado isolado** com entrada simulada e (se preciso) resposta simulada do
  serviço; ela devolve o resultado do estado, o próximo passo e, nos níveis de inspeção mais
  detalhados, as entradas/saídas intermediárias.
- Cubra explicitamente os caminhos de erro: tempo esgotado, `Catch` acionado, `Choice` sem `Default`.
- Em IaC, passe ARNs por substituição de definição (SAM `DefinitionSubstitutions`), nunca literais
  de conta/região. Ative logs e X-Ray; veja `arquiteto-cloud-aws/references/observabilidade.md`.

## 9. Checklist de revisão de uma state machine

1. `QueryLanguage: JSONata` no topo e nenhum campo JSONPath misturado?
2. Standard vs Express justificado; passos Express idempotentes?
3. Toda `Task` com `TimeoutSeconds` e `Retry` com backoff + jitter + teto?
4. `Catch` final leva a compensação ou a `Fail` com causa legível?
5. `Output` mínimo; dados de longa vida em `Assign`; leituras protegidas por `$exists()`?
6. Map com `MaxConcurrency` pensado no gargalo a jusante; resultado grande indo para S3?
7. `.sync`/`.waitForTaskToken` só em Standard, com timeout?
8. Estados testados com `TestState` (incluindo caminhos de erro)?
