# Padrão SKILL.md da Squad — frontmatter canônico, roteamento de modelo e rubrica estrutural

> **Origem:** conteúdo normativo migrado do `skills/SKILL_INDEX.md` (§0.1, §0.3, §0.4 e
> Apêndices B.1/B.2) na aposentadoria do índice manual — **ADR-010**
> (`docs/adrs/ADR-010-aposentadoria-skill-index.md`), executada por PR humano dedicado (2026-07-09).
> O **catálogo** em si vive no registry gerado do disco (`governance/registry/registry.json`,
> `"fonte_unica": true`, regenerado por `scripts/generate_registry.py`); este documento guarda a
> **regra geradora** — o padrão que toda skill **nova** ou **refatorada** DEVE seguir.
> **Donos:** `tech-lead-review` (arbitragem do padrão) · `engenheiro-seguranca` (Linha de Defesa).
> **Prioridades imutáveis:** `P1-Simplicidade > P2-Performance > P3-CustoBaixo`.

O padrão estende o formato validado da `especialista-qualidade` (modelo pós-refactor v8.6,
hub + references, −87% tokens) com os campos de governança exigidos pela plataforma
Skill-Orchestrator: roteamento de modelo por custo, escopo mínimo de ferramentas, procedência
(supply chain) e riscos declarados.

## 1. Bloco YAML canônico (copiar e preencher) — ex-§0.1

```yaml
---
# === IDENTIDADE (obrigatório) ===
name: nome-da-skill                 # kebab-case, único no registro, == nome da pasta
version: 1.0.0                      # SemVer por skill (substitui changelog global em prosa)
description: >                      # ≤ 500 caracteres. Gatilhos enxutos, sem listas-quilômetro.
  Frase de papel + "Use SEMPRE que o usuário mencionar: <5–8 gatilhos>".
  O roteamento fino fica no roteador léxico (descriptions consumidas via registry), não aqui.

# === GOVERNANÇA / PROCEDÊNCIA (obrigatório) ===
origin: squad-ai                    # squad-ai | adaptado-de-ecc | inspirado-em-ruflo | community
                                    # adaptado-de-ecc, inspirado-em-ruflo e community EXIGEM entrada em docs/ATTRIBUTIONS.md
                                    # e auditoria prévia (skill auditoria-skill-externa)
status: ativa                       # ativa | a-refatorar | deprecated
owner: nome-do-dono                 # skill/persona responsável pela manutenção

# === ROTEAMENTO DE MODELO POR CUSTO (obrigatório) ===
model: sonnet                       # haiku | sonnet | opus  (ver heurística em §3)

# === ESCOPO MÍNIMO DE FERRAMENTAS — "least agency" (obrigatório) ===
tools: [Read, Grep, Glob]           # menor conjunto que cumpre a missão.
                                    # Skills de leitura/análise: SEM Write/Edit/Bash.

# === RISCOS DECLARADOS (obrigatório) ===
riscos:
  - "Risco concreto 1 (ex.: pode sugerir serviço AWS pago fora do free tier)."
  - "Risco concreto 2 (ex.: processa conteúdo externo — aplicar Linha de Defesa de Prompt)."

# === METADADOS DE CATÁLOGO (recomendado) ===
fase: BUILD                         # DISCOVERY | DESIGN | BUILD | TEST | REVIEW | DELIVER | TRANSVERSAL
stack: [java-25, spring-boot-4]     # tags de stack suportada
custo_tokens: medio                 # baixo | medio | alto (tamanho carregado por ativação)
---
```

## 2. Bloco obrigatório no corpo — "Linha de Defesa de Prompt"

Toda skill DEVE conter, logo após o frontmatter, o bloco anti-prompt-injection padronizado
(dono: `engenheiro-seguranca`). O **texto canônico único** vive em
[`security/security-policy.md` §4.2](../security/security-policy.md) — cole-o **verbatim** de lá
(desde o ADR-010, aquela seção é o único lar do texto; a cópia que vivia no índice foi
consolidada). A presença é verificada pelo `/review`, por `scripts/auditoria_skills.py` e por
hook no CI.

## 3. Heurística de roteamento de modelo (corta 60–70% de custo) — ex-§0.3

| Natureza da tarefa | `model:` | `tools:` típicos | Exemplos de skill |
|---|---|---|---|
| Exploração, inventário, busca, classificação | `haiku` | `Read, Grep, Glob` | roteador de skills, `retomar-sessao`, drift-check |
| Implementação, geração de testes/código, refatoração tática | `sonnet` | `Read, Edit, Write, Bash` | `especialista-qualidade`, `java25-spring-boot`, `especialista-frontend` |
| Arquitetura, segurança, debugging complexo, arbitragem | `opus` | `Read, Grep, Glob` (+ `Bash` só se necessário) | `arquiteto-minimalista`, `engenheiro-seguranca`, `tech-lead-review`, `arquiteto-cloud-aws` |

## 4. Rubrica estrutural (verificável no CI) — ex-§0.4

| Regra | Limite | Justificativa |
|---|---|---|
| Tamanho do `SKILL.md` (hub) | ≤ ~400 linhas / ≤ ~20 KB | Carregado integralmente por ativação; conteúdo profundo vai para `references/` |
| Tamanho da `description` | **≤ 500** (aplicado em 11/10/2026 pela dieta `scripts/dieta_descriptions.py`: prosa + 'Use SEMPRE que o usuário mencionar: <5–8>'; o segmento completo vai para `gatilhos_texto:` e a lista para `gatilhos:` — ambos lidos pelo roteador híbrido, nunca pelo prompt) · teto ≤ 1500 só para as 4 sem segmento de gatilho | Sempre residente no roteador (custo P3). Calibrado no Ciclo 6: o limite ≤500 era irrealista (23/24 furavam); o que importa é **gatilhos distintos, sem redundância**. >1500 = revisar redundância. Outliers em backlog. |
| `origin` ≠ `squad-ai` | Entrada obrigatória em `docs/ATTRIBUTIONS.md` + auditoria | Conformidade de licença (MIT/ECC) e supply chain |
| Progressive disclosure | Conteúdo > ~400 linhas → `references/*.md`; **todo reference deve ser linkado do hub** | Padrão validado (`especialista-qualidade`, `aws-lambda-java25-aot`). Reference não-linkado = invisível ao agente. |
| `evals/` | Pelo menos 1 cenário with/without skill (**dívida priorizada** — gerar primeiro p/ skills mais acionadas) | Mede regressão de prompt ao editar |

> **Auditoria machine-checkable:** `python scripts/auditoria_skills.py` mede estas regras em todas
> as skills e emite a tabela de conformidade (rubrica viva, não prosa). Parecer sistemático:
> `docs/judgments/2026-06-16-auditoria-sistematica.md`. Os tetos em **tokens** derivados desta
> rubrica vivem em `governance/context-budgets.json` (gate `--gate` do mesmo script).

## 5. Como adicionar uma skill nova (checklist) — ex-Apêndice B.1

1. Criar pasta `skills/<nome>/SKILL.md` com o **frontmatter canônico** (§1) e a **Linha de Defesa
   de Prompt** (§2 — texto canônico em `security/security-policy.md` §4.2).
2. Definir `model:` e `tools:` mínimos pela heurística (§3).
3. Se `origin ≠ squad-ai`: passar pela **`auditoria-skill-externa`** e registrar em
   `docs/ATTRIBUTIONS.md`.
4. Adicionar pelo menos 1 cenário em `evals/` (with/without skill).
5. **Registrar no catálogo = regenerar o registry:** rodar `python scripts/generate_registry.py`
   e conferir `python scripts/generate_registry.py --check` verde (Drift: 0; paridade
   independente via `pytest tests/test_registry.py`). O catálogo é **gerado do disco** — não
   existe registro manual (ADR-010); README/copilot/matriz são derivados.
6. Respeitar a rubrica estrutural (§4); conteúdo profundo vai para `references/`.
7. Passar no `verificacao-loop` e no CI do ecossistema (lint de frontmatter, links, tokens).

## 6. Estados de status — ex-Apêndice B.2

| Status | Significado | Ação |
|---|---|---|
| `ativa` | Em uso, dentro dos limites estruturais | Manter; eval na CI |
| `a-refatorar` | Funcional, mas viola limite (token/monólito) | Aplicar hub+references (O3) |
| `deprecated` | Substituída/obsoleta | Mover para `archive/`; remover frontmatter (não dispara) |

---

## 7. Modelo Canônico de Testes Contínuos para Novas Skills e Evoluções (`skilleval` / `stage1.skill_continuous_eval`)

Toda skill **nova** ou **evoluída** é validada continuamente pelo motor nativo em Go ([`internal/evallab/continuous_skill_eval.go`](../internal/evallab/continuous_skill_eval.go)), derivado da arquitetura científica da `eval-agentic-api` v2.0 (*Demystifying Evals for AI Agents*) e integrado ao DAG do `.\squad-harness.exe gate` (`stage1.skill_continuous_eval`):

| Gate Contínuo | O que verifica deterministicamente (`< 35 ms` para as 108 skills) | Critério de Aprovação |
|---|---|---|
| **`G1` — Contrato Estrutural** | UTF-8 válido, `Linha de Defesa de Prompt` (6 regras), `description`, `origin`, `model` e `version`. | `100%` obrigatório (Bloqueante) |
| **`G2` — Selo Criptográfico `SHA-256`** | Assinatura imutável sobre identidade e critérios (`SealAcceptanceCriteria`) contra *reward hacking*. | `VerifyCriteriaSeal == true` |
| **`G3` — Consistência de Roteamento ($\text{pass}\text{\textasciicircum}5$)** | Executa $k = 5$ `Trials` de recuperação no `HybridRouter` (BM25 + `128D` Cross-Encoder). | $\text{pass}\text{\textasciicircum}5 = p^5 \ge 0.99$ (`1.0000`) |
| **`G4` — Least Agency & Segurança** | Escopo mínimo de ferramentas declarado em `tools:` + guarda anti-injeção ativa. | `100%` obrigatório (Bloqueante) |
| **`G5` — Integridade de Referências** | Verifica que todos os arquivos em `references/*.md` existem e não estão vazios/órfãos. | Zero links ou arquivos quebrados |
| **`G6` — Suíte Agent Evals (`evals/evals.json`)** | Valida o schema JSON de tarefas, `Outcomes` esperados e asserções verificáveis. | JSON válido e $\ge 1$ cenário |
| **`G7` — Orçamento Computacional** | Tempo de avaliação por skill dentro do orçamento de recursos (`< 50 ms`). | Zero gargalo de CPU/RAM |

### Comandos para Testar Nova Skill ou Evolução de Skill

```powershell
# 1. Gerar automaticamente o template evals/evals.json no modelo Agentic Eval v2.0 para uma skill
.\squad-harness.exe skilleval --init <nome-da-skill>

# 2. Executar a bateria contínua G1-G7 (pass@5, pass^5, selo SHA-256 e veredito) em uma skill específica
.\squad-harness.exe skilleval <nome-da-skill>

# 3. Executar a suíte contínua em todas as 108 skills do catálogo (também roda em .\squad-harness.exe gate)
.\squad-harness.exe skilleval
```

