"""Eval executavel de `compactacao-estrategica` -- pendencias, custo-beneficio e fail-open.

Lacunas absorvidas (tecnica reescrita da compactacao de eventos do google/adk-python,
`src/google/adk/apps/compaction.py`, commit 47e613d, licenca Apache-2.0; nenhum codigo copiado):
  (1) acao ainda ABERTA (sem observacao) no turno atual nunca entra na fatia esquecida --
      senao a observacao chega depois sem a acao (orfa);
  (2) acao aberta de um turno ANTERIOR (ja houve nova mensagem do usuario depois) e
      considerada morta e NAO bloqueia o corte para sempre;
  (3) so compacta se a fatia esquecida pesar mais que o ultimo resumo (senao o resumo novo
      nao encolhe o contexto e o custo da chamada e jogado fora);
  (4) fail-open: se o sumarizador falhar (resumo vazio/None), a visao e o historico
      original intacto -- a fatia nunca e descartada sem resumo.
Roda contra o modulo real `scripts/ponto_de_corte.py`.
"""

import importlib.util
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent
MODULO = RAIZ / "scripts" / "ponto_de_corte.py"


def carregar():
    spec = importlib.util.spec_from_file_location("ponto_de_corte", MODULO)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def pares(n, ini=0, tokens=10):
    ev = []
    for i in range(ini, ini + n):
        ev.append({"tipo": "acao", "id": f"a{i}", "tokens": tokens})
        ev.append({"tipo": "observacao", "id": f"a{i}", "tokens": tokens})
    return ev


def base():
    return [{"tipo": "system", "tokens": 10}, {"tipo": "user", "tokens": 10}]


def test_acao_aberta_do_turno_atual_nunca_e_esquecida():
    m = carregar()
    # acao "p" disparada cedo e ainda sem resposta (ex.: ferramenta longa rodando)
    ev = base() + pares(3) + [{"tipo": "acao", "id": "p", "tokens": 10}] + pares(20, ini=3)
    plano = m.planejar(ev, max_eventos=30, keep_first=1)
    if plano["decisao"] in ("condensar", "reset"):
        fatia = ev[plano["inicio"]:plano["fim"]]
        assert all(e.get("id") != "p" for e in fatia), plano
    else:
        assert plano["decisao"] == "adiar"


def test_acao_aberta_do_turno_atual_com_soft_adia_em_vez_de_cortar_antes_dela():
    m = carregar()
    ev = base() + [{"tipo": "acao", "id": "p", "tokens": 10}] + pares(20)
    plano = m.planejar(ev, max_eventos=30, keep_first=1)
    assert plano["decisao"] == "adiar", plano


def test_acao_aberta_de_turno_anterior_e_morta_e_nao_bloqueia():
    m = carregar()
    ev = (base() + [{"tipo": "acao", "id": "morta", "tokens": 10}]
          + [{"tipo": "user", "tokens": 10}] + pares(20))
    plano = m.planejar(ev, max_eventos=30, keep_first=1)
    assert plano["decisao"] == "condensar", plano


def test_nao_compacta_se_fatia_nao_pesa_mais_que_o_ultimo_resumo():
    m = carregar()
    ev = base() + [{"tipo": "resumo", "tokens": 5000}] + pares(20, tokens=10)
    # soft por eventos; a fatia (sem o resumo antigo) pesa ~200 tokens < 5000 do resumo
    plano = m.planejar(ev, max_eventos=30, keep_first=2)
    assert plano["decisao"] == "nao_compensa", plano


def test_compacta_quando_fatia_pesa_mais_que_o_ultimo_resumo():
    m = carregar()
    ev = base() + [{"tipo": "resumo", "tokens": 20}] + pares(20, tokens=100)
    plano = m.planejar(ev, max_eventos=30, keep_first=1)
    assert plano["decisao"] == "condensar", plano


def test_fail_open_sumarizador_falhou_mantem_historico_original():
    m = carregar()
    ev = base() + pares(30)
    plano = m.planejar(ev, max_eventos=40, keep_first=1)
    assert plano["decisao"] == "condensar"
    for falha in (None, "", "   "):
        assert m.aplicar(ev, plano, falha) == ev
    visao = m.aplicar(ev, plano, "resumo ok")
    assert len(visao) < len(ev)
    assert any(e["tipo"] == "resumo" and e.get("texto") == "resumo ok" for e in visao)


def test_skill_documenta_pendencias_custo_e_fail_open():
    skill = (RAIZ / "SKILL.md").read_text(encoding="utf-8")
    for termo in ("aberta", "fail-open", "47e613d", "Apache-2.0", "último resumo"):
        assert termo in skill, termo
