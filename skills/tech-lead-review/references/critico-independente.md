# Crítico Independente — como discordar com evidência

> Carregado sob demanda pelo `tech-lead-review`. Implementa o §11 do ciclo 2026-09-14:
> *"mecanismo de Critic/Reviewer independente para decisões críticas; evite consenso artificial;
> quando houver divergência, compare soluções utilizando evidências."*
>
> Não é uma skill nova. É um **protocolo** dentro do `tech-lead-review`, porque um crítico que
> vira agente separado com catálogo próprio é mais uma boca na *agent soup* — e a independência
> que importa não vem do processo, vem de **o que o crítico não vê**.

## 1. O que "independente" quer dizer aqui

Independência é uma propriedade da **entrada**, não do prompt. Um segundo agente que recebe
"o autor decidiu X porque Y — você concorda?" vai concordar: a justificativa ancorou a resposta.

| | Crítico ancorado (inútil) | Crítico independente |
|---|---|---|
| Recebe | decisão + justificativa do autor | **problema, restrições e critérios de aceite** |
| Não recebe | — | a decisão do autor, o nome de quem propôs, o histórico da discussão |
| Produz | "concordo, com ressalvas" | **sua própria proposta**, depois o confronto |
| Falha típica | consenso em 1 volta | divergência genuína que exige evidência |

**Regra de ouro:** o crítico só vê a decisão do autor **depois** de registrar a própria proposta.
Inverter essa ordem anula o mecanismo.

## 2. Quando acionar (e quando não)

| Aciona crítico independente | Não aciona |
|---|---|
| Escolha arquitetural que custa caro para desfazer (persistência, fronteira de serviço, protocolo) | correção localizada com teste que prova |
| Introdução de dependência nova ou de serviço gerenciado | refactor interno sem mudança de contrato |
| Mudança em fronteira de segurança (authz, cripto, IAM, entrada externa) | ajuste de texto, log, formatação |
| Alteração de teto em budget (cobertura, performance, severidade) | qualquer coisa que o gate mecânico já reprova sozinho |
| Trade-off em que P1/P2/P3 não decidem claramente | decisão já coberta por ADR vigente |

> Onde o gate mecânico decide, **não convoque ninguém**: exit code não precisa de segunda opinião.
> O crítico existe para o que nenhum oráculo automático resolve.

## 3. Protocolo em 4 passos

### Passo 1 — Enunciado cego

O árbitro escreve o problema **sem a solução**: objetivo de negócio, restrições duras, critérios
de aceite, o que já existe no repositório. Passa isso ao crítico. Nada de "o autor pensou em…".

### Passo 2 — Proposta independente

O crítico produz sua própria proposta antes de ver qualquer outra. Registra em
`.claude/pipeline/<slug>/critico-proposta.md`. **Timestamp importa**: é o que prova que a
proposta veio antes do confronto.

### Passo 3 — Confronto por evidência

Agora as duas propostas ficam lado a lado. Cada divergência entra numa linha:

| Ponto | Proposta A | Proposta B | Evidência que decide | Como obter | Custo |
|---|---|---|---|---|---|
| Persistência | DynamoDB single-table | Aurora Serverless | p95 do padrão de acesso real e custo/1M req | rodar o access pattern contra os dois por 1 h | 2 h |
| Cold start | AOT | JVM + SnapStart | cold start p50 medido no artefato real | `bench/medir.py` nos dois | 30 min |

**Regras do confronto:**

1. **Divergência sem evidência proposta é divergência mal formulada.** Se ninguém consegue dizer
   *qual medição decidiria*, a discussão é de gosto — e aí P1 > P2 > P3 decide, em uma linha.
2. **Evidência barata roda antes de discutir.** Trinta minutos de benchmark encerram três horas
   de debate. (Neste ciclo: a crença "AOT é mais rápido" caiu em 6 minutos de medição — AOT é
   **34× melhor no cold start** e **33% pior no p50 quente**. Nenhum dos dois lados estava certo.)
3. **Evidência cara vira decisão reversível.** Se medir custa mais que desfazer, escolha o
   caminho mais fácil de desfazer e registre o gatilho de revisão.
4. **Concordância em tudo é sinal de alarme, não de sucesso.** Se as duas propostas coincidem em
   todos os pontos, ou o problema era trivial (não precisava de crítico) ou o enunciado vazou a
   solução (passo 1 falhou). Diga qual dos dois — não celebre.

### Passo 4 — Veredito e registro

```
DECISÃO: <o que foi decidido>
DIVERGÊNCIAS: <n> — resolvidas por evidência: <n>; por P1>P2>P3: <n>; escaladas ao humano: <n>
EVIDÊNCIA DECISIVA: <medição, com arquivo e número>
DESCARTADO: <a proposta que perdeu, e o que faria ela ganhar>
GATILHO DE REVISÃO: <o fato futuro que reabriria esta decisão>
```

O campo **DESCARTADO** não é cortesia: ele é o que permite reabrir a decisão sem refazer a
análise no dia em que a premissa mudar.

## 4. Limite de voltas (nunca laço infinito)

| Volta | O que acontece |
|---|---|
| 1 | propostas independentes + confronto |
| 2 | só se surgiu **evidência nova**; reformular sem evidência nova é proibido |
| 3 | **última** — encerra por P1 > P2 > P3 ou escala ao humano |

Três voltas sem convergir **não** viram quatro. Escale com o quadro de divergências em mãos:
o humano decide melhor vendo o trade-off do que vendo mais uma rodada de argumentos.

## 5. Anti-padrões que este protocolo existe para matar

| Anti-padrão | Como aparece | Antídoto |
|---|---|---|
| **Consenso artificial** | "concordo com a abordagem do colega" sem análise própria | passo 1 cego + proposta registrada com timestamp |
| **Deferência ao modelo maior** | opus propôs, sonnet aceita | evidência decide, não o roteamento de modelo |
| **Crítica cosmética** | 12 comentários de nome de variável, zero sobre a fronteira do serviço | severidades: MINOR não atrasa entrega; o crítico responde pelas 7 dimensões |
| **Divergência performática** | discordar para parecer rigoroso | toda divergência declara a evidência que a decidiria |
| **Autoridade por antiguidade** | "sempre fizemos assim" | ADR vigente vale; hábito não documentado, não |

## 6. Como o gate verifica que o protocolo rodou

`scripts/quality/gate_runner.py` lê `reports/code-review.json`. Para decisão marcada como
crítica, o arquivo precisa trazer:

```json
{
  "critico_independente": {
    "proposta_registrada_em": "2026-09-14T05:12:00-03:00",
    "confronto_registrado_em": "2026-09-14T05:41:00-03:00",
    "divergencias": 3,
    "resolvidas_por_evidencia": 2,
    "resolvidas_por_prioridade": 1,
    "escaladas": 0
  }
}
```

`proposta_registrada_em` **posterior** a `confronto_registrado_em` = protocolo violado
(o crítico viu a decisão antes de propor) → **MAJOR**, e a revisão não conta.
