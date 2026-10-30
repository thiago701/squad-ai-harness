# tech-lead-review · reference — Auditoria de Cobertura do review

> Adicionado na v1.3 (18/10/2026). Fecha a lacuna "nenhum achado = tudo coberto": o revisor
> declara o que leu, o que não leu e o estado de cada categoria de risco, e o veredito fica preso
> a essa declaração.

## Por que

Um review que só lista achados é indistinguível de um review que não olhou metade do diff. Quem
lê "APROVADO, sem achados" não sabe se o arquivo gerado, a migration ou a lente de concorrência
foram vistos. A cobertura explícita transforma ausência de achado em afirmação verificável.

## Os três passos (antes do PASSO 5 — veredito)

1. **Inventário primeiro.** Liste todos os arquivos do diff antes de começar; se o diff veio
   truncado, abra arquivo por arquivo até ter visto toda linha alterada.
2. **Status por categoria.** Para cada categoria do checklist (simplicidade, performance, custo,
   segurança, negócio, arquitetura) registre `achado`, `limpo` ou `não verificado (motivo: …)`.
   "Limpo" é afirmação positiva — só vale se você olhou.
3. **Declare as lacunas.** Todo arquivo ou categoria que você não conseguiu verificar entra em
   `Não revisado`, com o motivo (gerado, binário, fora do contexto, sem runtime, sem carga…).

## Formato

```markdown
### Cobertura
Revisado: src/pagamento.py, src/repo.py
Não revisado: src/gen/schema.py (motivo: código gerado pelo protoc)
Categorias:
- simplicidade: limpo
- performance: não verificado (motivo: sem carga de referência para o p95)
- custo: limpo
- segurança: achado
- negócio: limpo
- arquitetura: limpo

Veredito: NAO_VERIFICADO
```

`Não revisado: nenhum` é válido quando a cobertura é total.

## Regras que o `scripts/checar_cobertura.py` impõe

| Regra | Rejeita quando |
|---|---|
| Seção obrigatória | não há `### Cobertura` (inclusive em "nenhum achado") |
| Diff inteiro declarado | algum arquivo alterado não está em `Revisado` nem em `Não revisado` |
| Lacuna justificada | item de `Não revisado` ou categoria `não verificado` sem motivo |
| Categoria com status | alguma das 6 categorias sem `achado`/`limpo`/`não verificado` |
| Aprovação só com cobertura total | veredito começa com `APROVADO` e existe qualquer lacuna → use `NAO_VERIFICADO` |

Uso: `python skills/tech-lead-review/scripts/checar_cobertura.py relatorio.md <arquivos do diff…>`
(exit 0 = aceito, 1 = rejeitado com os motivos listados). Eval: `evals/eval_cobertura.py`
(aceite ingênuo deixa passar 6/9 "tudo coberto" falsos; o checador, 0/9, sem rejeição indevida).

Coerência com o Modo Subagente: lente ausente/caída já é `NAO_VERIFICADO`; a auditoria de
cobertura estende a mesma regra ao review single-pass e às categorias dentro de cada lente.

## Procedência

- Fonte: https://github.com/getsentry/skills — `skills/find-bugs/SKILL.md`, commit `f57ada2`
  (f57ada2d0b640406ea7e25b11d636c530e77c58b), licença **Apache-2.0** (© 2025 Functional Software,
  Inc. dba Sentry).
- O que entrou: a ideia da auditoria pré-conclusão (inventário de arquivos, status por item do
  checklist, lista do que não pôde ser verificado e por quê) e o inventário completo do diff antes
  de revisar. Reescrito em PT-BR com as categorias P1/P2/P3 da Squad, o veredito `NAO_VERIFICADO`
  e um checador determinístico próprio; nenhum texto ou código foi copiado.
- O que não entrou: o checklist OWASP do find-bugs (já coberto pela lente Veracode e pelo
  `engenheiro-seguranca`) e o formato de saída por achado (já coberto pelo Pre-Report Gate).

## Changelog

- **1.3 (2026-10-18):** Auditoria de Cobertura no hub + `scripts/checar_cobertura.py` +
  `evals/eval_cobertura.py`; seção "Veredito tipado (R5)" movida verbatim para
  `references/veredito-tipado-reasoningbank.md` para manter o hub ≤ 5000 tokens residentes.
