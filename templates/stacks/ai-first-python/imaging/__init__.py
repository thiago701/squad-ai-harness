"""Slot para a camada DETERMINÍSTICA do seu domínio — renomeie esta pasta.

Chame de `imaging/`, `parsing/`, `audio/`, `text/` — o que for. A ideia é a que
se repete em todo produto AI-First: **o determinístico protege o generativo**.

Antes da IA: validação barata que rejeita entrada ruim. Rejeitar custa
milissegundos; gerar a partir dela custa segundos e dinheiro — e o resultado
seria reprovado de qualquer jeito. Num projeto real, essa validação rejeitou 34%
das entradas antes de qualquer chamada paga.

Depois da IA: validação de saída que decide entre entregar, regerar uma vez, ou
degradar para o terminal.
"""
