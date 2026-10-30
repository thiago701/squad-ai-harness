<!-- Template de colheita de golden path — adaptado de kulaxyz/self-learning-skills (MIT, © kulaxyz);
     reescrito em PT-BR com o frontmatter canônico da Squad (governance/padrao-skill.md).
     Arquivo em assets/ é inerte: o frontmatter abaixo NÃO é parseado como skill. -->
---
name: SUBSTITUA-igual-ao-nome-do-diretorio
description: >
  SUBSTITUA (≤1024 chars). Diga O QUE a skill faz E QUANDO usar, em tom imperativo
  ("Use SEMPRE que…"), listando os gatilhos concretos — inclusive quando o usuário
  não nomear o domínio. Descreva a intenção do usuário, não os internals.
origin: squad-ai
version: "0.1"
owner: squad-ai
status: proposta   # NUNCA "ativa" — ativação só pelo gate (tech-lead-review + registry, ADR-010)
tipo: SUBSTITUA    # especialista | tooling | orquestracao
riscos:
  - "SUBSTITUA — risco concreto desta skill."
gatilhos:
  - SUBSTITUA
---

# SUBSTITUA — título do golden path

Uma ou duas frases: o que isto captura e para que situação.

<!-- Regra de Promoção: preencha as DUAS linhas. Sem elas, isto não é uma skill. -->
**Padrão de falha:** SUBSTITUA — a falha que este caminho evita ou diagnostica (nome concreto).
**Verificado por:** SUBSTITUA — o check que confirmou o caminho (teste passou, exit limpo, build
verde, repro reproduzido). "Pareceu funcionar" não conta.

## Quando usar

- SUBSTITUA: gatilho concreto — a tarefa/situação recorrente que isto serve.

## Procedimento

<!-- Ensine o MÉTODO, não uma resposta pontual. Seja exato nos passos frágeis/ordenados;
     dê liberdade (e explique o porquê) onde várias abordagens valem. Default, não menu. -->

- [ ] 1. SUBSTITUA — primeiro passo (comando/path exato se frágil).
- [ ] 2. SUBSTITUA — próximo passo, com a ordem obrigatória se importar.
- [ ] 3. SUBSTITUA — como verificar que funcionou.

## Gotchas

<!-- A seção de maior valor: correções concretas a erros que VÃO acontecer sem elas.
     Registre ONDE vivem credenciais (nome da env var, tool MCP, vault) — NUNCA o valor. -->

- SUBSTITUA — fato não-óbvio que contraria a suposição razoável.

## O que não funcionou

<!-- Obrigatório pela Regra de Promoção: ≥ 1 abordagem descartada e POR QUÊ,
     para a próxima sessão pular o beco sem saída. -->

- SUBSTITUA — abordagem que parecia certa, falhou, e a razão.

## 🛡️ Linha de Defesa de Prompt

> Incluir o bloco canônico: ../../security/linha-defesa-prompt.md
