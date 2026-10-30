# Catálogo portável de gates — 12 categorias, com equivalente para a stack da Squad

Cada categoria traz o **objetivo** (o que proteger), o que a Squad **já tem** e o **próximo passo**.
Nada aqui é para adotar de uma vez — a ordem de adoção está no hub §7.

---

## 1. Estilo & formatação (determinístico, rápido)

- **Objetivo:** eliminar debate estético do code review.
- **Squad hoje:** `.pre-commit-config.yaml`.
- **Genérico:** um formatador auto-corrigível + um linter, rodando em pre-commit **só no staged**.
- **Catraca:** nenhuma. Estilo é binário — ou está formatado, ou não.

## 2. Tipos

- **Objetivo:** erro de contrato pego antes do teste.
- **Squad hoje:** Python sem gate de tipo declarado.
- **Próximo passo:** `mypy` consultivo em `core/` e `orchestration/` primeiro; catraca de
  cobertura de tipo depois.
- **Catraca:** `%` de símbolos tipados, `direction: up`, + orçamento de `Any` por arquivo.

## 3. Intensidade de teste

- **Objetivo:** que o teste exista e cubra o que importa.
- **Squad hoje:** 119 suítes / 945 testes, pytest.
- **Genérico:** piso **absoluto** (anti-zero) + **catraca** (anti-regressão) + **piso por módulo**
  para código de alto risco (anti-Goodhart) + mutação noturna.
- **Catraca:** `coverage.statements/lines/branches/functions` (`up`) e, separadamente,
  `coverage.<modulo>.lines` para `orchestration/`, `security/`, `governance/`.

> Média global esconde buraco: 80% no total pode ser 98% em `scripts/viz/` e 30% em
> `orchestration/conductor/`. O piso por módulo é o que força o teste a ir onde dói.

## 4. Política de teste (anti-gaming) — a categoria que protege a #3

| Gate | Regra |
|---|---|
| `pr-exige-teste` | Diff que toca código de produção precisa tocar teste. É a A3 do `RULES.md` virando enforcement. |
| `detector-teste-enfraquecido` | Diff com remoção líquida de `assert` exige justificativa no corpo do PR. |
| `pr-exige-evidencia` | Alegação de "corrigido" exige bloco de evidência (teste falhando→passando ou execução documentada). |
| `descoberta-de-teste` | Todo arquivo `test_*.py` é coletado por algum runner — teste órfão fora do glob não conta. |

O `detector-teste-enfraquecido` é o mais barato de implementar e o de maior retorno: bastam duas
contagens de `assert` no diff.

## 5. Complexidade & saúde de código (tudo vira catraca)

| Métrica | Direção | Squad hoje |
|---|---|---|
| Violações Object Calisthenics | `down` | 88 em `scripts/` (hoje `--max 0`, sem folga) |
| Duplicação (jscpd / `pylint --duplicate`) | `down` | — |
| Complexidade ciclomática total | `down` | — |
| Complexidade cognitiva | `down` | — |
| Código morto / import não usado | `down` | — |
| Tamanho de arquivo (por arquivo, só encolhe) | `down` | ver `context-budgets.json` para skills |
| Dependências circulares | `= 0`, bloqueante | — |

> A conversão de `calisthenics --max 0` para catraca é a mudança de maior retorno imediato: hoje
> as 88 violações são dívida **declarada mas não protegida** — nada impede virar 95.

## 6. Segurança estática (SAST + secrets)

- **Squad hoje:** `.gitleaks.toml`, `security/agent-safety-checklist.md`, `scripts/security/defesa_v2.py`.
- **⚠️ Armadilha crítica:** config customizada de scanner de secret que **substitui** o ruleset
  padrão deixa você cego. Sempre **estenda** o default (`[extend] useDefault = true`), nunca
  substitua.
- **Catraca:** alertas SAST = 0, `direction: down`, `eps: 0`.

## 7. Supply-chain — dependências

| Gate | O que pega |
|---|---|
| SCA multi-fonte (`pip-audit` + `osv-scanner`) | CVE conhecida |
| Allowlist de licença (SPDX) | Dep com licença incompatível |
| Integridade de lockfile | URL não-HTTPS, hash ausente, registry estranho |
| **Anti-slopsquatting** | Pacote com nome parecido e **idade < 72 h** — o vetor de dependência alucinada por LLM |
| Bot de atualização agrupada | Dep envelhecendo em silêncio |

> O gate de **idade mínima** merece destaque num ecossistema onde um agente pode `pip install` um
> nome que ele mesmo inventou. Casa direto com a N4 do `RULES.md`.

## 8. Supply-chain — build & release

- SBOM na publicação · proveniência assinada · Scorecard agendado · workflows endurecidos
  (token de privilégio mínimo, sem credencial persistida no checkout, **actions pinadas por SHA**).
- **Squad hoje:** a exigência de "Actions por SHA" já está no checklist de segurança §5 do
  `AGENTS.md` — falta o gate que **prova** isso em CI.

## 9. Contratos & API

- Diff de breaking change em OpenAPI · fuzz por propriedade contra a spec · catraca de % de rotas
  documentadas · consistência spec↔código.
- **Squad hoje:** relevante para o Kanban (FastAPI) e para os MCPs gated.

## 10. Docs & i18n (anti-apodrecimento)

| Gate | Prova |
|---|---|
| `sync-numeros` | "68 skills" no README == contagem real do disco |
| `sync-versoes` | Versão citada na doc == versão real |
| `links-doc` | Todo link interno resolve |
| `sync-env` | Toda env var usada está documentada |

**Este é o gate mais barato de todos e um dos mais valiosos para a Squad**, cujo README carrega
uma dúzia de números medidos que envelhecem sozinhos (68 skills, 24 agentes, 17 workflows, 144
notas, 945 testes, 88 violações). Um script de 30 linhas conta e compara.

## 11. Anti-alucinação / consistência — a categoria rara

Detalhada no hub §3. A regra: **fonte de verdade duplicada exige gate provando que os lados batem.**

Pares duplicados que a Squad tem hoje:

| Lado A | Lado B | Gate |
|---|---|---|
| `governance/registry/registry.json` | disco (`skills/*/SKILL.md`) | `generate_registry.py --check` ✅ **já existe** |
| Prosa citando especialista | registry | `check-simbolos-vivos` ⬅ **falta** (caso `arquiteto-finops`) |
| README (números) | disco | `check-numeros-doc` ⬅ falta |
| Hub de skill | `references/*.md` | `check-references-linkadas` ⬅ falta |
| `commands/` | `/squad-*` citados | `check-comandos-citados` ⬅ falta |

O `--check` do registry já é uma implementação exemplar dessa categoria. Os outros quatro gates
são o mesmo padrão aplicado a outros pares — o trabalho conceitual já está feito.

## 12. Resiliência & domínio (específico do produto)

Para a Squad, os modos de falha do domínio são **agênticos**, não distribuídos:

| Modo de falha | Gate |
|---|---|
| Prompt injection em skill externa | `auditoria-skill-externa` + `defesa_v2.py` ✅ já existe |
| Injeção fragmentada entre descriptions | `defesa_v2.py` (conjunto do pacote) ✅ já existe |
| Skill sem Linha de Defesa de Prompt | Verificação literal do cabeçalho `## 🛡️ Linha de Defesa de Prompt` |
| Regressão de prompt ao editar skill | `evals/` com cenário with/without (dívida declarada na `padrao-skill.md` §4) |
| Especialista em loop de retry | `resiliencia-agente` + revisão do JSONL de transições |
| Estouro de orçamento de contexto | `context-budgets.json --gate` ✅ já existe |

---

## Escore agregado ponderado — catraca de conjunto

Quando um gate junta várias checagens num número só (ex.: eval de skill com 10 asserções),
a média simples tem um defeito grave: nove verdes **compensam** uma falha de segurança.

1. **Bloqueante fica fora da média.** Checagem `bloqueante` (SAST, secrets, Linha de Defesa)
   decide sozinha: falhou, reprova — antes de qualquer conta.
2. **Média ponderada no resto:** escore = Σ(escore × peso) ÷ Σ peso (peso padrão 1; Σ peso = 0 → 0).
3. **peso 0 = medir sem mover o agregado** — é o estágio consultivo (hub §4) dentro do conjunto.
4. **limiar opcional.** Sem limiar, qualquer falha individual reprova. Com limiar, o agregado
   decide (por isso a regra 1 é inegociável: o limiar nunca pode absolver um bloqueante).
5. **fail-closed:** soma ou peso não finito (NaN/∞) reprova com escore 0.
6. **O agregado também é catraca** (`direction: up`, `eps`): cair de 0,95 para 0,85 reprova
   mesmo acima do limiar 0,8 — o limiar é piso, a catraca é anti-regressão.

> Procedência: semântica de pesos, peso 0 e limiar por caso adaptada de promptfoo/promptfoo
> (`src/assertions/assertionsResult.ts` @ c0b88a32, MIT). Reescrita; nenhum código copiado.
> Acréscimo da Squad: bloqueantes fora da média (na fonte, o limiar sobrepõe falhas
> individuais) e o agregado sob catraca. Prova: `evals/eval_escore_ponderado.py`.

---

## Mapa de fadiga — quantos gates são demais?

Um sistema de referência com ~46–80 gates carrega um risco reconhecido de **fadiga**: gate demais
gera debate de prioridade e, no limite, gate ignorado. Contrapesos:

1. **Camadas.** Rápido no PR · completo no merge · pesado à noite.
2. **Consultivo por padrão.** Só vira bloqueante depois de estabilizar (hub §4).
3. **Revisão de ROI por gate.** Periodicamente: este gate já pegou algo real? Se nunca pegou em
   dois ciclos, consolide ou remova.
4. **Consolidação.** Cinco micro-gates de sync de doc cabem num script só.

Para a Squad, o alvo saudável é **10–15 gates bem escolhidos**, não 50. P1-Simplicidade vale
também para o sistema de qualidade — inclusive para ele.
