# engenheiro-devops · Cultura DevOps e cultura de aprendizagem
> Quando carregar: conduzir postmortem sem culpa, registrar lição no `error_ledger`, planejar GameDay ou kaizen, diagnosticar cultura (Westrum, Três Vias, capacidades do Accelerate) ou medir sinais de cultura no repositório.

## As Três Vias — o que cada uma exige na prática
As Três Vias (*The Phoenix Project*, *The DevOps Handbook*) resumem os princípios do DevOps; cada uma vira práticas observáveis no repositório e no pipeline.

| Via | Princípio | Prática observável | No harness |
|---|---|---|---|
| 1ª · Fluxo | trabalho flui do desenvolvimento à produção em lotes pequenos, sem passar defeito adiante | PRs pequenos, WIP limitado, main sempre verde | tiers do `squad-pipeline`; `references/lean-management.md`; `references/ci-cd.md` |
| 2ª · Feedback | informação volta rápido de produção e de teste para quem decide | testes no PR, alerta que descreve a falha, review sem fila | `verificacao-loop` (GATE 2); `references/observabilidade.md` |
| 3ª · Aprendizado contínuo | experimentar, repetir e aprender com a falha sem punição | postmortem sem culpa, lição verificável, GameDay, kaizen | este arquivo |

Pergunta de diagnóstico por via: quanto tempo o PR mais antigo está aberto? Quanto tempo separa a falha do alerta que a nomeia? A última falha virou uma lição que o preflight devolve às próximas entregas?

## Tipologia de Westrum — comportamentos, não rótulos
Ron Westrum (*A typology of organisational cultures*, Quality & Safety in Health Care, 2004, hoje BMJ Quality & Safety) descreve três tipos de cultura pelo modo como a informação circula; o *Accelerate* a usa para ligar cultura e desempenho. O que importa é o comportamento observado.

| Comportamento | Patológica (orientada a poder) | Burocrática (orientada a regra) | Generativa (orientada a desempenho) |
|---|---|---|---|
| Má notícia | quem traz é punido ou ignorado | é encaminhada por canal formal e demora | quem traz é treinado e agradecido; vira ação |
| Falha | busca de culpado | aplica-se a regra e a sanção | investigação do sistema (postmortem sem culpa) |
| Responsabilidade | evitada | restrita ao escopo de cada área | compartilhada, inclusive o risco |
| Cooperação entre times | desencorajada | tolerada | recompensada |
| Ideia nova | esmagada | vira problema para a regra | implementada, com experimento |

Como observar (evidência, não opinião):
- **Falha:** o último postmortem nomeou pessoa? Tem ação com dono e prazo? Foi fechada?
- **Má notícia:** o tempo entre perceber e relatar um problema (timestamps do canal) e a reação a quem relatou.
- **Cooperação:** PRs revisados por outro time; tempo até o primeiro comentário (§ Sinais de cultura).
- **Ideia nova:** propostas (ADR, PR de experimento) aceitas versus ignoradas sem resposta.
- **Medição:** questionário anônimo com as seis afirmações do instrumento Westrum usado pela DORA (escala Likert; dora.dev, capacidade "Generative organizational culture", consultado em 11/10/2026): "On my team, information is actively sought"; "Messengers are not punished when they deliver news of failures or other bad news"; "On my team, responsibilities are shared"; "On my team, cross-functional collaboration is encouraged and rewarded"; "On my team, failures are treated primarily as opportunities to improve the system"; "On my team, new ideas are welcomed". Reportado agregado por time, nunca por pessoa.
- Rótulo colado num time vira arma: registre o comportamento e a ação de melhoria, não o tipo.

## Postmortem sem culpa
Postmortem sem culpa é o ritual central da 3ª Via (e do SRE do Google): trata o incidente como falha do sistema e produz ações verificáveis em vez de culpados. Arquivo sugerido: `docs/postmortems/INC-<id>.md`, versionado.

### Template
Estrutura mínima da ata; cada campo tem fonte e nenhum nome de pessoa aparece como causa.
```markdown
**Postmortem <INC-id> — <título sobre o sistema, sem nome de pessoa>**
Severidade: <política do banco> · Impacto (UTC): <início> -> <fim> · Mudança relacionada: <PR/SHA ou nenhuma>
**Impacto (medido):** <o que quebrou, para qual categoria de usuário, por quanto tempo> · fonte: <métrica ou log>
**Linha do tempo (UTC, de logs e do canal do incidente)**
| Hora | Evento | Fonte |
**Detecção:** <como foi detectado; tempo até detectar; o alerta existia?>
**Fatores contribuintes (sistema, processo, ferramenta; nunca pessoa)**
- <fator> — o que no sistema tornou isso possível ou difícil de detectar
**O que funcionou:** <detecção, rollback ou comunicação que ajudaram>
**Onde tivemos sorte:** <o que poderia ter piorado>
**Ações**
| ID | Ação | Tipo (prevenir/detectar/mitigar) | Dono (login) | Prazo (AAAA-MM-DD) | Como verificar |
| A1 | <ação> | <tipo> | <login> | <data> | <comando ou métrica> |
**Lição registrada:** error_id <id da linha em memory/error_ledger.jsonl>
```
No arquivo real, os rótulos em negrito viram títulos `##` (o lint do § Oráculo aceita as duas formas). O dono da ação é atribuição de trabalho, nunca atribuição de culpa.

### Conduzir em 45 minutos
Formato de reunião com tempo marcado; a linha do tempo chega pronta, extraída de logs e do canal do incidente.
- **Antes:** facilitador que não atuou na resposta monta a linha do tempo e o rascunho; convida quem agiu e quem opera o serviço.
- **0–5 min:** regras: foco no sistema, perguntas "o que" e "como", não "quem" nem "por que você".
- **5–15 min:** confirmar fatos e horários; para cada decisão, o que se sabia e o que o sistema mostrava naquele momento.
- **15–30 min:** fatores contribuintes: por que o sistema permitiu e por que não detectou. Se a resposta para na pessoa, perguntar o que tornaria o erro impossível, evidente ou barato.
- **30–40 min:** ações: poucas, priorizadas, cada uma com tipo, dono, prazo e como verificar.
- **40–45 min:** lição para o ledger; leitura final dos fatores sem nomes.

### O que NÃO vai na ata
Itens que transformam a ata em instrumento de culpa ou em vazamento; o lint do § Oráculo cobre parte deles.
- Nome de pessoa como causa; "erro humano", "descuido" e "deveria ter" como fator.
- Adjetivo, julgamento de intenção ou competência; avaliação de desempenho ou sanção.
- Dado de cliente, PII, segredo, token, hostname ou URL interna, log sem máscara.
- Especulação sem dado: escrever "não sabemos" e abrir ação de investigação.
- Ação sem dono e prazo: isso é ideia, não ação.

## Capacidades do Accelerate
O livro *Accelerate* (Forsgren, Humble, Kim; IT Revolution, 2018, Apêndice A) agrupa **24 capacidades** associadas a desempenho de entrega em cinco grupos — continuous delivery (8), architecture (2), product and process (4), lean management and monitoring (5) e culture (5); nomes em inglês conforme IT Revolution, "24 key capabilities to drive improvement in software delivery". Tratar como hipóteses a medir, não como checklist de maturidade. Lista por nome:
- **Entrega contínua:** controle de versão de todos os artefatos de produção; automação de deploy; integração contínua; desenvolvimento baseado em tronco; automação de testes; gestão de dados de teste; segurança desde o início (shift left); entrega contínua.ntrega contínua.
- **Arquitetura:** arquitetura fracamente acoplada; arquitetura para times empoderados (escolha de ferramentas).
- **Produto e processo:** feedback do cliente; fluxo de valor visível; lotes pequenos; experimentação pelo time.
- **Gestão lean e monitoramento:** processo leve de aprovação de mudança; monitoramento de aplicação e infraestrutura para decisões de negócio; verificação proativa da saúde do sistema; limites de WIP; visualização do trabalho para monitorar qualidade e comunicar.
- **Cultura:** cultura generativa (Westrum); apoio ao aprendizado; colaboração entre times; recursos e ferramentas que tornam o trabalho significativo; liderança transformacional.

Onde o harness já toca: limite de WIP e gestão visual (`references/lean-management.md`); aprovação de mudança (`references/frameworks-ti.md`); monitoramento (`references/observabilidade.md`); shift left (gatilho de segurança, `05b-veracode.md`); automação de testes (`verificacao-loop`).

## Aprendizagem no harness — do postmortem ao error_ledger e ao instinto
Uma ata só ensina se virar lição que as próximas entregas encontram; o `memory/error_ledger.jsonl` é esse destino, e a promoção a instinto é um segundo passo, com evidência e aprovação humana.
- **Lição (uma linha JSON por lição), no schema vigente do ledger** (campos do `memory/error_ledger.jsonl` em 11/10/2026: error_id, ts, categoria, linguagem, bug, diagnostico, causa_raiz, solucao, teste_preventivo, tags, status, origin, prescreen_ok): `error_id`, `bug` e `solucao` são as chaves que o preflight lê (`scripts/preflight.py`); `causa_raiz` recebe os fatores contribuintes (sistema/processo, nunca pessoa), `teste_preventivo` o oráculo que prova a correção, `tags` o incidente (`INC-id`) e o alvo (módulo/caminho) para o casamento com a tarefa.

```json
{"error_id":"POST-<AAAA-MM-DD>-<nn>","ts":"<ISO-8601 UTC>","categoria":"<deploy|dados|observabilidade|infra>","linguagem":"<java|python|infra>","bug":"<padrão de falha em uma frase, sem pessoa>","diagnostico":"<como foi detectado>","causa_raiz":"<fatores de sistema/processo>","solucao":"<o que checar ou fazer na próxima vez>","teste_preventivo":"<comando ou métrica que prova a correção>","tags":["INC-<id>","<modulo-ou-caminho>"],"status":"ativo","origin":"postmortem","prescreen_ok":true}
```
- **Regras:** o prefixo do `error_id` diz a origem (`POST-` postmortem, `CHAOS-` experimento, ver `references/chaos-engineering.md § Relatório antes/depois e lição`); append-only (correção é nova linha apontando o `error_id` anterior); campo desconhecido é `null` explícito, nunca estimado; a lição entra pelo rito gated do `aprendizado-continuo`, com o texto aprovado por humano antes do append; sem nome, dado de cliente, segredo ou URL interna.
- **O laço fecha sozinho:** o preflight devolve "erros passados" no `00-preflight.md`; o `context_pack` traz lições que casam com a tarefa e com o código do alvo; o REVIEW monta checklist a partir do ledger; e, pelo `verificacao-loop`, defeito registrado no módulo tocado nos últimos 90 dias dispara mutation. `alvo` é o campo que permite esse casamento.
- **Promoção a instinto (`aprendizado-continuo`, sempre gated):** um incidente gera lição de escopo projeto, não instinto. O candidato surge na reincidência do padrão e só é promovido pela Regra de Promoção da skill: check aprovado, padrão de falha nomeado e beco sem saída eliminado, com evidência. Projeto -> global exige o padrão em 2+ projetos com confiança >= 0,8 (valores da skill). Nenhum agente promove sozinho.

## GameDay e kaizen como rituais
Os dois rituais transformam aprendizado em hábito: o GameDay ensaia a falha antes que ela aconteça; o kaizen converte uma lição por semana em melhoria medida.
- **GameDay:** ensaio planejado, com papéis fixos, para validar detecção, resposta e rollback contra uma hipótese de estado estável. Roteiro, ferramentas (AWS FIS, Chaos Toolkit, LitmusChaos, Gremlin), raio de impacto e critério de abortar: `references/chaos-engineering.md § GameDay — roteiro de 2h`; não repetir aqui.
- **Produção:** só com política aprovada por Risco/Segurança (`references/chaos-engineering.md § Regras do banco`); com política, é mudança normal, com janela e aprovação humana explícita.
- **Saída como ritual de aprendizagem:** hipótese confirmada ou refutada, lacunas (alerta não disparou? runbook errado?), ações com dono e prazo, lição no ledger.
- **Kaizen:** formato de 30 min em `references/lean-management.md § Kaizen semanal (30 min)`; as ações de postmortem e de GameDay alimentam a pauta, e o time escolhe uma por semana.
- **Medir:** GameDays realizados versus planejados (contados); ações com prazo cumprido / ações abertas (issues com rótulo `acao-postmortem` e `closed_at`). Cadência é decisão do time.

## Sinais de cultura medíveis no repo
Sinais de saúde da cultura saem de dados que o GitHub e o ledger já guardam; medir, não estimar, sempre agregado por time e nunca como meta nem avaliação individual (quando vira meta, deixa de medir).

```python
#!/usr/bin/env python3
# Uso: gh pr list --repo <org>/<repo> --state merged --limit 100 \
#        --json number,author,createdAt,reviews,comments,files | python3 sinais_cultura.py
import json, re, statistics as st, sys
from datetime import datetime as dt
BOTS = {"<logins de bots do repositório>"}                 # fora da conta de "primeira resposta"
TESTE = re.compile(r"(^|/)(src/test|tests?|__tests__)/|Test\.java$|_test\.py$|\.spec\.ts$")
def t(s): return dt.fromisoformat(s.replace("Z", "+00:00"))

def primeira_resposta_h(pr):
    ev = [(x.get("submittedAt") or x["createdAt"], x["author"]["login"]) for x in pr["reviews"] + pr["comments"]]
    ts = [t(quando) for quando, quem in ev if quem != pr["author"]["login"] and quem not in BOTS]
    return (min(ts) - t(pr["createdAt"])).total_seconds() / 3600 if ts else None

prs = json.load(sys.stdin)
esperas = [e for e in map(primeira_resposta_h, prs) if e is not None]
com_teste = sum(any(TESTE.search(f["path"]) for f in pr["files"]) for pr in prs)
print(f"PRs={len(prs)} sem_resposta={len(prs) - len(esperas)}")
if esperas: print(f"1a_resposta_h mediana={st.median(esperas):.2f} max={max(esperas):.2f}")
print(f"PRs com teste: {com_teste}/{len(prs)}   # proxy: toca arquivo de teste, não mede qualidade")
```

```bash
# lições por incidente: INC com 0 lições = postmortem que não virou aprendizado
for f in docs/postmortems/INC-*.md; do id=$(basename "$f" .md)
  printf '%s\t%s\n' "$id" "$(jq -r --arg id "$id" 'select(.incidente_ref==$id)|.error_id' memory/error_ledger.jsonl | wc -l)"
done
```
- **Tempo até o primeiro comentário de PR:** criação do PR até a primeira review ou comentário de outra pessoa que não seja bot.
- **% de PRs com teste:** PRs mergeados que tocam arquivo de teste / PRs mergeados. Proxy, não qualidade.
- **Lições por incidente:** linhas do ledger com `incidente_ref` / incidentes fechados.
- **Postmortem com nome como causa:** deve ser zero (lint do § Oráculo).

## Oráculo — como provar que foi feito
O GATE 2 executa o lint abaixo sobre um postmortem real; "revisado e aprovado" não conta.
- Postmortem com **>= 1 ação com dono e prazo ISO**, e a lição correspondente no `memory/error_ledger.jsonl`.
- **Nenhum nome de pessoa como causa:** o lint pega `@login` e vocabulário de culpa; nome próprio solto só a leitura final da reunião pega.

```bash
PM=docs/postmortems/INC-<id>.md
awk -F'|' '$2 ~ /A[0-9]+/ && $5 ~ /[A-Za-z0-9]/ && $6 ~ /[0-9]{4}-[0-9]{2}-[0-9]{2}/' "$PM" | grep -q . \
  || echo "FALHA: sem ação com dono e prazo"
jq -e --arg id "INC-<id>" 'select(.incidente_ref==$id)|.error_id' memory/error_ledger.jsonl >/dev/null \
  || echo "FALHA: sem lição no ledger"
sed -n '/Fatores contribuintes/,/O que funcionou/p' "$PM" \
  | grep -n -i -E '@[A-Za-z0-9_-]+|culpa|negligên|descuido|erro humano|esqueceu|deveria ter' \
  && echo "FALHA: pessoa ou culpa nos fatores"
```

## Anti-padrões
- **Caça ao culpado disfarçada:** "erro humano" como causa raiz.
- **Postmortem teatro:** ata bonita sem ação, ou com ação sem dono e prazo.
- **Cinco porquês que terminam em pessoa:** a investigação para onde deveria começar.
- **Lição que morre na ata:** o aprendizado não chega ao ledger e a próxima entrega repete o erro.
- **Promoção por entusiasmo:** virar instinto a partir de um único incidente, sem evidência nem GATE.
- **GameDay sem hipótese:** injetar falha sem SLI, sem condição de parada ou, pior, em produção sem aprovação.
- **Métrica de cultura como meta:** transformar tempo de review ou % de testes em objetivo ou ranking de pessoas.
- **Rótulo Westrum:** classificar o time em vez de registrar comportamentos e ações.

## Checklist de banco
- [ ] Regulatório: incidente classificado como relevante pela política segue o fluxo interno e regulatório de comunicação; o postmortem não o substitui.
- [ ] Janela de mudança: ação corretiva que altera produção entra como mudança (padrão ou normal), com janela; GameDay em produção só com política aprovada e como mudança normal.
- [ ] Segregação de ambientes: ferramentas e credenciais de injeção de falha só nos ambientes aprovados; facilitador do postmortem fora da resposta ao incidente.
- [ ] Dados sensíveis: ata e lição sem dado de cliente, PII, segredo, hostname ou URL interna; logs anexados mascarados; nenhum nome como causa.
- [ ] Trilha de auditoria: postmortem versionado; lição append-only com `incidente_ref`; ações rastreadas até o fechamento; texto da lição aprovado por humano.
