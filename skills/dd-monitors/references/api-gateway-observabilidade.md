# API Gateway — o que monitorar, o que logar e o que não dá para ver

> **Origem:** técnicas adaptadas de `awslabs/agent-plugins` (Apache-2.0), skill `aws-serverless/api-gateway`
> (referências de métricas/alarmes e de logging), reescritas com palavras próprias. Os nomes de métrica
> do Datadog abaixo vêm da integração AWS: **confirme no catálogo de métricas da sua conta** antes de
> publicar um monitor, porque a integração pode renomear ou prefixar.

## 1. Três tipos de API, três vocabulários

| Ponto | REST | HTTP | WebSocket |
|---|---|---|---|
| Erros 4xx/5xx na métrica | `4XXError` / `5XXError` | `4xx` / `5xx` | variam por rota; confira |
| Dimensão do alarme | nome da API | id da API | id da API |
| Log de execução | sim | **não** | sim |
| Rastreamento X-Ray ativo no gateway | sim | **não** | — |
| Cache | sim | não | não |

Consequência prática: um monitor escrito para REST **não dispara** em API HTTP por causa do nome da
métrica; copie o monitor e troque o nome, não presuma que "5xx" é universal. Em API HTTP o rastreamento
distribuído nasce na Lambda; correlacione pelo identificador de requisição da integração gravado no log de acesso.

## 2. Latência: `Latency` x `IntegrationLatency`

- `Latency` = do recebimento pelo gateway até a resposta; **não inclui** a rede entre cliente e gateway.
- `IntegrationLatency` = só o tempo no backend.
- A diferença entre as duas é o custo do gateway (autorizador, mapeamentos, WAF). Se `Latency` sobe e
  `IntegrationLatency` não, o problema está **no gateway** (autorizador lento, template pesado), não na função.
- Alerte o p99 de `IntegrationLatency` contra o SLA do backend e o p99 de `Latency` contra o SLO do cliente;
  os dois juntos separam "backend degradado" de "gateway degradado" já na mensagem do alerta.

## 3. Conjunto mínimo de monitores de produção

1. **Taxa de 5xx** (proporção sobre o total, não contagem absoluta): ordem de 1% é um ponto de partida,
   ajuste pelo histórico. Contagem fixa dispara à toa em madrugada de pouco tráfego.
2. **4xx por anomalia** (não por limiar fixo): pico súbito costuma ser contrato quebrado, falha de
   autenticação em massa ou abuso.
3. **p99 de `IntegrationLatency`** contra o SLA do backend.
4. **Aproximação do limite de requisições da conta**: alertar perto de 80% do teto, para pedir aumento
   *antes* de estrangular. O teto padrão é por conta e região; verifique o valor vigente, ele muda.
5. **Taxa de acerto do cache** (só REST com cache): queda indica invalidação indevida ou chave de cache errada.
6. **Composto** para reduzir ruído: 5xx **e** latência altas juntas = backend falhando (acordar plantão);
   só 4xx alto = problema do cliente (prioridade menor, canal de equipe).

Detalhes que evitam alerta ruim: trate dados ausentes como "não violando" em API de baixo tráfego; use
janela de avaliação de vários períodos (anti-flap, ver "Boas Práticas de Alertas" no hub) e sempre
defina limiar de recuperação.

## 4. Log de acesso x log de execução

| | Acesso | Execução |
|---|---|---|
| O que traz | uma linha estruturada por requisição, formato à sua escolha | passo a passo interno (mapeamento, autorizador, integração) |
| Quando usar | investigação e análise em volume | depuração pontual |
| Custo | previsível | **alto**: dezenas de eventos por requisição no nível INFO |
| Limite | gabarito de formato com teto de poucos KB | cada evento é **truncado em ~1 KB** |
| Atraso | pode chegar com minutos de atraso | idem |

Regras:

- Produção: execução em **ERROR**; INFO só por tempo curto e em estágio específico. Em volume alto, o custo
  de logs de execução INFO pode ultrapassar o da própria API e da função juntos.
- Dashboard e alerta vêm de **métricas** (quase tempo real); log de acesso é para depois do alerta.
- Defina **retenção** explicitamente (grupo de logs criado pelo IaC). O padrão do CloudWatch é "nunca
  expira". Ordem de grandeza: INFO de execução por dias; ERROR por 2–4 semanas; acesso por 1–3 meses;
  trilha de conformidade conforme a política da organização.
- **Dados sensíveis:** log de execução pode registrar corpo e cabeçalhos; não habilite o registro de corpo
  completo em API que trafega dado pessoal sem decisão do dono dos dados (LGPD).

## 5. Campos do log de acesso que mais valem a pena

Em REST, a requisição passa por fases: **WAF → autenticação → autorizador → autorização → integração**.
Cada fase expõe status, latência e erro próprios. Isso permite diagnosticar um 403 sem ligar log de execução:

- falha na fase WAF = bloqueio do firewall;
- falha na fase de autenticação = credencial malformada (ex.: assinatura inválida);
- falha na fase do autorizador = o autorizador devolveu negação;
- falha na fase de autorização com "cliente não autorizado" = credencial válida, permissão insuficiente
  (política de recurso ou IAM).

Outros campos úteis: identificador de requisição estendido (pedido de suporte exige), tipo de resposta de
erro do gateway (separa throttling, timeout de integração e falha de autorizador), latência total e de
integração, principal do autorizador (rastrear por usuário), chave de API (consumo por cliente).

**Armadilha clássica (proxy Lambda):** existem *dois* status de integração. Um é o da **plataforma Lambda**
(quase sempre 200, mesmo quando a função lança exceção) e outro é o **devolvido pelo código da função**.
Monitor que olha o primeiro nunca vê erro de aplicação; use o segundo.

## 6. Métrica a partir de log (quando a nativa não existe)

O gateway **não registra** certos eventos: 413 (corpo grande demais), excesso de 429 e 500 internos do
próprio serviço. Para ver throttling, crie uma métrica a partir de log de acesso filtrando pelo tipo de
resposta de erro "throttled". Para SLO de latência mais apertado que o p99 nativo, conte requisições com
latência acima do limite do SLO. Para consumo por cliente, inclua a chave de API no formato de log e filtre
por ela, usando dimensão de métrica.

## 7. Rastreamento e auditoria

- X-Ray ativo no gateway é **só REST**; ligue também na função para o rastro ponta a ponta. Defina regras
  de amostragem (custo) e, entre contas, configure o acesso de observabilidade entre conta de monitoramento e de origem.
- Auditoria de **quem mudou a configuração** vem da trilha de eventos de gerenciamento (CloudTrail); ela
  **não** registra as requisições em si. Não use para monitorar operação.

## 8. Diagnóstico rápido: "não vejo logs"

Ordem de suspeita: (a) REST/WebSocket — papel IAM de envio para CloudWatch ausente ou não configurado na
conta/região; (b) HTTP — política de recurso do grupo de logs não autoriza o serviço a escrever; (c) log
não habilitado no estágio ou desligado por override no método; (d) grupo de logs inexistente.

## Checklist

- [ ] Monitor usa o nome de métrica do **tipo** de API (REST ≠ HTTP).
- [ ] 5xx como taxa; 4xx por anomalia; p99 de integração e de latência total separados.
- [ ] Alerta de teto de requisições da conta (≈80%) e, se REST com cache, de acerto de cache.
- [ ] Execução em ERROR em produção; retenção explícita em todo grupo de logs.
- [ ] Formato de log de acesso com fases, tipo de erro do gateway e status de integração **do código**.
- [ ] Nenhum corpo de requisição com dado pessoal sendo logado sem decisão do dono dos dados.
- [ ] Recovery threshold, janela anti-flap e destino de notificação definidos.
