# Contratos dirigidos pelo consumidor (CDC)

Um `*.cdc.yaml` por consumidor, numa pasta por API. Formato, camadas e comandos: skill
[`contrato-reverso`](../../skills/contrato-reverso/SKILL.md) →
[`references/formato-contrato.md`](../../skills/contrato-reverso/references/formato-contrato.md).

Neste repositório: `task-manager/` é o caso de validação da skill (Task Manager em `app/`).

```bash
python skills/contrato-reverso/scripts/cr.py verificar --raiz . --nivel auto
python ops/run.py contrato-reverso            # pelo harness
```
