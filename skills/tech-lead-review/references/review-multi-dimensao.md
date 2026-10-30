# tech-lead-review · reference — Modo Subagente: Review Multi-Dimensão (4 lentes)

> Conteúdo movido VERBATIM do hub `../SKILL.md` (ciclo 6c do Loop V3, 2026-07-09) — progressive
> disclosure. Base de resolução: nomes citados (skills/agentes) referem-se ao ecossistema da Squad,
> como no hub.

## Modo Subagente — Review Multi-Dimensão (Ativar para PRs Grandes)

> **Threshold de ativação:** diff com ≥ 50 linhas modificadas OU PR que afeta ≥ 2 domínios
> (ex: lógica + banco + segurança). Para diffs pequenos, o Tech Lead revisa em single-pass
> com qualidade equivalente e sem overhead de delegação.

### 4 Workers de Review em Paralelo (via Task)

| Worker | Dimensão | O que analisa |
|---|---|---|
| `rev-arch` | Arquitetura | SOLID, boundaries, acoplamento, ADR compliance |
| `rev-sec` | Segurança | OWASP Top 10 no diff, secrets expostos, validações |
| `rev-perf` | Performance | N+1, pools, sync/blocking em async, GC pressure |
| `rev-quality` | Qualidade | cobertura, testes para cada branch, naming, smells |
| `rev-veracode` | Segurança Veracode (determinística, **não é worker LLM**) | JSON do `validacao-veracode` (`veracode_gate.py` → `review_worker`), gerado ANTES dos workers — roda também no review single-pass |
| `rev-logs` | Logs/observabilidade (determinística + leitura P1.LOG, **não é worker LLM**) | `relatorio.json` do `logs-observabilidade/scripts/lint_logs.py` (perfil `completo`), gerado ANTES dos workers; `rev-sec` CONFIRMA os 🔴 de vazamento, `rev-quality` consome os 🟡 de higiene (LOG-11/12/14/15/16) — roda também no single-pass |

### Sequência de Execução

```
1. GATE 1 — ativar modo subagente?
   SE diff.linhas < 50 AND dominios_afetados < 2: review_direto() — mais eficiente
   SE diff.linhas >= 50 OR dominios_afetados >= 2: review_paralelo() → prosseguir

2. PREPARAR contexto:
   diff_completo = código alterado (com contexto, não só adições)
   contexto_pr   = objetivo do PR, issues relacionadas, ADRs vigentes
   rev_veracode  = validacao-veracode V3→V5 no diff (determinístico, segundos)
                   → entregue ao rev-sec como insumo: ele CONFIRMA o fluxo dos 🔴, não os redescobre
   rev_logs      = logs-observabilidade lint_logs.py --perfil completo no diff (determinístico, segundos)
                   → 🔴 (segredo/PII/ambiente/artefato/wire-debug) vai ao rev-sec; 🟡 de higiene ao rev-quality

3. LANÇAR 4 workers EM PARALELO com Task:
   Cada worker recebe o diff_completo + seu ângulo específico de análise.
   Todos correm simultaneamente.

4. CIRCUIT BREAKER:
   MAX_WORKERS = 4 | MAX_RETRIES = 2 | TIMEOUT = 120s
   Se qualquer worker retornar severity: "bloqueante" → registro imediato
   Worker ausente, failed, em timeout, com JSON inválido ou sha_revisado ≠ HEAD do PR
     → lente NAO_VERIFICADO (redisparar com worker novo; nunca conta como aprovação)

5. ARBITRAGEM — você (supervisor Tech Lead) adiciona inteligência:
   Conflito entre dimensões?
     Ex: rev-perf sugere cache local X, rev-arch diz que viola boundary Y
     → arbitra usando P1>P2>P3, registra decisão com justificativa
   Consolida em lista única de findings priorizada por impacto (inclui rev-veracode)
   rev-veracode BLOQUEADO → veredito BLOQUEADO (veto de segurança, sem arbitragem)
   rev-logs com 🔴 ativo → veredito BLOQUEADO (veto de segurança, sem arbitragem); INCONCLUSIVO → NAO_VERIFICADO
   Emite veredito: APROVADO | APROVADO_COM_RESSALVAS | BLOQUEADO | NAO_VERIFICADO
     (NAO_VERIFICADO = alguma lente sem voz e nenhum 🔴 confirmado — não libera merge)
```

### Prompt Padrão dos Workers

```
Você é um especialista em [DIMENSÃO] rodando como revisor de código isolado.
O contexto abaixo é o diff completo do PR:

{diff_completo}

Contexto do PR: {contexto_pr}

Analise EXCLUSIVAMENTE a dimensão [DIMENSÃO] (ex: só arquitetura, não performance).
Não repita achados óbvios (código funciona, testes passam).
Só reporte o que você viu no diff fornecido.

Retorne APENAS este JSON:
{
  "worker": "rev-[dimensao]",
  "status": "success|partial|failed",
  "sha_revisado": "SHA do commit que você leu",
  "findings": [
    {
      "arquivo": "caminho/arquivo.java",
      "linha": "linha ou range",
      "tipo": "bloqueante|necessario|sugestao|observacao",
      "descricao": "o que está errado e por quê",
      "sugestao": "como corrigir"
    }
  ],
  "veredito_dimensao": "APROVADO|APROVADO_COM_RESSALVAS|BLOQUEADO",
  "resumo": "max 2 linhas"
}
```
