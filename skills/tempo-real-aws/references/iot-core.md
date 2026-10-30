# AWS IoT Core — capacidades, limites e padrões

> Parte da skill `tempo-real-aws`. Hub: `../SKILL.md`. Fatos com fonte em
> `../../arquiteto-cloud-aws/references/fatos-verificados-aws.md` §4 (consulta 2026-10-08).

## 1. Identidade e provisionamento

| Opção | Quando |
|---|---|
| Certificado X.509 por dispositivo (registrado previamente) | frota pequena, fábrica controla a gravação |
| Fleet provisioning por claim | dispositivo sai de fábrica com certificado de claim e troca por um definitivo |
| Fleet provisioning por usuário confiável | instalador autenticado gera claim temporário (expira em 5 min) |
| Just-in-Time Provisioning (JITP) | CA própria registrada com auto-registro + template |

Chave privada **nunca** sai do dispositivo nem entra no repositório; exemplos usam placeholders.

## 2. Política por thing (privilégio mínimo)

```json
{"Effect": "Allow", "Action": "iot:Connect",
 "Resource": "arn:aws:iot:<região>:<conta>:client/${iot:Connection.Thing.ThingName}",
 "Condition": {"Bool": {"iot:Connection.Thing.IsAttached": "true"}}}
{"Effect": "Allow", "Action": "iot:Publish",
 "Resource": "arn:aws:iot:<região>:<conta>:topic/dt/<app>/${iot:Connection.Thing.Attributes[tenantId]}/${iot:Connection.Thing.ThingName}/alarme"}
```

- Variáveis de thing exigem client ID = thing name e só valem em MQTT/MQTT-WSS.
- Em CloudFormation dentro de `Fn::Sub`, escreva `${!iot:...}` para a variável literal.
- Client ID duplicado derruba a conexão anterior — dois processos com o mesmo id ficam se derrubando.

## 3. Tópicos

- `dt/<app>/<contexto>/<thing>/<tipo>` para dados; `cmd/<app>/<contexto>/<destino>/<tipo>` para comandos.
- Sem `/` inicial, minúsculas, números e hífen; até 7 barras; thing name perto do fim.
- `#` só em regras; dispositivo usa `+` no máximo. Tópicos `$aws/...` são reservados.

## 4. Mensagens

- QoS 0 e 1 (**QoS 2 não suportado**); o broker **não garante ordem**; QoS 1 pode duplicar.
- Payload até 128 KB. Retained: 1 por tópico, assinatura com wildcard não recebe.
- Sessão persistente para receber o que chegou offline (MQTT 5: até 7 dias; padrão 1 h).
- **Idempotência:** o dispositivo gera um id por ocorrência (ex.: `alarmeId`); o backend deriva a
  chave (UUID v5 de tenant+thing+id) — todas as cópias convergem para o mesmo efeito.

## 5. Rules Engine

- SQL sobre o tópico (`topic(n)` extrai níveis; `WHERE` filtra) → até 10 ações.
- Ações: Lambda, DynamoDB(v2), SQS, Kinesis, Firehose, Step Functions, S3, SNS, republish, HTTP…
  **Não há ação direta para EventBridge** — passe por SQS/Lambda.
- Preferir SQS como ação: amortece picos e dá retry/DLQ com `ReportBatchItemFailures`. A ação
  `stepFunctions` com nome aleatório criaria execução duplicada para mensagens duplicadas.
- **Error action** obrigatória (fila de erro + alarme): sem ela, a falha só aparece em log.

## 6. Device Shadow

- Use quando há **estado** a sincronizar com dispositivo intermitente (ex.: "modo manutenção").
- `desired` (nuvem) × `reported` (dispositivo) → `delta`; versão incrementa a cada update; update com
  versão antiga é rejeitado; deltas podem chegar **fora de ordem** → descartar versão menor.
- Documento ≤ 8 KB; named shadows por assunto (ex.: `manutencao`); tópicos `$aws/things/<thing>/shadow/...`.

## 7. Presença

Lifecycle events (`$aws/events/presence/connected|disconnected/<clientId>`) chegam fora de ordem e
duplicados — use `versionNumber` e nunca trate "desconectado" como certeza imediata.

## 8. Testes

| Cenário | Como |
|---|---|
| Dispositivo reenvia ao reconectar | `DispositivoIntermitenteTest.reenvioAoReconectar` |
| Payload/tópico fora do contrato | `DispositivoIntermitenteTest.thingInvalido`; contrato `alarme-dispositivo.v1` |
| SQL da regra × contrato | `tests/test_aws_referencia_contratos.py::test_sql_da_regra_iot_produz_os_campos_do_contrato_do_alarme` |
| Política sem wildcard amplo | revisão + cfn-lint; `[GAP]` simulação de política exige conta (IoT policy simulator) |
