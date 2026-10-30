---
description: Investigação sistemática de defeitos — hipótese, reprodução, isolamento e correção mínima com teste de regressão.
argument-hint: <descrição do bug / stack trace / comportamento inesperado>
origin: squad-ai
---

Você está executando o comando **/squad-debug** — fachada fina de debugging (tarefa de alta dificuldade → modelo **opus**).

Sintoma reportado: **$ARGUMENTS**

Conduza a investigação de forma disciplinada, acionando o especialista mais adequado ao domínio do defeito (`arquiteto-performance` para lentidão/gargalo; `engenheiro-seguranca` se houver suspeita de falha de segurança; `especialista-banco` para problemas de dados; `java25-spring-boot`/Tech Lead para a stack):

1. **Reproduza** o problema de forma determinística antes de qualquer mudança. Se não reproduzir, não corrija às cegas.
2. **Formule hipóteses** explícitas e ordene-as por probabilidade. Investigue com Read/Grep/Glob/Bash — colete evidências, não suposições.
3. **Isole a causa-raiz** (não o sintoma). Use bisseção, logs estruturados e profiling quando aplicável.
4. **Escreva primeiro um teste que falha** capturando o bug; depois aplique a **correção mínima** que o torna verde (regressão garantida).
5. **Verifique** que a correção não quebrou nada (rode a suíte). Registre a lição aprendida na memória (candidata a instinto via /squad-evolve-skills).

**Arbitragem:** `P1-Simplicidade > P2-Performance > P3-CustoBaixo`. Correção mínima e segura vence solução abrangente e arriscada.

**Entrega:** causa-raiz documentada + teste de regressão + correção mínima. Encaminhe para **/squad-review**.
