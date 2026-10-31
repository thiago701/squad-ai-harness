# Memo — Arquiteto E (Domínio de Grafo Relacional, Kumo PQL & RelGT · `engenheiro-especificacao` + `arquiteto-ia`)

## Posição em 5 linhas
A tecnologia **Kumo (`KumoRFM` + `RelGT` + `PQL` + `DiskGraph`)** representa a transição de heurísticas manuais de engenharia de features para **Relational Deep Learning (RDL)** diretamente sobre tabelas e entidades conectadas no tempo. Na Squad AI, o repositório, os desenvolvedores/agentes, os commits/diffs, as 106 skills, os 25 especialistas JEV e os episódios de execução formam exatamente um **Relational Entity Graph (REG) heterogêneo temporal**. Ao implementar **DiskGraph (POC-01)** e **PQL + RelGT com In-Context Learning (POC-02)** em Rust, a Squad AI ganha um oráculo preditivo capaz de responder consultas SQL-like sobre eventos futuros de engenharia sem treinamento offline lento.

## Propostas concretas
1. **Esquema Canônico do Relational Entity Graph (REG) da Squad AI:**
   Modelar 6 tabelas/entidades relacionais conectadas por chaves estrangeiras temporais (`timestamp_unix`):
   - `modules (module_id, domain, loc, complexity, critical_tier)`
   - `files (file_id, module_id [FK], ext, churn_30d, touches_auth, touches_db)`
   - `skills (skill_id, model_tier, domain, token_cost_avg)`
   - `commits (commit_id, module_id [FK], files_count, diff_lines, timestamp_unix)`
   - `gate_episodes (episode_id, module_id [FK], skill_id [FK], gate_state, surprise, duration_ms, rss_mb, timestamp_unix)`
   - `infra_nodes (node_id, module_id [FK], resource_type, timeout_sec, memory_mb, drift_flag)`
2. **Gramática Executável Kumo PQL (POC-02):**
   Suportar consultas declarativas PQL nativas:
   ```sql
   PREDICT COUNT(gate_episodes.gate_state = 'BLOCKED', 0, 7, days) > 0
   FOR EACH modules.module_id
   ASSUMING touches_auth = true
   ```
   ```sql
   PREDICT AVG(gate_episodes.rss_mb, 0, 1, days)
   FOR EACH skills.skill_id
   ```
   ```sql
   PREDICT MAX(infra_nodes.drift_risk, 0, 30, days)
   FOR EACH modules.module_id
   ```
3. **Tokenização 5D RelGT + Atenção Híbrida + In-Context Learning (POC-01 & POC-02):**
   Cada nó no subgrafo amostrado até `anchor_time` é convertido num vetor de embedding combinando as **5 dimensões do artigo RelGT da Kumo AI**:
   - $E_{\text{feat}}$: atributos numéricos/categóricos normalizados da linha.
   - $E_{\text{type}}$: embedding do tipo da tabela (`MODULE`, `FILE`, `SKILL`, `EPISODE`, `INFRA`).
   - $E_{\text{hop}}$: distância topológica relativa à entidade-semente ($h \in \{0, 1, 2, 3\}$).
   - $E_{\text{time}}$: codificação harmônica/logarítmica do delta temporal $\Delta t = t_{\text{anchor}} - t_{\text{event}} \ge 0$.
   - $E_{\text{struct}}$: assinatura estrutural local (grau de entrada/saída, coeficiente de clustering local e comunidade Leiden).
   O **RelGT** aplica *Local Multi-Head Attention* sobre a vizinhança amostrada + *Global Centroid Attention* (K centróides aprendíveis do banco inteiro) e resolve o alvo via **In-Context Learning (ICL)** comparando a representação final da entidade-alvo com um *context set* de exemplos históricos rotulados anteriores a `anchor_time`!

## Respostas às tensões do meu domínio
- **T2 & T3 (Kumo em Rust sem Python):** O Kumo original usa Rust no seu motor `DiskGraph` de baixo nível e Python na camada de orquestração. Na nossa coleção de POCs, portamos **tanto o `DiskGraph` quanto o parser `PQL` e o forward-pass `RelGT` + `ICL` 100% para Rust nativo**, eliminando completamente o runtime Python!
- **T6 (Validação Científica):** Compararemos o **RelGT + PQL (POC-02)** contra a heurística atual do Go (`computeSurpriseLocked` / `MinVerifiedOccurrences = 3`) em tarefas reais de predição de falha de Gate e recomendação de especialista, medindo $F_1$, Precisão, Recall, Brier Score (calibração) e Latência.

## Riscos e armadilhas
- 🔴 **Vazamento do futuro (*Data Leakage*) no ICL:** Se os exemplos de contexto (*in-context support set*) vierem de timestamps posteriores ao `anchor_time`, a validação é inválida. Mitigação: particionamento temporal estrito ($t_{\text{support}} < t_{\text{anchor}} \le t_{\text{horizon}}$).

## Dúvidas que SÓ o usuário pode responder (com default)
- **Q5:** O catálogo de queries PQL das POCs deve cobrir tanto **classificação binária** (ex.: probabilidade de `BLOCKED` no Gate) quanto **regressão contínua** (ex.: predição de pico de RAM/latência e blast radius)? *(Default: Sim, implementar ambos os modos de predição no motor PQL+RelGT).*

## O que eu vetaria se visse no plano
- Veto chamar um modelo linear simples de "Kumo RelGT": a POC-01 e a POC-02 devem implementar de verdade a **Tokenização 5D**, o **Amostrador Temporal sem Vazamento**, o **Parser PQL (`PREDICT ... FOR EACH ... ASSUMING ...`)**, a **Atenção Híbrida Local+Global em Tiles** e o **In-Context Learning**.
