# Arquitetura de referência

Leia quando for decidir store, banco, fila, canal, ou quando alguém propuser quebrar o
monólito. Ordem de decisão: **P1-Simplicidade > P2-Performance > P3-CustoBaixo**.

---

## 1. Divergência entre o briefing e o repositório (leia primeiro)

O briefing desta skill afirma que `llm-gateway` está entregue (94 testes, 100% de cobertura)
e que `rag-kit`, `channel-whatsapp` e `conversation-core` estão previstos. **No repositório
`squad-ai-core` a situação é a inversa**, verificada em 2026-08-08:

| Pacote | Briefing | Repositório |
|---|---|---|
| `rag_kit` | previsto | **entregue** — chunking, embedding, InMemory + PgVector, busca híbrida, `evaluate_retrieval` |
| `conversation_core` | previsto | **entregue** — orquestrador, guard, idempotência, sessão, métricas, `CircuitBreaker`, `ResilientCaller`, `ResilientLlm` |
| `channels.whatsapp` | previsto | **entregue** — assinatura Meta, parser de webhook, adapter |
| `template-chatbot-avancado` | previsto | **entregue** |
| `llm-gateway` | entregue | **não existe** — aparece como próximo gatilho em `docs/PLAN-EVOLUCAO.md`: *"`llm-gateway` no lugar de `ExtractiveLlm`"* |

Consequência de projeto, e o motivo de ela ser esta:

- O projeto gerado **não adivinha** a API do `llm-gateway`. Ele declara o contrato esperado
  (abaixo), isola-o em `app/llm.py`, e traz um **teste de contrato** que falha alto quando o
  pacote real estiver instalado e divergir.
- Sem o gateway, o produto **não fica sem funcionar e não usa mock**: entra em modo extrativo,
  que devolve o trecho recuperado citando a fonte. Determinístico, custo zero, auditável.
- Resiliência **não é reimplementada**: vem de `conversation_core.ResilientCaller`.

Quando o `llm-gateway` existir, o trabalho é: rodar `pytest -m gateway`, ajustar `LlmGateway`
se o contrato divergir, e ligar `LLM_GATEWAY_ATIVO=1`. Nada mais.

### Contrato esperado do `llm-gateway`

```python
from llm_gateway import Gateway

gw = Gateway.from_env()
r = gw.complete(prompt=..., system=..., tenant=..., task=...)
r.text          # str
r.model         # str  — qual modelo o roteamento escolheu
r.input_tokens  # int
r.output_tokens # int
r.cost_brl      # float
```

`task` é a intenção classificada pela triagem — é por ela que o gateway roteia para o modelo
barato ou caro. O produto **não** escolhe modelo, **não** cacheia e **não** conta teto global:
isso é do gateway. O produto mantém o teto *por conversa e por tenant* porque é regra de
negócio do cliente, não de infraestrutura.

---

## 2. Desenho

```
WhatsApp (Cloud API) ─┐
                      ├─→ canais ─→ MessageOrchestrator ─→ Agente ─→ llm-gateway
Widget web ───────────┘   (adapter)  (conversation_core)     │        (ou extrativo)
                                                             ↓
                                              rag_kit (chunking, híbrido, store)
                                                             ↓
                                              SQLite: trilha · leads · curadoria · versões
```

Um processo. Um container. Um volume por cliente. **Deploy isolado por cliente** já é o
default — não é preciso multi-tenancy no banco para tê-lo.

`tenant` continua existindo em todas as tabelas porque (a) a mesma imagem serve vários
clientes em ambiente de teste, (b) o custo por tenant precisa ser somável, e (c) migrar para
um banco compartilhado depois não exige mudar schema.

### O que veio de onde (nada reimplementado)

| Precisa de | Vem de | Não escrevemos |
|---|---|---|
| chunking, embedding, busca híbrida, store | `rag_kit` | nenhum retriever próprio |
| idempotência de webhook, sessão, métricas, guard de entrada | `conversation_core` | nenhuma dedupe própria |
| timeout, retry, circuit breaker | `conversation_core.ResilientCaller` | nenhum retry próprio |
| assinatura Meta, parser de webhook | `channels.whatsapp` | nenhum HMAC próprio |
| roteamento por custo, cache de LLM | `llm-gateway` | nenhum roteador próprio |

O que é **do produto**, e por isso mora aqui: vertical-pack, política de recusa, ancoragem de
resposta, leads, curadoria com gate humano, trilha de custo e LGPD, painel.

---

## 3. Por que stdlib (e quando parar de usar)

O projeto gerado tem **zero dependência de runtime**: `http.server` e `sqlite3`.

Para até ~1k conversas/mês por tenant — o volume informado — o gargalo é a chamada ao LLM
(centenas de ms), não o servidor web (unidades de ms). FastAPI, Postgres e Redis aqui seriam
complexidade acidental: três processos a operar, três coisas a atualizar, três formas de cair.

Nenhum módulo de negócio importa HTTP. Trocar `http_app.py` por FastAPI é reescrever **um**
arquivo.

### Gatilhos de troca — mude quando o número aparecer, não antes

| Sinal medido | Movimento | Custo de adiar |
|---|---|---|
| p95 do endpoint acima de 300 ms sem contar o LLM | FastAPI + uvicorn | baixo — troca de um arquivo |
| > 10k conversas/mês, ou base > ~50 MB | `PgVectorStore` (já existe no `rag_kit`) + Postgres | baixo — troca do store |
| Reindexação demora mais que a janela de atendimento | fila + worker | médio |
| Vários clientes no mesmo host disputando CPU | um container por tenant (já é o default) | nenhum |
| Precisa de horizontal scaling real | sessão e idempotência em Redis | alto — planeje antes |

Um sinal que **não** justifica troca: "é assim que fazem em produção". Produção de quem, com
qual volume.

---

## 4. Monólito modular — a fronteira que importa

Os módulos se chamam por função. A fronteira é o **import**, não a rede.

```
config ← db ← auditoria ← servico → agente → conhecimento → rag_kit
                 ↑          ↑         ↓
              dashboard   leads   ferramentas → PMS do cliente
                            curadoria
```

Regras que mantêm a fronteira honesta:

- `agente.py` não conhece SQL. `leads.py` não conhece HTTP. `http_app.py` não tem regra
  de negócio.
- Toda integração externa entra por uma porta: `LlmPort`, `FonteDeDisponibilidade`,
  `KnowledgePort`. Trocar o PMS do cliente é escrever um adapter, não mexer no agente.
- **Quebrar em microsserviço exige ADR** em `docs/adr/` com o número que justifica. Latência
  de rede, serialização, retry distribuído e um deploy a mais são o preço; escreva o que
  você compra com isso.

---

## 5. Custo — onde ele é medido e onde é limitado

| Camada | Responsabilidade |
|---|---|
| `llm-gateway` | escolher modelo por tarefa, cachear, limitar globalmente |
| `app/auditoria.py` | somar por conversa e por tenant a partir de `cost_brl` de cada resposta |
| `app/servico.py` | comparar com o teto **antes** de chamar o modelo; estourou → extrativo |
| `app/dashboard.py` | custo por conversa, custo por tenant, tokens |

O teto degrada, não bloqueia. Cliente que estourou continua sendo atendido — com resposta
extrativa citando fonte — e o motivo (`teto_conversa` / `teto_mes`) fica na trilha. Derrubar
o atendimento por causa de orçamento é transformar problema de custo em problema de receita.

Funil que faz o custo caber: **triagem por palavra (custo zero) → retrieval (custo zero) →
LLM só no fim, e só se houve fonte.** Pergunta sem cobertura nunca chega ao modelo.

---

## 6. Canais

Ambos entram pelo mesmo `MessageOrchestrator`, que dá idempotência, sessão e métricas.

| Canal | Cuidado que não pode faltar |
|---|---|
| WhatsApp | verificar `X-Hub-Signature-256` (`WHATSAPP_VERIFICAR_ASSINATURA=1` em produção); responder 200 rápido — a Meta reenvia, e é a idempotência que segura; janela de 24h para mensagem livre |
| Widget web | CORS restrito ao domínio do cliente antes de ir a público; sem `id` na requisição, cada turno ganha correlação própria |
| Instagram DM | mesma infra do WhatsApp Cloud API, limites próprios — adapter novo, agente inalterado |

O canal nunca contém lógica de IA. Se um `if` de negócio apareceu em `canais.py`, ele está no
lugar errado.

---

## 7. Deploy (VPS + Docker Compose)

Um `docker-compose.yml` por cliente. Volume nomeado para `var/` (banco, versões da base),
bind mount para `dados/` e `verticais/` — assim o dono do estabelecimento pode trocar um PDF
sem rebuild.

```bash
cp .env.example .env      # tenant, tetos, segredos do WhatsApp, PAINEL_TOKEN
make docker-up
```

Não exponha 8080 direto: o compose publica em `127.0.0.1`. Ponha um proxy com TLS na frente
e proteja `/painel` e `/api/*` com `PAINEL_TOKEN` (e, de preferência, com IP allowlist).

Backup é `docker run --rm -v <vol>:/var alpine tar czf - /var` — um arquivo. Restaurar é o
inverso. Não construa mais que isso antes de o cliente pedir.
