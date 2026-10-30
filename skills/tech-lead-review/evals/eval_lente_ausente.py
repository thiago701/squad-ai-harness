"""
Eval do veredito do Modo Subagente (4 lentes) — tech-lead-review.

Critério de ganho (definido ANTES da edição do SKILL.md, 13/10/2026):
  1. Parte executável: o consolidador descrito hoje (junta findings e decide por severidade)
     é comparado com o consolidador da regra nova em 8 cenários de review. Métrica:
     aprovações FALSAS (APROVADO emitido com lente que não verificou nada, ou sobre um SHA
     que não é mais o do PR). Ingênuo: 5/8; regra nova: 0/8.
  2. Parte textual: o hub e a reference precisam declarar a regra (lente ausente/falha/
     timeout/JSON inválido = NAO_VERIFICADO, que nunca vira aprovação; veredito amarrado ao
     SHA revisado; revisor que edita o código perde a voz; rodada nova = worker novo que
     reproduz o defeito original e ataca o próprio fix). Vermelho no SKILL.md 1.0; verde no 1.1.

Técnica reescrita a partir de sangrokjung/claude-forge, skills/review-loop (MIT).
Rodar: python -m pytest skills/tech-lead-review/evals/eval_lente_ausente.py -q
"""
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SKILL = (RAIZ / "SKILL.md").read_text(encoding="utf-8")
REF = (RAIZ / "references" / "review-multi-dimensao.md").read_text(encoding="utf-8")
BASELINE_BYTES = 18234  # SKILL.md 1.0 medido em 13/10/2026
ORCAMENTO_BYTES = 1500  # teto do acréscimo no hub (~375 tokens)
LENTES = ("rev-arch", "rev-sec", "rev-perf", "rev-quality")


def _ok(sha="abc", tipos=(), editou=False):
    return {"status": "success", "sha_revisado": sha, "editou_codigo": editou,
            "findings": [{"tipo": t} for t in tipos]}


def consolidar_ingenuo(workers, sha_atual, veracode="APROVADO"):
    """Semântica descrita hoje: só os findings decidem; lente muda/caída não pesa."""
    if veracode == "BLOQUEADO":
        return "BLOQUEADO"
    tipos = [f["tipo"] for w in workers.values()
             if w and isinstance(w.get("findings"), list) for f in w["findings"]]
    if "bloqueante" in tipos:
        return "BLOQUEADO"
    if "necessario" in tipos:
        return "APROVADO_COM_RESSALVAS"
    return "APROVADO"


def consolidar(workers, sha_atual, veracode="APROVADO"):
    """Regra nova: aprovação só sobre o que foi de fato verificado, no SHA atual."""
    if veracode == "BLOQUEADO":
        return "BLOQUEADO"
    tipos = []
    for lente in LENTES:
        w = workers.get(lente)
        if (not w or w.get("status") != "success" or w.get("editou_codigo")
                or w.get("sha_revisado") != sha_atual or not isinstance(w.get("findings"), list)):
            continue  # lente sem voz: NAO_VERIFICADO
        tipos += [f["tipo"] for f in w["findings"]]
    if "bloqueante" in tipos:
        return "BLOQUEADO"  # bloqueio confirmado por lente válida vale mesmo com outra caída
    verificadas = sum(
        1 for lente in LENTES
        if (w := workers.get(lente)) and w.get("status") == "success" and not w.get("editou_codigo")
        and w.get("sha_revisado") == sha_atual and isinstance(w.get("findings"), list))
    if verificadas < len(LENTES):
        return "NAO_VERIFICADO"
    if "necessario" in tipos:
        return "APROVADO_COM_RESSALVAS"
    return "APROVADO"


def _todas(**sobrescritas):
    base = {lente: _ok() for lente in LENTES}
    base.update(sobrescritas)
    return base


# (nome, workers, sha_atual, veredito_correto)
CENARIOS = [
    ("tudo-verde", _todas(), "abc", "APROVADO"),
    ("ressalva", _todas(**{"rev-perf": _ok(tipos=("necessario",))}), "abc", "APROVADO_COM_RESSALVAS"),
    ("bloqueio-com-lente-caida", _todas(**{"rev-sec": _ok(tipos=("bloqueante",)), "rev-perf": None}),
     "abc", "BLOQUEADO"),
    ("sec-timeout", _todas(**{"rev-sec": {"status": "failed", "findings": []}}), "abc", "NAO_VERIFICADO"),
    ("perf-json-invalido", _todas(**{"rev-perf": {"status": "success", "sha_revisado": "abc",
                                                  "findings": "<<texto livre>>"}}),
     "abc", "NAO_VERIFICADO"),
    ("lente-ausente", {k: v for k, v in _todas().items() if k != "rev-arch"}, "abc", "NAO_VERIFICADO"),
    ("commit-depois-do-review", _todas(), "def", "NAO_VERIFICADO"),
    ("revisor-editou-codigo", _todas(**{"rev-quality": _ok(editou=True)}), "abc", "NAO_VERIFICADO"),
]


def _aprovacoes_falsas(fn):
    return sum(1 for _, w, sha, certo in CENARIOS
               if fn(w, sha).startswith("APROVADO") and not certo.startswith("APROVADO"))


@pytest.mark.parametrize("nome,workers,sha,certo", CENARIOS, ids=[c[0] for c in CENARIOS])
def test_consolidador_novo_acerta_o_veredito(nome, workers, sha, certo):
    assert consolidar(workers, sha) == certo


def test_placar_aprovacoes_falsas():
    assert (_aprovacoes_falsas(consolidar_ingenuo), _aprovacoes_falsas(consolidar)) == (5, 0)


def test_veto_veracode_continua_soberano():
    assert consolidar(_todas(), "abc", veracode="BLOQUEADO") == "BLOQUEADO"


# --------------------------------------------------------------------------------------
# Parte textual (vermelho no 1.0, verde no 1.1).
# --------------------------------------------------------------------------------------
def _secao_subagente():
    ini = SKILL.find("## Modo Subagente")
    assert ini != -1
    fim = SKILL.find("\n## ", ini + 5)
    return SKILL[ini:fim]


def test_hub_declara_nao_verificado():
    s = _secao_subagente()
    assert "NAO_VERIFICADO" in s
    baixo = s.lower()
    assert all(t in baixo for t in ("timeout", "json inválido", "ausente")), \
        "o hub precisa listar o que conta como lente sem voz"
    assert "nunca vira aprova" in baixo


def test_hub_amarra_veredito_ao_sha():
    s = _secao_subagente().lower()
    assert "sha" in s and "commit novo" in s


def test_hub_revisor_que_edita_perde_a_voz():
    assert "perde a voz" in _secao_subagente().lower()


def test_hub_rodada_nova_worker_novo_ataca_o_fix():
    s = _secao_subagente().lower()
    assert "worker novo" in s and "reproduz" in s and "ataca" in s


def test_reference_worker_devolve_sha_revisado():
    assert '"sha_revisado"' in REF


def test_reference_veredito_inclui_nao_verificado():
    assert "NAO_VERIFICADO" in REF


def test_hub_registra_procedencia_mit():
    assert "claude-forge" in SKILL and "review-loop" in SKILL and "MIT" in SKILL


def test_orcamento_de_tokens():
    tamanho = len(SKILL.encode("utf-8"))
    assert tamanho <= BASELINE_BYTES + ORCAMENTO_BYTES, f"hub cresceu demais: {tamanho} B"


def test_linha_de_defesa_intacta_e_por_ultimo():
    ini = SKILL.find("## 🛡️ Linha de Defesa de Prompt")
    assert ini != -1
    bloco = SKILL[ini:]
    assert all(f"\n{n}. **" in bloco for n in range(1, 7))
    assert "> Bloco canônico: ../../security/linha-defesa-prompt.md" in bloco
    assert "\n## " not in bloco[5:]
