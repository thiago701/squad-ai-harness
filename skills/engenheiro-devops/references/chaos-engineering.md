# engenheiro-devops · Chaos Engineering
> Quando carregar: validar resiliência de infra com injeção de falha, desenhar experimento ou GameDay, escolher entre AWS Fault Injection Service / Chaos Toolkit / LitmusChaos / Gremlin, definir raio de impacto e critério de abortar, ou registrar lições de um experimento.

Chaos engineering não é "quebrar coisas": é **testar uma hipótese sobre o estado estável** do sistema, com raio mínimo e
saída de emergência provada antes. No banco, só em pré-produção/sandbox até existir política explícita (ver "Regras do banco").

## Ciclo do experimento
Contexto: seis passos, cada um com um artefato verificável; pular um passo invalida o experimento.

| # | Passo | Artefato que prova |
|---|---|---|
| 1 | Hipótese de estado estável | frase "dado/quando/esperamos" + SLI com tolerância declarada |
| 2 | Experimento | template (FIS) ou arquivo (Chaos Toolkit/Litmus) versionado no repo |
| 3 | Raio de impacto mínimo | alvo único e seleção limitada (ex.: 1 task), ambiente e tag explícitos |
| 4 | Critério de abortar | alarme de aborto + parada manual, **testados antes** |
| 5 | Observação | painel/queries do SLI antes, durante e depois, com timestamps |
| 6 | Aprendizado | relatório + linha em `memory/error_ledger.jsonl` + ação com dono e prazo |

## Hipótese e estado estável medido
Contexto: "estável" é um conjunto de SLIs com tolerância, medidos antes da injeção — não uma impressão de que está tudo bem.
- Template: *Dado* o serviço `<svc>` em `<ambiente>` com `<SLI>` dentro de `<tolerância>`, *quando* injetarmos `<falha>` em `<alvo>` por `<duração>`,
  *esperamos* que `<SLI>` permaneça dentro da tolerância **porque** `<mecanismo: retry com backoff, circuit breaker, multi-AZ...>`.
- SLIs típicos: latência p99, taxa de erro 5xx, saturação (CPU/conexões), métrica de negócio. Origem: Micrometer/Prometheus/CloudWatch
  (`references/observabilidade.md`). Sem SLI medido antes, não há experimento.
- A tolerância é declarada **antes** (ex.: reutilize o limiar dos alarmes de `principios-e-deploy.md` § 6.2), nunca ajustada depois do resultado.

## Raio de impacto e critério de abortar
Contexto: o experimento precisa poder parar sozinho (alarme) e por decisão humana (kill switch), e ambos precisam ter sido exercitados.
- **Escada de raio:** 1 task/pod → 1 instância → 1 serviço → 1 AZ. Só suba um degrau depois de o anterior confirmar a hipótese.
- **Aborto automático:** condição de parada ligada a alarme (no FIS, *stop conditions* apontando para alarme do CloudWatch).
  Reaproveite os alarmes de erro/latência do canary. **Aborto manual:** `aws fis stop-experiment --id <id>` ou "Halt" no Gremlin.
- **Teste do abort antes do experimento real:** execute um experimento inócuo em sandbox, force o alarme para `ALARM` e confirme a parada.
- **Timebox:** toda injeção tem duração máxima; terminou o tempo, o rollback roda (Chaos Toolkit `rollbacks`, `desfazer` do runbook).

## Ferramentas
Contexto: escolha pelo plano de controle e pelo que o banco permite sair da rede; versões ficam no registro de dependências, não aqui.

| Ferramenta | Quando escolher | Atenção |
|---|---|---|
| AWS Fault Injection Service (FIS) | Lambda/ECS/EC2/RDS na AWS; IAM e CloudWatch nativos; stop conditions | role mínima por experimento; confirmar ações com `aws fis list-actions` |
| Chaos Toolkit | experimento declarativo e portátil (hipótese, método, rollbacks) rodando no CI | precisa de extensão/driver aprovado; ações via `process`/`python` |
| LitmusChaos | Kubernetes (ChaosEngine, probes de verificação) | só vale se houver cluster; RBAC restrito ao namespace |
| Gremlin | catálogo amplo de ataques e "Halt" central | agente fala com plano de controle externo: **exige aprovação de egress/segurança** |

```json
{
  "description": "hipotese-001: parar 1 task em hml nao viola o SLI de erro",
  "targets": {"tasks-alvo": {"resourceType": "aws:ecs:task",
      "resourceTags": {"servico": "<svc>", "chaos": "permitido"}, "selectionMode": "COUNT(1)"}},
  "actions": {"parar-task": {"actionId": "aws:ecs:stop-task", "targets": {"Tasks": "tasks-alvo"}}},
  "stopConditions": [{"source": "aws:cloudwatch:alarm", "value": "<arn-do-alarme-de-aborto>"}],
  "roleArn": "<arn-da-role-fis-minima>",
  "tags": {"experimento": "chaos-001", "ambiente": "hml"}
}
```

```json
{
  "title": "hipotese-002: latencia da dependencia nao derruba o health",
  "steady-state-hypothesis": {"title": "servico saudavel", "probes": [
    {"type": "probe", "name": "health-200", "tolerance": 200,
     "provider": {"type": "http", "url": "https://<endpoint-hml>/actuator/health", "timeout": 3}}]},
  "method": [{"type": "action", "name": "injetar-latencia", "pauses": {"after": 120},
     "provider": {"type": "process", "path": "<script-aprovado>", "arguments": "--delay-ms 300"}}],
  "rollbacks": [{"type": "action", "name": "remover-latencia",
     "provider": {"type": "process", "path": "<script-aprovado>", "arguments": "--reset"}}]
}
```

## Catálogo de falhas
Contexto: sete famílias de falha para começar a escrever hipóteses de resiliência; os nomes de ação mudam entre ferramentas e versões, a pergunta não.

| Falha | Injeção (exemplos) | Pergunta que responde |
|---|---|---|
| Latência / rede | FIS (ações de rede de ECS/EC2), Litmus `pod-network-latency`/`loss`, Gremlin Latency/Packet Loss | timeouts, retry com backoff+jitter e circuit breaker se comportam? |
| Instância / pod / task | FIS parar instância/task, Litmus `pod-delete`, Gremlin Shutdown | probes, auto-recovery e graceful shutdown (`health-probes-graceful-shutdown.md`) seguram? |
| Dependência externa | resposta 5xx/lenta via stub, FIS injeção de erro de API/Lambda, Gremlin Blackhole | fallback e degradação existem? reprocessamento é idempotente (`saga-pattern.md`)? |
| AZ | FIS desconectividade por subnet/AZ (conferir cenários da biblioteca FIS) | capacidade e multi-AZ sobrevivem à perda de uma AZ? |
| DNS | Litmus DNS chaos, Gremlin DNS | TTL, cache negativo e retentativa estão corretos? |
| Esgotamento de recursos | FIS/SSM stress de CPU, Litmus `pod-cpu-hog`/`memory-hog`/`disk-fill`, Gremlin CPU/Memory/Disk | limites, autoscaling, backpressure e pool de conexões reagem? |
| Relógio | Gremlin Time Travel; em Java, `java.time.Clock` injetável em teste | JWT, TTL, certificado e chave de idempotência toleram deriva? |

## GameDay — roteiro de 2h
Contexto: GameDay é o experimento conduzido por pessoas, com papéis fixos; qualquer participante pode pedir abort, o Facilitador executa.

| Min | Bloco | Saída |
|---|---|---|
| 0–10 | Abertura: hipótese, escopo, raio, abort, janela, comunicação | plano confirmado pelo dono do serviço |
| 10–25 | Pré-voo: baseline do estado estável, **teste do abort**, rollback pronto | baseline e abort testado anexados |
| 25–70 | Experimento (um por vez); Observador narra desvios, Escriba marca horários | linha do tempo com timestamps |
| 70–85 | Recuperação: confirmar retorno ao estado estável | SLIs "depois" medidos |
| 85–105 | Repetição após correção ou segundo experimento da escada | comparação antes/depois |
| 105–120 | Retrospectiva: hipótese acertou? ações com dono e prazo | relatório + linha no `error_ledger` |

Papéis: **Facilitador** (conduz e executa o abort), **Operador** (injeta), **Observador** (mede), **Escriba** (registra), **Dono do serviço** (aprova escopo; ≠ Operador).

## Regras do banco
Contexto: produção de banco tem regulação e risco sistêmico; o padrão desta skill é conservador.
- **Somente pré-produção/sandbox** até existir política explícita aprovada por Risco/Segurança. Sem política, experimento em `prod` é recusado.
- **Janela declarada** (início/fim, chamado de mudança; dossiê em `references/frameworks-ti.md § CAB e janela de mudança`) e comunicação prévia; fora da janela, kill switch ligado.
- **Kill switch testado antes**; **dados sintéticos** (nunca cópia de produção); role mínima restrita por tag (`chaos=permitido`).
- Ferramenta com agente que sai da rede só com egress aprovado; credenciais via cofre/OIDC, nunca no repo.

## Relatório antes/depois e lição
Contexto: o relatório é o artefato que o GATE 2 confere; a lição vira memória operacional só depois de registrada.
```markdown
# CHAOS-<AAAA-MM-DD>-<nn> — <título>
Hipótese: dado <estado>, ao injetar <falha> em <alvo> por <duração>, <SLI> fica em <tolerância>.
Ambiente/janela: hml · <início>–<fim> · aprovado por <nome> (≠ operador) · abort testado em <execução>
| SLI (fonte/query) | Antes | Durante | Depois | Dentro da tolerância? |
|---|---|---|---|---|
| p99 (<query>) | <medido> | <medido> | <medido> | sim/não |
Confirmada? sim/não · Abortou? sim/não (motivo, horário) · Ações: <dono, prazo, ticket>
```
Lição: uma linha em `memory/error_ledger.jsonl` via `aprendizado-continuo`, no schema vigente do ledger (error_id, ts, categoria, linguagem, bug, diagnostico, causa_raiz, solucao, teste_preventivo, tags, status, origin, prescreen_ok); o formato completo está em `references/cultura-devops-aprendizagem.md § Aprendizagem no harness`:
`{"error_id":"CHAOS-<AAAA-MM-DD>-<nn>","ts":"<ISO-8601 UTC>","categoria":"infra","linguagem":"infra","bug":"<o que a hipótese não previu>","diagnostico":"<SLI que saiu da tolerância>","causa_raiz":"<fator de sistema>","solucao":"<correção + ticket>","teste_preventivo":"<experimento repetido verde>","tags":["GAMEDAY-<data>","<servico>"],"status":"ativo","origin":"chaos","prescreen_ok":true}`

## Oráculo — como provar que foi feito
- Relatório preenchido: hipótese, SLI **antes/durante/depois** com query e timestamp, tolerância declarada antes do experimento.
- Abort testado: em sandbox, `aws cloudwatch set-alarm-state --alarm-name <alarme-aborto> --state-value ALARM --state-reason "teste de abort"`
  durante um experimento inócuo e `aws fis get-experiment --id <id> --query 'experiment.state.status'` devolve `stopped`.
- Estado estável restaurado: SLIs "depois" dentro da tolerância do baseline (comparação por query, não por impressão).
- Lição registrada: `grep -c '"error_id":"CHAOS-' memory/error_ledger.jsonl` ≥ 1 para o id do experimento.
- Nenhum registro de experimento com `ambiente=prod` sem política citada.

## Anti-padrões
- **Caos de produção por coragem:** injetar em prod sem política, janela e abort provado.
- **Hipótese de fé:** "vai aguentar" sem SLI medido antes e sem tolerância declarada.
- **Abort de enfeite:** botão/alarme que nunca foi acionado em teste.
- **Raio total:** derrubar o serviço inteiro ou a AZ no primeiro experimento.
- **Tolerância móvel:** ajustar o limiar depois de ver o resultado para "passar".
- **GameDay sem escriba:** sem linha do tempo, não há aprendizado nem auditoria.
- **Lição órfã:** achado sem dono, prazo e linha no `error_ledger`.
- **Dado real no teste:** usar cópia de produção em vez de dados sintéticos.

## Checklist de banco
- [ ] Ambiente de pré-produção/sandbox segregado; produção só com política explícita citada no relatório.
- [ ] Janela de mudança registrada e comunicada; aprovador nominal ≠ operador.
- [ ] Kill switch e alarme de aborto testados antes; role de injeção com privilégio mínimo e escopo por tag.
- [ ] Dados sintéticos; nenhum dado sensível em logs do experimento.
- [ ] Trilha de auditoria: quem aprovou, quem injetou, quando, resultado e `correlation_id`.
- [ ] Impacto regulatório avaliado (ex.: continuidade de negócio) com Risco/Compliance quando tocar serviço crítico.
