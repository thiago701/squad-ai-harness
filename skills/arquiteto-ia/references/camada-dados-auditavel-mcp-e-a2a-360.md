# Camada de Fornecimento de Dados Auditáveis via MCP + Step Functions Express (`0 Lambda`) para Pipelines Multi-Agente A2A (Avaliação 360°)

> **Origem:** validado em produção/sandbox na integração entre *Consolidador de Treinamentos* e *Avaliação 360° Enterprise (`avaliacao-enterprise-a2a`)* (out/2026).
> **Vínculos:** `LL-0042`, `LL-0052`, `LL-0053` · `instinto-0019` · `Baterias Q10 e Q12`.

---

## 1. Problema Arquitetural: Como Alimentar Agentes Avaliadores (A2A) sem Alucinação nem Acoplamento Frágil

Quando um pipeline multi-agente (como o **Avaliação 360° Enterprise** com `Agente Coletor` → `Agente Avaliador` → `Agente Revisor` → `Agente PDI`) precisa incorporar evidências reais de outro domínio (ex.: treinamentos obrigatórios, certificações em IA/DevOps, horas dedicadas e evolução de ranking ao longo do ano):
- **Anti-padrão 1 (Scraping / Leitura de Telas):** fazer o agente ler HTML ou CSVs soltos gera alucinação numérica e quebra quando o layout muda.
- **Anti-padrão 2 (Acesso Direto ao Banco Operacional):** expor a tabela transacional principal aos agentes de IA mistura modelos de leitura de UI com insumos analíticos e exige recomputar elegibilidade complexa no prompt do LLM.
- **Padrão Canônico (Camada Auditável Dual: API Serverless `0 Lambda` + Servidor MCP `JSON-RPC 2.0`):**
  1. **Dataset Tabular Determinístico + Histórico de Marcos/Conquistas (`contracts/auditoria-360.schema.json`):** pré-calcula 45 colunas tabulares por colaborador, 187 marcos gamificados retroativos (`2026-02` a `2026-10`) e bijeções mensais de ranking (`1..N`);
  2. **Insumo Estruturado Pronto para o Prompt Avaliador (`insumoAvaliacao360A2A`):** entrega o status de compliance do Gate 4 (`"complete"` para `>= 80%` concluído ou `"partial"`), `pontosDestacar[]` com prefixo normativo `"(Treinamentos) "` e `insumo_texto_pdi` determinístico;
  3. **Duplo Canal de Consumo com Autenticação por Sistema Cliente (`clientId` + `apiKey` + `escopos[]`):**
     - **Canal Cloud (Data Lake / RH / A2A remoto):** `POST /integracao/auditoria-360` → Step Functions Express `consolidador-treinamentos-auditoria` (`0 Lambda`) validando segredo no Secrets Manager + leitura DynamoDB/S3;
     - **Canal Agêntico Local/Remoto (MCP stdio `JSON-RPC 2.0`):** `scripts/mcp/servidor_auditoria_360_mcp.py` expondo 5 tools tipadas para agentes Claude Code / LangGraph / A2A.

---

## 2. Arquitetura de Armazenamento Híbrido (DynamoDB + Materialização Dual S3 `< 256 KB`)

```
[ETL Retroativo / Pós-Sync: gerar_auditoria_360.py]
       │
       ├──► DynamoDB: auditoria-desempenho-treinamentos (884 itens, PITR + Deletion Protection)
       │      ├─ PK=META#AUDITORIA_360 | SK=SNAPSHOT#2026               (1 item executivo)
       │      ├─ PK=DATASET#2026       | SK=COLAB#<colabId>             (58 linhas tabulares)
       │      ├─ PK=COLAB#<colabId>    | SK=MARCO#<data>#<codigo>       (187 marcos conquistados)
       │      └─ PK=RANKING#<periodo>  | SK=POS#<001..058>#<colabId>    (638 posições: ciclo + anual + 9 meses)
       │
       └──► S3: auditoria-360/* (Materialização Dual)
              ├─ dataset-consolidado-2026.json  (~302 KB — completo para Data Lake e MCP)
              ├─ dataset-tabular-2026.csv       (58 × 45 — ingestão direta Pandas/Spark/PowerBI)
              ├─ marcos-conquistas-2026.jsonl   (187 linhas NDJSON — stream de eventos/conquistas)
              └─ dataset-tabular-api-2026.json  (~134 KB < 190 KB — projeção compacta para Step Functions Express!)
```

### Regra de Ouro contra `States.DataLimitExceeded` (`256 KB`) no Step Functions Express (`LL-0053`)
- O estado `Task` (`arn:aws:states:::aws-sdk:s3:getObject`) falha com `States.DataLimitExceeded` se o objeto S3 lido ultrapassar `262.144 bytes` (`256 KB`).
- Sempre materialize uma **Projeção Compacta para API (`dataset-tabular-api-2026.json`, `< 190 KB`)** omitindo textos longos redundantes que já existem nos itens individuais do DynamoDB (`COLAB#<id>`), mantendo o arquivo analítico completo (`dataset-consolidado-2026.json`) separado para Data Lake e MCP.

---

## 3. Autenticação Multi-Cliente com Escopos Granulares no Secrets Manager

Cada sistema consumidor recebe um `clientId`, uma `apiKey` exclusiva e uma lista restrita de `escopos[]` dentro do segredo `consolidador-treinamentos/integracao-clientes-api-keys`:

| `clientId` | Sistema Consumidor | Escopos Autorizados (`escopos[]`) |
|---|---|---|
| `avaliacao-360-a2a` | Pipeline Multi-Agente Avaliação 360° (`avaliacao-enterprise-a2a`) | `dataset:read`, `colaborador:read`, `marcos:read`, `ranking:read` |
| `datalake-corp` | Enterprise Corporate Data Lake & Analytics | `dataset:read`, `marcos:read`, `ranking:read` |
| `rh-corporativo` | Sistemas Corporativos de RH / Talent Management | `dataset:read`, `colaborador:read`, `ranking:read` |

### Validação JSONata Segura (`auditoria-auth.jsonata`)
- **Regra Gramatical (`LL-0052`):** no motor JSONata do AWS Step Functions, **nunca use o operador unário `!`** (`!$exists(...)`); use obrigatoriamente **`$not(...)`**:
  ```jsonata
  (
    $cfg := $lookup($secret.clientes, $clientId);
    $clientValido := $exists($cfg) and $cfg.ativo = true and $cfg.apiKey = $apiKey;
    $escopoOk := $clientValido and ($escopoRequerido in $cfg.escopos);
    {
      "autorizado": $clientValido and $escopoOk,
      "motivo": $not($clientValido) ? "credencial_invalida" : ($not($escopoOk) ? "escopo_insuficiente" : "ok")
    }
  )
  ```
- **Invariante 5 (Zero Eco de Segredo):** o estado `GetSecretValue` armazena o segredo em `Assign` interno apenas para o passo de validação; nenhum estado terminal (`200`, `401`, `403`, `400`) inclui `apiKey` ou `SecretString` no `Output`.

---

## 4. Contrato das 5 Tools do Servidor MCP (`servidor_auditoria_360_mcp.py`)

O servidor MCP implementa `JSON-RPC 2.0` (`initialize`, `tools/list`, `tools/call`) sobre `stdio`, exigindo `clientId` e `apiKey` em toda chamada:

1. **`obter_resumo_executivo_360`** (`escopo: dataset:read`): retorna KPIs globais auditados da equipe (`58` colaboradores, `334/682 = 49,0%`, `27` colaboradores `"complete"` elegíveis ao Gate 4, `187` marcos conquistados) e o catálogo de marcos.
2. **`listar_dataset_tabular_360`** (`escopo: dataset:read`): retorna o dataset tabular de 45 colunas com filtros por `perfilCarreira`, `statusComplianceA2A` (`complete`/`partial`), `faixaDesempenhoCiclo` e `limite`.
3. **`obter_dossie_treinamentos_colaborador`** (`escopo: colaborador:read`): retorna o dossiê completo de 1 colaborador (`colabId` ou `funcional`), seu histórico de marcos/conquistas e o bloco **`insumoAvaliacao360A2A`** pronto para injeção direta no `Agente Coletor` / `Agente PDI` do projeto `avaliacao-enterprise-a2a`.
4. **`listar_historico_marcos_360`** (`escopo: marcos:read`): filtra conquistas retroativas por `colabId`, `codigoMarco`, `categoria` (`TRILHA`, `EXCELENCIA`, `CADENCIA`, `ENGAJAMENTO_EXTRA`, `RANKING`) ou `mesCalendario` (`2026-02..2026-10`).
5. **`consultar_ranking_ciclo_mensal`** (`escopo: ranking:read`): retorna o ranking ordenado (`1..58`) para `2026-H2`, `2026-ANUAL` ou qualquer mês retroativo (`2026-02` a `2026-10`).

---

## 5. Invariantes Contínuos de Qualidade (`Baterias Q10 e Q12`)

Toda camada de fornecimento de dados A2A/MCP deve ser protegida por testes contínuos determinísticos:
- **Bijeção de Rankings (`Q10.4`, `Q10.5`, `Q12.5`):** `set(posicoes) == set(range(1, N + 1))` no ciclo, no ano e em todos os meses retroativos;
- **Conservação de Entregas no Tempo (`Q10.6`):** a soma das entregas mensais (`2026-02..2026-10`) de cada colaborador deve ser igual a `cursos_concluidos_total`;
- **Paridade Cruzada 4-Planos (`Q12.1..Q12.4`):** paridade exata `58 == 58 == 58 == 58` entre Roster, Relatório do Gestor pós-manifesto, JSON de Auditoria 360° e CSV/JSONL exportados.
