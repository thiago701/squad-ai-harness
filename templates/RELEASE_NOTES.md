# Notas de Versão — [Nome do Projeto] vX.Y.Z

<!--
  RELEASE NOTES (NOTAS DE VERSÃO)
  Quando usar: a cada release que vá para homologação ou produção.
  Quem preenche: Tech Lead a partir dos PRs/commits da versão; humano revisa.
  Regra de ouro: escreva para QUEM CONSOME a release (usuários, integradores, operação),
  não para quem escreveu o código. Destaque BREAKING CHANGES com guia de migração.
  Versionamento: Semantic Versioning (https://semver.org) — MAJOR.MINOR.PATCH.
    MAJOR = quebra compatibilidade | MINOR = funcionalidade compatível | PATCH = correção.
-->

| Campo | Valor |
|---|---|
| **Projeto** | [Nome do Projeto] |
| **Versão (semver)** | [vX.Y.Z] |
| **Data de lançamento** | [AAAA-MM-DD] |
| **Tipo de release** | [Major \| Minor \| Patch \| Hotfix] |
| **Autor(es)** | [Nome / Agente] |
| **Status** | [Rascunho \| Publicada \| Revertida] |
| **Documentos relacionados** | [DEPLOYMENT_PLAN.md] · [PRD.md] |

---

## 1. Destaques

<!-- 2 a 4 frases sobre o que esta versão entrega de mais relevante.
     É o "resumo executivo" que stakeholders leem. -->

[Esta versão entrega X e Y, melhorando Z. O destaque é a funcionalidade A, que reduz o tempo de B.]

## 2. Novas Funcionalidades

<!-- Liste o que passou a existir. Vincule ao requisito do PRD (RF-XXX) quando possível.
     Descreva o BENEFÍCIO para o usuário, não só a mudança técnica. -->

| ID | Funcionalidade | Benefício | Referência |
|---|---|---|---|
| FEAT-001 | [Exportação de relatórios em PDF] | [usuário baixa relatórios sem planilha intermediária] | [RF-012 / PR #123] |
| FEAT-002 | [...] | [...] | [...] |

## 3. Correções de Bugs

<!-- O que foi corrigido. Inclua o sintoma percebido pelo usuário, não só a causa técnica. -->

| ID | Correção | Sintoma anterior | Referência |
|---|---|---|---|
| FIX-001 | [Corrige cálculo de juros em datas de virada de mês] | [valor divergente no fechamento] | [ISSUE #45] |
| FIX-002 | [...] | [...] | [...] |

## 4. Breaking Changes e Guia de Migração

<!-- A seção MAIS importante. Toda quebra de compatibilidade DEVE estar aqui com passo a passo
     de migração. Se esta seção tem itens, a versão é MAJOR. Se está vazia, declare explicitamente. -->

> [ ] **Esta versão NÃO contém breaking changes.** (marque e pule esta seção se verdadeiro)

| ID | O que mudou | Impacto | Ação necessária |
|---|---|---|---|
| BREAK-001 | [Endpoint `GET /v1/pedidos` removido] | [integrações que o usam quebram] | [migrar para `GET /v2/pedidos` — ver abaixo] |

### Guia de Migração — BREAK-001

<!-- Passo a passo concreto. Inclua exemplo de antes/depois sempre que possível. -->

1. [Substitua a chamada `GET /v1/pedidos` por `GET /v2/pedidos`.]
2. [Ajuste o parser: o campo `valor` agora é objeto `{ "moeda": "BRL", "montante": 100.0 }`.]
3. [Teste em homologação antes de promover.]

```diff
- GET /v1/pedidos        →  { "valor": 100.0 }
+ GET /v2/pedidos        →  { "valor": { "moeda": "BRL", "montante": 100.0 } }
```

## 5. Melhorias de Performance

<!-- Ganhos mensuráveis. Sempre com número (antes → depois). Sem número, é só "ficou melhor". -->

| Melhoria | Métrica | Antes | Depois |
|---|---|---|---|
| [Cache na consulta de catálogo] | [p95 do endpoint /catalogo] | [800 ms] | [120 ms] |
| [...] | [...] | [...] | [...] |

## 6. Melhorias de Segurança

<!-- Correções e endurecimentos de segurança. NÃO exponha detalhes de CVE não corrigida.
     Vincule ao SECURITY_REVIEW.md quando aplicável. -->

| Melhoria | Tipo | Severidade tratada | Referência |
|---|---|---|---|
| [Atualização de dependência X para versão sem CVE] | [Dependência] | [Alta] | [CVE-AAAA-NNNN] |
| [Rate limiting no endpoint de login] | [Hardening] | [Média] | [SECURITY_REVIEW.md] |

## 7. Outras Melhorias

<!-- Refatorações visíveis, ajustes de UX, documentação, débito técnico quitado. -->

- [Mensagens de erro mais claras no formulário de cadastro]
- [Documentação da API atualizada (API_SPEC.md)]

## 8. Problemas Conhecidos

<!-- Seja honesto. Liste limitações e bugs conhecidos com workaround e previsão de correção.
     Omitir problema conhecido gera retrabalho e perda de confiança. -->

| ID | Problema | Impacto | Workaround | Previsão de correção |
|---|---|---|---|---|
| KNOWN-001 | [Exportação falha para relatórios > 10 mil linhas] | [usuários com grande volume] | [filtrar por período] | [vX.Y.(Z+1)] |
| KNOWN-002 | [...] | [...] | [...] | [...] |

## 9. Compatibilidade

<!-- O que esta versão exige do ambiente e com o que ela conversa. -->

| Item | Requisito / Compatibilidade |
|---|---|
| **Runtime** | [Java 25 / Python 3.13.5 / Node 22 — conforme a stack] |
| **Banco de dados** | [PostgreSQL ≥ 15 — exige migração M-045] |
| **Versão de API** | [v2 — v1 descontinuada nesta versão] |
| **Dependências externas** | [serviço X ≥ vN] |

## 10. Como Atualizar

<!-- Instrução curta e direta de como sair da versão anterior para esta. Aponte para o DEPLOYMENT_PLAN. -->

1. [Leia a seção 4 (Breaking Changes) e aplique a migração, se houver.]
2. [Execute o deploy conforme DEPLOYMENT_PLAN.md.]
3. [Valide com os smoke tests pós-deploy.]

## 11. Agradecimentos / Contribuidores

<!-- Opcional. Pessoas/agentes que contribuíram nesta versão. -->

- [Nome / Agente — contribuição]

---

## Histórico de Revisões (deste documento)

| Versão | Data | Autor | Mudança |
|---|---|---|---|
| 0.1.0 | [AAAA-MM-DD] | [autor] | Criação inicial |
