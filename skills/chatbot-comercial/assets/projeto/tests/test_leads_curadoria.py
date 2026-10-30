"""M3 (leads) e M4 (retreinamento com gate humano)."""

from __future__ import annotations

import pytest

from app.agente import Entrada
from app.curadoria import AprovacaoAusente
from app.leads import extrair_lead, qualificar


def test_qualificacao_vem_do_pack(servico):
    regras = servico.pack.captura_lead["qualificacao"]
    assert qualificar({"data_entrada": "2026-10-20", "hospedes": 2}, regras) == "quente"
    assert qualificar({"data_entrada": "2026-10-20"}, regras) == "morno"
    assert qualificar({}, regras) == "frio"


def test_qualificacao_respeita_regras_customizadas():
    """A config do pack é usada de verdade — não é decoração."""
    regras = {"vip": ["orcamento", "empresa"], "comum": ["orcamento"], "padrao": "novo"}
    assert qualificar({"orcamento": 5000, "empresa": "ACME"}, regras) == "vip"
    assert qualificar({"orcamento": 5000}, regras) == "comum"
    assert qualificar({}, regras) == "novo"
    assert qualificar({}, {}) == "frio"


def test_extrai_lead_com_nome_contato_e_datas(servico):
    lead = extrair_lead(
        "meu nome é Ana Paula, meu whats é 11999998888, quero de 20/10/2026 a 22/10/2026 para 2 pessoas",
        sessao="s1", canal="web", intencao="disponibilidade", usuario="u1", pack=servico.pack,
    )
    assert lead is not None
    assert lead.nome == "Ana Paula"
    assert lead.qualificacao == "quente"
    assert lead.contato_mask.endswith("8888")
    assert "99999" not in lead.contato_hash


def test_nao_gera_lead_sem_contato_real(servico):
    """Id de sessão do widget não é contato — lead vazio é ruído no painel."""
    assert extrair_lead(
        "tem vaga de 20/10/2026 a 22/10/2026 para 4 pessoas", sessao="web:demo",
        canal="web", intencao="disponibilidade", usuario="web:demo", pack=servico.pack,
    ) is None
    do_whatsapp = extrair_lead(
        "tem vaga de 20/10/2026 a 22/10/2026 para 4 pessoas", sessao="wa:5511999998888",
        canal="whatsapp", intencao="disponibilidade", usuario="5511999998888", pack=servico.pack,
    )
    assert do_whatsapp is not None and do_whatsapp.qualificacao == "quente"


def test_nao_gera_lead_em_intencao_nao_comercial(servico):
    assert extrair_lead(
        "que horas e o check in? 11999998888", sessao="s1", canal="web",
        intencao="checkin", usuario="u1", pack=servico.pack,
    ) is None


def test_dedupe_por_contato_e_nao_rebaixa_qualificacao(servico):
    comum = {"sessao": "s1", "canal": "web", "usuario": "u1", "pack": servico.pack}
    quente = extrair_lead(
        "sou a Ana, 11999998888, de 20/10/2026 a 22/10/2026 para 2 pessoas",
        intencao="disponibilidade", **comum,
    )
    frio = extrair_lead("11999998888 quanto custa?", intencao="tarifa", **comum)
    primeiro = servico.leads.salvar(quente)
    segundo = servico.leads.salvar(frio)
    assert primeiro == segundo
    salvos = servico.leads.listar()
    assert len(salvos) == 1
    assert salvos[0]["qualificacao"] == "quente"


def test_exportacao_csv_mascara_contato(servico):
    lead = extrair_lead(
        "sou o Joao, 11988887777, quero 12/12/2026 para 2 pessoas",
        sessao="s2", canal="whatsapp", intencao="disponibilidade", usuario="u2", pack=servico.pack,
    )
    identificador = servico.leads.salvar(lead)
    servico.leads.marcar(identificador, "contatado")
    csv = servico.leads.exportar_csv()
    assert "contato_mask" in csv
    assert "11988887777" not in csv
    assert "contatado" in csv
    assert servico.leads.listar(qualificacao="quente")


def test_curadoria_bloqueia_reindexacao_sem_aprovacao(servico):
    item = servico.curadoria.marcar_ruim(
        interacao_id=None, pergunta="qual a senha do wifi", motivo="sem_fonte"
    )
    servico.curadoria.propor(
        item, fonte_alvo="estrutura", texto_proposto="A senha do wi-fi é entregue no check-in."
    )
    with pytest.raises(AprovacaoAusente):
        servico.curadoria.aplicar(item, servico.base, reindexar=servico.reindexar)


def test_aprovacao_exige_identificar_quem_aprovou(servico):
    item = servico.curadoria.marcar_ruim(interacao_id=None, pergunta="tem heliponto")
    servico.curadoria.propor(item, fonte_alvo="estrutura", texto_proposto="Não há heliponto.")
    with pytest.raises(AprovacaoAusente):
        servico.curadoria.aprovar(item, aprovado_por="  ")


def test_proposta_vazia_e_rejeitada(servico):
    item = servico.curadoria.marcar_ruim(interacao_id=None, pergunta="x")
    with pytest.raises(ValueError):
        servico.curadoria.propor(item, fonte_alvo="", texto_proposto="")
    with pytest.raises(ValueError):
        servico.curadoria.aprovar(item, aprovado_por="thiago")


def test_ciclo_completo_curadoria_versao_e_rollback(servico):
    antes = servico.agente.responder(
        Entrada(texto="tem bicicletario", sessao="s3", usuario="u3")
    )
    assert antes.sem_fonte

    item = servico.curadoria.marcar_ruim(
        interacao_id=None, pergunta="tem bicicletario", motivo="sem_fonte"
    )
    servico.curadoria.propor(
        item,
        fonte_alvo="estrutura",
        texto_proposto="Há bicicletário coberto com dez ganchos ao lado do estacionamento.",
    )
    servico.curadoria.aprovar(item, aprovado_por="thiago")
    relatorio = servico.curadoria.aplicar(item, servico.base, reindexar=servico.reindexar)
    assert relatorio["versao_id"] > 0

    depois = servico.agente.responder(
        Entrada(texto="tem bicicletario", sessao="s4", usuario="u3")
    )
    assert not depois.sem_fonte
    assert "bicicletário" in depois.texto.lower()

    versoes = servico.curadoria.versoes()
    assert versoes and versoes[0]["aprovado_por"] == "thiago"
    servico.curadoria.rollback(versoes[0]["id"], servico.base, reindexar=servico.reindexar)


def test_rejeitar_tira_da_fila(servico):
    item = servico.curadoria.marcar_ruim(interacao_id=None, pergunta="tem heliponto")
    servico.curadoria.rejeitar(item, aprovado_por="thiago")
    assert all(p["id"] != item for p in servico.curadoria.pendentes())


def test_rollback_de_versao_inexistente(servico):
    with pytest.raises(ValueError):
        servico.curadoria.rollback(9999, servico.base, reindexar=servico.reindexar)


def test_item_inexistente(servico):
    with pytest.raises(ValueError):
        servico.curadoria.aprovar(4242, aprovado_por="thiago")
