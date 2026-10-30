---
description: Orquestra o loop Build -> Audit(5 vetores) -> Fix de uma wave do projeto, a partir de um WAVE-SPEC.yaml e do OpenDesign. Gated (GATE 1 le a spec; GATE 2 antes de commitar), com metricas reais e ReasoningBank.
argument-hint: <WAVE-SPEC.yaml>
origin: spec-kit
---

Voce esta executando **/squad-wave** — o orquestrador do **spec-kit** (`skills/squad-ai/spec-kit/`).
Roda o loop **Build -> Audit(5 vetores) -> Fix** para uma wave, com as disciplinas do Squad AI:
gates, ReasoningBank, P1>P2>P3, gated autonomy.

Wave a executar: **$ARGUMENTS** (um arquivo `WAVE-SPEC.yaml`).

## GATE 1 — design antes de codigo (PARE se a spec nao estiver pronta)
1. Localize o `OPENDESIGN.md` do projeto. Se **ausente, vazio ou com placeholders `[...]`**,
   **PARE** e peca o preenchimento (use `skills/squad-ai/spec-kit/opendesign/OPENDESIGN-GUIDE.md`,
   secao "Checklist de Pronto-para-build"). **Nao execute build sem spec.**
2. Confirme: >= 1 RN, >= 1 AC com gate SPARC mapeado, Non-Goals explicitos, Status =
   Pronto-para-build.

## Plano
Rode o runner para imprimir o plano em ordem de dependencia (owner | gate | budget):
`pwsh skills/squad-ai/spec-kit/waves/wave-runner.ps1 $ARGUMENTS` (ou `powershell -File ...`).

## Fluxo
1. **Build** — execute as sub_tasks `owner=build` na ordem de `depende_de`. So o que a
   wave pede; nada de Non-Goal.
2. **Audit (5 vetores, em sequencia)** — para cada sub_task `owner=audit:*`, aplique o
   protocolo de `skills/squad-ai/spec-kit/audit-vectors/`:
   `fidelity` -> `security` -> `functional` -> `a11y` (N/A se nao houver UI) -> `judge`.
   Cada vetor reporta achados com **severidade** (🔴 bloqueante / 🟡 / 🔵) e **prova citavel**.
   Seguranca toca auth/input/query/cripto/secrets → aciona `engenheiro-seguranca` (🔴 = nao-negociavel).
3. **Fix** — para cada achado **bloqueante**, abra uma sub_task `owner=fix` com o finding
   como input. Corrija e re-rode o vetor que apontou.
4. **Loop** — repita Audit -> Fix ate `resultado=GREEN` (zero bloqueante) **ou** atingir o
   max de ciclos (default 3; alem disso, registre `DEFERRED` e pare — nao silencie).

## GATE 2 — antes de commitar
- Apresente o **relatorio final**: metricas (tokens reais, duracao, tool-calls), achados por
  vetor, e `resultado` (GREEN | DEFERRED | FAILED). Rode a suite completa (`pytest -q`).
- Grave metricas e resultado no YAML:
  `wave-runner.ps1 $ARGUMENTS -Record -Resultado <R> -TokensReais <n> -DuracaoMin <n> -ToolsCalls <n>`.

## Saida
- `WAVE-SPEC.yaml` atualizado com **metricas reais** e `resultado`.
- **ReasoningBank**: se um padrao de fix se repetiu **>= 2x**, registre-o
  (`wave-runner.ps1 ... -FixPattern "<padrao>" -FixTaskId <id>` grava em
  `.claude/banco-padroes/spec-kit-fixes.md`) — passo DISTILL/CONSOLIDATE do laco R2.
- **Commit atomico** com mensagem padronizada: `wave(W-N): <objetivo> [GREEN|DEFERRED]`.

## Disciplina
P1-Simplicidade > P2-Performance > P3-CustoBaixo. Gated, nao autonomo: GATE 1 sem spec
= parar; achado 🔴 = parar e corrigir; nenhum vetor aprova sem evidencia lida (anti-inflacao).
