# Rule — Segurança always-on de Python + FastAPI

> **Natureza:** regra **always-on**. Só invariantes. **Segurança nunca é
> negociável** — vulnerabilidade crítica é 🔴 **bloqueante** e prevalece sobre
> P1/P2/P3.
> **Aplica-se a:** todo código Python (`*.py`) do ecossistema.

---

## Sempre

- **`bandit` + `pip-audit` no CI.** SAST do código + auditoria de dependências.
  Achado CRITICAL/HIGH trava o gate (🔴) — não se faz merge "para corrigir depois".
- **Validação na borda com Pydantic v2.** Toda entrada externa é tipada e
  validada antes de tocar o domínio; conteúdo externo é **não confiável** por padrão.
- **Secrets fora do código.** Sempre via **variável de ambiente** ou **secrets
  manager** (AWS Secrets Manager/SSM). Nunca em código, log ou commit.
- **Versões pinadas** e dependências justificadas (P1: a stdlib/CLI não resolve?).

## Nunca

- **Nunca** `eval`/`exec`/`pickle.loads` sobre input externo; **nunca**
  `subprocess(..., shell=True)` com dado do usuário.
- **Nunca** montar SQL por concatenação de string — **query parametrizada**/ORM.
- **Nunca** logar/retornar secrets, tokens ou stack trace cru ao cliente.
- **Nunca** `verify=False` em TLS nem desabilitar checagem de certificado.

---

## Skill (conteúdo profundo)

- **engenheiro-seguranca** — OWASP, auth/autz (JWT/OAuth/RBAC), cripto, injection,
  LGPD, prompt injection, guardrails. Gatilho automático em diff que toca
  **auth / input / queries / cripto / secrets**.
