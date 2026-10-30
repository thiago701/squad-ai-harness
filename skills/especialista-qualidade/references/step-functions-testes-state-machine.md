# Testes de máquinas de estado do Step Functions (TestState)

> Eixo: testar a **lógica de uma state machine** (transformação de dados, escolha de caminho, retry, catch)
> sem implantar nem acionar serviços reais. Critérios reescritos a partir de awslabs/agent-plugins
> (Apache-2.0); confirme nomes de parâmetros na documentação AWS vigente antes de automatizar — a API é recente.

## Quando usar

| Pergunta | Ferramenta |
|---|---|
| A definição ASL está estruturalmente válida? | Validação local do arquivo (extensão `.asl.json` ativa o diagnóstico no editor) |
| Este **estado** transforma entrada/saída como eu espero? | Chamada de teste de estado isolado com mock |
| O **caminho** A→B→C funciona de ponta a ponta? | Encadeamento de testes de estado (saída de um vira entrada do próximo) |
| O fluxo funciona com serviços reais, permissões e limites? | Execução real em ambiente de teste (fora do escopo deste reference) |

Regra de pirâmide: a maior parte dos casos fica no teste de estado com mock (rápido, sem custo de
infraestrutura); poucas execuções reais cobrem integração, IAM e quotas.

## Antes de tocar a conta AWS

1. Peça autorização explícita para usar a API de teste na conta; nunca presuma acesso.
2. Confirme as credenciais (identidade chamadora) antes de qualquer chamada.
3. Sem credenciais: monte o comando/SDK para a pessoa rodar, em vez de improvisar.
4. Permissão mínima: só a ação de teste de estado. Com mock, o papel de execução é dispensável; sem mock,
   o chamador precisa também de permissão para passar o papel. Revelar segredos em tarefas HTTP exige
   permissão própria — não a conceda por padrão.

## Níveis de inspeção

Comece no mais barato e suba só se precisar: **INFO** (saída, status, próximo estado) → **DEBUG**
(+ entrada após transformação, resultado bruto, variáveis — o nível para depurar fluxo de dados) →
**TRACE** (+ requisição/resposta HTTP, para tarefas HTTP). Saída em TRACE com segredos revelados **nunca**
vai para o repositório nem para log de CI.

## O mock é um contrato — acerte o formato

O erro nº 1 é mock com forma diferente da resposta real da API do serviço. Procedimento:

1. Identifique o serviço e a operação pelo recurso da tarefa (ex.: invocar Lambda → resposta da operação
   de invocação, com código de status e payload).
2. Abra a referência da API desse serviço e copie a **forma** da resposta (nomes sensíveis a caixa, tipos,
   campos obrigatórios).
3. Escreva o mock com essa forma; o resultado entra como texto JSON dentro do campo de resultado.

Três modos de validação do mock, usados em sequência durante o desenvolvimento:

| Modo | Uso |
|---|---|
| NONE | Prototipar a lógica do estado; sem checagem de forma |
| PRESENT | Valida só os campos presentes; bom para mocks parciais |
| STRICT (padrão) | Exige campos obrigatórios e tipos; **o modo da CI** |

Mock de erro usa um objeto com nome do erro e causa; o nome tem de ser o que o Retry/Catch do estado
realmente declara — senão o teste passa por engano ou cai no handler errado.

## Tipos de estado que exigem atenção

- **Task com `.sync`:** o mock simula a API de **consulta de status** (a que o serviço usa para saber se
  terminou), não a de disparo. Ex.: iniciar execução aninhada síncrona → mock da descrição da execução.
- **Task com `waitForTaskToken`:** mock obrigatório e um contexto com token fictício. Sem mock, a chamada
  falha por validação.
- **Activity:** mock obrigatório.
- **Map:** o teste cobre o processamento de **entrada e saída** do Map (seleção de itens, lotes,
  concorrência máxima, tolerância a falha), não o interior das iterações; o mock é a saída **inteira** do
  Map. Em Map distribuído, entregue os dados na própria entrada, como se tivessem vindo do armazenamento.
  Para testar um estado *dentro* do Map, indique o nome do estado e o teste preenche índice e valor do item.
- **Parallel:** o mock é um array com um elemento por ramo, **na ordem da definição**.
- **Tarefa HTTP:** use TRACE só quando precisar ver a requisição; cuidado com segredos (acima).

## Retry e Catch

- Retry: informe quantas tentativas já ocorreram para simular a 2ª, 3ª… e afirme o status "reexecutável",
  o intervalo de espera e o índice da regra que casou. Teste também o **esgotamento** (tentativas acima
  do máximo caem no Catch ou falham).
- Catch: injete cada erro previsto e afirme o status "erro capturado", o **próximo estado** e a forma do
  erro na saída. Um erro não listado deve cair no `States.ALL`/falhar — teste esse caso também.
- Erro vindo de um estado filho em Map/Parallel: declare qual estado causou o erro ao simular.
- Limiar de falha do Map: simule N iterações falhas e afirme se o Map tolera ou falha.

## Encadeamento e contexto

- Caminho completo = sequência de testes de estado em que a **saída** de um e o **próximo estado**
  indicado alimentam o seguinte. Ele valida transformações e transições, mas **não** substitui execução
  real (não testa IAM, limites nem latência).
- Estados que leem o objeto de contexto (nome/horário da execução, token) precisam de contexto fictício
  **fixo** no teste — nada de horário corrente, para o teste ser reprodutível.
- Em script de automação, falhe o job se o próximo estado ou a saída divergir do esperado; não apenas
  imprima a resposta.

## Diagnóstico rápido

| Sintoma | Provável causa |
|---|---|
| Erro de tipo de campo no mock | Forma diferente da resposta real da API |
| Campo obrigatório ausente | Complete o mock ou rebaixe para PRESENT **só** localmente |
| Falha de validação em `.sync` | Você mockou a API de disparo, não a de consulta |
| Teste de Map "passa" sem exercitar a lógica | Mock da saída inteira esconde erro de seletor — verifique em DEBUG a entrada após o seletor |
| Teste de retry sempre acerta de primeira | Contador de tentativas não informado |

## Anti-padrões

- Mock inventado de memória, sem conferir a forma real da API.
- CI em NONE/PRESENT por "estar quebrando" — o mock é que precisa ser corrigido.
- Só testar o caminho feliz; Retry/Catch sem teste.
- Tratar o encadeamento de testes de estado como substituto de uma execução real em ambiente de teste.
- Executar a API de teste na conta sem autorização, ou versionar saída de TRACE com segredos.
