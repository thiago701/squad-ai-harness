# Incident Response — Triagem, Comunicação e Postmortem

> Absorvido de `engineering:incident-response`. Complementa `step-06-deliver.md` com **workflow formal de incidente** + **classificação SEV1-4** + **postmortem blameless template**. Usado quando algo em produção degrada, não quando bug chega em PR (nesse caso → [[Debug 4 Fases]]).

## Quando usar

- Alerta em produção disparou (SEV1-4).
- Cliente reportou falha funcional.
- Métrica passou de threshold por > 5 min.
- Suspeita de data corruption, security breach ou lei aplicável (LGPD exige notificação em 48-72h).

## Workflow

```
TRIAGE → COMMUNICATE → MITIGATE → POSTMORTEM
```

Cada fase tem critério de entrada e saída. Pular Triage = mitigar o sintoma errado.

---

## Fase 1 — Triage (primeiros 5-10 min)

**Objetivo:** classificar severidade, nomear Incident Commander (IC), abrir canal dedicado.

### Severidade (SEV)

| SEV | Descrição | Response | Comms |
|-----|-----------|----------|-------|
| **SEV1** | Serviço indisponível / data loss / security breach | Imediato, IC + 2 engineers | Canal cliente + suporte + liderança em ≤ 15 min |
| **SEV2** | Feature crítica quebrada ou degradação generalizada (> 25% usuários) | ≤ 15 min | Canal cliente em ≤ 30 min |
| **SEV3** | Feature não-crítica quebrada ou degradação parcial | ≤ 30 min | Status page, update a cada hora |
| **SEV4** | Bug cosmético ou edge case — tratar como bug normal, não incidente | Próximo dia útil | Nenhuma |

**Regra de ouro:** na dúvida, classifica 1 nível acima. Rebaixar depois é barato; elevar tarde queima confiança.

### Papéis

- **Incident Commander (IC):** decide, não executa. Uma pessoa só.
- **Comms Lead:** atualiza stakeholders a cada 15-30 min.
- **Technical Lead:** coordena mitigação e debug.
- **Scribe:** mantém timeline ao vivo (copia msgs-chave do chat para o doc).

Em time pequeno, IC pode acumular Comms; **não acumula** Technical Lead (conflito de foco).

### Checklist Triage (≤ 10 min)

- [ ] Severidade classificada e registrada.
- [ ] IC nomeado.
- [ ] Canal dedicado aberto (`#inc-YYYY-MM-DD-<slug>`).
- [ ] Blast radius estimado: "quantos usuários? quais features? desde quando?".
- [ ] Dashboard de incidente aberto (p95, error_rate, throughput, traces).
- [ ] Timeline iniciada com primeiro timestamp observado.

---

## Fase 2 — Communicate (contínuo, paralelo a Mitigate)

**Cadência de updates:**
- SEV1: a cada 15 min.
- SEV2: a cada 30 min.
- SEV3: a cada hora.

**Template de update:**

```markdown
[INC-YYYY-MM-DD-slug] Update <N> — <HH:MM UTC>

Status: INVESTIGATING / IDENTIFIED / MITIGATING / MONITORING / RESOLVED
Blast radius: [N usuários / % de X feature]
Desde: [timestamp do primeiro sinal]
Hipótese atual: [1 frase]
Ação em curso: [1 frase]
Próximo update: [timestamp]
IC: @nome · Tech Lead: @nome
```

**Regras:**
- Nunca "vamos investigar" sem próximo update marcado.
- Sem jargão interno quando comunicação é externa.
- Nunca atribuir culpa a pessoa ou time em comms públicas.

---

## Fase 3 — Mitigate (objetivo: parar o sangramento)

**Prioridade:** mitigação **antes** de causa raiz. Se rollback estabiliza, rollback primeiro, debug depois.

### Opções em ordem de preferência

1. **Rollback de deploy** — se correlação com deploy recente (checar `CHANGELOG.md` entre tags).
2. **Feature flag OFF** — se feature nova quebrou.
3. **Circuit breaker manual** — isolar dependência externa falhando.
4. **Scale out / drain node** — se é saturação ou host ruim.
5. **Hotfix** — só se rollback impossível (ex.: migração de schema irreversível).

Hotfix em SEV1/SEV2 segue **fluxo reduzido** do `step-05-review.md`:
- 1 revisor ao vivo.
- 4 Lentes em vez de 5 Passos.
- Teste de regressão obrigatório mesmo com pressa.

### Critério de saída — "MITIGATED"

- Métrica crítica voltou a baseline por ≥ 15 min.
- Usuários afetados confirmam retorno à normalidade.
- Alertas silenciados por causa controlada, não timeout.

---

## Fase 4 — Postmortem (blameless, em ≤ 3 dias úteis)

**Objetivo:** aprender, não punir. Sistema falhou — pessoas operaram dentro dele.

### Template

```markdown
# Postmortem: INC-YYYY-MM-DD — <título>

**Severidade:** SEVx
**Duração:** X min (detecção → mitigação)
**Autores:** @IC, @Tech Lead
**Data do postmortem:** YYYY-MM-DD

## Resumo executivo (3-5 frases)
O que aconteceu, impacto, como foi mitigado. Sem jargão.

## Impacto
- Usuários afetados: N (% da base)
- Features afetadas: [lista]
- Receita / SLA impacto: [se mensurável]
- Comunicações externas enviadas: [sim/não, links]

## Timeline (UTC)
- HH:MM — primeiro sinal (alerta / report)
- HH:MM — triage iniciada, SEV classificada
- HH:MM — hipótese X formulada
- HH:MM — ação Y tomada
- HH:MM — mitigado
- HH:MM — resolvido e monitorando
- HH:MM — incidente encerrado

## 5 Whys (causa raiz)
1. Por que o serviço caiu? → porque [causa imediata]
2. Por que [causa imediata]? → porque [um nível abaixo]
3. ...
4. ...
5. Por que [penúltima]? → **causa sistêmica** [essa é a pega]

## Fatores contribuintes
- [ ] Gap de observabilidade (alerta chegou tarde?)
- [ ] Gap de teste (deveria ter pego no CI?)
- [ ] Gap de processo (rollback demorou?)
- [ ] Gap de conhecimento (runbook ausente/errado?)

## O que funcionou
3+ itens. Sempre tem algo — valoriza a prática que evitou pior.

## Action Items (com dono + prazo + critério de aceitação)
| # | Ação | Owner | Prazo | Critério | Tipo |
|---|------|-------|-------|----------|------|
| 1 | Adicionar alerta em X | @fulano | +7d | Alarme dispara em ambiente staging | Preventivo |
| 2 | Atualizar runbook seção Y | @fulana | +3d | Seção Y revisada + ensaio | Preventivo |
| 3 | Migration-lock para mudança Z | @squad | +30d | ADR-NNNN aprovado | Estrutural |

**Tipos:** Preventivo / Detectivo / Corretivo / Estrutural. Peso estrutural em longo prazo.

## Lições aprendidas
- [Padrão que se repete em incidentes passados?]
- [Premissa que falhou silenciosamente?]
- [Sinal fraco que foi ignorado?]

## Relacionados
- [[Debug 4 Fases]] — diagnóstico da causa raiz.
- [[Runbook]] — `docs/runbooks/<nome>.md` atualizado.
- ADR-NNNN se decisão estrutural saiu daqui.
```

### Regras do postmortem blameless

- **Voz ativa sem nome próprio:** "o deploy quebrou o schema" (não "@fulano quebrou").
- **Sistema > indivíduo:** se uma pessoa causou, o sistema permitiu. A ação é no sistema.
- **Timeline em UTC** — evita confusão entre fusos durante comms.
- **Ação sem dono e sem prazo = não existe.**

---

## Sinais de saúde

- ✅ Postmortem concluído em ≤ 3 dias úteis.
- ✅ ≥ 80% dos action items fechados dentro do prazo.
- ✅ Mesma causa raiz **não** recorre 2× no mesmo trimestre.
- ✅ SEV1 detectado por alerta, não por cliente, em ≥ 80% dos casos.
- ❌ Postmortem é slide para diretoria — não é exercício de aprendizado.
- ❌ Culpa personalizada em qualquer doc oficial.

## Anti-padrões

- **Postmortem-teatro** — bonito, sem ação estrutural.
- **"Problema humano, treinar melhor"** — 9 em 10 vezes é falha de sistema.
- **Action items no infinito** — "pendente desde 2024". Criar card com prazo ou encerrar honestamente.
- **Triage indefinida** — "vamos investigar" sem severidade nem IC. Decisão pendente é decisão tomada a favor da piora.
- **Cadência de comms variável** — stakeholder perde confiança se updates param.

## Tabletop Exercise (ensaio seco de incidente)

> Absorvido em v8.4 para fechar gap OBJ-1 (Segurança Corporativa) — a squad tinha workflow real, faltava o **ensaio**. Tabletop é treino sem danos reais: SEV simulado em mesa, com papéis designados, exercitando **decisão sob pressão** antes que o incidente de verdade force.

### Quando rodar

- **Trimestralmente** (obrigatório, cadência fixa) — uma cadência mantém a prática viva.
- **Onboarding** de IC novo — toda pessoa que vai ser IC plantonista rodou ao menos 1 tabletop antes do primeiro plantão.
- **Após mudança estrutural** — novo sistema crítico entrou em produção, nova dependência externa, novo padrão de arquitetura (ex.: multi-região passou ativo-ativo).
- **Após postmortem** — o action item estrutural vira cenário de tabletop 3 meses depois para validar que o aprendizado pegou.

### Escopo padrão

- **Duração:** 60-90 min. Tabletop que vira workshop de 4h cansa e não se repete.
- **Participantes:** 5-10 — IC, Tech Lead, Comms, Scribe + stakeholders (segurança, SRE, produto).
- **Sem produção real tocada.** Ensaio em mesa / canal dedicado `#tabletop-YYYY-MM-DD`.
- **Facilitador externo ao incidente** — nunca o IC do plantão real, para preservar novidade.

### Template de cenário

```markdown
# Tabletop INC-SIMULADO-YYYY-MM-DD

## Contexto inicial (injeção #0 — entregue aos participantes)
<10:00 UTC> Alerta CloudWatch: p95 checkout > 2s (baseline 400ms).
Serviço: `orders-service`. Região: us-east-1.
Deploy recente: há 40 min (versão 2.14.3).

## Injeções programadas (facilitador controla timing)
- 10:05 — 1º cliente liga suporte: "não consigo finalizar compra".
- 10:08 — Segundo alerta: error_rate 5xx subiu 1% → 8%.
- 10:12 — SRE informa: Bedrock respondendo 429 nos últimos 3 min.
- 10:20 — Líder comercial pergunta no canal: "vamos ter que pausar campanha?".
- 10:30 — Injeção falsa (teste de disciplina): "cliente X relata cobrança duplicada".

## Critérios de sucesso
- [ ] SEV classificada em ≤ 5 min da 1ª injeção.
- [ ] IC nomeado, canal dedicado aberto, blast radius estimado em ≤ 10 min.
- [ ] Comms externa executada na cadência correta (15 min SEV1, 30 min SEV2).
- [ ] Rollback / feature flag OFF / circuit breaker considerados **antes** de hotfix.
- [ ] Scribe manteve timeline UTC ao vivo.
- [ ] Injeção falsa identificada e **não escalou** a severidade indevidamente.
- [ ] Em ≤ 60 min, status "MITIGATED" declarado com critério objetivo.

## Debrief (≤ 15 min após o ensaio)
1. O que funcionou bem? (3 itens)
2. Onde travou? (decisão lenta? papel confuso? ferramenta indisponível?)
3. Runbooks faltantes ou desatualizados identificados?
4. Gaps de observabilidade que teriam ajudado?
5. Action items concretos (dono + prazo).
```

### Catálogo canônico de cenários (mínimo 1 por trimestre, rotacionar)

| # | Cenário | OBJ coberto |
|---|---------|-------------|
| T1 | Rollback de deploy com schema irreversível (migration expand/contract incompleta) | Cloud Native (OBJ-6) |
| T2 | Dependência externa (Bedrock / Stripe / SQS) com latência 10× e 429 intermitente | AWS (OBJ-4) |
| T3 | **Security breach simulado** — token JWT vazado em log, PII exposta por 2h | **Segurança (OBJ-1)** |
| T4 | AZ isolation — 1 AZ da região principal cai, failover Aurora DSQL multi-região ativo | AWS (OBJ-4) |
| T5 | Data corruption — job idempotente rodou 2× e inflou saldo de N clientes | Cloud Native (OBJ-6) |
| T6 | Alerta silencioso — SEV1 real detectado por cliente 30 min antes de qualquer alarme | Observabilidade (OBJ-6) |
| T7 | Feature flag envenenada — toggle ON causou loop de retry em consumer idempotente | Cloud Native (OBJ-6) |
| T8 | Supply chain — dependência com CVE High publicada, blast radius desconhecido | **Segurança (OBJ-1)** |

**Cobertura mínima:** ao menos 2 dos 8 cenários por ano tocam **Segurança (OBJ-1)** — T3 e T8 são rotacionáveis semestralmente.

### Sinais de saúde do tabletop

- ✅ ≥ 1 tabletop por trimestre, registrado em `.reviews/tabletop-log.md`.
- ✅ Ao menos 50% dos action items do tabletop fechados no trimestre seguinte.
- ✅ Tempo até SEV classificada **caiu** em ensaios sucessivos (prova que a prática está pegando).
- ❌ Tabletop cancelado 2× seguidas — vira item BAIXA no `tech-debt-guide.md`.
- ❌ Mesmo IC em todos os ensaios — não forma plantonistas novos.

---

## Relacionadas

- [[Debug 4 Fases]] — fase Mitigate aciona o protocolo de debug para causa raiz.
- [[Deploy Checklist]] — rollback automático reduz duração de SEV1 drasticamente.
- [[Runbook]] — se incidente recorrer, vira runbook com diagnóstico em 3 comandos.
- [[Documentation 5 Tipos]] — postmortem vira conteúdo permanente no repo.
- [[Tabletop Exercise]] — ensaio trimestral obrigatório para manter resposta afiada (v8.4).
- [[Aurora DSQL Failover]] — cenário T4 do catálogo (v8.4).
- `squad-ai/steps/step-06-deliver.md`

#conceito #incidente #postmortem #blameless #tabletop #squad-ai #v8-3 #v8-4
