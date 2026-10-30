# Templates da comissão

## 1. Brief (`comissao/00-brief.md`)

```markdown
# BRIEF DA COMISSÃO — <projeto>
> Motor: squad-pipeline (tier <large>). Fase: Intake + Research + Plan → GATE 1.
> Arbitragem: P1-Simplicidade > P2-Performance > P3-CustoBaixo. Segurança não negociável. Saída: PLANO + SPEC, NENHUM CÓDIGO.

## 1. Pedido (verbatim, resumido sem perder requisito)
<frontend / backend / dados / segurança / conta-região / critérios de aceite do usuário>
<ajustes do usuário em voo: "DECISÃO DO USUÁRIO (dd/mm hh:mm): ..." — decisão fechada, a comissão não rediscute>

## 2. Contexto de negócio (dos arquivos)
<caminhos dos arquivos staged> · <fatos relevantes> · <contagens, nunca nomes>

## 3. Fatos de plataforma que a comissão deve respeitar (verificar, não assumir)
- <serviço>: <fato> (fonte ou "a verificar")

## 4. Referência de UX/código (ponto de partida, não cópia)
<tokens, componentes, arquivos staged>

## 5. Tensões que a comissão precisa resolver
T1. <conflito 1 — por que é conflito>
...
T10. <...>

## 6. Formato de retorno de cada arquiteto (≤ 1.200 palavras)
# Memo — <papel>
## Posição em 5 linhas
## Propostas concretas (numeradas, cada uma com "por quê" ligado a P1/P2/P3 ou Segurança)
## Respostas às tensões do meu domínio
## Riscos e armadilhas (🔴🟠🟡)
## Dúvidas que SÓ o usuário pode responder (máx. 5, cada uma com default)
## O que eu vetaria se visse no plano

## 7. Adendos (dd/mm hh:mm) — <nova avaliação pedida pelo usuário, com fatos já levantados e hipóteses>
```

## 2. Prompt de despacho (Rodada 1)

```
Você é o <Papel> da comissão de arquitetos virtuais da Squad AI.
Carregue a doutrina com a ferramenta Skill: `<skill>`. Leia o brief em <caminho> e, se precisar, os arquivos de contexto que ele aponta.
OBJETIVO DE NEGÓCIO: <1 parágrafo com o porquê do usuário + decisões fechadas>
Seu foco: <tensões Tx..Ty> + <entregáveis específicos do papel>
CRITÉRIO DE ACEITE: <verificável: fontes, custo explícito, contrato completo...>
FORMATO DE RETORNO: §6 do brief (+ seções extras do papel). Grave em <comissao/rodada1/X-papel.md> e responda só com um resumo de 10 linhas. pt-br.
```

## 3. ADR (Rodada 2)

```markdown
## ADR-NN — <decisão em uma linha>
**Decisão.** <o quê, com números> (quem propôs: A, B…)
**Por quê.** <P1/P2/P3 ou segurança — 1–3 frases>
**Rejeitado.** <alternativa> (quem propôs) — <motivo>. <alternativa 2> — <motivo>.
**Condições.** <🔴 itens de GATE 2 que a decisão exige>
```
Seções fixas do documento: **Consenso (sem voto)** · ADRs · **Dúvidas consolidadas para o usuário (não votáveis, com default)**.

## 4. Cédula de voto (Rodada 2)

```
RODADA 2 — leia <ADRs-v1.md>. Como <Papel>, vote cada ADR: APROVO ou OBJEÇÃO (motivo ≤ 120 palavras + alternativa concreta).
Atenção especial: <ADR-x (onde sua proposta foi rejeitada — diga se aceita o motivo)>, <ADR-y (pergunta técnica específica do seu domínio)>.
Grave em <comissao/rodada2/voto-X.md> e responda com um resumo de 5 linhas. pt-br.
```

## 5. Confirmação (Rodada 3)

```
RODADA 3 (final) — leia <ADRs-v2.md> (<o que foi incorporado do seu voto>).
Responda em ≤ 8 linhas, sem gravar arquivo: "SEM DÚVIDAS" ou a dúvida/erro restante com correção concreta.
Ponto específico: <a mudança mais arriscada da v2 vista pelo seu domínio — ex.: "isso mantém as 2 Queries?">
```

## 6. GATE 1 — mensagem ao usuário (estrutura)
1. Onde estão os arquivos (1 linha).
2. Como a dúvida foi zerada (rodadas, placar, o que a revisão independente achou).
3. Arquitetura em 1 frase + custo.
4. Respostas às perguntas que ele fez durante o processo (com o ADR).
5. **Desvios do pedido original** (cada um vira Qn).
6. Pré-requisitos 🔴 antes do primeiro deploy.
7. "Responda 'aprovado' para os defaults, ou ajuste Qx."
