# Game day na AWS — roteiro

> Reference de `testes-resiliencia-caos-aws`. Base: REL12-BP05 (game days regulares), REL12-BP01
> (playbooks), REL12-BP04 (caos). Cultura, roteiro genérico de 2 h e regras do banco: `engenheiro-devops`
> (`chaos-engineering.md`). Aqui: o recorte AWS.

## 1. O que a AWS pede (REL12-BP05)

- Programa com **frequência, escopo e objetivos definidos** (a AWS não fixa cadência: "regularly").
- **Todos os stakeholders, inclusive negócio**; data, hora e cenário avisados.
- Execução com automação (FIS, CloudWatch, X-Ray, Systems Manager, Step Functions, IaC).
- **Retrospectiva sem culpados** com ações rastreadas.
- Antipadrões: procedimento nunca exercitado; decisores de negócio de fora; stakeholders sem aviso;
  testar só falha técnica; não realimentar o processo; culpar pessoas.
- REL12-BP01: playbooks **como código** (SSM Automation, Lambda, EventBridge, alarmes) e telemetria
  retida por tempo suficiente.

## 2. Papéis

| papel | responsabilidade |
|---|---|
| mestre do jogo | conduz, injeta a falha (FIS), controla o tempo e o critério de abortar |
| time de resposta | detecta, diagnostica e recupera usando os runbooks reais |
| observador/escriba | linha do tempo, decisões, lacunas |
| negócio | decide comunicação e impacto aceitável |
| segurança/operação | autoriza e acompanha (obrigatório no banco) |

## 3. Roteiro

1. **Antes:** objetivo e hipótese; cenário do catálogo (`catalogo-falhas-aws.md`); template FIS com stop
   conditions; ambiente (pré-prod por padrão); runbooks e acessos conferidos; comunicação enviada.
2. **Durante:** injeção; medir **tempo até detectar** (alarme), **até diagnosticar** e **até recuperar**;
   anotar tudo; abortar se sair do raio previsto.
3. **Depois:** comparação com a hipótese e o RTO; lacunas de alarme, runbook, permissão e arquitetura;
   ações com dono e prazo; experimento confirmado vira regressão automática no pipeline.

## 4. Relatório (modelo)

```markdown
# GAMEDAY-<AAAA-MM-DD> — <cenário>
Hipótese: ...            Ambiente: pré-prod | prod (aprovação: ...)
Injeção: template FIS <id>, alvos, duração, stop conditions
Linha do tempo: injeção hh:mm · alarme hh:mm · diagnóstico hh:mm · recuperação hh:mm
Resultado: hipótese confirmada | refutada — evidências (métricas, prints, logs)
RTO medido × meta: ...   Impacto ao usuário: ...
Lacunas e ações (dono, prazo): ...
Regressão automatizada criada: sim/não (onde)
```

## 5. Cadência sugerida (ponto de partida da Squad)

- Trimestral por sistema crítico; após mudança arquitetural grande; após incidente relevante (reproduzir
  o incidente como cenário).

## Fontes

- https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_testing_resiliency_game_days_resiliency.html
- https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_testing_resiliency_playbook_resiliency.html
- https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_testing_resiliency_failure_injection_resiliency.html
