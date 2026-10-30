# Política de Segurança

Obrigado por ajudar a manter o **SquadAI Harness** seguro.

## Versões suportadas

| Versão | Suportada |
|---|---|
| `master` (linha principal) | ✅ |
| Branches de feature / PRs abertos | ⚠️ apenas via gate de CI |
| Tags de release anteriores à última | ❌ |

## Como reportar uma vulnerabilidade

**Não abra issue público para vulnerabilidades.** Use um canal privado:

1. **GitHub Security Advisories** — aba **Security → Report a vulnerability** deste repositório (preferido).
2. Ou e-mail para o mantenedor com o assunto `[SECURITY] squad-ai-harness`.

Inclua: descrição, passos para reproduzir, impacto e versão/commit afetado. Resposta esperada em **até 72 h**; correção coordenada antes de divulgação pública.

## Modelo de segurança (resumo)

Este projeto é um ecossistema de **skills de IA + orquestrador + pipelines de CI**. O princípio central é **"gated, not autonomous"**: nenhum artefato externo ou modificação entra em produção sem **revisão humana** (Pull Request + checks). A política técnica completa (14 classes de verificação, deny-lists, supply-chain) está em [`security/security-policy.md`](security/security-policy.md).

Pilares aplicados:

- **Skills são supply chain.** Todo `SKILL.md`/hook/config é superfície de execução. Importação de skill externa passa pelo portão [`skills/auditoria-skill-externa`](skills/auditoria-skill-externa/SKILL.md) + **[NVIDIA SkillSpector](https://github.com/NVIDIA/SkillSpector)** como auditor padrão ([`security/skillspector-policy.md`](security/skillspector-policy.md)).
- **Segredos.** Nunca commitados. Varredura automática (`gitleaks`) no CI e em pre-commit; um achado bloqueia o merge. Credenciais vêm de *secrets* do GitHub Actions, nunca de arquivo. Rotação: [`security/credential-rotation.md`](security/credential-rotation.md).
- **Dependências.** Pinadas com limite superior; `pip-audit` no CI; `dependabot` mantém deps e GitHub Actions atualizadas. Actions devem ser fixadas por SHA.
- **Prompt injection.** Conteúdo externo é dado não-confiável; toda skill carrega a *Linha de Defesa de Prompt* ([`security/linha-defesa-prompt.md`](security/linha-defesa-prompt.md)).
- **Operações perigosas** exigem confirmação humana explícita (deny-list em `security/security-policy.md` §5/§13).

## Gates de CI relacionados

| Workflow | O que verifica |
|---|---|
| [`security.yml`](.github/workflows/security.yml) | `gitleaks` (segredos) · `pip-audit` (CVEs) · Unicode invisível |
| [`skillspector-audit.yml`](.github/workflows/skillspector-audit.yml) | SkillSpector (64 padrões) + pré-screen estático das skills |
| `squad-ci.yml` / `change-audit-pipeline.yml` | testes, qualidade, auditoria de mudanças |

## Ambiente corporativo

- **Configuração por variável de ambiente, proxy e modo offline:** [`docs/CONFIGURACAO-AMBIENTE.md`](docs/CONFIGURACAO-AMBIENTE.md).
- **Troubleshooting operacional (encoding, sandbox, proxy, kanban):** [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).
- **Relatório de prontidão para produção (checklist ✅/⚠️/❌):** [`docs/relatorios/PRONTIDAO-CORPORATIVA-2026-09-26.md`](docs/relatorios/PRONTIDAO-CORPORATIVA-2026-09-26.md).

> Segurança nunca é negociável: uma vulnerabilidade crítica é **bloqueante** e suspende qualquer trade-off de prioridade.
