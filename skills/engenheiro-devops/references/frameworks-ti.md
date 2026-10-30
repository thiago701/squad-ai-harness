# engenheiro-devops · Frameworks de TI × DevOps em banco
> Quando carregar: responder a auditoria ou gestão de mudanças; enquadrar o pipeline como mudança padrão/normal/emergencial; montar o dossiê para o CAB; definir janela, segregação de funções, SLO e error budget; ligar incidente e problema ao postmortem e ao `error_ledger`.

## Como ler os três frameworks
Aqui os frameworks aparecem pelo nome das práticas, sem citar cláusulas; a redação exata das exigências vem da política interna do banco e deve ser confirmada lá. Eles pedem um resultado de controle (mudança autorizada, testada, reversível e rastreável); DevOps entrega esse resultado por automação e evidência gerada, e onde o banco exige reunião ou aprovação humana, o pipeline prepara o dossiê.
- **ITIL 4:** práticas Change enablement, Release management, Deployment management, Incident management, Problem management, Service level management e Service configuration management.
- **COBIT 2019 (ISACA):** objetivos **BAI06 Managed IT Changes**, **BAI07 Managed IT Change Acceptance and Transitioning**, **BAI10 Managed Configuration**, **DSS02 Managed Service Requests and Incidents** e **DSS03 Managed Problems** (rótulos conforme *COBIT 2019 Framework: Governance and Management Objectives*, ISACA, 2018).
- **SRE do Google:** livros *Site Reliability Engineering* e *The Site Reliability Workbook*: SLI, SLO, error budget, postmortem sem culpa.

## Tipos de mudança e o pipeline como "mudança padrão"
O ITIL 4 (Change enablement) distingue mudança padrão, normal e emergencial; o pipeline gated da Squad consegue ser o procedimento de uma mudança padrão auditável quando as condições abaixo são verificáveis.

| Tipo | Quando | Autorização | O que o pipeline faz |
|---|---|---|---|
| Padrão (pré-aprovada) | repetível, baixo risco, procedimento conhecido | o **modelo** é aprovado uma vez e revalidado; cada instância passa pelo GATE 2 humano | roda os gates e gera o dossiê sozinho; sem CAB por instância |
| Normal | risco ou impacto fora do modelo | autoridade de mudança (CAB) por instância | gera o dossiê, espera a decisão e a janela; deploy só com aprovação registrada |
| Emergencial | restaurar serviço ou fechar risco crítico | aprovador de emergência nominal | GATE 2 humano e bloqueio por achado crítico continuam; evidência completa no prazo da política; postmortem obrigatório |

**Condições para o pipeline valer como modelo de mudança padrão** (todas checáveis):
1. Pipeline versionado, com `.github/workflows/`, `ops/` e `contracts/` sob CODEOWNERS.
2. Gates fail-closed: `verificacao-loop` PRONTO e `05b-veracode.md` sem achado crítico.
3. Rollback definido e testado (ver `references/principios-e-deploy.md § 6.2 Automated Rollback com CloudWatch Alarms`).
4. Aprovação humana nominal no GATE 2, de pessoa diferente do autor.
5. Dossiê gerado automaticamente (§ CAB e janela de mudança).
6. Critérios de exclusão objetivos e revisão periódica do modelo; revogar se incidentes ligados a mudanças padrão subirem (medir: incidentes com `change_ref` / deploys no período).

**Critérios de exclusão (a mudança vira normal):** tier `large`; gatilho de segurança disparado (auth, input, queries, cripto, secrets); mudança irreversível de dados sem expand-contract; IAM, rede ou infraestrutura compartilhada; orçamento de erro esgotado (§ SRE). Achado crítico não é critério de exclusão: `achados_criticos > 0` torna o `commit` PROIBIDO em qualquer tipo, emergencial incluído. Esta classificação é proposta a validar com a gestão de mudanças; o enquadramento oficial é do banco.

## CAB e janela de mudança — o dossiê que o pipeline entrega
O CAB (no ITIL 4, o papel de autoridade de mudança, delegável conforme o risco) decide com evidência, não com apresentação. O dossiê é o `99-relatorio.md` mais os artefatos que ele aponta; cada campo tem fonte e nenhum fica "a definir".

| Campo do dossiê | Fonte no pipeline |
|---|---|
| Identificação (repo, PR, SHA, slug) | PR e `.claude/pipeline/<slug>/` |
| Risco e tier | `00-preflight.md` (tier por sinal) |
| Objetivo, escopo, critérios de aceite | `01-intake.md` |
| Plano e veredito do GATE 1 | `03-plano.md` e `03-plano.veredito.json` |
| Evidência de teste | relatório do `verificacao-loop` (PRONTO, exit code), cobertura medida, `06-review.md` |
| Segurança | `05-seguranca.md` (se gatilho), `05b-veracode.md`, SBOM CycloneDX |
| Rollback | seção do plano e evidência do teste de rollback |
| Aprovador (GATE 2) | login nominal e timestamp, no `99-relatorio.md` |
| Janela | início e fim previstos e reais (deployment `in_progress` -> `success`) |
| Resultado | desfecho, SLI após o deploy, custo real vs orçado |

Se o template do `99-relatorio.md` ainda não tem esses campos, acrescentá-los é a mudança de menor custo (com GATE).

A janela é decidida pelo calendário de mudanças do banco, não pelo time. O pipeline só a aplica, lendo variáveis do ambiente do GitHub; bloqueios (fechamento, datas de pico) ficam em lista versionada mantida por quem é dono do calendário.

```yaml
# Job de pré-deploy: bloqueia fora da janela. INI/FIM (HHMM) vêm de variáveis do environment, não do código.
# Bloqueios por data (fechamento, picos) entram como segunda checagem sobre a lista versionada (omitida aqui).
- name: Verificar janela de mudança
  env:
    TZ: America/Sao_Paulo
    INI: ${{ vars.JANELA_INICIO }}
    FIM: ${{ vars.JANELA_FIM }}
  run: |
    agora=$(date +%H%M)
    if [ "$INI" -le "$FIM" ]; then   # janela no mesmo dia
      { [ "$agora" -ge "$INI" ] && [ "$agora" -le "$FIM" ]; } && ok=1 || ok=0
    else                             # janela cruza a meia-noite
      { [ "$agora" -ge "$INI" ] || [ "$agora" -le "$FIM" ]; } && ok=1 || ok=0
    fi
    [ "$ok" = 1 ] || { echo "Fora da janela ($INI-$FIM): deploy bloqueado"; exit 1; }
```
O deploy de produção usa `environment: <ambiente-prod>` com revisores obrigatórios e a opção de impedir autoaprovação; a aprovação fica no histórico do run.

## Segregação de ambientes e de funções
Quem codifica não aprova produção, e cada ambiente tem suas próprias chaves. No harness, o agente de IA conta como parte de quem codifica: o humano que aprova o GATE 2 não é quem dirigiu o agente nem o autor do PR.

| Função | Pode | Não pode |
|---|---|---|
| Autor (humano + agente) | abrir PR, rodar pipeline em dev/hom | aprovar o próprio PR, aprovar ou disparar deploy em produção |
| Revisor técnico | aprovar PR de outro autor | aprovar PR que escreveu |
| Aprovador de produção (GATE 2) | aprovar o environment de produção | ser o autor da mudança |
| Identidade do pipeline (OIDC) | assumir a role do **próprio** ambiente | usar credencial de outro ambiente; ter humano com chave de produção |
| Administrador da plataforma | alterar workflows, roles, proteção de branch | fazê-lo sem revisão de outro administrador |

- **Por ambiente:** conta AWS (ou equivalente) e role separadas; confiança OIDC restrita por `sub` (ver `references/ci-cd.md § Workload Identity Federation — Zero credenciais long-lived na CI`); secrets e variáveis no environment, nunca no repositório.
- **Branch protection:** revisão obrigatória, aprovação invalidada por push novo, revisão de code owners, checks obrigatórios, sem force push.
- **Break-glass:** acesso emergencial com justificativa, prazo de expiração, registro e revisão posterior.
- **Dados:** ambiente não produtivo sem dado real de cliente (sintético ou mascarado).

## Incidente e problema — ligação com postmortem e error_ledger
Incident management restaura o serviço o mais rápido possível; Problem management busca a causa e reduz a recorrência. O elo entre os dois é o postmortem (ver `references/cultura-devops-aprendizagem.md § Postmortem sem culpa`).
1. **Detecção e abertura:** alerta (ver `references/observabilidade.md`); incidente com id, severidade pela política do banco e `change_ref` (PR/SHA do deploy suspeito).
2. **Mitigação:** rollback antes de diagnóstico profundo, quando houver mudança recente.
3. **Fechamento e postmortem:** ações com dono e prazo; lição no `memory/error_ledger.jsonl`.
4. **Problema:** quando o mesmo `error_id` ou padrão reaparece (limite de recorrências declarado pelo time), abre-se registro de problema com erro conhecido, contorno e ação permanente; mudança permanente segue § Tipos de mudança.
5. **Medidas:** tempo de recuperação (da detecção ao serviço restaurado, não ao postmortem), falha de mudança (incidentes com `change_ref` / deploys que serviram tráfego) e recorrência (lições com `error_id` repetido). Definições e armadilhas: `references/dora-metrics.md § Armadilhas de medição — o que conta e o que não conta`.

## SRE — SLI, SLO e error budget como ponte entre controle e velocidade
O error budget transforma "pode mudar?" numa conta em vez de uma disputa: enquanto há orçamento, a mudança padrão flui; quando acaba, o controle aperta sozinho.
- **SLI:** eventos bons / eventos válidos na janela. **SLO:** alvo do SLI na janela, escolhido pelo dono do serviço. **Error budget:** (1 - SLO) x eventos válidos na janela móvel.
- **Onde medir:** Spring Boot via Micrometer/Prometheus; Lambda via CloudWatch (`Invocations`, `Errors`); ALB via CloudWatch (`RequestCount`, `HTTPCode_Target_5XX_Count`). SLI de latência exige histograma habilitado.

```promql
# SLI de disponibilidade (Grafana: $__range = janela do SLO; no Prometheus puro, trocar pela janela do SLO)
sum(increase(http_server_requests_seconds_count{application="<svc>",status!~"5.."}[$__range]))
/ sum(increase(http_server_requests_seconds_count{application="<svc>"}[$__range]))
```
```python
#!/usr/bin/env python3
# Uso: orcamento_erro.py --bons <n> --total <n> --slo <0..1>
# bons/total = SLI REAL da janela do SLO (consulta salva com timestamp); nunca digitar estimativa.
import argparse, sys
p = argparse.ArgumentParser()
p.add_argument("--bons", type=float, required=True)    # eventos bons na janela móvel
p.add_argument("--total", type=float, required=True)   # eventos válidos na mesma janela
p.add_argument("--slo", type=float, required=True)     # alvo definido pelo dono do serviço
a = p.parse_args()
if a.total <= 0 or a.slo >= 1:
    print("SLI indefinido (janela sem eventos) ou SLO=1 (sem orçamento)"); sys.exit(2)
orcamento = (1 - a.slo) * a.total      # eventos ruins tolerados na janela
gasto = a.total - a.bons               # eventos ruins observados
restante = orcamento - gasto
print(f"SLI={a.bons / a.total:.6f} SLO={a.slo} orcamento={orcamento:.0f} gasto={gasto:.0f} "
      f"restante={restante:.0f} consumido={gasto / orcamento:.1%}")
sys.exit(0 if restante > 0 else 1)     # exit 1 = esgotado -> política de orçamento entra
```
Aritmética ilustrativa (não é medição): com SLO de 0,999 e 2.000.000 de eventos válidos na janela, o orçamento é 2.000 eventos ruins.

**Quando o orçamento acaba** (política escrita e acordada antes, em `docs/slo/<servico>.md`: SLI, SLO, janela, dono, política):
- mudanças de funcionalidade congelam; seguem correção de confiabilidade, segurança e rollback;
- mudança padrão passa a normal (autoridade de mudança) enquanto o restante for <= 0;
- o consumo gera postmortem, mesmo sem incidente único;
- saída: orçamento positivo na janela móvel, ou exceção assinada pelo dono do serviço e pelo responsável de risco, com prazo.
Confiabilidade também é a dimensão operacional do DORA (`references/dora-metrics.md`). Alertar por velocidade de consumo (burn rate, janelas curta e longa) está em *The Site Reliability Workbook* (O'Reilly, 2018), cap. 5 "Alerting on SLOs", Tabela 5-8, parâmetros sugeridos para SLO de 99,9%: página com burn rate 14,4 (janela longa 1 h, curta 5 min, 2% do orçamento), página com burn rate 6 (6 h / 30 min, 5%) e ticket com burn rate 1 (3 dias / 6 h, 10%) — ponto de partida a adaptar ao SLO do serviço, não regra.

## Controles que o auditor pede
Auditoria quer provar quem fez o quê, com qual autorização e se dá para refazer; cada controle abaixo tem evidência gerada, não declarada.
- **Trilha:** PR, reviews, run, deployment e `99-relatorio.md` ligados pelo SHA, com identidade e timestamp.
- **Aprovação nominal:** conta pessoal via SSO, nunca conta compartilhada; bot e agente de IA não aprovam GATE. Evidência: review `APPROVED` e `gh api repos/<org>/<repo>/actions/runs/<id>/approvals` (histórico de aprovação do environment).
- **Reprodutibilidade do build:** mesmo SHA, mesmo artefato (o G10 de `quality/quality-gates.md` exige build reproduzível): Maven Wrapper, versões pinadas, imagem base por digest, ações de terceiros por SHA quando a política exigir, SBOM CycloneDX e digest do artefato registrados no dossiê (ver `references/devsecops.md § SBOM CycloneDX e supply chain`).
- **Retenção:** a retenção padrão de logs e artefatos do Actions é configurável e pode ser menor que a exigida; exportar o dossiê (relatório, vereditos, SBOM, aprovações) para o repositório de retenção do banco (ex.: bucket com Object Lock, escrita só pela role do pipeline), com hash SHA-256 registrado. Retenção padrão do GitHub Actions: 90 dias, configurável de 1 a 90 dias em repositório público e de 1 a 400 em privado (GitHub Docs, "Configuring the retention period for GitHub Actions artifacts and logs", consultado em 11/10/2026). Prazo do dossiê: o da política de retenção do banco (entrada humana; costuma superar 400 dias — por isso a exportação).

## Tabela — pedido do framework -> como o pipeline gated atende
Mapa entre o que cada framework pede e o artefato da Squad que prova; a última linha lista o que o harness não cobre.

| Pedido (framework · prática) | Como o pipeline atende | Artefato / oráculo |
|---|---|---|
| Mudança avaliada e autorizada antes de implementar (ITIL 4 Change enablement · COBIT BAI06) | GATE 1: humano aprova o plano; `gate_aprovado` sem aprovação humana = `REQUER_GATE_HUMANO` | `03-plano.md`, `03-plano.veredito.json` |
| Avaliação de risco e impacto | tier por sinal; gatilho de segurança | `00-preflight.md` |
| Teste e aceitação antes de produção (Release/Deployment management · COBIT BAI07) | GATE 2: `verificacao-loop` PRONTO (exit code) e aprovação humana | relatório do gate, `06-review.md` |
| Segurança no ciclo de desenvolvimento | lente `rev-veracode` fail-closed; crítico bloqueia `commit` | `05b-veracode.md`, `validar_transicao` -> PROIBIDA |
| Segregação de funções | `aprovacao_humana` obrigatória; autor != aprovador imposto no GitHub | `contracts/pipeline-state-machine.json`; review `APPROVED` de outro login |
| Reversão planejada | rollback exigido no plano (GATE 1; G10 de `quality/quality-gates.md`) e testado antes do GATE 2 | seção do plano; execução do rollback |
| Rastreabilidade ponta a ponta | "o pipeline não carrega estado oculto": tudo em artefato | `.claude/pipeline/<slug>/01..99` |
| Revisão pós-implementação | relatório final e REMEMBER (Fase 7.5) | `99-relatorio.md`, `memory/episodes.jsonl` |
| Incidentes e problemas (ITIL 4 · COBIT DSS02/DSS03) | postmortem e lição que o preflight devolve às próximas entregas | `memory/error_ledger.jsonl` |
| Configuração e reprodutibilidade (Service configuration management · COBIT BAI10) | wrapper, versões pinadas, SBOM | SBOM CycloneDX, digest |
| Níveis de serviço (Service level management · SRE) | SLO e error budget como gate de pré-deploy | exit code de `orcamento_erro.py` |
| **Não coberto pelo harness** | decisão do CAB, calendário de janela, IAM de produção, retenção longa | processos do banco; o pipeline só consome (variáveis, revisores) e exporta evidência |

## Oráculo — como provar que foi feito
O GATE 2 executa os comandos abaixo sobre uma entrega real; "revisado e aprovado" não conta.
- **Checklist de mudança preenchido** a partir dos artefatos, sem campo "a definir".
- **Máquina de estados** devolve PERMITIDA só com aprovação humana e sem achado crítico (`contracts/validator.py`).
- **Aprovador diferente do autor** no PR da entrega.
- **Error budget** calculado de SLI real: `bons` e `total` saem da consulta salva em `evidencias/sli-<janela>.json` (`{consulta, ts, bons, total}`); o exit code de `orcamento_erro.py` é o oráculo (0 = há orçamento, 1 = esgotado).

```bash
D=.claude/pipeline/<slug>
for f in 00-preflight 01-intake 03-plano 05b-veracode 06-review 99-relatorio; do test -s "$D/$f.md" || echo "FALTA $f.md"; done
grep -n -i -E 'a definir|tbd|a preencher|<preencher>|n/a' "$D/99-relatorio.md" && echo "FALHA: campo aberto"
n=$(gh pr view <n> --repo <org>/<repo> --json author,reviews \
  --jq '.author.login as $a | [.reviews[]|select(.state=="APPROVED" and .author.login!=$a)]|length')
test "${n:-0}" -ge 1 || echo "FALHA: sem aprovação de outro autor"
python3 -X utf8 - <<'EOF'
from contracts.validator import validar_transicao as v
ok   = v("gate2_pendente", "gate_aprovado", aprovacao_humana=True,  achados_criticos=0)
sem  = v("gate2_pendente", "gate_aprovado", aprovacao_humana=False, achados_criticos=0)
crit = v("gate2_pendente", "gate_aprovado", aprovacao_humana=True,  achados_criticos=1)
assert (ok.transicao, sem.transicao, crit.transicao) == ("PERMITIDA", "REQUER_GATE_HUMANO", "PROIBIDA")
EOF
J=evidencias/sli-<janela>.json
python3 orcamento_erro.py --bons "$(jq .bons $J)" --total "$(jq .total $J)" --slo <alvo>; echo "budget exit=$?"
```

## Anti-padrões
- **CAB teatro:** reunião que aprova sem ler evidência; o dossiê existe mas ninguém o abre.
- **Mudança padrão por decreto:** classificar como padrão sem o modelo aprovado nem critérios de exclusão.
- **Autoaprovação disfarçada:** o autor aprova por outra conta, ou o bot aprova o GATE.
- **Janela de papel:** janela documentada, mas o pipeline não a verifica.
- **Dossiê pós-fato:** montar a evidência depois do deploy, de memória.
- **SLO decorativo:** alvo publicado sem consulta que o meça e sem política para quando o orçamento acaba.
- **Emergência permanente:** todo deploy vira "emergencial" para fugir do CAB.
- **Evidência efêmera:** confiar na retenção padrão do Actions para um prazo regulatório.

## Checklist de banco
- [ ] Regulatório: tipo de mudança e modelo aprovados pela gestão de mudanças; normas aplicáveis (ex.: Res. CMN 4.893/2021, LGPD Lei 13.709/2018) confirmadas com Compliance.
- [ ] Janela de mudança: deploy de produção verificado pelo pipeline contra a janela e os bloqueios vigentes; mudança normal só após decisão registrada.
- [ ] Segregação de ambientes e funções: autor != aprovador, role OIDC por ambiente, CODEOWNERS no pipeline, break-glass com prazo e revisão.
- [ ] Dados sensíveis: dossiê sem dado de cliente, PII, segredo, URL ou host interno; ambientes não produtivos sem dado real.
- [ ] Trilha de auditoria: identidade nominal, SHA e digest ligados; dossiê exportado para retenção e hash registrado; todo deploy em produção com aprovação humana explícita.
