# Starter AI-First (Python) — os contratos, sem o produto

Base extraída de uma POC AI-First real (totem multimodal, 4 semanas, 131 testes). Contém
**só o que se repete** em qualquer produto onde a IA é o produto — nada específico do
domínio de origem.

## O que este starter dá, e por que cada peça existe

| Arquivo | Resolve |
|---|---|
| `ai/ports.py` | O contrato de provedor. Nenhum SDK de fornecedor no domínio |
| `ai/errors.py` | Taxonomia transitório × permanente. Sem ela, retry vira gerador de custo |
| `ai/router.py` | Roteamento por regras, disjuntor com lockout, teto de orçamento |
| `ai/providers/terminal.py` | O provedor que **não pode falhar** — fim de toda cadeia |
| `infra/telemetry.py` | Marcos T0…Tn, percentis, selo em todo número |
| `infra/queue.py` | Fila persistente + worker. HTTP nunca segura inferência longa |

## As cinco regras que o starter codifica

**1. Nenhum SDK de fornecedor fora de `ai/providers/`.** Trocar de provedor é trocar uma
linha de configuração. O adapter tem três responsabilidades, nesta ordem: traduzir o erro
do fornecedor para a taxonomia da casa, reportar custo realizado, respeitar o timeout que
o chamador passa.

**2. Toda cadeia termina em algo que não pode falhar.** Um produto de IA sem terminal
determinístico tem a disponibilidade do seu fornecedor mais frágil. O terminal é local,
barato, instantâneo — e é parte do desenho, não plano B.

**3. Erro permanente vai para lockout, não para cooldown.** Um 401 repetido três vezes é
três vezes o mesmo 401 e o triplo do tempo. Falha que não volta sozinha exige humano.

**4. Teto de orçamento é sinal de primeira classe.** Em 80% degrada para o caminho barato
e avisa; em 100% trava no terminal. O serviço **não para** — degrada.

**5. Todo número leva selo.** `medido` · `proxy` · `estimado` · `pendente`. Nenhuma
estimativa apresentada como medição.

## Como usar

```bash
cp -r templates/stacks/ai-first-python <seu-projeto>/backend/app
```

Depois: implemente um adapter real em `ai/providers/`, ajuste `Decisao` no router para os
sinais do seu domínio, e escreva o `TerminalProvider` do **seu** caso — a resposta local
que sempre existe.

## Ordem de implementação que funcionou

1. **Mock primeiro.** Com latência simulada e falha programada — senão o frontend é escrito
   assumindo resposta instantânea e o caminho de erro nunca é exercitado.
2. **Fluxo inteiro em mock**, ponta a ponta, antes de gastar um centavo.
3. **Telemetria antes de otimizar** qualquer coisa.
4. **Um provedor real**, medido.
5. **Router e segundo provedor**, com fault injection.

## Skills relacionadas

`arquiteto-ia` (camadas AI-First) · `engenheiro-langgraph` (workflow stateful) ·
`ai-imagem-generativa` (providers de imagem) · `ai-evaluation` (baseline e gate) ·
`integracao-hardware-periferico` (periféricos) · `resiliencia-agente` (taxonomia herdada).
