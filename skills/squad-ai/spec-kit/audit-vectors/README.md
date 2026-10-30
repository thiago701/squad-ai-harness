# Audit Vectors — os 5 vetores de auditoria do spec-kit

Depois de cada **Build** de uma wave, o loop do `/squad-wave` aciona **5 vetores de
auditoria** em sequencia. Cada vetor e um protocolo independente, com criterio proprio e
severidade. A ideia (do workflow Build->Audit->Fix) e que **gerar e auditar sao papeis
separados** — o mesmo agente que constroi nao se auto-aprova; cada vetor procura uma
classe distinta de falha que os outros nao veem.

## Os 5 vetores

| Vetor | Pergunta que responde | Machine-checkable? | Quando aplica |
|---|---|---|---|
| [`fidelity.md`](fidelity.md) | O codigo faz o que a spec pediu (e so isso)? | **Sim** (grep/teste de AC e Non-Goal) | sempre |
| [`security.md`](security.md) | Ha vulnerabilidade, segredo ou injecao? | parcial (patterns + dep-check) | sempre que toca auth/input/query/cripto/secrets |
| [`functional.md`](functional.md) | Funciona de verdade (testes passam)? | **Sim** (pytest/cobertura) | sempre |
| [`a11y.md`](a11y.md) | A UI e acessivel (WCAG 2.2 AA)? | parcial (inspecao de codigo) | **so** skills que geram UI |
| [`judge.md`](judge.md) | A qualidade sobrevive a um juiz cetico? | nao (julgamento por evidencia) | apos build, antes do merge |

## Ordem e por que

`fidelity -> security -> functional -> a11y -> judge`

1. **fidelity** primeiro: se o codigo nem corresponde a spec, o resto e ruido.
2. **security** cedo: vulnerabilidade 🔴 e bloqueante (nao-negociavel, prevalece sobre P1/P2/P3).
3. **functional**: prova executavel de que funciona.
4. **a11y**: so se houver UI; senao `N/A`.
5. **judge** por ultimo: o juizo independente consolida, cego a autoria, por evidencia.

## Severidade (comum aos vetores)

- 🔴 **bloqueante** — barra o merge. Vira sub_task `owner=fix` na MESMA wave.
- 🟡 **necessario** — corrige na proxima wave (registrar como divida).
- 🔵 **observacao** — conhecimento; nao bloqueia.

## Disciplina

- **Machine-checkable > impressao.** Onde da, o criterio e grep/teste/exit-code, nao opiniao.
- **Gated, nao autonomo.** Achado bloqueante PARA o loop (o runner imprime DEFERRED).
- **Anti-inflacao.** Nenhum vetor "aprova" sem evidencia citavel (arquivo:linha, comando, saida).
- **Reuso, nao reinvencao.** Os vetores integram o que ja existe: `scan-secrets` (hook),
  `pytest`, `validate_skills.py`, `auditoria_skills.py`, `/squad-judge` (`quality/independent-judge.md`).
