# engenheiro-devops · CI, testes contínuos e CD maduros
> Quando carregar: desenhar ou endurecer pipeline além do básico; trunk-based development; testes de contrato; mutation testing no pipeline; flaky test; canary, blue-green ou ring com critério de promoção; feature flag; rollback automático; "delivery ou deployment?"; revisar o desenho de pipeline antes do GATE 1.

## Trunk-based development
Contexto: integração contínua de verdade é integrar no tronco várias vezes ao dia; a lista base de proteção de branch e o ciclo de flags já estão em `references/principios-e-deploy.md § Trunk-Based Development`, aqui entra o que falta: medir e impor.
- **Branches de vida curta:** o PR nasce, é revisado e entra no tronco no mesmo dia útil sempre que possível; trabalho incompleto entra **atrás de feature flag**, não em branch longa.
- **Regras no GitHub** (rulesets ou branch protection, versionadas e revisadas): exigir PR; checks obrigatórios; aprovação de quem **não** fez o último push (`Require approval of the most recent reviewable push`); revisão de CODEOWNERS; dispensar aprovações obsoletas; resolver conversas; bloquear force push e deleção; histórico linear ou merge queue (`Require merge queue`) quando o tronco recebe muitos PRs.
- **Meça a vida do PR** em vez de supor (mediana e p90 de `createdAt → mergedAt`):

```bash
gh pr list --state merged --limit 200 --json createdAt,mergedAt | jq -c \
  '[.[] | ((.mergedAt|fromdate)-(.createdAt|fromdate))/3600] | sort
   | {n: length, p50_h: .[length/2|floor], p90_h: .[(length*0.9)|floor]}'
```

- Tamanho de PR e idade de branch são metas **do time sobre a própria baseline** (`references/dora-metrics.md § Metas`); não copie limite de outro lugar.

## Pirâmide de testes e testes de contrato
Contexto: muitos testes unitários rápidos, menos de integração, poucos de ponta a ponta; entre serviços, o contrato substitui o E2E frágil. Comandos por stack: `verificacao-loop § Comandos por stack` (Java/Maven, Python, Go, Rust) — aqui só o desenho.
- **Unitário:** sem I/O, determinístico, roda no PR (impactado). **Integração:** Testcontainers ou equivalente, banco e mensageria reais. **E2E:** poucos, só caminhos de negócio críticos, em pré-produção.
- **Contrato guiado pelo consumidor (consumer-driven):** o consumidor declara o que usa; o provedor verifica no **próprio** pipeline antes de publicar.
  - **Pact:** o consumidor gera o arquivo de pacto; o provedor o verifica; `can-i-deploy` (Pact Broker/PactFlow CLI) responde se a versão é compatível com o que está em cada ambiente.
  - **Spring Cloud Contract:** contratos (DSL ou YAML) geram testes do provedor e *stubs* para o consumidor; indicado quando o provedor é Spring Boot e o time controla os dois lados.
  - Mensageria (SQS/SNS): o Pact cobre mensagens assíncronas com *Message Pact*, agnóstico de fila — testa a mensagem, não o broker (docs.pact.io, "How Pact works § Non-HTTP testing"); na matriz de suporte (docs.pact.io/roadmap/feature_support, consultada em 11/10/2026) Pact-JVM, Pact Python, Pact Go e Pact JS marcam "Y" e Pact Rust tem só suporte básico. O Spring Cloud Contract tem contratos de mensageria próprios.
- Regra: contrato quebrado **bloqueia o deploy do provedor**, não vira aviso. Mock escrito à mão pelo consumidor, sem verificação no provedor, não é contrato.

## Mutation testing no pipeline
Contexto: cobertura mede se o teste passou pelo código; mutação mede se ele **detecta** mudança de comportamento. Gatilhos, tetos e oráculos Go/Rust/Java/Python estão em `verificacao-loop § GATE 2 em dois tamanhos` e `§ Comandos por stack`; não duplique.
- **No PR (impactado):** só dispara por gatilho determinístico (D5): tier large, diff sensível (auth/input/queries/cripto/secrets) ou módulo com defeito no `memory/error_ledger.jsonl` nos últimos 90 dias. Escopo restrito às classes alteradas.
- **No nightly (completo):** mutação do repositório inteiro, resultado anexado ao relatório do `gate_runner.py` (`reports/gates.json`) com série histórica.
- **Java:** PIT via `org.pitest:pitest-maven:mutationCoverage`. O antigo goal `scmMutationCoverage` (só arquivos alterados no SCM) **não existe mais** no pitest-maven atual (código-fonte do master e pitest.org, consultados em 11/10/2026 — a integração com git passou ao plugin comercial arcmutate); para repetir análises mais rápido use `-DwithHistory` ou `historyInputFile`/`historyOutputFile` (pitest.org, "Maven Quick Start"), e limite o alvo com `targetClasses` a partir do diff. **Python:** mutmut 3.x usa `mutmut run` e `mutmut browse`, com escopo em `[tool.mutmut] source_paths = ["src/"]` no `pyproject.toml` (ou `[mutmut] source_paths=src/` no `setup.cfg`); `paths_to_mutate` e `mutmut results` são da linha 2.x — confira com `mutmut --version` (mutmut.readthedocs.io, consultado em 11/10/2026).
- Teto sempre em **duas** pontas: `score_min` e `sobreviventes_max` absoluto (percentual sozinho é cego em base pequena). O teto só aperta; afrouxar exige ADR com a medição.
- Mutante sobrevivente é lido como teste faltando: o conserto é escrever o teste, nunca excluir o mutante da análise.

## Testes contínuos — cada estágio com oráculo e tempo-alvo
Contexto: "teste contínuo" significa que todo estágio do pipeline tem um oráculo executável e um tempo-alvo declarado; estágio sem os dois é cerimônia.

| Estágio | Oráculo (exit code / relatório) | Tempo-alvo | Onde roda |
|---|---|---|---|
| Local / pre-push | `ops/hooks/pre-push` | <alvo do time> | estação |
| PR rápido | build, lint, estático, unitários impactados | <alvo do time> | PR |
| PR contratos | verificação de contrato + `can-i-deploy` | <alvo do time> | PR |
| PR segurança | segredos, dependências, SBOM, `05b-veracode.md` | <alvo do time> | PR |
| Pós-merge | artefato único e imutável (SHA) + suíte do módulo | <alvo do time> | tronco |
| Pré-produção | smoke, E2E, contratos, ensaio de rollback | <alvo do time> | pré-prod |
| Canary/ring | SLI vs. baseline (próxima seção) | janela mínima | produção |
| Nightly | cadeia completa, mutação completa, OSV | <alvo do time> | agendado |

- O alvo é **declarado** em ADR e **medido** no log; estourar o alvo é defeito do pipeline, tratado como bug. O valor não vem de relatório: sai da baseline do time.
- Meça o tempo por estágio sem adivinhar: `gh run view <run_id> --json jobs | jq -c '.jobs[] | {estagio: .name, seg: ((.completedAt|fromdate) - (.startedAt|fromdate)), resultado: .conclusion}'`.

## Flakiness é defeito
Contexto: teste que passa e falha no mesmo SHA corrói a confiança em todo o pipeline; trate como bug com dono e prazo, não como ruído.
- **Detecção:** repetição automática marca o teste como instável (`rerunFailingTestsCount` no Surefire; `pytest-rerunfailures` no Python); "rerun até passar" nunca esconde o resultado: o relatório lista os instáveis.
- **Quarentena com prazo:** teste instável sai do caminho obrigatório, vai para job não bloqueante e ganha issue com dono e `prazo=AAAA-MM-DD`. Prazo vencido = consertar ou apagar o teste; prorrogar em silêncio é proibido.

```bash
# falha se houver teste em quarentena sem prazo ou com prazo vencido
hoje=$(date -u +%F); rc=0
while IFS= read -r l; do
  p=$(grep -oE 'prazo=[0-9]{4}-[0-9]{2}-[0-9]{2}' <<<"$l" | cut -d= -f2)
  if [ -z "$p" ] || [[ "$p" < "$hoje" ]]; then echo "QUARENTENA INVALIDA: $l"; rc=1; fi
done < <(grep -rn '@Tag("quarentena")' src/test)   # JUnit 5; em pytest use o marker
exit $rc
```

- Métricas: instáveis ativos, idade do mais antigo, reexecuções por semana no tronco.

## Progressive delivery — canary, blue-green e ring
Contexto: expor a mudança por etapas, com critério **quantitativo** de promoção e de reversão; os mecanismos AWS (CodeDeploy ECS canary, alarmes, `AutoRollbackConfiguration`) estão em `references/principios-e-deploy.md § 6.1 e 6.2`, e o alias canary de Lambda em `references/lambda-deploy.md`.

| Estratégia | Como | Quando o banco usa |
|---|---|---|
| Canary | fração do tráfego para a nova versão, ampliada por etapas | serviços com tráfego suficiente para medir |
| Blue-green | dois ambientes; troca de tráfego e volta imediata | mudança de risco alto ou de esquema compatível |
| Ring | coortes: ring 0 interno/funcionários, ring 1 piloto, ring 2 geral (via flag por segmento) | funcionalidade de negócio visível ao cliente |

- **Critério de promoção** = SLI + comparador (contra a **baseline** do mesmo período, não contra um número fixo) + janela mínima + amostra mínima. Sem amostra mínima, a etapa **estende**; nunca promove nem reprova por poucos dados.
- **Critério de reversão** = alarme ou consumo de error budget acima do que o SLO permite; dispara sozinho, sem esperar humano. Os valores vêm do SLO do serviço (`references/observabilidade.md`), nunca de memória:

```yaml
# politica-promocao.yaml — contrato lido pelo pipeline; valores <...> vêm do SLO do serviço
estrategia: canary                 # canary | blue-green | ring
etapas_pct: [<etapa_1>, <etapa_2>, 100]
por_etapa:
  janela_minima: <cobre ao menos um ciclo típico de tráfego>
  amostra_minima: <requisicoes>    # abaixo disso, estende a etapa
promover_se:                       # todos, comparando canary x baseline
  - {sli: erro_5xx, regra: "<= baseline + <margem>"}
  - {sli: latencia_p99, regra: "<= baseline + <margem>"}
  - {sli: indicador_de_negocio, regra: ">= baseline - <margem>"}
reverter_se:                       # qualquer um dispara rollback automático
  - {alarme: <alarme-cloudwatch-do-servico>}
  - {sli: erro_5xx, regra: "> <limite do SLO>", por: <janela>}
aprovacao_humana: antes_da_etapa_1_em_producao   # GATE humano + trilha
```

## Feature flags no pipeline maduro
Contexto: flag separa deploy de release; o ciclo de quatro estados e os alertas de flag zumbi estão em `references/principios-e-deploy.md § Feature Flag Lifecycle`. Resumo do ciclo: criar → ligar por % → 100% → **remover**.
- **Taxonomia:** release (curta), experimento, operacional (kill switch, permanente e revisado) e permissão. Só a primeira e a segunda têm data de remoção.
- **Data de remoção nasce com a flag** (campo `prazo`); remover a flag e o ramo morto é entrega da mesma história, não "limpeza futura". Dívida de flag = flags vencidas e idade da mais antiga, métricas do time.
- **Testar os dois caminhos** (ligada e desligada) no PR; flag desligada em produção é um estado a ser exercitado no pré-prod.
- **Em banco, ligar flag em produção é mudança:** quem, quando, valor anterior e novo, aprovação e trilha de auditoria; autor da mudança de código não liga sozinho a flag de produção.

## Rollback automático
Contexto: rollback que nunca foi exercitado é esperança; o rollback é parte do deploy e é ensaiado antes de valer.
- **Gatilho:** alarme de SLO (CloudWatch/Prometheus) ou queima de error budget; o pipeline monitora a etapa e reverte sem humano. Alvo da reversão: o **artefato imutável anterior** (mesmo SHA já testado), nunca um rebuild.
- **Pré-condição de dados:** migração em duas fases (expandir, depois contrair) para a versão anterior continuar funcionando com o esquema novo; migração irreversível exige aprovação humana explícita e plano de avanço (*forward fix*).
- **Ensaio em pré-produção a cada mudança de pipeline de deploy:** publicar a versão N+1, injetar falha controlada (AWS FIS, Chaos Toolkit ou flag de falha de teste), esperar o alarme, confirmar que a versão N voltou a servir e registrar o tempo de reversão em `reports/rollback-drill.json` (`ts`, `sha_de`, `sha_para`, `segundos`, `resultado`).
- Todo rollback vira evento `rollback` em `dora/eventos.jsonl` (entra no CFR) e, se houver causa raiz, lição em `memory/error_ledger.jsonl`.

## Delivery versus deployment
Contexto: continuous **delivery** mantém todo commit liberável e deixa a decisão de ir à produção para uma pessoa; continuous **deployment** envia automaticamente à produção tudo o que passa no pipeline.

| | Delivery | Deployment |
|---|---|---|
| Passo humano antes da produção | sim (aprovação, janela) | não |
| Pré-produção | automática | automática |
| Pré-requisito | pipeline verde e artefato imutável | idem, mais reversão automática e flags |

- **Padrão do banco:** delivery, com **aprovação humana explícita** para produção, janela de mudança e trilha. Deployment em produção só para classes de mudança classificadas como baixo risco por ADR e aprovadas por Risco/Compliance (ex.: código atrás de flag desligada), com rollback automático. Mudança que toca auth/input/queries/cripto/secrets (gatilho de segurança do `squad-pipeline`) **nunca** vai sem aprovação humana.
- `contracts/pipeline-state-machine.json`: a transição `gate2_pendente → commit` só com `aprovacao_humana`; o equivalente de produção é o GATE humano do desenho abaixo.

## Pipeline maduro — diagrama com os gates do harness
Contexto: o desenho integra o fluxo do `squad-pipeline` (GATE 1, GATE 2) ao caminho até produção; os tempos entre `[ ]` são os alvos declarados do time.

```
commit curto -> PR (branch protegida, vida curta)
  GATE 1 (plano, standard/large): gate1_plano.py LIBERADO + aprovacao humana, ANTES de codar
  PR:  [ ] rapido   build/lint/estatico/unit IMPACTADOS
       [ ] contratos verify do provedor + can-i-deploy
       [ ] seguranca segredos, deps, SBOM, 05b-veracode.md (validacao-veracode)
       [ ] mutacao   impactada, so se gatilho D5
  GATE 2 (verificacao-loop): cadeia IMPACTADA (trivial/small/standard) | COMPLETA (large/nightly)
       PRONTO + aprovacao_humana  ->  merge no tronco (gate2_pendente -> commit)
  tronco: artefato unico e imutavel (SHA) + SBOM
  pre-prod: [ ] smoke + E2E + contratos + ensaio de rollback (reports/rollback-drill.json)
  APROVACAO HUMANA para producao (GMUD/janela, trilha)          <- GATE humano
  producao: canary/ring -> promove (criterio) | reverte (automatico)
  evento deploy -> dora/eventos.jsonl
  nightly (fora do caminho critico): suite completa, mutacao completa, OSV, relatorio DORA
```

## Oráculo — como provar que foi feito
Contexto: o GATE 2 exige medição e evidência de execução para cada estágio, mutação e rollback; prosa não conta.
- **Tempo por estágio:** `gh run view <run_id> --json jobs | jq ...` (seção Testes contínuos) sobre ≥ 4 semanas de execuções; cada estágio com alvo declarado em ADR e medido. Estágio sem alvo ou acima dele reprova.
- **Mutação:** `python scripts/quality/gate_runner.py --projeto . --budget quality-budget.yaml --continuar --json reports/gates.json` no nightly; o gate MUTATION do relatório traz `score_min` e `sobreviventes_max`, com histórico por data.
- **Rollback:** `reports/rollback-drill.json` de pré-produção com `resultado` e `segundos`, gerado por execução real (alarme disparado, versão anterior servindo), vinculado ao SHA do deploy.
- **Contrato e quarentena:** verificação de contrato verde no pipeline do provedor; script de quarentena com exit 0; lista de flags vencidas vazia ou com ADR.
- **Vida do PR:** consulta de `createdAt → mergedAt` registrada na baseline. "Revisado e aprovado" não é oráculo.

## Anti-padrões
Contexto: defeitos nomeados de pipelines imaturos, usados em revisão de desenho.
- **Branch de longa vida:** semanas sem integrar; o merge vira projeto.
- **Flag eterna:** release toggle sem prazo nem remoção.
- **Rerun até passar:** repetição que esconde o instável em vez de listá-lo.
- **Mutação de enfeite:** rodar PIT/mutmut sem teto absoluto de sobreviventes nem gatilho.
- **Pipeline sem alvo:** estágio sem tempo declarado que só cresce.
- **Canary no olhômetro:** promover olhando gráfico, sem critério, janela e amostra.
- **Rollback de papel:** nunca ensaiado, sem artefato imutável ou com migração irreversível.
- **Contrato fantasma:** mock do consumidor que o provedor nunca verifica.

## Checklist de banco
Contexto: condições de banco para um pipeline de entrega contínua passar em auditoria.
- [ ] Regulatório: rastreabilidade commit → PR → artefato (SHA) → deploy → aprovação, consultável; mudança em produção com registro de quem aprovou.
- [ ] Janela de mudança: aprovação humana e janela respeitadas; deployment automático só para classes de baixo risco aprovadas em ADR.
- [ ] Segregação de ambientes e funções: autor não aprova o próprio PR nem liga a própria flag em produção; credenciais por OIDC/WIF com escopo por ambiente.
- [ ] Dados sensíveis: pré-produção e testes com dados sintéticos; nenhum segredo em pipeline, log ou política de promoção.
- [ ] Trilha de auditoria: `dora/eventos.jsonl`, `reports/gates.json`, `reports/rollback-drill.json` e regras de branch versionados e imutáveis (append-only).
