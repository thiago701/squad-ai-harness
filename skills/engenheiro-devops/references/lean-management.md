# engenheiro-devops · Lean Management na entrega de software
> Quando carregar: mapear o fluxo de valor (VSM) da ideia ao deploy, medir lead time e tempo de ciclo, definir limite de WIP, caçar desperdício na entrega, conduzir o kaizen semanal ou ligar o custo por entrega do harness à melhoria de processo.

## Princípio: medir o fluxo antes de mexer nele
Lean aplicado a software é tornar o trabalho visível, limitar o que está em andamento e melhorar uma coisa por vez. A regra da Squad: nenhum tempo é estimado. Todo número tem fonte (API do GitHub, log de pipeline, `memory/sli.jsonl`) ou fica marcado `não medido: <motivo>`. A espera entre etapas é invisível a olho nu; só o timestamp mostra onde ela está.

## Mapa de fluxo de valor (VSM) em 1 hora com o time
O VSM é o desenho das etapas reais entre "pedido aceito" e "em produção", com o tempo de cada uma. Ele é montado com os dados já extraídos, não de memória.
- **Antes (facilitador, 15 min):** extrair as últimas entregas (no mínimo 5) com os scripts de § Onde medir. Levar a tabela pronta.
- **0–10 min:** fixar início e fim ("issue/card aceito" -> "deployment `success` em produção"). Sem isso o lead time não é comparável.
- **10–30 min:** listar as etapas na ordem em que acontecem de fato (não a do procedimento), incluindo as invisíveis no repo: refinamento, aprovação de GATE, CAB, janela de mudança.
- **30–50 min:** para cada etapa, anotar três campos:
  - **Tempo de processamento (PT):** tempo com mãos no trabalho. Etapa automática: duração do job (medido). Etapa humana: declarado pelo executor e rotulado `declarado`.
  - **Espera:** tempo parado na fila antes da etapa. É o decorrido medido menos o PT; rotular `derivado`.
  - **% completo e correto (%C&A):** fração dos itens que chegam à etapa e seguem sem voltar por erro ou informação faltante. Proxy medível: PRs sem rodada `CHANGES_REQUESTED`; runs sem `run_attempt` > 1.
- **50–60 min:** apontar as duas maiores esperas e o menor %C&A; sair com **um** candidato a kaizen, não uma lista.
- Saída: `docs/fluxo/vsm-AAAA-MM-DD.md` com uma linha por entrega. Eficiência de fluxo = soma dos PT / lead time, por entrega.

```markdown
| entrega | issue criada | 1º commit | PR pronto | 1ª review | aprovado | merge | deploy success | lead time h | ciclo h | tier / tokens | fonte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| PR#<n> | <ISO UTC> | <ISO UTC> | <ISO UTC> | <ISO UTC> | <ISO UTC> | <ISO UTC> | <ISO UTC> | <calculado> | <calculado> | <relatorio-custo> | api / log / declarado |

| etapa | PT mediana h | espera mediana h | %C&A | n | fonte |
|---|---|---|---|---|---|
| <etapa do mapa> | <medido ou declarado> | <derivado> | <proxy medido> | <n> | api / log / declarado / derivado |
```
Célula sem dado vira `não medido: <motivo>`, nunca um valor aproximado.

## Onde medir no repo (timestamps, nunca estimativa)
Cada etapa do VSM nasce de um par de eventos do GitHub ou do pipeline. A estação só alcança o GitHub: `gh` e `gh api` bastam; o que vive em outra ferramenta (card no Jira, chamado de CAB) é exportado por um humano ou marcado `não medido`.

| Etapa | Início | Fim | Fonte |
|---|---|---|---|
| Fila do backlog | issue criada | primeiro commit da branch | `issues/{n}` `created_at`; `pulls/{n}/commits` |
| Desenvolvimento | primeiro commit | PR pronto p/ review | timeline `ready_for_review` (ou `created_at` do PR) |
| Espera por review | PR pronto | 1ª review de outro autor | `pulls/{n}/reviews` `submitted_at` |
| Review e retrabalho | 1ª review | última `APPROVED` | `reviews[].state` |
| Espera de merge | aprovação | `merged_at` | `pulls/{n}` |
| CI | job `created_at` | job `completed_at` | `actions/runs/{id}/jobs` (fila = `started_at` - `created_at`) |
| Aprovação/janela | CI verde na main | deployment `in_progress` | `deployments/{id}/statuses` |
| Deploy | `in_progress` | `success` | `deployments/{id}/statuses` |

```python
#!/usr/bin/env python3
# Uso: gh pr list --repo <org>/<repo> --state merged --limit 50 \
#        --json number,author,createdAt,mergedAt,reviews | python3 pr_tempos.py
import json, math, statistics as st, sys
from datetime import datetime as dt

def t(s): return dt.fromisoformat(s.replace("Z", "+00:00"))
def h(a, b): return (t(b) - t(a)).total_seconds() / 3600      # horas decorridas

linhas, sem_aprov = [], []
for pr in json.load(sys.stdin):
    outros = [r for r in pr["reviews"] if r["author"]["login"] != pr["author"]["login"]]
    aprov = [r["submittedAt"] for r in outros if r["state"] == "APPROVED"]
    if not aprov: sem_aprov.append(pr["number"])         # merge sem aprovação de outro autor
    linhas.append({
        "abertura_ate_1a_review": h(pr["createdAt"], min(r["submittedAt"] for r in outros)) if outros else None,
        "abertura_ate_aprovacao": h(pr["createdAt"], max(aprov)) if aprov else None,
        "aprovacao_ate_merge":    h(max(aprov), pr["mergedAt"]) if aprov else None,
        "abertura_ate_merge":     h(pr["createdAt"], pr["mergedAt"])})

for k in linhas[0]:
    xs = sorted(x[k] for x in linhas if x[k] is not None)
    if xs:   # p85 por posto (nearest-rank); mediana, nunca média
        print(f"{k}: n={len(xs)} mediana_h={st.median(xs):.2f} p85_h={xs[math.ceil(.85*len(xs))-1]:.2f}")
print("PRs sem aprovação de outro autor:", sem_aprov or "nenhum")
```

```bash
# merge -> deploy: momento do primeiro "success" de cada deployment do ambiente de produção
R=<org>/<repo>
gh api "repos/$R/deployments?environment=<ambiente-prod>&per_page=50" --jq '.[]|[.id,.sha,.created_at]|@tsv' |
while IFS=$'\t' read -r id sha criado; do
  ok=$(gh api "repos/$R/deployments/$id/statuses" \
    --jq '[.[]|select(.state=="success")]|sort_by(.created_at)|first|.created_at // empty')
  printf '%s\t%s\t%s\n' "$sha" "$criado" "${ok:-sem-success}"
done   # juntar com mergeCommit.oid do PR; deploy agrupando merges: usar o 1º SHA que contém o merge
```
Merge sem aprovação de outro autor aparece como achado, não como linha omitida. Para o deploy usar `environment:` no job (é ele que cria o registro de deployment).

## Lead time × tempo de ciclo
As duas métricas respondem a perguntas diferentes e só são comparáveis se início e fim forem declarados no VSM.
- **Lead time:** do ponto de vista de quem pede. Início = issue/card aceito no backlog; fim = deployment `success` em produção. Inclui a fila antes de alguém começar.
- **Tempo de ciclo:** do ponto de vista de quem entrega. Início = primeiro commit (ou PR draft); fim = o mesmo deployment `success`. Exclui a fila do backlog.
- **Lead time for changes (DORA):** só commit -> produção, um trecho do total. Definição, armadilhas (ex.: squash merge apaga o horário dos commits originais) e coleta: `references/dora-metrics.md § As quatro métricas e a dimensão de confiabilidade — definições` e `§ Como medir neste repositório (fontes por métrica)`; não repetir aqui.
- Reportar **mediana e um percentil alto fixo (p85 ou p95)**, com `n`. Média esconde cauda; entrega única não é amostra.
- Relação de Little (médias, sistema estável): WIP médio = vazão média x lead time médio. Serve para raciocinar (mais WIP, mesmo throughput, lead time maior), não para prever um item.

## Limite de WIP
WIP é tudo que foi começado e não chegou à produção. Limitar WIP encurta a fila, reduz troca de tarefa e expõe bloqueios cedo.
- **Contar antes de limitar:** linhas "Em andamento" do `WORKING-CONTEXT.md` + PRs abertos + branches com commits não integrados. As três fontes devem concordar; divergência é WIP invisível.
- **Como definir:** observar o WIP real por 2 a 4 semanas; começar no valor mais frequente observado e baixar um item por vez nos kaizens. Ponto de partida comum: no máximo um item por pessoa (ou por par).
- **Sinais de violação:** contagem acima do limite por mais de um dia útil; item mais velho com idade acima do p85 histórico de ciclo; item novo iniciado com outro bloqueado sem registro de bloqueio; mesmo autor com commits em várias branches no mesmo dia.
- **Reação:** parar de começar, começar a terminar. O item mais antigo recebe a atenção antes de qualquer item novo; o bloqueio vira linha com dono.
- O GitHub não impõe WIP: o limite é combinado do time e o desvio é sinal, não bloqueio automático.

## Os 7 desperdícios traduzidos para software
Tradução de Mary e Tom Poppendieck dos desperdícios do Lean para a entrega. A lista de sete abaixo segue *Implementing Lean Software Development: From Concept to Cash* (Addison-Wesley, 2006): partially done work, extra features, relearning, handoffs, task switching, delays, defects. O livro anterior, *Lean Software Development: An Agile Toolkit* (Addison-Wesley, 2003, Tabela 1.1), usava outra lista — partially done work, extra processes, extra features, task switching, waiting, motion (hand-offs), defects; ao citar, diga qual. Cada um tem sinal observável e medida; o sinal vira candidato a kaizen, nunca acusação a pessoa.

| Desperdício | Em software | Sinal observável / como medir |
|---|---|---|
| Trabalho parcialmente feito | código não integrado ou não implantado | idade dos PRs abertos; branches velhas (`git for-each-ref --sort=committerdate`); merges na main sem deploy |
| Features extras | código sem requisito ou sem uso | arquivos no diff fora de "arquivos a tocar" do `03-plano.md`; flag nunca ligada; `spec-code-drift-detector` (código não rastreado) |
| Reaprendizado | redescobrir o que já se sabia | mesmo `error_id` repetido no `memory/error_ledger.jsonl`; erro do preflight ignorado; pergunta repetida em PR |
| Handoffs | contexto perdido entre pessoas ou times | nº de donos por item; reatribuições no card; retornos por informação faltante (%C&A) |
| Troca de tarefa | atenção fragmentada | WIP acima do limite; PRs paralelos do mesmo autor; branches distintas com commits no mesmo dia |
| Espera | fila entre etapas | esperas do VSM: PR -> review, aprovação -> merge, merge -> deploy, fila de runner, janela de mudança |
| Defeitos | retrabalho e escapes | commits `Revert`; hotfix após deploy; `CHANGES_REQUESTED`; re-runs (`run_attempt` > 1); taxa de falha de mudança (ver `references/dora-metrics.md`) |

## Kaizen semanal (30 min)
Kaizen é uma melhoria pequena, com dono, prazo e medida, repetida toda semana. O que não tem medida "depois" não é kaizen.
- **Antes:** rodar os scripts de extração; a reunião não gasta tempo coletando dado.
- **0–5 min:** resultado da melhoria anterior, mesma medida e mesmo script: manter, ajustar ou reverter.
- **5–15 min:** escolher **um** ponto de dor nos dados (maior espera do VSM, item mais velho do WIP, desperdício mais frequente).
- **15–25 min:** definir a melhoria: hipótese, **dono** (uma pessoa), **prazo** (data), medida antes (baseline já extraída) e quando medir depois.
- **25–30 min:** registrar e encerrar. Melhoria que altere pipeline de produção, controle de acesso ou janela não é decidida aqui: segue GATE humano e gestão de mudança.
- Conclusão só com `n` suficiente declarado pelo time; uma entrega comparável não prova nada. Resultado negativo também é registrado.
- Ações de postmortem entram como candidatas à pauta (ver `references/cultura-devops-aprendizagem.md § GameDay e kaizen como rituais`); o kaizen escolhe uma, não todas.

```markdown
**Kaizen AAAA-Www**
- Dor (dado): <métrica, valor medido, fonte>
- Melhoria: <uma mudança> · Dono: <login> · Prazo: <AAAA-MM-DD>
- Medida: <métrica> de <baseline> para <alvo> · Comando: <script>
- Resultado (preencher no kaizen seguinte): <antes> -> <depois> · decisão: manter|ajustar|reverter
```

## Amarração com o harness
O harness já produz dois dos três instrumentos do Lean (custo e quadro); o terceiro, os timestamps, vem do GitHub.
- **`python ops/run.py relatorio-custo`:** custo real por entrega a partir de `memory/sli.jsonl` (o compacto é versionado no repo-fonte, conforme `.gitignore`; na estação do banco fica local, porque a cópia consumidora nunca faz push), casado com o `00-preflight.meta.json` por janela de tempo e agregado por tier (n, média, mediana, p95 de tokens frescos). Observacional: nunca reprova. Sem ids por padrão; `--gravar` escreve `custo.md` na pasta da entrega. Use a coluna de custo ao lado do lead time no VSM, sempre comparando dentro do mesmo tier. Token não é dinheiro: converter só com a tabela de preço do contrato vigente do banco (entrada humana; nunca preço de memória).
- **`WORKING-CONTEXT.md` como quadro de WIP:** seção `## Em andamento`, uma linha por item (`| id | item | dono | início AAAA-MM-DD | estado | bloqueio |`). Se o arquivo já tem seção equivalente, use-a; a regra é uma linha por item, com data de início. É arquivo residente (custa contexto a cada turno): item concluído sai da tabela e vai para o `99-relatorio.md` da entrega.

```bash
# WIP = linhas da tabela sob "## Em andamento" (até o próximo "##"), sem cabeçalho nem separador
awk '/^## Em andamento/{f=1;next} /^## /{f=0} f && /^\| *[A-Za-z0-9#]/ && !/^\| *id *\|/' WORKING-CONTEXT.md | wc -l
# fonte independente: PRs abertos. Divergência entre os dois números = WIP invisível
gh pr list --repo <org>/<repo> --state open --json number --jq length
```
- **Fases do pipeline como etapas do VSM:** os estados de `contracts/pipeline-state-machine.json` (`gate1_pendente`, `gate2_pendente`) são esperas por humano. Medir pelos eventos `gate` do `memory/sli.jsonl` (campo `ts`) quando existirem; senão pelo PR. Não inferir por `mtime` de arquivo.

## Oráculo — como provar que foi feito
O GATE 2 executa; "revisado e aprovado" não conta.
- `docs/fluxo/vsm-*.md` com **>= 5 linhas** de entregas reais totalmente medidas (sem `não medido`), cada uma com timestamps ISO e `fonte`; nenhuma célula com `~`, `aprox`, `estimad`, `a definir`.
- Reprodutibilidade: rodar `pr_tempos.py` sobre o JSON arquivado e obter os mesmos números de `docs/fluxo/vsm-resumo.txt` (saída arquivada do mesmo script).
- WIP contado: saída dos dois comandos acima, com data UTC, anexada ao relatório.
- Lead time extraído de timestamps: cada valor aponta para o par de eventos de § Onde medir.

```bash
n=$(grep -h -E '^\| PR#[0-9]+' docs/fluxo/vsm-*.md | grep -v 'não medido' | wc -l)
test "$n" -ge 5 || echo "FALHA: menos de 5 entregas totalmente medidas ($n)"
grep -n -E '~|aprox|estimad|a definir' docs/fluxo/vsm-*.md && echo "FALHA: valor estimado ou aberto"
python3 pr_tempos.py < prs-arquivado.json | diff - docs/fluxo/vsm-resumo.txt || echo "FALHA: não reproduz"
```

## Anti-padrões
- **VSM de memória:** tempos de cabeça. Sem timestamp, é opinião.
- **WIP de fachada:** limite escrito no quadro, mas nunca contado nem confrontado com os PRs abertos.
- **Média que mente:** reportar média de uma distribuição com cauda longa.
- **Lead time sem início:** início e fim não declarados; cada pessoa mede um trecho diferente.
- **Otimizar a etapa errada:** acelerar o CI enquanto o PR espera dias por review.
- **Kaizen de lista:** várias melhorias, nenhum dono, prazo ou "depois" medido.
- **Ranking de pessoas:** usar tempos por indivíduo; o fluxo é do sistema.
- **Gaming do relógio:** fatiar ou fechar e reabrir PR para "zerar" a espera.

## Checklist de banco
- [ ] Regulatório: a extração usa só metadados (timestamps, números de PR); nenhum conteúdo de PR, dado de cliente ou título sensível no VSM.
- [ ] Janela de mudança: espera por CAB e por janela aparece como etapa própria no VSM, não escondida em "deploy".
- [ ] Segregação: PRs mergeados sem aprovação de outro autor foram listados e tratados como achado.
- [ ] Dados sensíveis: nenhum nome de pessoa no VSM ou kaizen (login só como dono de ação), nenhum ranking individual, nenhuma URL interna.
- [ ] Trilha de auditoria: scripts, JSON de entrada e VSM versionados e datados em UTC; kaizen que muda produção passou por GATE humano e registro de mudança.
