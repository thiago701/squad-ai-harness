# engenheiro-devops · DORA para DevOps
> Quando carregar: medir ou discutir frequência de deploy, lead time, change failure rate, tempo de recuperação ou confiabilidade; montar linha de base de entrega; definir meta de melhoria de pipeline; interpretar "somos Elite/High?"; auditar um número DORA citado por alguém.

## Fonte, citação e o que esta reference NÃO traz
Contexto: as métricas vêm do programa de pesquisa DORA (DevOps Research and Assessment, hoje do Google Cloud), e quem as cita precisa dizer de qual edição. Edições (dora.dev/publications, consultado em 11/10/2026): *State of DevOps Report* 2014–2017 (DORA com Puppet); *Accelerate State of DevOps Report* 2018, 2019, 2021, 2022, 2023 e 2024; 2025 renomeado *State of AI-assisted Software Development*; sem relatório em 2020. Citação mínima: "Accelerate State of DevOps Report, DORA/Google Cloud, <ano>, p. <n>" — limiares das faixas: `<ler na edição citada>`; base conceitual: Forsgren, Humble, Kim, *Accelerate* (IT Revolution, 2018).
- Esta reference traz **definições, fórmulas e como medir neste repositório**. Ela **não traz limiares numéricos**: eles mudam entre edições e nunca devem sair de memória.
- A tabela de faixas em `references/observabilidade.md § DORA Metrics` **não cita edição**: trate-a como ilustrativa e não a copie para relatório. O cálculo de lead time daquele workflow usa a idade das execuções de deploy (`now − created_at`), que não é commit → deploy; para o número oficial use a consulta abaixo.
- A estação de trabalho só alcança o GitHub: o limiar de uma edição é lido por um humano no PDF e registrado em `docs/dora-baseline.md` com (relatório, editor, ano, página).

## As quatro métricas e a dimensão de confiabilidade — definições
Contexto: quatro métricas de entrega (vazão e estabilidade) mais confiabilidade operacional, medidas sempre por serviço.

| Métrica | Definição precisa | Eixo |
|---|---|---|
| Deployment frequency | quantas vezes, por unidade de tempo, uma versão chega com sucesso à produção | vazão |
| Lead time for changes | tempo entre o commit e esse commit rodando em produção | vazão |
| Change failure rate (CFR) | deploys que serviram tráfego e exigiram correção (rollback, hotfix, incidente) ÷ deploys que serviram tráfego | estabilidade |
| Time to restore / failed deployment recovery time | da abertura (detecção) ao fechamento (serviço restaurado) de uma falha | estabilidade |
| Confiabilidade (quinta dimensão) | o serviço cumpre seu SLO? medida por atingimento de SLO e consumo de error budget | operação |

- O nome da quarta métrica mudou: MTTR (histórico) → "time to restore service" → "failed deployment recovery time" nas edições recentes (restringe-se a falhas causadas por deploy); confirme o nome na edição citada.
- Histórico oficial (dora.dev, "History of DORA metrics", consultado em 11/10/2026): **2018** acrescenta disponibilidade e passa a falar em desempenho de entrega e operação (SDO); **2021** amplia disponibilidade para **confiabilidade** — a própria DORA registra que chamá-la de "quinta métrica" naquela edição foi impreciso, por ser medida operacional, não de entrega; **2023** renomeia *time to restore service* para **failed deployment recovery time**, separando falhas causadas por mudança de falhas externas; **2024** introduz a quinta métrica, **deployment rework rate** ("percentual de deploys que são trabalho não planejado para corrigir bugs"). Use o nome e a definição da edição citada.
- Confiabilidade neste repo = fração de janelas dentro do SLI-alvo e saldo de error budget por serviço (SLI/SLO/error budget em `references/frameworks-ti.md § SRE`; a coleta das métricas em `references/observabilidade.md`); o alvo do SLO é decisão do dono do serviço, não vem do relatório.

## Contrato de eventos (a fonte de verdade é o log, não a prosa)
Contexto: toda métrica sai de um JSONL append-only de eventos (1 objeto por linha, UTF-8, `ts` ISO-8601 UTC, nulo explícito quando desconhecido), no mesmo espírito de `memory/sli-schema.md`.
- Arquivo `dora/eventos.jsonl`, escrito pelo job do pipeline (script determinístico), nunca por agente LLM; correção = nova linha, jamais edição.
- `deploy`: `ts, servico, env, sha, resultado, categoria, commits_ts[]`. `resultado` = `sucesso` (chegou a 100%) · `revertido` (serviu tráfego parcial e voltou) · `falha` (abortado antes de servir tráfego). `categoria` = `codigo | config | iac | flag`.
- `rollback`: `ts, servico, deploy_sha`. `incidente_aberto`: `ts, id, servico, deploy_sha|null`. `incidente_fechado`: `ts, id`.
- Sem segredo, sem payload de cliente, sem URL interna; `id` é a chave do ticket (ex.: `INC-123`), nunca o texto.

## Armadilhas de medição — o que conta e o que não conta
Contexto: números DORA se corrompem pela definição do evento, não pela conta; decida cada regra abaixo uma vez, registre em ADR e **não mude no meio da série**.
- **O que é deploy:** a versão (serviço, `env=prod`, `sha`) passou a servir tráfego de produção; 1 evento por (serviço, sha, execução). Não contam: staging, re-run do mesmo workflow, cada job de uma matrix, build sem promoção.
- **Agregação:** reporte por serviço. Somar dezenas de Lambdas/ECS e comparar com um time de um serviço único infla a frequência.
- **Rollback não é "deploy bom":** registre `tipo=rollback`; ele entra no CFR e fica fora do numerador de frequência.
- **Config, flag e IaC:** classifique por `categoria`; virar flag é release, não deploy (separar deploy de release). Decida se `config`/`iac` entram e mantenha.
- **Janela de mudança:** em banco a frequência é limitada por política; reporte também "deploys por janela" e "commits prontos aguardando janela".
- **Lead time e squash merge:** o squash apaga o horário dos commits originais. Use os commits do PR (`gh pr view --json commits`) ou `compare` entre dois SHAs de deploy; senão você mede só merge → deploy. Use `committer date`, não `author date`.
- **CFR sem incidente registrado é CFR zero falso:** cobertura de registro é pré-condição; auditar quantos rollbacks/hotfixes não têm ticket.
- **Atribuição:** falha de provedor ou de dependência externa sem deploy causador (`deploy_sha: null`) fica fora do CFR e dentro do recovery de confiabilidade.
- **Canary revertido automaticamente** serviu tráfego: `revertido` entra no CFR e no relatório separado "escapou para 100% ou não".
- **Recovery:** abre na detecção (alarme/CloudWatch), não na criação tardia do ticket; fecha no serviço restaurado, não no post-mortem. Mediana e percentil alto, nunca só média; reporte `n`.
- **Amostra pequena:** com `n` baixo a mediana oscila; reporte `n` ao lado de cada número e não compare períodos de `n` muito diferentes.

## Como medir neste repositório (fontes por métrica)
Contexto: GitHub Actions e a API do GitHub dão commits, PRs e deployments; CloudWatch/CodeDeploy dão o evento terminal do deploy e os alarmes.

| Métrica | Fonte | Como |
|---|---|---|
| Frequência | evento `deploy` (job final do workflow de deploy, ou EventBridge do CodeDeploy, state `SUCCESS`) | contar `resultado=sucesso`, `env=prod`, por serviço e semana |
| Lead time | `commits_ts[]` do deploy + `ts` do deploy | `gh api repos/{o}/{r}/compare/{sha_ant}...{sha}` lista os commits entre dois deploys; `ts_deploy − committer.date` |
| CFR | `deploy` + `rollback` + `incidente_aberto.deploy_sha` | deploys com causa ÷ deploys que serviram tráfego |
| Recovery | `incidente_aberto` → `incidente_fechado` | diferença de `ts` por `id`; ou alarme CloudWatch `ALARM` → `OK` |
| Confiabilidade | SLI no CloudWatch/Prometheus | % de janelas dentro do SLO; error budget restante |

- Permissões do job coletor (contrato): `contents: read`, `deployments: read`, `pull-requests: read`; sem token de longa duração (OIDC/WIF, ver `references/ci-cd.md`).
- CloudWatch Logs Insights serve de consulta quando o evento nasce no log: `fields @timestamp, servico, sha | filter tipo = "deploy" and env = "prod"`.
- Decomponha o lead time em etapas (PR aberto → merge → pipeline verde → aprovação/GMUD → janela → deploy): o maior trecho é o gargalo; em banco costuma ser espera, não build.

## Consulta de exemplo — JSONL → quatro métricas
Contexto: janela de 4 semanas, um serviço por arquivo; adapte `env` e `servico` antes de agregar.

```python
import json, sys, statistics as st
from datetime import datetime, timedelta
def t(s): return datetime.fromisoformat(s.replace("Z", "+00:00"))
def pct(xs, q): xs = sorted(xs); return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else None
ev = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
fim = max(t(e["ts"]) for e in ev); ini = fim - timedelta(weeks=4)       # janela da linha de base
dep = [e for e in ev if e["tipo"] == "deploy" and e["env"] == "prod" and e.get("categoria", "codigo") == "codigo"
       and ini <= t(e["ts"]) <= fim]
ok = [d for d in dep if d["resultado"] == "sucesso"]                    # chegou a 100%
serviu = [d for d in dep if d["resultado"] in ("sucesso", "revertido")]  # serviu tráfego
lead = [(t(d["ts"]) - t(c)).total_seconds() / 3600 for d in ok for c in d["commits_ts"]]  # horas
causa = {e["deploy_sha"] for e in ev if e["tipo"] in ("rollback", "incidente_aberto") and e.get("deploy_sha")}
ruins = {d["sha"] for d in serviu if d["resultado"] == "revertido"} | causa
aberto = {e["id"]: e for e in ev if e["tipo"] == "incidente_aberto" and e.get("deploy_sha")}
rec = [(t(f["ts"]) - t(aberto[f["id"]]["ts"])).total_seconds() / 3600
       for f in ev if f["tipo"] == "incidente_fechado" and f["id"] in aberto]
print({"n_deploys": len(ok), "deploys_por_semana": len(ok) / 4,
       "lead_h_p50": st.median(lead) if lead else None, "lead_h_p90": pct(lead, .9),
       "cfr": sum(d["sha"] in ruins for d in serviu) / len(serviu) if serviu else None,
       "recovery_h_p50": st.median(rec) if rec else None, "n_incidentes": len(rec)})
```

- Fórmulas: frequência = deploys `sucesso` ÷ semanas · lead time = `ts_deploy − committer_date` por commit · CFR = deploys com causa ÷ deploys que serviram tráfego · recovery = `fechado.ts − aberto.ts`.
- Rode com `python -I` sobre uma cópia do JSONL; o resultado entra no relatório com a **consulta registrada** (hash do script + janela + `n`).

## Faixas por nível — a estrutura, sem limiares
Contexto: os relatórios agrupam equipes em níveis (Elite, High, Medium, Low) e publicam, por métrica, a faixa de cada nível; a estrutura se repete, os valores não.

| Nível | Frequência de deploy | Lead time | CFR | Recovery |
|---|---|---|---|---|
| Elite | <ler na edição citada> | <ler na edição citada> | <ler na edição citada> | <ler na edição citada> |
| High | <ler na edição citada> | <ler na edição citada> | <ler na edição citada> | <ler na edição citada> |
| Medium | <ler na edição citada> | <ler na edição citada> | <ler na edição citada> | <ler na edição citada> |
| Low | <ler na edição citada> | <ler na edição citada> | <ler na edição citada> | <ler na edição citada> |

- Os limiares **mudam entre edições**; o número de níveis e seus nomes também variaram. Escreva sempre: "Accelerate State of DevOps Report, DORA/Google Cloud, <ano>, p. <n>"; limiar que o agente não leu na edição recebe `<ler na edição citada>` até um humano o ler.
- Posicione **cada métrica** na faixa da edição; não calcule um "nível geral" por média. Níveis servem para conversar com a liderança, não para definir a meta.

## Metas por nível — escolher o próximo passo a partir da própria medição
Contexto: a meta nasce da linha de base do time, não da tabela do relatório; o relatório só dá nome ao patamar.
1. **Linha de base ≥ 4 semanas** contínuas, por serviço, em `docs/dora-baseline.md`: consulta, `n`, mediana, p90 e o intervalo semanal (mínimo–máximo). Sem 4 semanas, não há meta.
2. **Gargalo primeiro:** decomponha o lead time; ataque a maior parcela. Uma métrica por trimestre, no máximo duas.
3. **Meta relativa:** "mediana das 4 semanas seguintes fora do intervalo semanal da baseline, na direção desejada". O nome do nível da edição citada acompanha, mas não é o alvo.
4. **Guarda-corpo:** vazão não sobe às custas de estabilidade; CFR e recovery não pioram além do pior valor semanal da baseline.
5. **Revisão trimestral** com os mesmos scripts; mudou a definição de evento = nova baseline, não continuação.
6. Métrica é do time, nunca de pessoa; não ranquear squads (Lei de Goodhart: virou meta individual, vira número maquiado).

## Ligação com o harness
Contexto: a Squad AI já tem telemetria própria; DORA não a substitui nem escreve nela.
- `scripts/relatorio_entrega.py` mede **custo em tokens por entrega do harness**, não DORA. Reuse o desenho: JSONL append-only, `ts` UTC, mediana e p95 por grupo, sem ids no relatório por padrão. `scripts/relatorio_dora.py` (Camada 0, 11/10/2026) implementa a consulta abaixo por serviço — `python -I scripts/relatorio_dora.py dora/eventos.jsonl [--semanas 4] [--fim ISO] [--categorias codigo,config] [--total] [--json]` — e imprime o `sha256` do próprio script como consulta registrada; testes em `tests/test_relatorio_dora.py`.
- `memory/sli.jsonl` só aceita escritores MCP, scripts da Camada 0 e humano (ver `memory/sli-schema.md § 4`); por isso `dora/eventos.jsonl` é arquivo próprio, com o mesmo contrato de nulos.
- Incidente que entrou no CFR vira lição em `memory/error_ledger.jsonl` (via `aprendizado-continuo`, gated); módulo com defeito registrado em 90 dias dispara mutação no GATE 2 (ver `verificacao-loop § GATE 2 em dois tamanhos`).
- Coleta automatizada e relatório semanal: `references/observabilidade.md § DORA Metrics` (workflow, Step Summary) — aponte, não duplique.

## Oráculo — como provar que foi feito
Contexto: o GATE 2 aceita número DORA só quando há consulta executável por trás; opinião e slide não contam.
- As quatro métricas saem de `dora/eventos.jsonl` por script versionado; o relatório cita a **consulta** (hash/caminho), a janela (≥ 4 semanas) e `n`. Número de prosa, de slide ou de memória reprova.
- `python -I scripts/relatorio_dora.py dora/eventos.jsonl` termina com exit 0 e imprime as métricas com `n` e o `sha256` do script; rodar duas vezes sobre o mesmo arquivo dá o mesmo resultado (teste de determinismo em `tests/test_relatorio_dora.py`).
- Faixa/nível citado traz (relatório, editor, ano, página); toda marca `<ler na edição citada>` é resolvida por humano em `docs/dora-baseline.md`.
- Meta registrada com baseline, intervalo semanal e guarda-corpo; a revisão seguinte compara contra o intervalo, não contra o relatório.

## Anti-padrões
Contexto: erros recorrentes de medição e de meta que tornam o número DORA inútil ou enganoso.
- **Número de memória:** limiar do relatório citado sem edição, ano e página.
- **Dashboard de vaidade:** gráfico sem consulta registrada nem `n`.
- **Frequência por soma:** somar todos os serviços para parecer Elite.
- **Rollback como deploy:** inflar frequência com reversões.
- **CFR zero falso:** não registrar incidente para não "sujar" a métrica.
- **Meta copiada do relatório:** perseguir a faixa da tabela em vez de superar a própria linha de base.
- **Média do MTTR:** um incidente longo é escondido (ou domina) a média; use mediana e percentil.
- **Métrica como avaliação individual:** vira jogo e corrompe o dado.

## Checklist de banco
Contexto: condições de banco para medir e publicar métricas de entrega sem violar regulação, segregação ou sigilo.
- [ ] Regulatório: definição de "falha" e "incidente" alinhada ao processo de gestão de incidentes/risco operacional vigente (confirmar com Compliance/Risco).
- [ ] Janela de mudança: lead time decomposto, com a espera por GMUD/janela como trecho próprio.
- [ ] Segregação de ambientes: só `env=prod` conta; staging e homologação ficam fora do numerador.
- [ ] Dados sensíveis: eventos sem dados de cliente, sem segredo e sem URL interna; `id` de ticket apenas.
- [ ] Trilha de auditoria: `dora/eventos.jsonl` append-only; correções por nova linha; script versionado e revisado por PR.
- [ ] Baseline ≥ 4 semanas arquivada antes de qualquer meta; revisão trimestral com aprovação humana.
