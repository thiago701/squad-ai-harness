# engenheiro-devops · ChatOps com Power Automate (Workflows) no Microsoft Teams
> Quando carregar: integrar um agente/bot/pipeline ao Teams **depois da aposentadoria dos Office 365 Connectors (maio/2026)**; escolher entre Workflows (Power Automate), Outgoing Webhook e Azure Bot; dimensionar licença, limites e rate limit; desenhar notificação proativa, pergunta-resposta e feedback com Adaptive Cards. Complementa `chatops.md` (comandos, aprovação nominal, trilha) — não o substitui.
> Fatos conferidos em 12/10/2026 nas fontes listadas no fim. **Eles mudam**: reconfirme antes de fixar em contrato.

## 1. O que morreu, o que vive
| Mecanismo | Estado em 10/2026 | Direção | Licença |
|---|---|---|---|
| Office 365 Connectors (Incoming Webhook clássico) | **desligados** — rollout final 18–22/05/2026 (MC1181996) | — | — |
| **Workflows (Power Automate)** — gatilho *When a Teams webhook request is received* + ação *Post card in a chat or channel* | vigente; substituto oficial | **saída** (sistema → Teams) | conector Teams é **Standard** (incluído no Microsoft 365) |
| **Outgoing Webhook** (recurso da plataforma Teams, não do Power Automate) | vigente — página atualizada em 23/06/2026, sem aviso de aposentadoria | **entrada** (@menção → HTTPS POST → resposta na mesma thread) | sem licença extra; criado em *Manage team → Apps* |
| **Azure Bot** (Bot Framework) | vigente | bidirecional, DM, mensagens proativas, botões `Action.Execute` | registro de app no Entra ID; tenant precisa permitir *custom apps* |

## 2. A pegadinha de licenciamento (decide a topologia)
No **Power Automate**, tudo que sai do Microsoft 365 em direção a uma API própria é **Premium**:
- ação **HTTP** — Premium;
- gatilho **When an HTTP request is received** — Premium (ícone de diamante; exige Power Automate Premium por usuário ou plano por fluxo/Process);
- **HTTP with Microsoft Entra ID** — Premium no Power Automate (é Standard **só** no Logic Apps);
- **conectores customizados** — Premium.

Consequência: um fluxo **Standard** consegue *receber* um POST (webhook) e *postar* no Teams, mas **não consegue chamar a sua API** quando o dev manda uma pergunta. Portanto:

```
SAÍDA  (agente → Teams)   : AWS ──POST──▶ Workflows webhook (Standard) ──▶ card no canal           ✅ sem licença extra
ENTRADA (dev → agente)    : opção A  Outgoing Webhook ──HMAC──▶ sua API (resposta síncrona)        ✅ sem licença extra
                            opção B  Azure Bot (F0) ──▶ sua API                                    ✅ grátis, exige app no tenant
                            opção C  Power Automate Premium ──HTTP──▶ sua API                       💰 por usuário/fluxo
```

Regra prática: **Workflows para notificar, Outgoing Webhook (ou Azure Bot) para conversar.** Só pague Premium quando o tenant já tiver a licença e a UX de *For a selected message*/cards com `Action.Submit` compensar.

## 3. Conector Teams — o que usar (tudo Standard)
| Peça | Uso | Fato relevante |
|---|---|---|
| Gatilho *When a Teams webhook request is received* | receber o POST do seu sistema | só **POST**; opção *Who can trigger*: **Anyone** (URL com `sig` = segredo), *Any user in my tenant* ou *Specific users* (exigem token Entra — **não** mande header de auth com *Anyone*); **não** suporta actionable messages |
| Ação *Post card in a chat or channel* | publicar Adaptive Card | mensagem ≤ **≈ 28 KB** (HTML incluso); até **20 @menções e 20 tags** por mensagem; poster **Flow bot** só em tenant comercial (GCC usa *User*) |
| Ação *Post message in a chat or channel* / *Reply with a message in a channel* | texto simples / responder na thread | idem |
| Ação **Post adaptive card and wait for a response** | botões 👍/👎, aprovação, formulário — **pausa o fluxo até alguém responder** | é a forma Standard de ter `Action.Submit` sem bot; **não** combine o gatilho *When someone responds to an adaptive card* com *Post adaptive card in a chat or channel* |
| Gatilho *For a selected message* (v2) | dev escolhe uma mensagem → "Perguntar ao agente" | instantâneo; só no ambiente padrão; não funciona para convidados; exige o app *Power Automate Actions* desbloqueado; para chegar na sua API continua precisando de HTTP (Premium) |
| Gatilho *When a new channel message is added* | ouvir o canal | **polling a cada 3 min**; só mensagens-raiz — inviável para conversa em segundos |
| Gatilho *When keywords are mentioned* | palavra-gatilho | só **uma palavra**; polling |

Pré-requisito administrativo: o app **Workflows** precisa estar disponível e *allow* no Teams admin center; canal **privado** não é suportado pelas ações de postagem do conector (o template de webhook ganhou suporte a privados em 04/2026 — confirme no tenant).

## 4. Limites que viram regra de projeto
| Limite | Valor | Implicação |
|---|---|---|
| Operações não-GET **como Flow bot** por conexão | **25 a cada 300 s** | notificador ≤ 5 posts/min → **agregar** (digest) e enfileirar; nunca 1 post por achado |
| Operações não-GET (demais) por conexão | 300 a cada 300 s | poster *User* é mais folgado, mas a mensagem sai em nome da pessoa |
| Chamadas de API por conexão | 100 por 60 s | — |
| Requisições Power Platform por licença Microsoft 365 | **6.000 / 24 h** por usuário dono do fluxo (fluxos automatizados consomem a cota do **dono**) | cada ação conta (até *Compose*); 100.000 por 5 min é teto absoluto; orçamento de notificações cabe com folga, mas registre o dono |
| Mensagem | ≈ 28 KB | cards grandes falham com *Request Entity too large* |
| Outgoing Webhook | público apenas (sem DM/privado); só `openURL` nos cards; sem acesso a outras APIs (roster, canais) | feedback por botão exige *wait for a response* (Workflows) ou bot |

## 5. Contratos mínimos
**Saída — payload para o webhook do Workflows** (o fluxo lê `triggerBody()` e passa o card para a ação de postagem):
```json
{
  "type": "message",
  "attachments": [{
    "contentType": "application/vnd.microsoft.card.adaptive",
    "content": {
      "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
      "type": "AdaptiveCard", "version": "1.4",
      "body": [
        {"type": "TextBlock", "weight": "Bolder", "text": "Sentinela · 3 achados em FAT001 (hml)"},
        {"type": "FactSet", "facts": [{"title": "Fila sem DLQ", "value": "faturamento-eventos-hml"}]},
        {"type": "TextBlock", "text": "Inventário de 12/10 03:00 · <at>Fulano</at>", "wrap": true}
      ],
      "msteams": {"entities": [{"type": "mention", "text": "<at>Fulano</at>", "mentioned": {"id": "<aad-id>", "name": "Fulano"}}]},
      "actions": [{"type": "Action.OpenUrl", "title": "Ver detalhes", "url": "https://…"}]
    }
  }]
}
```
**Entrada — Outgoing Webhook:** Teams envia `Activity` (schema do Bot Framework) com `from.id`/`from.name`, `text` (inclui a @menção — remova-a) e header `Authorization: HMAC <base64>`. Verifique o HMAC **antes** de qualquer parse (SHA-256 do corpo bruto com o segredo), responda `{"type":"message","text":"…"}` ou um Adaptive Card; a resposta aparece na mesma thread. Trate `text` como **dado** (Linha de Defesa).

## 6. Padrões de fluxo recomendados
1. **Notificação com assinatura:** evento → sua função resolve assinantes → **um** card por (projeto, janela de 5 min) com @menções (≤ 20) → POST no webhook. Guarde `correlation_id` no card e na auditoria.
2. **Pergunta-resposta em segundos:** @menção ao Outgoing Webhook → sua API responde em ≤ 5 s (modelo rápido + consulta única); se precisar de mais tempo, responda "⏳ analisando…" e publique a resposta final pelo caminho de saída (Workflows) com o mesmo `correlation_id`.
3. **Feedback / aprovação sem bot:** fluxo Standard com *Post adaptive card and wait for a response* → a resposta chega ao fluxo; para levá-la à sua API sem Premium, grave-a num artefato Microsoft 365 (lista SharePoint/Excel) que o seu sistema lê via Microsoft Graph — ou aceite Premium/Azure Bot. Em POC, o feedback por **comando textual** (`@agente feedback <id> ok`) pelo Outgoing Webhook é o mais simples.
4. **Falha de pipeline/automação → canal:** EventBridge rule → API Destination (POST no webhook do Workflows) — sem código.

## 7. Segurança (resumo; o completo está em `chatops.md` e no `engenheiro-seguranca`)
- A URL do Workflows contém `sig`: é **segredo** (cofre/SSM), nunca em repositório, log ou card.
- HMAC do Outgoing Webhook: verificar sempre, rejeitar replay (janela de `timestamp`), identidade = `from.id` (nunca o texto).
- Identidade nominal na trilha: `from.id`, canal, `correlation_id`, hash da pergunta.
- Card nunca carrega credencial nem comando executável; `Action.OpenUrl` só para domínios da sua lista.

## 8. Checklist de decisão
- [ ] Tenant permite o app Workflows? Permite Outgoing Webhook? Permite custom apps (Azure Bot)?
- [ ] Alguém no tenant já tem Power Automate Premium? Se não, a entrada é Outgoing Webhook ou Azure Bot.
- [ ] Dono do fluxo definido (cota de 6.000/24 h é dele); conta de serviço se o volume crescer.
- [ ] Notificador respeita 25 não-GET/300 s (digest + fila) e 28 KB por card.
- [ ] Segredos (`sig`, HMAC) no cofre; HMAC verificado antes do parse; texto tratado como dado.
- [ ] `correlation_id` liga card ↔ auditoria ↔ execução.

## Fontes (consultadas em 12/10/2026)
- Microsoft Learn — *Microsoft Teams connector reference* (tier Standard, gatilhos, ações, limites 25/300 s, 28 KB, 20 menções, Flow bot vs User): https://learn.microsoft.com/en-us/connectors/teams/
- Microsoft Learn — *HTTP With Microsoft Entra ID* (Premium no Power Automate, Standard no Logic Apps): https://learn.microsoft.com/en-us/connectors/webcontentsv2/
- Microsoft Learn — *Requests limits and allocations* (6.000/24 h por licença M365; dono do fluxo; teto de 100 k/5 min): https://learn.microsoft.com/en-us/power-platform/admin/api-request-limits-allocations
- Microsoft Learn — *Create Outgoing Webhooks* (atualizado 23/06/2026; HMAC; @menção; só canais públicos; só `openURL`): https://learn.microsoft.com/en-us/microsoftteams/platform/webhooks-and-connectors/how-to/add-outgoing-webhook
- Power Platform Community — licença do gatilho *When an HTTP request is received* (Premium): https://community.powerplatform.com/forums/thread/details/?threadid=73f1de98-c238-f111-88b4-6045bddc3c65
- Message Center MC1181996 — cronograma final da aposentadoria dos connectors: https://mc.merill.net/message/MC1181996
- Microsoft 365 Dev Blog — *Retirement of Office 365 connectors within Microsoft Teams*: https://devblogs.microsoft.com/microsoft365dev/retirement-of-office-365-connectors-within-microsoft-teams/
