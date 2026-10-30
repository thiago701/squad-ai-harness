---
description: Gera/atualiza documentação técnica e de usuário sincronizada com o código (README em camadas, ADRs, changelog).
argument-hint: [alvo: README | ADR | changelog | <fluxo/módulo a documentar>]
origin: squad-ai
---

Você está executando o comando **/squad-docs** — fachada fina do papel Documentation.

Alvo da documentação: **$ARGUMENTS** (se vazio, documente as mudanças recentes do working tree).

Siga as instruções abaixo deste próprio comando (modelo recomendado: haiku→sonnet) e, para diagramas conceituais/casos de uso, delegue à skill **`engenheiro-especificacao`**:

1. **Não duplique verdade.** A fonte canônica é o registry de skills e o código — gere/derive a documentação a partir dele, nunca espelhe à mão (evita o drift entre as 5 superfícies).
2. **README em camadas:** README curto (1 tela) + `CHANGELOG.md` separado + docs detalhadas. Evite changelog acumulado dentro do README.
3. **ADRs legíveis:** formato canônico com "Prioridades aplicadas (P1>P2>P3)" e "Critério de revisão". Materialize em `memory/decisoes/`.
4. **Diagramas:** use Mermaid (fluxo, sequência, C4) e tabelas Markdown onde agregam clareza.
5. **Higiene proativa:** ao documentar, remova comentários sem valor e mantenha o README atualizado na mesma entrega.

**Entrega:** documentação atualizada e consistente com o código, em português brasileiro, profissional e completa (sem stubs).
