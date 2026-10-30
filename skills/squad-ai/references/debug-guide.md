# Debug — Protocolo de 4 Fases

> Absorvido de `engineering:debug`. Complementa o fluxo de [[Incident Response]] e o [[Code Review 4 Lentes]] fornecendo um **método reprodutível de diagnóstico** quando o bug não é óbvio. Usado em `step-05-review.md` quando um PR vem com bug em staging/prod e em `step-06-deliver.md` durante mitigação de incidente.

## Quando usar

- Erro ou stack trace chegou, mas causa raiz não é clara.
- Comportamento diverge do esperado ("works on my machine" / "funciona em staging, falha em prod").
- Bug intermitente ou acontece só sob condições específicas.
- Regressão depois de um deploy recente — correlacionar com `CHANGELOG.md` gerado pelo release-please.

## As 4 Fases

```
REPRODUZIR → ISOLAR → DIAGNOSTICAR → CORRIGIR
```

A ordem importa. Pular "Reproduzir" é a causa #1 de bugs que voltam.

### 1. Reproduzir

Sem reprodução confiável, não há fix — há aposta.

**Capture o contexto exato:**
- Mensagem de erro + stack trace completo.
- Comportamento esperado vs. observado em uma frase cada.
- Sequência mínima de passos (inputs, estado, ambiente).
- Timestamp + trace-id (correlacionar com X-Ray / Application Signals).
- Versão do serviço (`git describe --tags`) e do deploy (`DEPLOY_ID` via `@Value` no Spring Boot).
- Ambiente: local, staging, prod, canary.

**Teste a reprodução:**
- Local primeiro. Se só reproduz em prod, isolar qual variável faz a diferença (dados? carga? feature flag? tempo do dia?).
- Escreva um teste que **falha** reproduzindo o bug (RED) — isso será a prova da correção depois (GREEN).

### 2. Isolar

Objetivo: reduzir o universo de causas possíveis até sobrar uma região pequena do código/infra.

**Técnicas (ordem crescente de custo):**
- **Binary search no código:** comentar ou `git bisect` entre commits suspeitos.
- **Binary search nos dados:** cortar o input pela metade até não reproduzir mais.
- **Rollback de deploy:** se o bug começou em um deploy específico, reverter em staging e confirmar que some.
- **Feature flag toggle:** se existe flag relacionada, alternar e observar.
- **Component narrowing:** desabilitar cache, chamar repositório direto sem serviço, mockar dependências externas.

**Ferramentas canônicas Java 25 + SB4:**
- `--enable-preview` + remote debugger para breakpoint em preview features.
- `jcmd <pid> Thread.dump_to_file` para deadlock / starvation.
- `jfr` (Flight Recorder) em JDK 25 com ZGC Generational.
- `@Observed` + OpenTelemetry GenAI traces.

### 3. Diagnosticar

Agora sim, **testar hipóteses**. Nunca "corrigir no palpite" antes de entender.

**Framework de hipótese:**
1. Escrever a hipótese: "Eu acho que X causa Y porque Z."
2. Desenhar o experimento que **falsificaria** X (não apenas confirmaria).
3. Rodar o experimento. Descartar ou aceitar.
4. Repetir até restar uma hipótese consistente com todas as evidências.

**Fontes a correlacionar:**
- Logs da janela de tempo (CloudWatch Logs Insights com `@timestamp between X and Y`).
- Métricas (latência, error rate, throughput) na mesma janela.
- Traces distribuídos (X-Ray / OTel).
- Deploys recentes (release-please PRs entre duas tags).
- Config changes (Parameter Store history, Secrets Manager rotation).
- Database (slow queries, locks, deadlocks em `pg_stat_activity`).

**Sinais de diagnóstico raso (evitar):**
- "Pode ser race condition" sem prova de concorrência real.
- "Falha intermitente é problema de rede" antes de ver o gráfico de retry.
- Chegar direto ao fix sem escrever a hipótese.

### 4. Corrigir

**Regra:** o fix é a consequência do diagnóstico, não uma adivinhação.

- **Teste RED-GREEN:** o teste escrito na fase Reproduzir deve virar GREEN com o fix, e RED se o fix for revertido.
- **Escopo mínimo:** corrija a causa raiz, não o sintoma. Se múltiplos sintomas apareceram, vale 1 PR por causa.
- **Regressão:** adicione teste de regressão nomeado (`repro_bug_XYZ_should_not_recur`).
- **Changelog:** registre via Conventional Commits (`fix(scope): ...`) para release-please gerar CHANGELOG com link para o postmortem.
- **Propagação:** se o bug afetou dados em prod, planeje migração/backfill separado do hotfix.

## Template de Output

```markdown
# Debug Report: [título]

## Contexto
- **Erro:** [mensagem + stack trace]
- **Esperado:** [1 frase]
- **Observado:** [1 frase]
- **Ambiente:** [local / staging / canary / prod]
- **Primeiro observado em:** [timestamp + trace-id]
- **Versão:** [git tag]

## Reprodução
- [Passos mínimos]
- [Teste que falha]: `path/to/test::test_name`

## Isolamento
- [O que foi testado e descartado]
- [Região suspeita: arquivo:linha ou componente]

## Diagnóstico
- **Hipóteses testadas:**
  1. [H1] — [resultado] — [evidência]
  2. [H2] — [resultado] — [evidência]
- **Causa raiz aceita:** [descrição]

## Fix
- PR: [link]
- Teste RED→GREEN: [nome]
- Teste de regressão: [nome]
- Escopo: [o que mudou + o que deliberadamente não mudou]

## Lições aprendidas
- [Sinal que teria revelado mais cedo]
- [Guardrail proposto — alerta / lint rule / ADR]
```

## Sinais de saúde

- ✅ Todo bug corrigido tem teste de regressão nomeado.
- ✅ Postmortem de incidente SEV2+ cita o Debug Report.
- ✅ Hipóteses escritas antes do fix — rastreável na PR description.
- ❌ Fix sem teste acompanhante.
- ❌ "Não consegui reproduzir, mas acho que é X" no commit message.

## Anti-padrões

- **Corrigir no escuro** — mudar código até "funcionar", sem hipótese.
- **Fix cosmético** — silenciar o erro sem entender (`try/catch` vazio, log downgrade a DEBUG).
- **Caça de red herring** — investigar a componente errado porque foi o último tocado, não o mais suspeito.
- **"Reboot corrigiu"** — reinício esconde a causa; o bug volta.
- **Debug em prod com println** — use logging estruturado com masking de PII, não `System.out`.

## Relacionadas

- [[Incident Response]] — quando o debug é em meio a incidente ativo.
- [[Code Review 4 Lentes]] — lente Corretude valida que o fix não regride outras invariantes.
- [[Release Please]] — `CHANGELOG.md` vira fonte de correlação com deploys recentes.
- `engenheiro-devops/references/release-please.md`
- [[Runbook]] — se o bug recorre, vira runbook documentado.

#conceito #debug #squad-ai #v8-3
