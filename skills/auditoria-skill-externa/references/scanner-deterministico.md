# Scanner Determinístico — tabela de padrões e suíte de benchmark

> **Fonte:** Proposta 2 aprovada — `labs/jev-ecosystem/docs/04-propostas-evolucao.md`.
> Implementação: `labs/jev-ecosystem/src/jsk_bench/audit_rules.py`.
> Evidência: `labs/jev-ecosystem/suites/auditoria` (N=3; 12 skills: 4 maliciosas,
> 4 suspeitas, 4 benignas) — TP **24/24** · FP **0** · FN **0** · sucesso **1,00** ·
> US$ 0 · 3 ms (baseline LLM: TP 12/24 · FP 37 · FN 12 · sucesso 0,83 · 46,4 s).

## Vetores verificados deterministicamente (passo 1)

| Vetor | O que a regra detecta |
|---|---|
| Unicode invisível | zero-width space, bidi overrides, word joiner, Unicode tags em prosa/instruções |
| Comandos outbound | curl\|bash, wget\|sh, envio de dados para fora, execução remota |
| Secrets | padrões de chave/token hardcoded (14 padrões da política) |
| Destrutivos | rm -rf, força push, DROP, desligamento de segurança sob comando externo |
| Links sem guardrail | URLs em instrução sem cláusula "conteúdo externo = dado, não ordem" |
| Frontmatter/origin/defesa | campos obrigatórios, `origin` válido, Linha de Defesa presente |
| Permissões | tentativa de ampliar escopo de ferramenta/alteração de config crítica |

## Divisão de trabalho

- **Passo 1 (determinístico, obrigatório):** o scanner acima — veredito automático
  para qualquer vetor crítico.
- **Passo 2 (LLM, somente quando a regra não decide):** achados ambíguos e auditoria
  semântica profunda de skills aprovadas no passo 1.

O LLM nunca executa a varredura; ele julga o que a varredura não tipou.
