# contracts/ — Contratos tipados e máquina de estados do pipeline (módulo ⑫)

> **Fase E1** do plano de evolução DSA (`docs/evolucao-dsa-2026-09-25/01-evolucao-arquitetura-squad-ai.md`).
> **Doutrina:** "O LLM pode SUGERIR uma transição; o código decide se é PERMITIDA" (e-book SDD §5.2.1).
> **P1:** stdlib pura, sem dependências, US$ 0, <1 ms por decisão.

## Estrutura

| Arquivo | Papel |
|---|---|
| `artefatos/prd.schema.json` | Contrato do artefato PRD (fase Intake/Descoberta) |
| `artefatos/plan.schema.json` | Contrato do artefato PLAN (fase Plan; DAG de passos) |
| `artefatos/relatorio-review.schema.json` | Contrato do relatório de verificação READY/NOT READY (fase Review) |
| `artefatos/retorno-delegacao.schema.json` | Contrato do **retorno de delegação** subagente → motor (I6, Onda 2 — 11/10/2026): `status` + `evidencias` + `artefatos`; concluído sem prova = retry |
| `pipeline-state-machine.json` | Mapa canônico de transições permitidas do pipeline gated (ADR-016) |
| `concorrencia.json` + `concorrencia.py` + `concorrencia.md` | **Concorrência por contrato** (I11, Onda 4): `concorrencia_max`, lease por módulo exclusivo, `RecursionGuard`, monitor de progresso e eventos `sem_progresso`/`escalonamento` no SLI |
| `validator.py` | Validador determinístico: 4 modelos JEV da Wave 1 (ver abaixo) |

## Os 4 modelos JEV implementados (Wave 1 de contratos — doc 03 §2.2)

| Função | Modelo | Entrada | Saída |
|---|---|---|---|
| `validar_artefato(tipo, dados, schema_versao)` | `jev.contrato-artefato` | artefato de handoff | `CONFORME` · `INCONFORME_RETRY` (erro instrutivo) · `INCONFORME_ESCALAR` (🔴 bloqueante) |
| `validar_transicao(estado, evento, tamanho=, aprovacao_humana=, achados_criticos=)` | `jev.maquina-estados-pipeline` | evento de avanço de fase | `PERMITIDA` · `PROIBIDA` · `REQUER_GATE_HUMANO` + destinos válidos |
| `validar_plano(plano, ferramentas_permitidas=None)` | `jev.validador-plano` | DAG do `.plan.md` antes do GATE 1 | `valido` + problemas (id duplicado, ciclo, dependência inexistente, tool fora da allowlist, destrutivo sem gate) |
| `validar_escalonamento(operacao, irreversivel=, confianca=, …)` | `jev.escalonamento-humano` | ação de alto impacto | `AUTONOMO` · `APPROVAL_GATE` · `BLOQUEADA` + alerta de maturidade (>20% de escalonamento) |

## Regras globais da máquina de estados

1. `gate_aprovado` **sem** aprovação humana → `REQUER_GATE_HUMANO` (nunca permitida).
2. `achados_criticos > 0` → **bloqueia** qualquer transição com destino `commit` (segurança nunca é negociável).
3. `tamanho == "trivial"` usa os atalhos (`intake → review → commit`); demais tamanhos usam o fluxo estrito
   (ADR-010: cerimônia proporcional ao blast radius).

## Uso

```python
from contracts.validator import validar_artefato, validar_transicao, validar_plano, validar_escalonamento

v = validar_artefato("prd", {"objetivo": "X", "criterios_aceite": ["C1"]})
assert v.veredito == "CONFORME"

t = validar_transicao("gate2_pendente", "gate_aprovado", aprovacao_humana=True, achados_criticos=0)
assert t.transicao == "PERMITIDA" and t.destino == "commit"
```

## Evidência (Quality Gate)

- **Testes:** `tests/test_contracts_validator.py` (50 testes) + `tests/test_jev_wave1_suites.py`
  (4 suítes × gold completo: TP total, FP=0, FN=0, sucesso=100%) + `tests/test_retorno_delegacao.py`
  (10 testes do retorno de delegação).
- **Benchmark completo (baseline LLM × variantes JEV):** suítes em
  `labs/jev-ecosystem/suites/{contratos,maquina-estados,plano,escalonamento}/`; resultados em
  `labs/jev-ecosystem/results/<suite>-runs.json` e `<suite>-gate.json` (Quality Gate P1–P6).

## Anti-drift (ADR-002)

Os campos obrigatórios em `validator.py` (`REQUIRED_FIELDS`) são **espelhos** dos JSON Schemas
canônicos — o teste `TestAntiDriftSchemas` falha se divergirem. Uma fonte de verdade, dois
consumidores verificados.
