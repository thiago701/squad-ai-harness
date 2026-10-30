# Modelo — relatório executivo de análise de produção

> Parte da skill `analise-producao-aws`. Hub: `../SKILL.md`. Sanitize antes de enviar
> (`governance/politica-evidencias-sigilo-qualidade.md` §5): sem segredo, sem dado pessoal, IDs de
> conta e ARNs reais só se o destinatário já tem esse acesso.

```markdown
# Análise de produção — <serviço/fluxo> — <data>

**Nível de validação:** V5 (observado em produção, somente leitura) · **Janela:** <início–fim UTC>
**Perfil:** <nome do perfil de leitura> · **Consultas:** <n> (plano aprovado pela guarda)

## 1. Situação observada
- [OK] <fato medido, com fonte: métrica/consulta + janela>
- [OK] ...

## 2. Impacto
- Quem/quantos: <usuários, % de requisições, ordens afetadas>
- Desde quando: <horário> · Ainda ocorrendo? <sim/não, até quando>

## 3. Evidências (linha do tempo)
| Horário (UTC) | Evento | Fonte |
|---|---|---|
| 10:42 | deploy da versão 37 da função X | CloudTrail lookup-events |
| 10:44 | p99 sobe de A para B ms | métrica Duration p99 |

## 4. Hipóteses (correlação ≠ causalidade)
| # | Hipótese | A favor | Contra | Teste que confirma |
|---|---|---|---|---|
| H1 | [AN] ... | ... | ... | ... |

## 5. Ações recomendadas (nenhuma foi executada)
| Prioridade | Ação | Risco | Quem autoriza |
|---|---|---|---|
| 1 | ... | ... | dono do serviço (N3) |

## 6. Lacunas
- [GAP] <o que não foi possível ver e por quê — permissão, retenção, ausência de métrica>
```

Regras: toda linha da seção 1 tem fonte; hipótese nunca aparece como causa; ação recomendada não é
executada pela análise; números sem `n`/janela são `[AN]`.
