"""M2 — ingestão multiformato, indexação incremental, citação e privacidade."""

from __future__ import annotations

import sys

import pytest

from app import conhecimento
from app.conhecimento import citar, extrair_texto, indexar, recuperar
from app.privacidade import hash_contato, mascarar_contato, redigir


class _MountFalso:
    """Conexão de mentira que recusa certos journal_modes, como NFS/SMB fazem.

    `sqlite3.Connection` é um tipo imutável — não dá para monkeypatch. Como
    `escolher_modo_de_jornal` só precisa de `execute`/`commit`, testar a função
    isolada é mais honesto do que fingir um driver.
    """

    def __init__(self, *recusados: str):
        self.recusados = recusados
        self.tentados: list[str] = []

    def execute(self, sql: str, *args):
        import sqlite3

        if "journal_mode=" in sql:
            modo = sql.split("=", 1)[1].strip()
            self.tentados.append(modo)
            if modo in self.recusados:
                raise sqlite3.OperationalError("disk I/O error")
            return _Linha(modo.lower())
        return _Linha(None)

    def commit(self):
        return None


class _Linha:
    def __init__(self, valor):
        self.valor = valor

    def fetchone(self):
        return (self.valor,)


def test_journal_cai_para_o_primeiro_modo_que_o_filesystem_aceita():
    """Mount de rede recusa WAL *e* DELETE — medido no mount real, não suposto."""
    from app.db import escolher_modo_de_jornal

    mount = _MountFalso("WAL", "DELETE")
    assert escolher_modo_de_jornal(mount) == "truncate"
    assert mount.tentados[:2] == ["WAL", "TRUNCATE"]


def test_journal_usa_wal_quando_da():
    from app.db import escolher_modo_de_jornal

    assert escolher_modo_de_jornal(_MountFalso()) == "wal"


def test_journal_falha_alto_quando_nenhum_modo_serve():
    """Sem journal possível, o certo é falhar dizendo o que fazer."""
    import sqlite3

    from app.db import MODOS_DE_JORNAL, escolher_modo_de_jornal

    with pytest.raises(sqlite3.OperationalError, match="disco local"):
        escolher_modo_de_jornal(_MountFalso(*MODOS_DE_JORNAL))


def test_banco_real_sobe_e_migra(tmp_path):
    from app import db

    conexao = db.conectar(tmp_path / "var" / "x.db")
    db.migrar(conexao)
    assert conexao.execute("SELECT count(*) FROM interacoes").fetchone()[0] == 0
    conexao.close()


def test_ingestao_markdown(config):
    texto = extrair_texto(config.dados_do_vertical / "tarifas.md")
    assert "Chalé Standard" in texto


def test_ingestao_csv(config, tmp_path):
    arquivo = config.dados_do_vertical / "extras.csv"
    arquivo.write_text("item,valor\ntraslado,180\nberço,0\n", encoding="utf-8")
    assert "item: traslado. valor: 180." in extrair_texto(arquivo)


def test_ingestao_json(config):
    texto = extrair_texto(config.dados_do_vertical / "ocupacao.json")
    assert "Chalé Standard" in texto


def test_ingestao_html(config):
    arquivo = config.dados_do_vertical / "site.html"
    arquivo.write_text(
        "<html><style>p{}</style><body><h1>Piscina</h1><p>Aberta das 8h às 20h.</p></body></html>",
        encoding="utf-8",
    )
    texto = extrair_texto(arquivo)
    assert "Piscina" in texto and "p{}" not in texto


def test_ingestao_export_whatsapp(config):
    arquivo = config.dados_do_vertical / "conversa.txt"
    arquivo.write_text(
        "12/03/2026 09:14 - Cliente: tem berço disponível?\n"
        "12/03/2026 09:15 - Recepção: temos duas unidades, sem custo.\n",
        encoding="utf-8",
    )
    texto = extrair_texto(arquivo)
    assert "Cliente: tem berço disponível?" in texto
    assert "Recepção: temos duas unidades" in texto


def test_pdf_sem_dependencia_avisa(config, monkeypatch):
    arquivo = config.dados_do_vertical / "menu.pdf"
    arquivo.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setitem(sys.modules, "pypdf", None)
    with pytest.raises(RuntimeError, match="pypdf"):
        extrair_texto(arquivo)


def test_indexacao_incremental_nao_reprocessa(servico):
    relatorio = servico.reindexar(forcar=False)
    assert relatorio["novas"] == []
    assert set(relatorio["inalteradas"]) >= {"tarifas", "politicas"}


def test_indexacao_detecta_arquivo_alterado(servico):
    alvo = servico.config.dados_do_vertical / "estrutura.md"
    alvo.write_text(alvo.read_text(encoding="utf-8") + "\nHá bicicletário coberto.\n",
                    encoding="utf-8")
    relatorio = servico.reindexar(forcar=False)
    assert "estrutura" in relatorio["atualizadas"]


def test_indexacao_reporta_erro_de_arquivo_vazio(servico):
    (servico.config.dados_do_vertical / "vazio.md").write_text("", encoding="utf-8")
    relatorio = servico.reindexar(forcar=False)
    assert any("vazio" in e for e in relatorio["erros"])


def test_pasta_inexistente_falha_alto(config):
    base = conhecimento.construir_base(config)
    import shutil

    shutil.rmtree(config.dados_do_vertical)
    with pytest.raises(FileNotFoundError):
        indexar(base, config)


def test_recuperar_respeita_score_minimo(servico):
    trechos = recuperar(servico.base, "cafe da manha", servico.config)
    assert trechos
    assert all(t.score >= servico.config.score_minimo for t in trechos)


def test_frases_relevantes_recorta_e_pontua():
    from app.conhecimento import frases_relevantes

    texto = "# Titulo A piscina é aquecida. O estacionamento é coberto. Não há elevador."
    recorte, nota = frases_relevantes("tem estacionamento coberto", texto)
    assert recorte.startswith("O estacionamento é coberto")
    assert nota > 0
    vazio, sem_nota = frases_relevantes("e ai", "Uma frase. Outra frase.")
    assert vazio.startswith("Uma frase") and sem_nota == 0.0
    unico, _ = frases_relevantes("qualquer", "")
    assert unico == ""


def test_citar_remove_duplicata_e_preserva_ordem(servico):
    trechos = recuperar(servico.base, "politica de cancelamento", servico.config)
    fontes = citar(trechos)
    assert len(fontes) == len(set(fontes))


@pytest.mark.parametrize(
    ("bruto", "marcador"),
    [
        ("meu email e joao@exemplo.com", "[EMAIL]"),
        ("meu telefone e (11) 99999-8888", "[TELEFONE]"),
        ("cpf 123.456.789-00", "[CPF]"),
        ("cartao 4111 1111 1111 1111", "[CARTAO]"),
    ],
)
def test_redacao_de_dado_pessoal(bruto, marcador):
    saida = redigir(bruto)
    assert marcador in saida
    assert "9999" not in saida.replace("[TELEFONE]", "")


def test_redacao_idempotente():
    uma = redigir("liga no 11999998888")
    assert redigir(uma) == uma


def test_hash_e_mascara_de_contato():
    assert hash_contato("11999998888") == hash_contato("11999998888")
    assert hash_contato("11999998888") != hash_contato("11999998887")
    assert hash_contato("") == ""
    assert mascarar_contato("5511999998888").endswith("8888")
    assert mascarar_contato("joao@exemplo.com") == "jo***@exemplo.com"
    assert mascarar_contato("") == ""
