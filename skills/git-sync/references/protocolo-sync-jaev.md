# Protocolo de sincronização JEV — git-sync

> Espelho operacional de `scripts/git/jev_git.py` + `scripts/git/squad_sync.py`.
> Em divergência, vale o código (e os 24 testes que o travam).

## 1. Classificação de estado (JEV, 0 tokens)

| Estado | Condição | Ação |
|---|---|---|
| `segredo_suspeito` | path de segredo nas mudanças | PARAR (humano) |
| `conflito` | arquivos não-mergeados | PARAR (humano) |
| `detached` | HEAD sem branch | PARAR (humano) |
| `divergido` | ahead>0 E behind>0 | PARAR (humano — nunca --force) |
| `sem_remote` | sem remote configurado | informar + configurar é N3 |
| `behind_sujo` | behind>0 com mudanças locais | pull --ff-only + verificar (tier verificador) |
| `behind_limpo` | behind>0, árvore limpa | pull --ff-only (N2) |
| `ahead_limpo` | ahead>0, árvore limpa | push (N3 gated) |
| `sujo_local` | mudanças, sem divergência | agrupar + commitar (N2) |
| `limpo_sincronizado` | nada | nada |

## 2. Plano de sincronização (ordem fixa)

1. branch padrão + mudanças → `git switch -c squad/sync-<data>` (N2)
2. `git fetch --prune` (N0) → **re-decide** com as refs atualizadas
3. behind → `git pull --ff-only` (N2); falha = PARAR (humano)
4. sujo → commits agrupados por área (N2)
5. ahead/branch nova → push (N3, só com `--push`)

## 3. Fail-closed

Qualquer passo com exit != 0 **para o fluxo** e imprime o diagnóstico. A CLI nunca
tenta: `--force`, `--no-verify`, `rebase` automático, `merge` implícito, `git clean`,
ou configuração de remote. Recuperação de história bifurcada é sempre humana.

## 4. Escada de escalação (onde o LLM entra)

| Situação | Destino |
|---|---|
| mecânica do git (estado, plano, agrupamento) | **JEV** (0 tokens, <5 ms) |
| behind+sujo (confiança 0,6) | verificador (re-decisão pós-fetch; sem LLM) |
| conflito/divergido/detached | **humano** |
| mensagem de commit narrativa | LLM pequeno (só a mensagem, sob pedido) |

## 5. Evidência

- 24 testes: `tests/test_jev_git.py` (16 decisões) + `tests/test_squad_sync.py`
  (8 integrações com git real: commits, push gated, fast-forward, divergência,
  conflito, segredo, branch padrão).
- Gold de 12 casos: `labs/jev-ecosystem/suites/git/cases.json` (suite `git` do
  harness — comparável contra LLM).
