# Template — PATCHBOARD_STATE

<!--
  PATCHBOARD STATE — estado compartilhado multi-agente como dado estruturado, NUNCA chat livre.
  Onde: .claude/saga/<saga_id>/state.json  (mutado só via JSON Patch RFC 6902)
  Kernel: scripts/saga/patchboard.py intercepta cada patch e valida, na ordem:
    1) schema (tipos/formato)  2) write contract (quem pode escrever o quê)  3) invariantes (runtime)
  Patch que falha é REJEITADO sem sujar o estado nem os logs dos outros agentes.
  Princípio: nenhum agente escreve descrição em linguagem livre no plano colaborativo.
-->

## 1. Schema (JSON Schema resumido)

```json
{
  "schema_ref": "templates/PATCHBOARD_STATE.md#schema",
  "type": "object",
  "required": ["plan", "tests", "security_findings", "review_verdict"],
  "properties": {
    "plan": {
      "type": "object",
      "properties": {
        "allowed_files": { "type": "array", "items": { "type": "string" } },
        "new_deps":      { "type": "array", "items": { "type": "string" } }
      }
    },
    "tests": {
      "type": "object",
      "properties": {
        "passing":  { "type": "boolean" },
        "coverage": { "type": "number", "minimum": 0, "maximum": 1 }
      }
    },
    "security_findings": {
      "type": "array",
      "items": { "type": "object", "properties": { "severity": { "enum": ["info", "low", "med", "high", "crit"] } } }
    },
    "review_verdict": { "enum": ["PENDING", "READY", "NOT_READY"] }
  }
}
```

## 2. Write contracts (quem pode escrever cada chave)

```json
{
  "arquiteto-minimalista":  ["plan"],
  "especialista-qualidade": ["tests"],
  "engenheiro-seguranca":   ["security_findings"],
  "tech-lead-review":       ["review_verdict"]
}
```

## 3. Invariantes de runtime (checadas a cada patch)

```json
[
  "secrets_exposed == 0",
  "all([f in plan.get('allowed_files', []) for f in files_touched])",
  "not (review_verdict == 'READY' and not tests.get('passing', False))",
  "not (any(f.get('severity') == 'crit' for f in security_findings) and review_verdict == 'READY')"
]
```

## 4. Estado inicial (exemplo)

```json
{
  "plan": { "allowed_files": ["src/auth/*.java"], "new_deps": [] },
  "tests": { "passing": false, "coverage": 0.0 },
  "security_findings": [],
  "review_verdict": "PENDING"
}
```

## 5. Mutação — só por JSON Patch (RFC 6902)

```json
[
  { "op": "replace", "path": "/tests/passing",  "value": true },
  { "op": "replace", "path": "/tests/coverage", "value": 0.92 }
]
```

Fluxo do kernel: recebe patch → valida schema → valida write contract do emissor → simula estado futuro → checa invariantes → **commit** (atualiza state.json + grava no Saga Log) ou **reject** (erro lógico ao emissor, estado intacto).

## 6. Anti-pattern bloqueado

> ❌ "O agente escreveu no chat: *acho que os testes passaram*."
> ✅ O agente emite `{"op":"replace","path":"/tests/passing","value":true}`; o kernel valida e registra. Sem ambiguidade, sem contaminação a jusante, com trilha de auditoria.
