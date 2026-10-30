# Referência — Tempo real com WebSocket (cliente resiliente + API WebSocket do API Gateway)

> Parte da skill `especialista-frontend`. Carregue quando a interface precisar de **atualização push** (chat, painel ao vivo, notificações, progresso de job) e o backend for ou puder ser **API WebSocket do API Gateway** com Lambda. Decisão de protocolo (REST vs HTTP vs WebSocket) fica em `../../arquiteto-cloud-aws/references/auth-e-api.md`; segurança de API em `../../engenheiro-seguranca/references/api-gateway-seguranca.md`.
>
> Procedência e licença: ver `docs/ATTRIBUTIONS.md` (colheita de 16/10/2026). Texto reescrito; limites e preços mudam — confirme na página oficial de quotas do API Gateway antes de fixar números.

## 1. Quando WebSocket (e quando não)

- Use quando o **servidor** precisa iniciar a mensagem com baixa latência. Se o cliente só consulta de tempos em tempos, polling curto ou SSE costuma ser mais simples e barato (P1 > P2 > P3).
- Cada conexão aberta cobra por minuto e cada mensagem enviada ou recebida conta — inclusive as do canal de retorno do servidor para o cliente. Muitos clientes ociosos conectados = custo contínuo; avalie antes.
- O contrato é por **mensagem com ação**: o backend roteia por um campo do corpo (por exemplo `action`). Defina e versione esse envelope como um contrato de API (`engenheiro-especificacao`).

## 2. Ciclo de vida da conexão — o que o front precisa assumir

| Fato do serviço | Consequência no cliente |
|---|---|
| Conexão cai por **duração máxima (ordem de 2 h)**, mesmo com atividade | Reconexão transparente é fluxo normal, não erro |
| **Ociosidade (ordem de 10 min)** fecha a conexão sem aviso claro | Enviar heartbeat bem abaixo do limite (por exemplo a cada 5–9 min) numa rota leve |
| Desconexão no servidor é **melhor esforço** | Nunca dependa do evento de desconexão para lógica crítica; o cliente detecta falha no próximo envio |
| Autorização acontece **só no momento da conexão** | Mensagens seguintes não são reautorizadas: a política cacheada do autorizador deve cobrir tudo que a sessão fará, e ações sensíveis devem revalidar no backend |
| Quadro e payload têm teto pequeno (dezenas e poucas centenas de KB) | Mensagem grande vai por upload/URL pré-assinada; o socket só carrega o aviso |

### Máquina de estados mínima do cliente (Angular: serviço com Signals/RxJS)

`conectando → aberto → (fechado | erro) → aguardando-backoff → conectando`.

- **Reconexão com backoff exponencial e jitter**, com teto e contador; pare e mostre estado "offline" depois de N falhas, com ação manual de tentar de novo.
- Distinga fechamento **intencional** (logout, rota destruída) de acidental: o primeiro cancela o laço de reconexão.
- **Ao reconectar**: reautentique (token novo), reinscreva-se nos tópicos/salas e **ressincronize o estado** (busque por REST o que perdeu enquanto estava fora, ou peça replay a partir do último id visto). Mensagens podem ser perdidas ou duplicadas — trate com id de mensagem e deduplicação idempotente.
- Exponha o estado de conexão como Signal (`conectado`, `reconectando`, `offline`) para a UI mostrar banner e desabilitar ações que exigem o canal.
- Fila de saída em memória com limite durante a reconexão; descarte ou avise em vez de crescer sem teto.
- Encerre o socket e os timers no `DestroyRef`/`ngOnDestroy` — vazamento de conexões é bug comum e custa dinheiro.

## 3. Identidade e sessão (lado servidor que o front precisa entender)

- O servidor guarda o par **usuário ↔ connectionId** numa tabela (DynamoDB) no momento da conexão. O `connectionId` muda a cada reconexão; o usuário permanece. Para enviar a "um usuário", consulta-se o id atual por índice secundário no usuário.
- Limpeza de conexões velhas: TTL na tabela e remoção ao receber o erro de "conexão inexistente" (GoneException) no envio.
- Usuário anônimo: o cliente gera um id aleatório e o envia pelo cabeçalho de subprotocolo; o backend **precisa devolver o mesmo subprotocolo** na resposta, senão muitos navegadores recusam a conexão.
- Nunca coloque token em query string se houver alternativa: URLs acabam em log. Prefira subprotocolo/primeira mensagem autenticada, e trate o que o cliente envia como entrada não confiável (validação de esquema no backend).

## 4. Backend mínimo (visão geral, para alinhar contrato com quem implementa)

- Rotas especiais de conexão, desconexão e padrão (fallback), mais rotas customizadas pelo campo de seleção. Cada rota → uma função Lambda integrada por proxy, com permissão de invocação específica por rota.
- Envio ao cliente: a Lambda chama a API de gerenciamento de conexões (postar/consultar/derrubar conexão) com permissão IAM dedicada de gerenciar conexões. Para implementação Java, ver `../../aws-lambda-java25-aot/SKILL.md` e `references/api-gateway.md` desta família.
- **Throttling por rota** (burst e rate) protege o backend contra enxurrada de mensagens de um cliente; não pode passar do limite da conta.
- Multirregião: o `connectionId` pertence à região onde nasceu; mensagens precisam sair por ela. Estado de conexão em tabela global, roteamento de entrada por latência/geo, propagação entre regiões por evento. Só vale o custo com requisito real de disponibilidade.

## 5. Checklist de revisão (front + contrato)

- [ ] Existe reconexão com backoff + jitter, parada após falhas e estado visível ao usuário?
- [ ] Heartbeat configurado abaixo do limite de ociosidade; reconexão planejada para o limite de duração?
- [ ] Reconexão reautentica, reinscreve e ressincroniza o estado perdido?
- [ ] Mensagens têm id, versão de contrato e deduplicação no cliente?
- [ ] Ações sensíveis são revalidadas no servidor (autorização só na conexão)?
- [ ] Sem token em URL; entrada do cliente validada no backend (`engenheiro-seguranca`)?
- [ ] Socket e timers encerrados ao destruir o componente/serviço?
- [ ] Teste do cliente com socket simulado cobrindo queda, reconexão e mensagem duplicada (`especialista-qualidade`)?
- [ ] Custo estimado (conexões × minutos + mensagens) e alternativa mais simples (polling/SSE) descartada com motivo?
