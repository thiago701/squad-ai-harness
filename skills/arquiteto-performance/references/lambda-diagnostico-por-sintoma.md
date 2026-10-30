# Referência — Lambda: diagnóstico por sintoma (concorrência, event source mapping, VPC)

> Parte da skill `arquiteto-performance`. Carregue sob demanda quando o relato for "a Lambda está lenta,
> throttlando, acumulando fila ou falhando" e a tabela de heurísticas do hub não bastar. Hub: `../SKILL.md`.
> Proveniência: técnica reescrita a partir de `awslabs/agent-plugins` (Apache-2.0), skill `aws-lambda`
> (guia de troubleshooting). Nenhum trecho copiado — ver `docs/ATTRIBUTIONS.md`.

## Ordem de investigação (antes de mexer em qualquer configuração)

1. **Logs recentes** da função: procure timeout, saída anormal do runtime e negação de permissão.
2. **Métricas**: taxa de erro, duração (média *e* p99), throttles, memória usada, idade do iterador (streams).
3. **Configuração**: timeout, memória, VPC, role IAM, concorrência reservada/provisionada.
4. **Reproduzir** com o evento que falhou — local primeiro; depois contra a função implantada, para eliminar
   diferença de ambiente.
5. **Tracing** (X-Ray ou equivalente) para achar qual chamada a jusante está lenta ou falhando.
6. **Dependências externas**: banco, APIs, filas — alcançáveis e saudáveis?

Regra: uma hipótese por vez, com métrica que a confirme. Mudar memória, timeout e concorrência juntos apaga a
causa.

## Latência alta — causas em ordem de checagem

| # | Suspeita | Como confirmar | Ação |
|---|---|---|---|
| 1 | Cold start | Lentidão só nas primeiras chamadas após ociosidade (`InitDuration` presente) | Clientes fora do handler, pacote menor, SnapStart/Provisioned (ver hub, seção Lambda) |
| 2 | Memória baixa = CPU baixa | Duração estável e alta; memória usada perto do limite | Subir memória e medir (Power Tuning) |
| 3 | Chamada externa lenta | Segmento lento no trace | Reuso de conexão, endpoint de VPC, timeout de SDK explícito |
| 4 | Pacote grande | `InitDuration` cresce com o tamanho | Podar dependências, camadas só para o que é compartilhado |
| 5 | Função em VPC | Cold start com setup de rede | Conferir caminho de saída (ver seção VPC abaixo) |

## Erros de função — leitura rápida

| Mensagem / sinal | Causa | Correção |
|---|---|---|
| "Task timed out after N seconds" | Execução passou do timeout | Achar o passo lento antes de simplesmente aumentar o timeout |
| Saída anormal do runtime | Estouro de memória ou processo derrubado | Aumentar memória; procurar vazamento |
| Acesso negado a API AWS | Falta ação na role | Adicionar **só** a ação e o recurso necessários (nunca curinga) |
| Recurso não encontrado | ARN ou região errada | Verificar existência na região da função |
| Muitas requisições (429) | Limite de concorrência atingido | Seção seguinte |

## Throttling e concorrência

**A conta que importa:** concorrência ≈ requisições por segundo × duração média em segundos. Reduzir a
duração reduz a concorrência necessária tanto quanto subir limite — e é mais barato.

Fatos que desfazem diagnósticos errados:

- O limite padrão de concorrência é **da conta, por região**, compartilhado por todas as funções. Uma função
  gulosa derruba as vizinhas; é isso que a concorrência reservada resolve (ela *garante* capacidade para uma
  função e *limita* seu teto ao mesmo tempo).
- O escalonamento sob demanda tem **taxa máxima de novas instâncias por janela de tempo** — pico abrupto
  throttla mesmo abaixo do teto da conta.
- **Invocação assíncrona nunca é rejeitada na entrada.** O evento é enfileirado e só depois tenta executar;
  se throttlado, volta à fila interna e é retentado por **até 6 horas**. Consequências: não precisa de SNS/
  EventBridge "como amortecedor de throttle" na frente de chamada assíncrona direta; se precisa de entrega
  garantida, configure DLQ ou destino de falha na própria função; concorrência reservada = 0 aceita o evento
  mas ele falha no processamento e segue o caminho de retry → DLQ.
- Para absorver pico em fluxo síncrono de entrada, a opção estrutural é **fila na frente** (SQS), trocando
  erro 429 por latência de fila.

**Passos:** olhar `ConcurrentExecutions` e `Throttles` no mesmo gráfico; descobrir se uma única função consome
a conta; comparar limite da conta com a soma das reservas; só então decidir entre reservar (proteger a crítica),
limitar (conter a ruidosa), pedir aumento de cota ou enfileirar.

## Event source mapping (ESM) — por origem

| Origem | Sintoma | Investigação | Remédio |
|---|---|---|---|
| Stream do DynamoDB / Kinesis | Idade do iterador subindo | Paralelização por shard (padrão 1, máx. 10), duração do handler, registro "veneno" em retry infinito, throttle | Subir paralelização e tamanho de lote; isolar registro ruim com bisseção de lote; limitar tentativas; mover falha persistente para destino de falha |
| Kinesis | Erro de throughput de leitura excedido | Vários consumidores no mesmo shard (2 MB/s por shard) | Fan-out aprimorado; modo sob demanda; mais shards se provisionado |
| SQS | Mensagens acumulando na DLQ | Visibilidade da fila **≥ timeout da função**; falha parcial de lote sem relatório; contagem máxima de recebimento baixa demais | Habilitar relato de falhas parciais de lote; ajustar a política de redrive |
| Kafka/MSK | Mapeamento preso em criando/falhou | Função fora da VPC do cluster; security group sem regra nas portas do broker; autenticação IAM/SASL mal configurada; segredo SASL em formato errado | Corrigir rede e credencial, nessa ordem |

Observação de método: um lote que falha por inteiro por causa de **um** item é o gerador clássico de DLQ
inflada e de duplicidade — trate com falha parcial de lote **e** handler idempotente.

## VPC e rede

- **Timeout falando com serviços AWS** de dentro de subnet privada = falta de caminho. Opções (escolha uma):
  endpoint de gateway para DynamoDB e S3 (gratuito, preferido); endpoints de interface para os demais (custo
  por hora + dados); NAT (mais caro, necessário para internet geral); ou saída IPv6 com gateway de saída só
  para IPv6, que dispensa NAT quando a VPC tem CIDR IPv6.
- **Esgotamento de IPs/ENIs**: erro de limite de interface de rede ao subir instâncias. Use várias subnets em
  AZs distintas e dimensione o CIDR; a reserva de concorrência também serve de teto para o consumo de IPs.

## SnapStart — quando "não funciona" ou dá resultado estranho

- **Valores repetidos** (UUID, timestamp, aleatório iguais entre invocações): foram gerados na inicialização,
  antes do snapshot. Gere dentro do handler, nunca em campo estático/inicializador.
- **Conexão morta na primeira chamada após ociosidade**: o objeto de conexão veio no snapshot, o socket não.
  Valide antes de usar ou reconecte via hook de pós-restauração.
- **Cold start continua alto**: SnapStart só vale para **versão publicada ou alias** que aponta para ela (não
  `$LATEST`); não combina com concorrência provisionada, EFS nem armazenamento efêmero acima do padrão; exige
  runtime suportado.

## Falhas de deploy mais comuns (SAM/CloudFormation)

| Sinal | Causa | Solução |
|---|---|---|
| Build falha | Dependência ausente ou runtime incompatível | Build em container; conferir manifesto de dependências |
| Criação de role IAM falha | Faltou capability de IAM no deploy | Declarar a capability no arquivo de configuração |
| Stack em rollback completo | Recurso falhou na criação | Ler os eventos do stack para achar o recurso culpado |
| Stack presa em rollback completo | Deploy anterior falhou | Excluir a stack e reimplantar |
| "Sem mudanças" | Nada novo foi buildado | Rebuildar e conferir o perfil de configuração |

## API Gateway na frente da Lambda

- **502**: resposta da Lambda fora do formato esperado (faltam código de status e corpo serializado).
- **503**: Lambda throttlada — voltar à seção de concorrência.
- **500**: exceção não tratada — logs da função.
- **CORS**: origem permitida igual ao domínio do frontend (nunca curinga em produção), `OPTIONS` respondendo os
  cabeçalhos certos, e a Lambda devolvendo cabeçalhos CORS se a integração for *proxy*.

## Anti-padrões a nomear

- Aumentar timeout/memória/concorrência "para ver se passa" sem métrica que justifique.
- Usar SNS/EventBridge só para "proteger" invocação assíncrona de throttle (ela já é enfileirada).
- Deixar DLQ crescer sem alarme, ou ESM sem tratamento de registro veneno.
- Subir limite de concorrência quando o problema é duração (a conta é RPS × duração).
