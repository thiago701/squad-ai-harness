# Vetor: Judge — juizo independente (aponta para /squad-judge existente)

O 5o vetor **nao reinventa** avaliacao: aciona o **juiz independente** que ja existe no
ecossistema — `/squad-judge`, protocolo em [`quality/independent-judge.md`](../../../quality/independent-judge.md),
vereditos em `quality/verdicts/`. Cego a autoria, adversarial, **por evidencia**.

## Quando acionar
- **Apos o build completo de uma wave** e depois dos vetores 1-4 (fidelity/security/functional/a11y).
- **Antes do merge** (parte do GATE 2). O judge consolida: e a ultima palavra antes de commitar.
- Nao no meio do build (seria ruido); o judge avalia o artefato pronto.

## O que o judge faz (resumo do protocolo)
1. Recebe **so o artefato + a rubrica** — nunca a auto-nota do autor nem a nota da rodada anterior.
2. Para cada objetivo/criterio: veredito (`atende`/`parcial`/`nao atende`) **com prova** (arquivo:linha, comando, saida).
3. Confronta com os `evals/` (with/without) — a skill/codigo dispara e entrega o esperado?
4. **Regra de inflacao:** nota so sobe com **delta estrutural verificavel**. Sem delta = nao infla.

## Criterios de severidade (espelham os vetores)
- 🔴 **bloqueia o merge** — objetivo nao atendido COM prova, ou achado HIGH de outro vetor confirmado.
- 🟡 **fix na proxima wave** — parcial com divida registrada.
- 🔵 **observacao** — nota de conhecimento; nao bloqueia.

## Anti-inflacao (o ponto do vetor)
O judge **nao aprova sem evidencia lida**. Checklist (de `independent-judge.md` §6):
- [ ] A nota subiu **sem** delta estrutural? → rejeitar a alta.
- [ ] Achado HIGH/CRITICAL **sem** prova (arquivo:linha/comando)? → rebaixar.
- [ ] O artefato **nao dispara** nos `evals/` apesar da descricao? → objetivo nao atendido.
- [ ] Elogio ("excelente", "robusto") **sem** evidencia? → ruido, remover.
- [ ] Reusou a nota anterior como ancora? → refazer cego a nota.

## Saida (formato)
```
JUDGE @ W<n>   (protocolo: quality/independent-judge.md)
veredito por objetivo, com prova; nota fundamentada; lista de achados citaveis.
-> grava em quality/verdicts/<artefato>.md
resultado: GREEN | NOT-GREEN (com os achados 🔴 que bloqueiam)
```

## Integracao com o loop
- Se o judge devolve 🔴 → vira sub_task `owner=fix`; o loop repete a auditoria.
- Se um veredito do judge e `failure` → o `/squad-wave` registra a trajetoria no
  ReasoningBank (passo JUDGE do laco R2), para nao repetir o anti-padrao.
