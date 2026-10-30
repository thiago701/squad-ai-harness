# Refatoração de Código Legado — protocolo seguro (N2 gated)

> Fonte: `labs/jev-code-review/docs/07-evolucao-staff.md` (fase 3) + motor
> `src/jev_review/refactor_engine.py`. Regra-mãe: **nunca refatore sem mecanismo
> para provar que o comportamento foi preservado.** Toda edição é N2 (versionada,
> reversível); commit/push/delete seguem N3.

## 1. Antes de tocar: caracterizar (o legado não se lê — se mapeia)

| O que descobrir | Como |
|---|---|
| Regras de negócio implícitas | comentários, mensagens de erro, validações, nomes de branch/issue, docs antigos |
| Fluxos críticos | pontos de entrada públicos, ordenação de chamadas, transações |
| Side effects | escrita em arquivo/DB/fila/cache dentro de métodos "de leitura" |
| Integrações externas | clientes HTTP/SDK/webservice, timeouts, retries, formatos de contrato |
| Contratos públicos | classes/métodos consumidos fora (registrar em `retrocompat.*` se alterar) |
| Dependências ocultas | reflexão, service locator, estaticos globais, config carregada em runtime |

**Saída obrigatória:** nota de caracterização (o que o código FAZ, com evidência
arquivo:linha) antes de qualquer edição.

## 2. Proteção: testes de caracterização primeiro

1. Escreva testes que **fixam o comportamento atual** (inclusive os "bugs" que os
   consumidores dependem) — é o contrato de segurança da refatoração.
2. Suíte verde = linha de base. Sem suíte verde, **não se refatora**: aumenta-se
   primeiro a capacidade de detectar regressão.
3. Priorize caracterizar os **fluxos críticos e side effects** (§1), não o código trivial.

## 3. Refatoração incremental (estado A → B → C)

- **Pequenas transformações verificáveis**, uma por ciclo: extrair método → renomear
  → mover → simplificar condicional → introduzir teste. Nunca reescrita épica.
- Após **cada** passo: rodar a suíte. Vermelho = **reverter o passo** e investigar
  (é N2; reverter é barato, não insistir).
- Métricas ANTES/DEPOIS a cada passo (`src/jev_review/metrics.py`): o gate rejeita
  automaticamente complexidade/LOC/duplicação/dívida que **subam** sem ganho.
- A ordem importa: **simplificação antes de abstração**. Remover código morto e
  duplicação antes de introduzir padrões.

## 4. Validação final (antes de propor o PR-rascunho)

- Suíte completa verde (unitária + integração + contrato, quando houver).
- `qualidade_nova >= qualidade_anterior` com deltas medidos no relatório.
- Re-review pelo pipeline JEV (cenário C, offline) + tribunal (court) sem blocker novo.
- Mudanças em API pública → `retrocompat.*` avaliado e consumidores mapeados.

## 5. O que NUNCA fazer no legado

- Reescrita completa "porque está feio" (P1: feio que funciona > bonito que regride).
- Abstração sem segundo uso real (anti-overengineering; o tribunal rebaixa).
- "Corrigir de passagem" bugs não caracterizados (vira teste de caracterização,
  depois vira correção separada e documentada).
- Alterar comportamento para "o que deveria ser" sem decisão humana explícita.
