# Protocolo Noturno do Batman — marcos, allow-list, orçamento e handoff

> Extensão do `scheduler/nightly-workflow.md` com a janela ampliada (19h00→08h00),
> poderes do modo Batman e o journal próprio. Autonomia: **N2 dentro da allow-list**;
> **N3 sempre gated**. `governance/autonomy-policy.md` prevalece sobre este documento.

## 1. Janela e fuso

- **Padrão:** 19h00 → 08h00 (fuso local). O usuário pode encurtar/alongar: "Ative o modo
  batman até 9h00" → fim 09h00.
- **Horário de fim é lei:** no minuto do fim, o turno conclui a tarefa atômica em curso,
  grava os artefatos e encerra. Nenhuma tarefa nova começa após o fim.
- Início: se o usuário ativar dentro da janela, começa imediato; se ativar fora, começa
  imediato e segue até o próximo 08h00 (ou horário informado).

## 2. Marco 1 — PLANEJAR (início do turno)

1. Ler, nesta ordem: `WORKING-CONTEXT.md` → `scheduler/allow-list.txt` →
   `scheduler/logs/checkin-*.md` (mais recente) → `memory/` (episódios/instintos recentes)
   → `git status`/`git log` (read-only).
2. Montar `scheduler/logs/batman-plan-YYYY-MM-DD.md`:
   - fila ordenada por **P1>P2>P3** e dependências (teste antes de refactor);
   - orçamento do turno (tokens/custo/tempo) com reserva de ~20% para o relatório;
   - gate explícito por tarefa ("prepara PR-rascunho → PARA, não commita/pushe").
3. Tarefas fora da allow-list vão para a seção "Enfileirado para humano".

## 3. Marco 2 — EXECUTAR EM LOOP RECURSIVO (N2, allow-list, até o horário-limite)

> **v2 (01/10/2026).** Diagnóstico que motivou a mudança: em 26/09 o runner girou a mesma
> bateria 7.601 vezes (nenhuma melhoria real); em 28/09 o turno dirigido pelo LLM parou às
> 00:48 por "quota 20/20". Agora: (1) só o horário-limite encerra; (2) a bateria tem
> intervalo de 30 min; (3) fila vazia dispara a **descoberta**; (4) nada devido ⇒ **dorme**
> com heartbeat; (5) job LLM tem **orçamento de tempo** e roda no agente headless ou é puxado
> pelo LLM da sessão (`proximo`/`concluir` + /loop); (6) job cria **subjobs** (`--novos`);
> (7) o **vigia** do Agendador do Windows reinicia o turno se o heartbeat parar.
> Comandos: `shift.py turno | proximo | concluir | executar | descobrir | vigia`.

O turno é **incansável e recursivo**: executa **ciclos** em sequência até o
**horário-limite** (cota de **50 ciclos**; o horário-limite sempre prevalece). Cada
ciclo executa **um job completo (fase planejada)** com **etapas ilimitadas**; job
recorrente ou inacabado é **reativado** e roda de novo no ciclo seguinte. O bloqueio
de um item N3 **não interrompe o turno** — enfileira e segue em outra frente.

### Ciclo padrão (um job por ciclo, etapas ilimitadas)

```
1. HEARTBEAT      — grava scheduler/logs/batman-heartbeat-YYYY-MM-DD.json
                    (ciclo, job, ts, status) — um crash perde no máximo 1 ciclo
2. EXECUTAR JOB   — roda TODAS as etapas do job (o LLM pode acrescentar etapas
                    sem limite: testes, gates, refactors, benchmarks, docs...)
3. REATIVAR?      — job recorrente (bateria) ou com falhas -> volta à fila
                    (reativação contada); job concluído -> sai da fila
4. DETECTAR       — diff de git status vs ciclo anterior: mudanças novas?
5. AUTOEVOLUIR    — sinais determinísticos -> gatilhos/lições no ledger
6. REGISTRAR      — journal + saúde do workspace + heartbeat de fim
7. AVALIAR        — horário-limite? -> RELATAR e morrer (cota só em demo)
                    fila sem job devido? -> DESCOBRIR; ainda nada? -> DORMIR até o
                    próximo item (heartbeat a cada 60 s) -> volta ao 1
```

### Fases planejadas (jobs — criados pelo plano e pelo LLM)

O plano do turno define fases; o LLM as registra em
`scheduler/logs/batman-jobs-<data>.json`:

```json
{"jobs": [
  {"id": "bateria-deterministica", "nome": "gates + testes", "etapas": [["comando", "arg"], "..."], "recorrente": true},
  {"id": "melhorias-tdd", "nome": "débitos com TDD", "etapas": [["python", "-m", "pytest", "..."], "..."], "recorrente": false}
]}
```

- `recorrente: true` → o job volta à fila todo ciclo (é a espinha de validação contínua).
- `recorrente: false` → roda até ficar verde e então sai da fila (fase concluída).
- Etapas são **ilimitadas**: a skill acrescenta quantas precisar para a fase.

### Regras do loop

- **Nunca ocioso de verdade, nunca girando em vão:** fim de um ciclo = próximo job devido;
  sem job devido, a descoberta procura trabalho; sem trabalho, o turno dorme até o próximo
  item agendado (repetir checagens idênticas não é trabalho — é teatro).
- **Sem trabalho novo ≠ parar:** o ciclo aprofunda validação e varredura — cada
  ciclo ainda produz evidência nova (baseline noturno, contagem de débitos, etc.).
- **Heartbeat a cada ciclo** — o arquivo é a prova de vida; sem ele, o turno seguinte
  suspeita de morte prematura.
- **Horário-limite é o ÚNICO freio do modo incansável:** atingido → conclui o ciclo
  atômico, grava relatório e encerra. A **cota-base de 50 ciclos** é marco informativo
  (orçamento de validação) — ao atingi-la, o turno registra e **segue trabalhando** até
  o horário-limite. Jobs pendentes ficam registrados para o turno seguinte retomá-los.

### Escopo típico de um job (tudo com evidência antes/depois)

- Rodar suítes de teste/regressão/E2E e registrar resultado (baseline noturno).
- Rodar gates da casa (`auditoria_skills`, `propagar_defesa --check`, `generate_registry --check`,
  prescreen, validador de evals) e corrigir achados **reversíveis**.
- Atacar débitos priorizados do backlog com TDD (teste primeiro, mudança mínima).
- Propor/rodar benchmarks (incluindo suítes JEV determinísticas) e aplicar melhorias
  aprovadas pelo gate anti-regressão.
- Criar/evoluir **modelos JEV** para decisões repetitivas do próprio turno (fluxo:
  hipótese → baseline → benchmark → gate → adoção só com ganho real).
- Criar novas **skills internas** quando o padrão se repetir 3× (regra da casa:
  auditável, com evals e defesa).
- Coordenar outros agentes/skills via handoff por artefato (nunca memória implícita).
- **Journal:** toda ação relevante registrada em `memory/batman-shift.jsonl`
  (`ts`, `acao`, `nivel`, `alvo`, `evidencia`, `resultado`, `ciclo`) — é o rastro da madrugada.

**Paradas obrigatórias (N3, enfileirar e seguir):** commit, push, merge, rebase,
delete de arquivos, config crítica, deps novas, credenciais, GUI sem opt-in, qualquer
ação fora da allow-list.

## 4. Marco 3 — RELATAR (fim do turno)

`docs/relatorios/batman/morning-report-YYYY-MM-DD.md` + **consolidado executivo em HTML**
em `tmp/batman/morning-report-YYYY-MM-DD.html` (artefato **temporário — ignorado pelo git**):

```
# Relatório da Madrugada — {{DATA}} (turno Batman)
- Janela: {{inicio}} → {{fim}} · Orçamento: {{usado}}/{{teto}} · Ciclos: {{N}} (+{{R}} renovações)
## Feito (com evidência antes/depois)
## Pendente de decisão humana (gates N3)
## Riscos e achados (inclui o que NÃO funcionou)
## Próximos passos + sugestão de prioridade P1/P2/P3
```

O HTML consolida os KPIs do turno (ciclos, renovações, bateria ok/falhas, janela,
mudanças detectadas, N3 executados = 0) em nível executivo.

Se o turno terminou cedo ou estourou o orçamento, o relatório declara explicitamente.

## 5. Monitor ASCII de transparência

A qualquer momento (com o turno rodando ou não), o painel de acompanhamento lê os
artefatos vivos e imprime um checklist ASCII — **sem emojis**, só marcadores `[✓]`
concluído / `[x]` falhou / `[!]` atenção / `[ ]` pendente:

```bash
python scripts/batman/shift.py monitor
```

O painel mostra: TURNO (vivo? ciclo atual) · CICLOS acumulados · ETAPAS ok/falhas ·
HEARTBEAT · FASES/JOBS (pendente / recorrente verde / reativado / concluído) ·
GATILHOS de automelhoria abertos · N3 executados (sempre 0) · artefatos. Tudo lido
do journal/heartbeat/ledger reais — nada estimado.

## 6. Handoff

Cada marco produz artefato em disco e o ciclo deixa heartbeat + journal; o marco
seguinte lê o artefato. O turno seguinte começa pelo relatório do anterior. O loop
só termina na janela/orçamento — fora isso, melhoria contínua não para.
