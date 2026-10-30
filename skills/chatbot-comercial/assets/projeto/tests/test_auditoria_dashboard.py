"""M5 — trilha, custo com teto, LGPD e dashboard."""

from __future__ import annotations

from dataclasses import replace

from app.agente import Entrada
from app.auditoria import exportar_trilha
from app.dashboard import custo_por_tenant, metricas, top_sem_resposta
from app.llm import RespostaLlm
from app.servico import Servico


class LlmCaro:
    """LLM real de teste que declara custo — permite exercitar o teto."""

    def __init__(self, custo: float = 0.30):
        self.custo = custo
        self.chamadas = 0

    def responder(self, *, sistema, pergunta, trechos, tenant, tarefa):
        del sistema, pergunta, tenant, tarefa
        self.chamadas += 1
        return RespostaLlm(
            texto=f"{trechos[0].text} (fonte: {trechos[0].source})",
            modelo="caro-v1",
            tokens_entrada=800,
            tokens_saida=120,
            custo_brl=self.custo,
            latencia_ms=42.0,
        )


def test_trilha_registra_todos_os_campos(servico):
    servico.responder(Entrada(texto="que horas serve o cafe", sessao="s1", usuario="u1"))
    linha = servico.conexao.execute("SELECT * FROM interacoes").fetchone()
    assert linha["intencao"] == "cafe"
    assert linha["fontes"]
    assert linha["modelo"] == "extrativo"
    assert linha["latencia_ms"] >= 0
    assert linha["correlacao"]


def test_trilha_nao_grava_dado_pessoal(servico):
    servico.responder(
        Entrada(texto="meu email e joao@exemplo.com, tem cafe da manha?", sessao="s1", usuario="u1")
    )
    linha = servico.conexao.execute("SELECT pergunta FROM interacoes").fetchone()
    assert "joao@exemplo.com" not in linha["pergunta"]
    assert "[EMAIL]" in linha["pergunta"]


def test_timeline_e_contexto_para_humano(servico):
    for texto in ("que horas e o check in", "isso e um pessimo servico"):
        servico.responder(Entrada(texto=texto, sessao="s9", usuario="u9"))
    contexto = servico.trilha.contexto_para_humano("s9")
    assert contexto["turnos"] == 2
    assert "checkin" in contexto["intencoes"]
    assert contexto["historico"][0]["pergunta"]


def test_teto_por_conversa_degrada_para_extrativo(config):
    apertado = replace(config, teto_custo_conversa_brl=0.20)
    servico = Servico.montar(apertado)
    caro = LlmCaro(custo=0.30)
    servico.agente = type(servico.agente)(
        pack=servico.pack, base=servico.base, llm=caro, config=apertado
    )
    try:
        primeira = servico.responder(Entrada(texto="qual o valor da suite master", sessao="c1", usuario="u"))
        assert primeira.modelo == "caro-v1"
        segunda = servico.responder(Entrada(texto="o cafe da manha esta incluso", sessao="c1", usuario="u"))
        assert segunda.modelo == "extrativo"
        assert segunda.motivo == "teto_conversa"
        assert caro.chamadas == 1
    finally:
        servico.conexao.close()


def test_custos_acumulam_por_conversa_e_mes(servico):
    servico.responder(Entrada(texto="qual o endereco da pousada", sessao="cX", usuario="u"))
    custos = servico.trilha.custos("cX")
    assert custos.conversa_brl == 0.0
    assert custos.teto_mes_brl > 0
    assert not custos.mes_estourado


def test_metricas_e_contencao(servico):
    servico.responder(Entrada(texto="tem estacionamento coberto", sessao="ok1", usuario="u"))
    servico.responder(Entrada(texto="isso e um pessimo servico", sessao="ruim1", usuario="u"))
    m = metricas(servico.conexao, servico.config.tenant)
    assert m["conversas"] == 2
    assert m["conversas_escaladas"] == 1
    assert m["taxa_contencao"] == 0.5
    assert m["custo_por_conversa_brl"] == 0.0


def test_top_sem_resposta_agrupa(servico):
    for sessao in ("a", "b"):
        servico.responder(Entrada(texto="voces tem heliponto", sessao=sessao, usuario="u"))
    topo = top_sem_resposta(servico.conexao, servico.config.tenant)
    assert topo[0]["ocorrencias"] == 2
    assert "heliponto" in topo[0]["pergunta"]


def test_custo_por_tenant(servico):
    servico.responder(Entrada(texto="a piscina e aquecida", sessao="t1", usuario="u"))
    linhas = custo_por_tenant(servico.conexao)
    assert linhas[0]["tenant"] == servico.config.tenant


def test_consentimento_bloqueia_lead(config):
    exigente = replace(config, exigir_consentimento=True)
    servico = Servico.montar(exigente)
    try:
        servico.responder(
            Entrada(
                texto="sou a Ana, 11999998888, quero 20/10/2026 a 22/10/2026 para 2 pessoas",
                sessao="p1", usuario="11999998888",
            )
        )
        assert servico.leads.listar() == []

        from app.privacidade import hash_contato

        servico.lgpd.registrar_consentimento(hash_contato("11999998888"), consentido=True)
        servico.responder(
            Entrada(
                texto="sou a Ana, 11999998888, quero 20/10/2026 a 22/10/2026 para 2 pessoas",
                sessao="p1", usuario="11999998888",
            )
        )
        assert len(servico.leads.listar()) == 1
    finally:
        servico.conexao.close()


def test_expurgo_e_direito_ao_esquecimento(servico):
    servico.responder(
        Entrada(
            texto="sou o Joao, 11988887777, quero 12/12/2026 para 2 pessoas",
            sessao="e1",
            usuario="u",
        )
    )
    from app.privacidade import hash_contato

    assert servico.lgpd.esquecer(hash_contato("11988887777"))["leads"] == 1

    servico.conexao.execute("UPDATE interacoes SET ts = '2000-01-01T00:00:00+00:00'")
    servico.conexao.commit()
    resultado = servico.lgpd.expurgar()
    assert resultado["interacoes"] >= 1


def test_exportar_trilha_jsonl(servico, tmp_path):
    servico.responder(Entrada(texto="tem berco para bebe", sessao="j1", usuario="u"))
    destino = tmp_path / "trilha.jsonl"
    assert exportar_trilha(servico.conexao, servico.config.tenant, destino) == 1
    assert destino.read_text(encoding="utf-8").count("\n") == 1


def test_painel_agrega_tudo(servico):
    servico.responder(Entrada(texto="qual o valor da suite master", sessao="pa", usuario="u"))
    painel = servico.painel()
    assert painel["vertical"]
    assert painel["metricas"]["conversas"] == 1
    assert painel["chunks_indexados"] > 0
