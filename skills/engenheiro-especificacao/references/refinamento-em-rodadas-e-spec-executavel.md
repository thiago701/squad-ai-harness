# Refinamento em rodadas e spec executável — reference de `engenheiro-especificacao`

> **Origem:** caso-modelo RadarIAOps (12–14/10/2026) — da pesquisa ao CLI operando contra a AWS, com 2 GATE 1,
> 4 rodadas de refinamento, 1 GATE 2 por onda e cenários e2e aprovados antes do código. Lições `LL-0016`…`LL-0022`
> em `memory/lessons-learned.md`. Use junto com `clarify-gate.md` (caça de ambiguidade) e
> `user-stories-e-refinamento.md` (stories/DoR) — esta reference cobre o que eles não cobrem: **como conduzir
> rodadas de decisão com o dono** e **quando a spec está pronta para virar código**.

## 1. A sequência que funcionou (e a ordem importa)

| # | Etapa | Artefato | Quem decide |
|---|---|---|---|
| 1 | Research & Reuse (o que a Squad já tem + fatos de plataforma verificados **hoje**) | `plano/relatorio-research.md` | Squad |
| 2 | PRD curto + plano com pilares/gates mensuráveis | `plano/<proj>.prd.md`, `.plan.md` | Squad |
| 3 | **GATE 1 — debate de decisões numeradas** (D0…Dn) | `debate-gate1.md` → ADRs | **dono** |
| 4 | Refinamento pós-GATE 1 (R1…Rn) — **refinar, não reabrir** | `debate-refinamento-plano.md` | dono só nos ❓ |
| 5 | Rodadas temáticas com **pauta do dono** (parte 2, 3, 4…) | `debate-refinamento-parteN-*.md` | dono só nos ❓ |
| 6 | Validação do desenho **contra os objetivos** (matriz Objetivo × Veredito × Condição) | página/diagrama + parecer | comissão de arquitetos |
| 7 | Spec modular + modelo de dados + diagrama + **backlog em ondas com IDs** (`O0-01`…) | `docs/spec/01..12`, DBML, `.drawio` | Squad |
| 8 | "aprovado, implemente" → uma onda por vez, **GATE 2 por onda** | `docs/pipeline/onda-N/` | dono |
| 9 | **Cenários e2e do valor de negócio aprovados antes da onda que os entrega** | `testes/e2e/cenarios.yaml` + `decisoes.md` | dono |

Pular 6 ou 9 é o erro caro: 6 pega objetivo não atendido antes do código; 9 pega dado que **não existe** na
fonte antes de alguém prometer a resposta (ver §4).

## 2. Formato de um item de decisão (debate)

```markdown
## D7 — <pergunta em uma linha> ❓|✅

**Contexto.** <por que a pergunta existe; o que muda com cada resposta>
**Tensão / posições.** `arquiteto-minimalista`: "…" · `arquiteto-cloud-aws`: "…" · `engenheiro-seguranca`: "…" (veto?)
**Opções.** A … · B … · C … (custo, risco, reversibilidade)
**Recomendação ✅.** <uma frase + por que vence na arbitragem P1>P2>P3, segurança é veto>
**O que só o dono decide.** <a parte que depende de contexto que a Squad não tem: orçamento, política da empresa, gosto>
```

Regras:
- **Numere tudo** (D, R, P, M, Q, DEB). O dono responde em lote ("1. R … 2. R …") e a resposta vira ADR.
- Cada item **termina** em ✅ aplicar (a Squad incorpora) ou ❓ dono — nunca em "a discutir".
- **Refinar não reabre**: decisão do GATE 1 só volta com fato novo, e o fato vai no topo do documento.
- **Superação explícita**: quando uma rodada derruba algo anterior, edite o topo do documento antigo com
  `> Nota (hh:mm): X foi superado por ADR-NNN` — histórico preservado, ninguém lê a recomendação velha como viva.
- Pedido lateral do dono ("inclua como débito…") vira `DEB-NN` **na fila de ondas** com dono e prazo-onda.
- Revisão independente (`tech-lead-review`, contexto limpo) entra **em toda rodada grande** e tem seção própria.

## 3. Restrições do ambiente do dono são requisitos de primeira classe

Capture **antes** das opções, numa seção "Restrições do ambiente" do intake — elas eliminam alternativas:

| Restrição (exemplo real) | Efeito no desenho |
|---|---|
| Confidencialidade bancária: nada da estação sai da empresa | sem SaaS externo; logs/dados na conta; IA só via Bedrock na conta |
| Proxy corporativo só libera GitHub/`gh` | rotinas nunca tentam internet externa; dependências pré-resolvidas (lockfile) |
| Repos novos **privados** | criação pelo dono (`gh repo create --private`), nunca pela automação |
| Sem endpoint público na POC | sem API Gateway; CLI com SigV4 + `StartSyncExecution`; MCP local (stdio) |
| Agentes só leitura na infra | IAM de leitura + catálogo de intenções sem verbos destrutivos (validador barra) |
| Conta pessoal, ambientes simulados por região | `dev/hml/prod` = `us-east-1/us-east-2/us-west-2`; no banco, contas por ambiente |

## 4. A spec só está pronta quando cada pergunta tem **rastro até a fonte** ("trace the answer")

Para cada pergunta de negócio que o produto promete responder:

1. **Cenário e2e executável** — `dado` (estado do mundo: repos/recursos), `quando` (o **comando real** do usuário,
   ex.: `radar perguntar "quais projetos usam DynamoDB?"`), `então` (o que a resposta contém/não contém).
2. **Oráculo** independente da implementação (função que confere a saída) + **gabarito** feito à mão a partir das
   fixtures, nunca gerado pelo parser que ele avalia (senão mede o parser contra ele mesmo).
3. **Origem de cada dado da resposta**, escrita na spec:
   - literal no IaC → `explicito`; via `var.*`/tfvars → `variavel`; **ausente = padrão do provedor** →
     `padrao_aws` (ex.: Lambda sem `architectures` = x86_64) — a resposta precisa dizer "padrão da AWS";
   - nome vindo de `local.*`/serviço de config → **o parser não vê**; defina a rota alternativa (ex.: descoberta
     por tag `repositorio=<repo>` no Resource Explorer) **antes** de prometer a resposta;
   - ambiente: convenção (`envs/<amb>.tfvars`) → fallback (região do provider) → presumido com `confiabilidade` baixa.
4. **Decisões de cenário** (`D-E2E-NN`) para cada lacuna que o passo 3 revelar — aprovadas pelo dono como as demais.
5. **Contrato de feature planejada**: enquanto a onda não chega, o comando responde com código e mensagem estáveis
   (ex.: exit 2 + "chega na Onda 2"). O e2e real **pula** (não falha) com esse contrato e passa a exigir a resposta
   quando a onda entra — o cenário vira o critério de aceite da onda.

> Evidência: no caso-modelo, escrever os 3 cenários antes da Onda 2 revelou 3 lacunas que a spec aprovada não
> tinha (nomes via `local.*`, arquitetura padrão, ambiente sem convenção) — todas viraram decisões em 1 rodada,
> antes de qualquer linha do assistente.

## 5. Ciclo de vida é requisito desde a Onda 0 (POC descartável)

Se o dono vai "testar, melhorar e apagar tudo para o próximo cenário", isso entra na **spec**, não depois:
tags de rastreamento obrigatórias, separação **conta-base** (singletons: bucket de state, agregador do Resource
Explorer, provider OIDC) × **plataforma** (descartável), runbook de limpeza testado e varredura de órfãos.
Detalhe técnico: `engenheiro-iac/references/poc-descartavel-aws.md`.

## 6. Definition of Ready de uma onda (além do DoR de story)

- [ ] Tarefas com ID (`O<n>-NN`), dono de cada uma (Squad × dono) e evidência esperada.
- [ ] Ações irreversíveis/da conta (apply, destroy, criar repo, segredos) marcadas **do dono**, com runbook.
- [ ] Cenários e2e da onda aprovados (ou contrato "planejado" se a onda só prepara terreno).
- [ ] Origem de cada dado das respostas da onda escrita (§4.3).
- [ ] Débitos (`DEB-NN`) que vencem nesta onda listados.
- [ ] Restrições do ambiente (§3) revisitadas — alguma mudou?

## 7. Anti-padrões (nomeie quando vir)

- **"Pergunta sem fonte"** — a spec promete uma resposta cujo dado não está em lugar nenhum que o sistema lê.
- **"Gabarito espelho"** — o gabarito foi gerado pela própria implementação; recall 100 % sem significado.
- **"Teardown depois"** — limpeza pensada após o primeiro apply: singletons e proteções viram retrabalho.
- **"Decisão zumbi"** — recomendação superada que continua no documento sem nota de superação.
- **"Debate sem dono"** — item que termina em "a discutir", sem ✅ nem ❓.
- **"Restrição descoberta no deploy"** — proxy, confidencialidade ou política de repo aparecendo só na execução.

