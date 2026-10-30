# Protocolo de planejamento de fluxo distribuído (obrigatório antes de implementar)

> Parte da skill `arquiteto-cloud-aws`. Hub: `../SKILL.md`. Exemplo completo que segue este
> protocolo: `labs/aws-referencia-ordens/docs/` (01 a 06). Marcas e níveis:
> `governance/politica-evidencias-sigilo-qualidade.md`.

## Os 7 artefatos

| # | Artefato | Conteúdo mínimo | Verificação |
|---|---|---|---|
| 1 | Requisitos | RF com id; RNF com **meta por cenário** e medição (ou `[GAP]` explícito — nunca número inventado) | revisão |
| 2 | Contratos | entrada, saída e eventos em JSON Schema (draft-04 para models do API Gateway), exemplos válidos e inválidos, versão | `scripts/aws/contratos.py` |
| 3 | Diagrama de arquitetura | Mermaid `flowchart` com gatilho, **identidade solicitante**, síncrono × assíncrono, persistência, eventos, notificação; nós `res:<Id>` = recursos do IaC | `scripts/aws/coerencia.py` |
| 4 | Diagrama do workflow | Mermaid `stateDiagram-v2` com estados, decisões, retries, timeouts, callbacks, compensações; **mesmas transições da ASL** + a ASL executável | `coerencia.py`, `asl_lint.py` |
| 5 | Sequências dos caminhos críticos | Mermaid `sequenceDiagram`: caminho feliz, duplicidade, timeout/expiração, falha e recuperação, reconexão | revisão |
| 6 | Decisões (ADR) | escolha + alternativas + por quê com fonte (`fatos-verificados-aws.md`) + trade-off P1>P2>P3 | revisão |
| 7 | Testes, observabilidade e recuperação | pirâmide com o que cada nível prova e **não** prova; mapa cenário → teste; alarmes; runbook de recuperação | testes executados |

## Regras de coerência

- **Não desenhe integração que a implementação ou o serviço não suportem.** Cada seta de integração
  aponta para uma linha da matriz oficial (ex.: Express não tem callback; HTTP API não integra com
  DynamoDB; IoT Rules não tem ação EventBridge).
- Diagrama, contrato e implementação mudam **no mesmo PR**; o gate `aws` reprova divergência.
- Assíncrono responde **aceite + identificador consultável**; nunca "concluído".
- Síncrono só onde o tipo de workflow, a API de execução e o timeout da integração permitem (Express +
  `StartSyncExecution`, HTTP API ≤ 30 s, at-most-once).

## Checklist de revisão do plano (para `tech-lead-review`)

- [ ] Identidade de quem dispara aparece no diagrama e nunca vem do corpo da requisição.
- [ ] Toda espera tem timeout; todo callback tem `TimeoutSeconds` e Catch de timeout.
- [ ] Todo efeito com retry é idempotente (como, e qual teste prova).
- [ ] Escrita dupla (estado + evento) resolvida por outbox ou CDC — qual e por quê.
- [ ] Consumidores de evento toleram duplicidade, atraso e fora de ordem.
- [ ] Notificação tem caminho de reconciliação (consulta autoritativa).
- [ ] Metas de latência/custo por cenário, com forma de medir; nenhuma promessa genérica.
- [ ] Nível de validação declarado por funcionalidade (V0–V5) e o que falta para V4.
