# Tech Debt — Categorização, Priorização e Remediação

> Absorvido de `engineering:tech-debt`. Complementa [[Code Review 4 Lentes]] (coluna 🔵) e `tech-lead-review/SKILL.md` fornecendo **6 categorias canônicas**, **framework de scoring quantitativo** e **plano de remediação paralelo a feature work**.

## Por que categorizar

Dívida técnica sem categoria vira "tudo é dívida, nada é dívida". Com categoria:
- Cada tipo tem dono natural (arquiteto, tech lead, devops, security).
- Priorização é comparável dentro da categoria.
- Remediação acumulada mostra onde investir em automação (Renovate, ArchUnit, lint rules).

## As 6 Categorias Canônicas

### 1. Code Debt
**Sinais:** duplicação alta, métodos > 20 linhas, classes > 300 linhas, naming fora da linguagem ubíqua, complexidade ciclomática > 10.
**Exemplo típico:** service class com 800 linhas cobrindo 3 domínios diferentes.
**Dono natural:** desenvolvedores do domínio + Tech Lead.
**Remediação típica:** refactor incremental via testes existentes (se existirem) ou via characterization tests antes de mexer.

### 2. Architecture Debt
**Sinais:** fronteira de Bounded Context violada, infraestrutura vazando para domínio, módulo Maven misturando responsabilidades (falha `ArchUnit`), padrão inconsistente (metade CQRS, metade CRUD).
**Exemplo típico:** `OrderService` lendo direto de `ProductRepository` em vez de usar integration event.
**Dono natural:** arquitetos (minimalist + clean-architect).
**Remediação típica:** ADR registrando o desvio + plano de extração (ver `adr-guide.md`).

### 3. Test Debt
**Sinais:** cobertura abaixo da meta, mutation score baixo, testes flaky, testes lentos, pirâmide invertida, ausência de contract test em API consumida.
**Exemplo típico:** módulo novo com 20% de cobertura "porque apertou o prazo".
**Dono natural:** Especialista Qualidade + time do módulo.
**Remediação típica:** freeze de features no módulo até cobertura/mutation voltar à meta. Ver `testing-strategy.md`.

### 4. Dependency Debt
**Sinais:** dependências com CVE aberto, major version atrás (Spring Boot 2 em projeto novo), libs mortas (sem release há > 18 meses), versões conflitantes entre módulos.
**Exemplo típico:** app em produção usando Log4j 2.14 (vulnerável) porque upgrade "quebrou testes".
**Dono natural:** Engenheiro DevOps + Segurança.
**Remediação típica:** [[Renovate]] automático + OWASP Dependency-Check bloqueante em CI + janela recorrente de upgrade.

### 5. Documentation Debt
**Sinais:** README desatualizado, ADR sem status, runbook sem ensaio há > 6 meses, onboarding que leva > 3 dias, link quebrado, doc órfã (autor saiu).
**Exemplo típico:** runbook de rollback que aponta para URL inexistente.
**Dono natural:** Tech Lead + autor original.
**Remediação típica:** ver `documentation-guide.md` princípio 4 — "manter atualizado ou deletar". Doc sem dono ativo é candidato a deletar.

### 6. Infrastructure Debt
**Sinais:** IaC drift (console mudou, Terraform não), sem health probe, sem graceful shutdown, dockerfile `FROM latest`, secret em variável de ambiente hardcoded, imagem base desatualizada, ECS task com CPU/mem mal dimensionado.
**Exemplo típico:** serviço sem `SIGTERM` handling, deploy causa 504 para inflight requests.
**Dono natural:** Engenheiro DevOps + Segurança.
**Remediação típica:** CI gate de IaC (terraform plan, checkov), renovação de imagem base recorrente.

---

## Framework de Scoring

Cada item de dívida recebe 3 notas de 1 a 5:

| Dimensão | O que mede | Exemplo de 5 (máximo) |
|---|---|---|
| **Impact** | Dor atual ou risco futuro concreto | Toda feature nova toca o módulo podre |
| **Risk** | Probabilidade + severidade de incidente | Bug intermitente já causou SEV2 no trimestre |
| **Effort (inv)** | Quão barato é remediar (1 = caro, 5 = barato) | Renovate sobe PR sozinho |

**Fórmula:**

```
Priority = (Impact + Risk) × (6 − Effort)
```

O `(6 − Effort)` inverte a escala: dívida cara tem multiplicador menor. Faixas típicas:

| Priority | Interpretação | Ação |
|---|---|---|
| ≥ 40 | Crítica | Pagar na próxima sprint |
| 25-39 | Alta | Pagar em ≤ 3 sprints, alocar 20% da capacidade |
| 10-24 | Média | Pagar quando tocar o código naquela área |
| < 10 | Baixa | Backlog; só pagar se vier no carona de feature |

**Exemplo aplicado:**

| Item | Impact | Risk | Effort | Priority |
|---|---|---|---|---|
| Log4j 2.14 em prod | 5 | 5 | 4 | (10) × (2) = **20... recalcular** → (5+5) × (6-4) = **20** |
| Renovate automático ausente | 4 | 4 | 5 | (8) × (1) = 8 → (4+4) × (6-5) = **8** |
| Módulo sem `ArchUnit` | 4 | 3 | 3 | (4+3) × (6-3) = **21** |
| README sem quickstart | 2 | 1 | 4 | (2+1) × (6-4) = **6** |

**Regra da conversa:** números sozinhos não decidem. Use o score para **ordenar**, não para **justificar**. Discussão de "por que 4 e não 3 em Impact" é sinal de que o item é ambíguo e precisa de mais evidência.

---

## Plano de Remediação Paralelo a Feature Work

### Regra dos 20%

Reservar **20% da capacidade da sprint** para dívida (1 dia em 5 para time de feature work). Essa alocação:
- Evita "vamos fazer depois" (que nunca vem).
- Mantém CI/infra sãs — dívida infra > 30d dá sintoma crônico.
- Decuplica features críticas de pedir "sprint de limpeza" depois de 6 meses (sinal de fracasso).

### Fluxo

1. **Inventário** (cada sprint ou mês): scan via ArchUnit, SonarQube, OWASP Dep-Check, tests lentos, runbooks sem ensaio. Cada achado vira card com categoria + score.
2. **Ranking**: ordenar por `Priority`.
3. **Sprint planning**: pegar top-N da lista até consumir 20% da capacidade.
4. **Retro**: "pagamos o que planejamos? por quê não?" — se 2 sprints seguidas falharam, **aumentar a fatia** até recuperar ou registrar ADR de desvio estrutural.

### Quando parar features e pagar dívida em massa

Bandeira vermelha: time gasta > 50% do tempo em correção, não em feature. Sintoma de dívida crítica acumulada. **Deadline de feature nova vai escorregar mesmo** — aproveite para pagar.

Sinais:
- Mesma incidência recorre em postmortem.
- Onboarding demora > 5 dias.
- CI > 30 min ou > 10% flaky.
- Upgrade de dep major impossível sem refatorar core.

Resposta: **Tech Debt Sprint** (2-4 semanas) com ADR explicando motivação, alvo quantitativo e critério de saída.

---

## Template de Item de Dívida (card no board)

```markdown
# [DEBT-NNN] <título curto>

**Categoria:** Code / Architecture / Test / Dependency / Documentation / Infrastructure
**Impact (1-5):** X — [justificativa com evidência]
**Risk (1-5):** X — [justificativa com evidência, ideal com link para incidente]
**Effort (1-5 inv):** X — [estimativa + o que cabe em 1 sprint]
**Priority:** (I+R) × (6-E) = NN

## Contexto
[2-3 frases de onde a dívida apareceu]

## Remediação proposta
[Passos concretos, ≤ 5 bullets]

## Critério de saída
[Como saberemos que está pago — métrica, test passing, ADR registrado]

## Dono
@fulano / @time

## Relacionado
- Incidente INC-YYYY-MM-DD (se aplicável)
- ADR-NNNN (se estrutural)
- PRs tocando a área
```

---

## Sinais de saúde

- ✅ Backlog de dívida tem score por item — priorização comparável.
- ✅ 20% da capacidade da sprint em dívida, observado em 3 sprints seguidas.
- ✅ Categoria Dependency automatizada (Renovate) — zero itens manuais abertos.
- ✅ Dívida crítica (≥ 40) fechada em ≤ 2 sprints.
- ❌ "Teremos sprint de dívida depois" — nunca chegou.
- ❌ Dívida sem categoria — "refactor geral".
- ❌ Score retroativo para justificar o que já era feito.

## Anti-padrões

- **Debt Porn** — listar 200 itens, pagar 2.
- **Arquiteto de Refactor** — propõe refactor grande sem ADR, sem score, sem critério de saída.
- **Gold Plating** — pagar dívida em módulo sem tráfego nem roadmap.
- **Ignorar Dependency Debt** — CVE aberto é dívida com deadline externo.
- **Score inflacionado** — tudo Impact 5, todo item prioritário, decisão sem sinal.

## Relacionadas

- [[Code Review 4 Lentes]] — coluna 🔵 Tech Debt vira card neste formato.
- [[Advogado do Diabo]] — pagar dívida também passa pelas 4 perguntas (problema concreto? time preparado? já tem ou antecipa? caminho de volta?).
- [[ADR Template]] — dívida estrutural justifica ADR.
- [[Renovate]] — automação mata a categoria Dependency Debt.
- `tech-lead-review/SKILL.md`

#conceito #tech-debt #priorizacao #squad-ai #v8-3
