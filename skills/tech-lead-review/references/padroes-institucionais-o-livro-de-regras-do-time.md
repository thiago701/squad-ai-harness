# tech-lead-review · Padrões Institucionais — O Livro de Regras do Time

> Reference da skill `tech-lead-review` (movida da SKILL.md em 11/10/2026 — hub + references, I3). Carregue só quando a tarefa pedir este tema.

## Padrões Institucionais — O Livro de Regras do Time

Estes padrões são estabelecidos por consenso e são **imutáveis até nova deliberação formal**. Toda entrega é verificada contra eles. Detalhe completo: `references/padroes-institucionais.md`.

- **Padrões de Código** — nomenclatura reveladora de intenção; tamanho (método de regra ≤20 linhas, classe ≤300, ≤3 parâmetros); estrutura (≤2 níveis de if, DI, negócio no domínio, I/O fora de loop).
- **Calistenia de Objetos × Java 25 — checklist de review** (fase: code review) — regras R1–R9 mapeadas a JEPs do JDK 25; fonte canônica: skill `java-modernizer`; Gate P1: a regra só entra se deixar o código *mais simples*.
- **Padrões de Arquitetura** — camadas Clean Architecture; domínio define portas; pirâmide de testes 60/20/15/5; agentes de IA (porta LLMPort, guardrails explícitos, lógica de negócio no LLM = 🔴).
- **Padrões de Pull Request** — Conventional Commits; descrição obrigatória (o quê/por quê/como testar + impactos de segurança, performance e observabilidade + checklist); tamanho ideal ≤400 linhas, >800 = dividir sem exceção.
