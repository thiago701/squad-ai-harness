# Caça à falha silenciosa — passada dedicada do review (v1.7)

Use quando o diff mexe em tratamento de erro, fallback, retry ou valores default. É típico de
código gerado por agente: o código "funciona" porque o erro foi engolido. Complementa o sinal
"Erro engolido" de `sinais-deterministicos-de-risco.md` (que só detecta o padrão) com o
julgamento de cada tratador.

## 1. Inventário (antes de julgar)
Liste todo ponto do diff que trata ou desvia de erro: `try/catch`/`except`, callbacks de erro,
ramos de estado de falha, fallback e valor default devolvido em caso de falha, log seguido de
continuação, `?.`/`??`/`getOrElse`/`.unwrap_or`, retry com limite.

## 2. Perguntas por tratador
1. **Erros ocultáveis:** quais erros *inesperados* este bloco também captura? Liste os tipos.
2. **Especificidade:** captura só o tipo esperado ou um catch amplo (`Exception`, `except:`, `Throwable`)?
3. **Fallback:** o comportamento alternativo foi pedido na spec/história? Se não, ele mascara o defeito.
4. **Propagar:** o erro deveria subir para quem sabe decidir? Engolir aqui impede limpeza de recurso?
5. **Rastro:** o log tem operação, ids e estado suficientes para depurar daqui a 6 meses (evento + `trace_id`)?
6. **Retry:** quando as tentativas se esgotam, alguém fica sabendo (erro, métrica, alerta)?

## 3. Severidade fixa (sem negociação)
| Achado | Severidade |
|---|---|
| catch vazio; catch amplo que engole; retorno default/`null` em erro sem log | 🔴 bloqueia |
| mock, stub ou fake no caminho de produção (fallback para dublê) | 🔴 bloqueia |
| fallback não previsto na spec; retry esgotado em silêncio; erro que deveria propagar | 🟡 AGUARDANDO |
| log sem contexto (operação/ids) ou mensagem genérica ao usuário | 🔵 sugestão |

## 4. Formato do achado
`arquivo:linha` · severidade · o que está errado · **Erros ocultáveis:** <tipos> · impacto para
usuário/depuração · correção concreta (capturar o tipo específico, propagar, ou registrar o
fallback na spec). Tratador correto também se registra em uma linha — prova que foi olhado.

---
Procedência: técnica reescrita a partir de `plugins/pr-review-toolkit/agents/silent-failure-hunter.md`
de anthropics/claude-plugins-official @ `f8c5e7a1dcb71b10cb74586224b5401f3de5db28`, licença
Apache-2.0 (verificada via API do GitHub). Ficou de fora: convenções de log/IDs específicas da
origem e o tom do agente. Ganho medido: `tests/test_absorcao_2026_10_28.py`.
