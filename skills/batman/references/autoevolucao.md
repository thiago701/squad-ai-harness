# Auto-evolução do Batman — a skill que se aprimora a cada turno

> O turno não só melhora o workspace: **melhora a si mesmo**. Este reference define o
> ciclo de auto-evolução — como o Batman gera gatilhos de automelhoria, registra lições,
> cria novos modelos JEV, novas skills/agentes e evolui a própria skill — sempre gated.

## 1. Ciclo de auto-evolução (roda em paralelo a cada ciclo do turno)

```
OBSERVAR ──► MEDIR ──► GERAR GATILHO ──► PROPOR ──► APLICAR (N2) ──► VALIDAR ──► LIÇÃO
   │            │           │              │           │             │          │
   └─ journal  └─ métricas └─ ledger de    └─ diff em  └─ edita      └─ gates   └─ lessons/
       do turno    do ciclo    auto-evolução   arquivo     SKILL.md/      verdes     instintos
```

## 2. Gatilhos de automelhoria (proativos, determinísticos + semânticos)

O runner determinístico detecta e registra **sinais fracos**; o LLM da skill converte
em proposta. Sinais determinísticos:

| Sinal | Gatilho gerado | Proposta típica |
|---|---|---|
| Falha na bateria do ciclo (gates/testes) | `falha-na-bateria` | corrigir a causa (regra/código/teste) ou endurecer a bateria |
| Ciclos sem trabalho novo (ociosidade > 2 ciclos) | `ociosidade` | ampliar a fila adaptativa / novas frentes de validação |
| Duração do ciclo crescente (≥ 2× o baseline) | `degradacao-de-performance` | perfilamento do próprio turno; otimizar comandos pesados |
| N3 enfileirado reaparecendo em vários turnos | `gate-recorrente` | automatizar a preparação do pedido humano (PR-rascunho pronto) |
| A mesma correção feita 3× à mão | `padrao-repetido` | criar **skill interna** ou **modelo JEV** para a decisão |

Sinais semânticos (LLM): a skill percebe que uma instrução sua era ambígua, um
reference estava desatualizado, ou uma capacidade descrita não era possível — e gera
o gatilho correspondente.

## 3. Ledger de auto-evolução

- `memory/batman-autoevolucao.jsonl` (local, gitignored): `{ts, ciclo, tipo:
  metrica|gatilho|licao|proposta, detalhe, status: aberto|aplicado|rejeitado}`.
- **Propostas aplicadas** viram commits (GATE 2 humano) e, ao fechar, a linha muda
  para `aplicado` — a madrugada nunca "esquece" o que propôs.

## 4. Lições aprendidas (para a evolução da própria skill)

1. Toda lição vira registro com **evidência** (o que aconteceu, custo, correção).
2. Lições maduras (2+ ocorrências) sobem para `memory/lessons-learned.md` e podem
   virar **instinto** (`memory/instintos/*.yaml`) ou edição da própria `SKILL.md`/references.
3. Editar a própria skill é **N2** (arquivo versionado, reversível) — mas a edição
   passa pelos mesmos gates de qualquer mudança: defesa intacta, auditoria 79/79,
   evals verdes. Nunca se reescreve a própria doutrina de segurança (Linha de Defesa
   e gates N3 são imutáveis por auto-edição).

## 5. Criar novos modelos JEV, skills e agentes

- **Novo modelo JEV:** decisão repetida ≥3× no turno → tipá-la (Choice/Score/Noul).
  Fluxo obrigatório em `motor-llm-jev.md` (hipótese → baseline → benchmark → gate).
  O modelo nasce em `labs/jev-*` com testes, e só é adotado com ganho medido.
- **Nova skill interna:** padrão reaparece em 3 projetos/turnos distintos → criar
  `skills/<nova>/SKILL.md` seguindo `governance/padrao-skill.md` (frontmatter canônico,
  Linha de Defesa, evals, origin). Registrar via `generate_registry.py` + gates.
- **Novo agente:** papel novo no roster (`orchestration/conductor/worker_pool.json`) —
  proposta como PR-rascunho (N1/N2) e **adoção gated** (merge humano).
- **Regra comum:** tudo nasce pequeno, com benchmark e evals; nada entra "porque o
  Batman quis" — entra porque o gate provou.

## 6. Métricas de auto-evolução do turno (reportadas no consolidado)

- Nº de gatilhos gerados (abertos/aplicados/rejeitados).
- Nº de lições registradas; nº de propostas que viraram PR-rascunho.
- Nº de modelos JEV/skills/agentes criados ou evoluídos no turno.
