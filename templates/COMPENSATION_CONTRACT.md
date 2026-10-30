# Template — COMPENSATION_CONTRACT

<!--
  CONTRATO DE COMPENSAÇÃO — toda skill/tool MUTÁVEL declara como desfazer o que faz.
  Onde: bloco `compensation_contract` no frontmatter da skill/tool.
  Validação: /review + CI (smoke test do ADR-006). Tool de efeito externo SEM contrato = 🔴.
  Princípio RAC: a compensação é DETERMINÍSTICA e declarada. O LLM pode sugerir, nunca decidir
  rollback de efeito externo na hora crítica. Mundo externo => par declarado OU aprovação humana.
-->

## Esquema

```yaml
compensation_contract:
  operation: <nome>
  effect_class: bufferable | externalized | irreversible
  tx_type: compensavel | pivo | retentavel
  idempotency_key: "<saga_id>_<step>_<attempt>"   # obrigatório se externalized/irreversible
  forward: "<comando/efeito que a tool executa>"
  compensation: "<comando inverso determinístico>"  # ou: human_required | n/a
  validator: <skill que valida a reversão>           # ex.: engenheiro-seguranca
  requires_human: <bool>                             # true para externalized/irreversible
```

## Regra de decisão (qual `effect_class`?)

| Pergunta | Sim → |
|---|---|
| O efeito fica só na working tree / memória local? | `bufferable` |
| O efeito sai para o mundo compartilhado mas tem inverso de negócio? | `externalized` |
| O efeito não tem par compensatório de negócio (e-mail, merge, pagamento, secret)? | `irreversible` |

`bufferable` → reversão `git`-nativa, sem humano. `externalized` → compensação declarada + `requires_human: true`. `irreversible` → **bloqueado na Outbox até settlement** (GATE 2 / humano).

## Exemplos de referência

```yaml
# 1) Criação de arquivo
operation: create_file
effect_class: bufferable
tx_type: compensavel
forward: "write <path>"
compensation: "git clean -f <path>"
requires_human: false

# 2) Edição de arquivo
operation: edit_file
effect_class: bufferable
tx_type: compensavel
forward: "edit <path>"
compensation: "git restore <path>"
requires_human: false

# 3) Execução de teste/check (read-only, sem efeito externo)
operation: run_tests
effect_class: bufferable
tx_type: compensavel
forward: "pytest / mvn test"
compensation: "n/a"
requires_human: false

# 4) Criação de branch/PR
operation: open_pr
effect_class: externalized
tx_type: retentavel
idempotency_key: "<saga_id>_open_pr_1"
forward: "gh pr create --head feature/<x>"
compensation: "gh pr close <n> && git push origin --delete feature/<x>"
validator: engenheiro-devops
requires_human: true

# 5) Comentário em PR (idempotente por marcador <!--saga-report-->)
operation: post_report_comment
effect_class: externalized
tx_type: retentavel
idempotency_key: "<saga_id>_report_1"
forward: "gh pr comment --body-file 99-relatorio.md"
compensation: "editar/remover comentário com marcador"
requires_human: false

# 6) Ação potencialmente destrutiva (bloqueada até settlement)
operation: delete_data | merge_master | rotate_secret | send_email | push_force
effect_class: irreversible
tx_type: pivo
forward: "RETIDO na Outbox até GATE 2 (settlement humano)"
compensation: human_required        # sem par determinístico de negócio
validator: engenheiro-seguranca
requires_human: true                # M3–M8 da autonomy-policy
```

## Checklist de aceite (CI)

- [ ] Toda tool com efeito declara `compensation_contract`.
- [ ] `externalized`/`irreversible` têm `idempotency_key` e `requires_human: true`.
- [ ] `compensation` é determinístico **ou** `human_required` — nunca "o agente decide".
- [ ] `bufferable` reverte 100% por `git` (testado por abort em fase compensável).
