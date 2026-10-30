# Model Router — roteamento por regras para produto de IA

> Referência da skill `ai-imagem-generativa`. Complementa `roteamento-modelo-adaptativo`, que
> roteia os modelos **da própria Squad**; aqui roteamos **provedores de IA dentro de um produto**.

## 1. Por que regras e não ML

Na Fase 0 há 2–4 provedores e nenhum dado histórico. Um roteador aprendido precisa de milhares de
observações rotuladas para superar seis `if`. **Regras explícitas são auditáveis, testáveis e
depuráveis às 23h de um evento** — um modelo de roteamento não é. Reavaliar só quando houver
> 10 mil sessões registradas e mais de 4 provedores.

## 2. Sinais de entrada

| Sinal | Origem | Uso |
|---|---|---|
| `health[p]` | Disjuntor (§4) | Provedor aberto é removido da cadeia |
| `p95_ms[p]` | Janela deslizante das últimas N chamadas | Degrada quem passou do SLA |
| `fila_len` | Job queue | Fila grande → prioriza velocidade sobre qualidade |
| `custo_acumulado` | Telemetria do evento | Aciona degradação por orçamento |
| `theme.tier` | Catálogo de temas | Tema premium pode gastar mais |
| `theme.tecnica` | Catálogo de temas | Filtro/segmentação nem chegam ao router |
| `online` | Health check de rede | Offline → só local |
| `gpu_livre` | Métrica do worker local | Evita enfileirar na GPU já saturada |

Todos observáveis em tempo real. Nenhum inferido.

## 3. A função

```python
def rotear(req: TransformRequest, ctx: RouterContext) -> list[Provider]:
    cadeia: list[Provider] = []

    if ctx.custo_acumulado >= ctx.teto_evento:
        return [FILTRO_LOCAL]                      # trava dura de orçamento

    if not ctx.online:
        cadeia = [p for p in (LOCAL_GPU,) if ctx.health[p]]
        return cadeia + [FILTRO_LOCAL]

    if ctx.fila_len > ctx.limite_fila or ctx.custo_acumulado >= 0.8 * ctx.teto_evento:
        preferencia = (RAPIDO_BARATO, PADRAO)      # SLA e orçamento vencem qualidade
    elif req.theme.tier == "premium":
        preferencia = (ALTA_QUALIDADE, PADRAO, RAPIDO_BARATO)
    else:
        preferencia = (PADRAO, RAPIDO_BARATO)

    # aderência: se o último caminho bom está saudável e dentro do SLA, mantenha
    if ctx.ultimo_bom in preferencia and ctx.health[ctx.ultimo_bom] \
       and ctx.p95_ms[ctx.ultimo_bom] <= ctx.sla_ms:
        preferencia = (ctx.ultimo_bom,) + tuple(p for p in preferencia if p != ctx.ultimo_bom)

    cadeia = [p for p in preferencia if ctx.health[p] and ctx.p95_ms[p] <= ctx.sla_ms * 1.5]
    return cadeia + [FILTRO_LOCAL]                 # invariante: cadeia nunca termina vazia
```

## 4. Disjuntor por provedor

Reaproveita a taxonomia de `resiliencia-agente`:

| Estado | Entra quando | Sai quando |
|---|---|---|
| `FECHADO` | normal | — |
| `ABERTO` | 3 falhas transitórias em 60 s, **ou** 1 falha permanente de credencial | após `cooldown` (30 s, dobrando até 5 min) |
| `MEIO-ABERTO` | fim do cooldown | 1 sucesso → `FECHADO`; 1 falha → `ABERTO` com cooldown dobrado |

**Falha permanente (401/403/quota encerrada) não entra em cooldown curto** — vai para lockout e
gera alerta ao operador. Tentar para sempre um caminho que não volta sozinho é o erro clássico.

## 5. Teto de custo

```python
teto_evento_usd     = 60.0
alerta_em           = 0.8
custo_por_imagem    = medido, não estimado
```

- 0–80%: operação normal.
- 80–100%: router força a cadeia barata; painel do operador mostra aviso.
- ≥100%: só filtro local. O evento **não para** — degrada.

Registre o custo **realizado**, incluindo retries e imagens descartadas pela validação de
qualidade. O custo de tabela subestima em 10–30% na prática.

## 6. Testes obrigatórios

| Cenário | Esperado |
|---|---|
| Provedor primário devolve 429 três vezes | Disjuntor abre; próxima sessão usa o secundário; nenhum erro na UI |
| Internet cai no meio da geração | Cadeia cai para local; se não houver GPU, filtro determinístico |
| Todos os provedores fora | Filtro determinístico entrega em < 2 s |
| Custo atinge o teto | Router trava em filtro local e emite alerta |
| Fila com 10 sessões | Router escolhe o caminho rápido |
| Credencial inválida | Lockout imediato + alerta; sem retry em loop |
| Provedor volta a responder | Meio-aberto → fechado após 1 sucesso |
