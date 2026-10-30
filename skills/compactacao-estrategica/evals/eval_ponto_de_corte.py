"""Eval executavel de `compactacao-estrategica` -- planejamento do ponto de corte.

Mede as lacunas absorvidas (tecnica reescrita do condenser do OpenHands/software-agent-sdk,
commit 4fedb7e, licenca MIT):
  (1) gatilho soft (excesso de eventos) adia quando nao ha corte valido; gatilho hard
      (tokens ou pedido explicito/erro de janela) nunca adia -- cai em reset;
  (2) preserva system + keep_first e a cauda recente; corta para ~metade (cache de prompt
      invalidado poucas vezes);
  (3) o corte nunca separa acao de sua observacao (sem orfaos na visao resultante);
  (4) resumo anterior entra na fatia esquecida (resumo recursivo);
  (5) varios motivos ao mesmo tempo -> vale o corte mais agressivo.
Roda contra o modulo real `scripts/ponto_de_corte.py`.
"""

import importlib.util
import json
import pathlib
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
MODULO = RAIZ / "scripts" / "ponto_de_corte.py"


def carregar():
    spec = importlib.util.spec_from_file_location("ponto_de_corte", MODULO)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sessao(n_pares, tokens=10):
    """system + user + n pares acao/observacao."""
    ev = [{"tipo": "system", "tokens": tokens}, {"tipo": "user", "tokens": tokens}]
    for i in range(n_pares):
        ev.append({"tipo": "acao", "id": f"a{i}", "tokens": tokens})
        ev.append({"tipo": "observacao", "id": f"a{i}", "tokens": tokens})
    return ev


def sem_orfaos(visao):
    acoes = {e["id"] for e in visao if e["tipo"] == "acao"}
    obs = {e["id"] for e in visao if e["tipo"] == "observacao"}
    return acoes == obs


def test_abaixo_dos_limites_nao_faz_nada():
    m = carregar()
    plano = m.planejar(sessao(5), max_eventos=40, max_tokens=10_000)
    assert plano["decisao"] == "nada"


def test_excesso_de_eventos_corta_para_metade_e_preserva_cabeca_e_cauda():
    m = carregar()
    ev = sessao(30)  # 62 eventos
    plano = m.planejar(ev, max_eventos=60, keep_first=1)
    visao = m.visao_resultante(ev, plano)
    assert plano["decisao"] == "condensar" and plano["motivos"] == ["EVENTOS"]
    assert len(visao) <= 30
    assert visao[0]["tipo"] == "system" and visao[1]["tipo"] == "user"
    assert visao[2]["tipo"] == "resumo"
    assert visao[-1] == ev[-1]


def test_corte_nunca_separa_acao_da_observacao():
    m = carregar()
    for keep in (1, 2, 3):
        for maximo in (20, 21, 22, 23):
            ev = sessao(15)
            plano = m.planejar(ev, max_eventos=maximo, keep_first=keep)
            visao = m.visao_resultante(ev, plano)
            assert plano["decisao"] == "condensar"
            assert sem_orfaos(visao), (keep, maximo, plano)


def test_resumo_anterior_entra_na_fatia_esquecida():
    m = carregar()
    ev = sessao(20)
    ev.insert(2, {"tipo": "resumo", "tokens": 50, "texto": "resumo da rodada 1"})
    plano = m.planejar(ev, max_eventos=30, keep_first=1)
    fatia = ev[plano["inicio"]:plano["fim"]]
    assert any(e["tipo"] == "resumo" for e in fatia)
    visao = m.visao_resultante(ev, plano)
    assert sum(1 for e in visao if e["tipo"] == "resumo") == 1


def _loop_gigante():
    ev = [{"tipo": "system", "tokens": 10}, {"tipo": "user", "tokens": 10},
          {"tipo": "acao", "id": "x", "tokens": 10}]
    ev += [{"tipo": "assistente", "tokens": 10} for _ in range(30)]
    ev.append({"tipo": "observacao", "id": "x", "tokens": 10})
    return ev


def test_gatilho_soft_sem_corte_valido_adia():
    m = carregar()
    plano = m.planejar(_loop_gigante(), max_eventos=20, keep_first=1)
    assert plano["decisao"] == "adiar"


def test_gatilho_hard_sem_corte_valido_faz_reset():
    m = carregar()
    ev = _loop_gigante()
    plano = m.planejar(ev, pedido=True, keep_first=1)
    visao = m.visao_resultante(ev, plano)
    assert plano["decisao"] == "reset"
    assert [e["tipo"] for e in visao] == ["system", "resumo"]


def test_excesso_de_tokens_e_hard_e_respeita_metade_do_teto():
    m = carregar()
    ev = sessao(30, tokens=100)  # 6200 tokens
    plano = m.planejar(ev, max_tokens=5000, keep_first=1)
    visao = m.visao_resultante(ev, plano)
    assert plano["motivos"] == ["TOKENS"] and plano["decisao"] == "condensar"
    assert sum(e.get("tokens", 0) for e in visao if e["tipo"] != "resumo") <= 2500
    assert sem_orfaos(visao)


def test_varios_motivos_vale_o_corte_mais_agressivo():
    m = carregar()
    ev = sessao(30, tokens=100)
    so_eventos = m.planejar(ev, max_eventos=60, keep_first=1)
    so_tokens = m.planejar(ev, max_tokens=2000, keep_first=1)
    ambos = m.planejar(ev, max_eventos=60, max_tokens=2000, keep_first=1)
    assert set(ambos["motivos"]) == {"EVENTOS", "TOKENS"}
    assert ambos["fim"] == max(so_eventos["fim"], so_tokens["fim"])


def test_cli_json_ascii_e_skill_documenta(tmp_path):
    entrada = tmp_path / "eventos.json"
    entrada.write_text(json.dumps(sessao(30)), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(MODULO), str(entrada), "--max-eventos", "60"],
                          capture_output=True)
    assert proc.returncode == 0
    saida = json.loads(proc.stdout.decode("ascii"))
    assert saida["decisao"] == "condensar"
    skill = (RAIZ / "SKILL.md").read_text(encoding="utf-8")
    for termo in ("soft", "hard", "cache", "4fedb7e", "MIT", "ponto_de_corte.py"):
        assert termo in skill
