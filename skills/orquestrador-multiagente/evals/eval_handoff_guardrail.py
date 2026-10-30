"""Eval de `orquestrador-multiagente` v1.1.0 -- tripwire tipado e filtro de handoff.

Lacuna (v1.0.0): a skill falava de disjuntores de handoff (ciclos) e de plano-como-contrato, mas nao
tinha (a) checagem de entrada/saida que ABORTA o fluxo com erro tipado no lugar de deixar o pipeline
seguir, nem (b) poda do historico entregue ao agente seguinte num handoff.
Tecnica reescrita do openai/openai-agents-python (MIT, commit 9abc918): guardrails com tripwire e
input filter de handoff que descarta itens de ferramenta/raciocinio. Sem copia de codigo.
"""

import importlib.util
import pathlib
import sys

import pytest

_RAIZ = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("handoff_guard", _RAIZ / "scripts" / "handoff_guard.py")
mod = importlib.util.module_from_spec(_spec)
sys.modules["handoff_guard"] = mod
_spec.loader.exec_module(mod)


def _historico():
    h = [{"tipo": "mensagem", "papel": "usuario", "texto": "Analise o repo X e gere o relatorio."}]
    for i in range(6):
        h.append({"tipo": "chamada_ferramenta", "nome": "grep", "args": f"padrao {i}"})
        h.append({"tipo": "saida_ferramenta", "texto": f"linha {i} " + "z" * 800})
        h.append({"tipo": "raciocinio", "texto": "pensando " * 40})
    h.append({"tipo": "mensagem", "papel": "assistente", "texto": "Achei 3 pontos; passo ao revisor."})
    h.append({"tipo": "handoff", "destino": "revisor"})
    h.append({"tipo": "mensagem", "papel": "usuario", "texto": "Revise so a parte de seguranca."})
    return h


def test_filtro_remove_ferramentas_raciocinio_e_handoff():
    filtrado, _ = mod.filtrar_handoff(_historico())
    tipos = {item["tipo"] for item in filtrado}
    assert tipos == {"mensagem"}


def test_filtro_preserva_ordem_e_ultima_tarefa():
    filtrado, _ = mod.filtrar_handoff(_historico())
    assert filtrado[-1]["texto"] == "Revise so a parte de seguranca."
    assert filtrado[0]["texto"].startswith("Analise o repo X")


def test_filtro_nao_muta_entrada_e_mede_economia():
    h = _historico()
    copia = [dict(i) for i in h]
    _, medida = mod.filtrar_handoff(h)
    assert h == copia
    assert medida["tokens_antes"] > medida["tokens_depois"] > 0
    assert medida["economia_pct"] >= 80


def test_filtro_janela_de_mensagens_mantem_a_primeira_tarefa():
    filtrado, _ = mod.filtrar_handoff(_historico(), max_mensagens=1)
    assert [i["texto"] for i in filtrado][-1] == "Revise so a parte de seguranca."
    assert len(filtrado) == 1


def test_tripwire_de_entrada_aborta_antes_do_agente():
    chamado = []

    def agente(entrada):
        chamado.append(entrada)
        return "ok"

    def sem_segredo(entrada):
        return mod.Veredito(disparou="sk-" in entrada, info="segredo na entrada")

    with pytest.raises(mod.TripwireEntrada) as exc:
        mod.executar_com_guardas(agente, "use a chave sk-123", entrada=[sem_segredo])
    assert chamado == []
    assert exc.value.guarda == "sem_segredo"
    assert isinstance(exc.value, mod.TripwireDisparado)


def test_tripwire_de_saida_rejeita_resultado():
    def saida_vazia(saida):
        return mod.Veredito(disparou=not saida.strip(), info="saida vazia")

    with pytest.raises(mod.TripwireSaida) as exc:
        mod.executar_com_guardas(lambda e: "  ", "tarefa", saida=[saida_vazia])
    assert exc.value.info == "saida vazia"


def test_sem_disparo_devolve_saida_e_resultados():
    ok = lambda x: mod.Veredito(disparou=False)
    saida, resultados = mod.executar_com_guardas(lambda e: e.upper(), "abc", entrada=[ok], saida=[ok])
    assert saida == "ABC"
    assert len(resultados) == 2


def test_guarda_que_explode_e_fail_closed():
    def quebrada(_):
        raise RuntimeError("classificador fora do ar")

    with pytest.raises(mod.TripwireEntrada):
        mod.executar_com_guardas(lambda e: e, "x", entrada=[quebrada])


def test_skill_documenta_e_versiona():
    skill = (_RAIZ / "SKILL.md").read_text(encoding="utf-8")
    assert "version: 1.1.0" in skill or "version: 1.2.0" in skill
    assert "Tripwire" in skill and "filtro de handoff" in skill.lower()
    assert "9abc918" in skill and "Linha de Defesa de Prompt" in skill
