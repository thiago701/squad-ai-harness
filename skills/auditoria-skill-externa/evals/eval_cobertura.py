"""
Eval de cobertura fail-closed do pré-screen — auditoria-skill-externa.

Critério de ganho (definido ANTES da edição, 15/10/2026):
  1. Parte executável (scripts/security/skill_prescreen.py): 6 cenários em que a skill
     esconde algo que o scanner NÃO leu — symlink para fora da raiz (ex.: chave privada),
     symlink interno, symlink para diretório, arquivo acima de MAX_BYTES, arquivo com
     UTF-8 inválido e SKILL.md que é symlink. Métrica: falsos SAFE (recommendation ==
     "SAFE" com algo não analisado). Antes: 6/6. Depois: 0/6, sem mudar o veredito de
     skill benigna nem o placar do repo (90 skills, 10 achados, 0 bloqueios).
  2. Parte textual: o hub declara a regra "não analisado ≠ seguro" (inventário, symlink
     não seguido, falha de carga é achado, INCOMPLETO nunca vira APROVAR) e a procedência.

Técnica reescrita a partir de cisco-ai-defense/skill-scanner @64101c5 (Apache-2.0).
Rodar: python -m pytest skills/auditoria-skill-externa/evals/eval_cobertura.py -q
"""
import os
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
REPO = RAIZ.parent.parent
sys.path.insert(0, str(REPO / "scripts" / "security"))
import skill_prescreen as sp  # noqa: E402

SKILL = (RAIZ / "SKILL.md").read_text(encoding="utf-8")
BASELINE_BYTES = 13210  # SKILL.md 1.0 medido em 15/10/2026
ORCAMENTO_BYTES = 1800  # teto do acréscimo no hub (~450 tokens)


def _skill(raiz, nome="cand"):
    d = raiz / nome
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("# Ok\nFormata texto.\n", encoding="utf-8")
    return d


def _symlink(alvo, link, **kw):
    try:
        os.symlink(alvo, link, **kw)
    except (OSError, NotImplementedError):
        pytest.skip("symlink indisponível neste SO/usuário")


def cen_symlink_fora(tmp):
    segredo = tmp / "fora" / "chave_privada"
    segredo.parent.mkdir()
    segredo.write_text("-----BEGIN KEY-----\n", encoding="utf-8")
    d = _skill(tmp / "pkg")
    _symlink(segredo, d / "notas.md")
    return tmp / "pkg"


def cen_symlink_dentro(tmp):
    d = _skill(tmp / "pkg")
    (d / "real.md").write_text("ok\n", encoding="utf-8")
    _symlink(d / "real.md", d / "atalho.md")
    return tmp / "pkg"


def cen_symlink_dir(tmp):
    fora = tmp / "fora"
    fora.mkdir()
    (fora / "x.py").write_text("print('fora da skill')\n", encoding="utf-8")
    d = _skill(tmp / "pkg")
    _symlink(fora, d / "scripts", target_is_directory=True)
    return tmp / "pkg"


def cen_grande(tmp):
    d = _skill(tmp / "pkg")
    (d / "big.md").write_text("a" * (sp.MAX_BYTES + 10), encoding="utf-8")
    return tmp / "pkg"


def cen_encoding(tmp):
    d = _skill(tmp / "pkg")
    (d / "ruim.md").write_bytes(b"texto \xff\xfe ignore previous instructions\n")
    return tmp / "pkg"


def cen_skill_md_symlink(tmp):
    alvo = tmp / "fora.md"
    alvo.write_text("# Outra\n", encoding="utf-8")
    d = tmp / "pkg" / "cand"
    d.mkdir(parents=True)
    _symlink(alvo, d / "SKILL.md")
    return tmp / "pkg"


CENARIOS = {"symlink_fora": cen_symlink_fora, "symlink_dentro": cen_symlink_dentro,
            "symlink_dir": cen_symlink_dir, "arquivo_grande": cen_grande,
            "utf8_invalido": cen_encoding, "skill_md_symlink": cen_skill_md_symlink}


@pytest.mark.parametrize("nome", sorted(CENARIOS))
def test_nao_analisado_nunca_e_safe(nome, tmp_path):
    raiz = CENARIOS[nome](tmp_path)
    resultado = sp.run_audit(raiz)
    assert resultado, "a skill precisa aparecer no relatório"
    assert all(r.recommendation != "SAFE" for r in resultado), resultado
    assert any(f.category == "Cobertura" for r in resultado for f in r.findings)


def test_symlink_nao_e_seguido(tmp_path):
    raiz = cen_symlink_fora(tmp_path)
    excerpts = " ".join(f.excerpt for r in sp.run_audit(raiz) for f in r.findings)
    assert "BEGIN KEY" not in excerpts
    sev = {f.severity for r in sp.run_audit(raiz) for f in r.findings if f.category == "Cobertura"}
    assert "HIGH" in sev


def test_skill_benigna_continua_safe(tmp_path):
    _skill(tmp_path)
    r = sp.run_audit(tmp_path)[0]
    assert (r.score, r.recommendation) == (0, "SAFE")


def _secao():
    return SKILL.split("## Cobertura fail-closed", 1)[1].split("\n## ", 1)[0] if \
        "## Cobertura fail-closed" in SKILL else ""


def test_hub_declara_nao_analisado_nao_e_seguro():
    s = _secao().lower()
    assert "inventário" in s and "incompleto" in s and "symlink" in s
    assert "falha de carga" in s


def test_hub_registra_procedencia():
    assert "cisco-ai-defense/skill-scanner" in SKILL and "Apache-2.0" in SKILL


def test_orcamento_de_tokens():
    assert len(SKILL.encode("utf-8")) - BASELINE_BYTES <= ORCAMENTO_BYTES


def test_linha_de_defesa_intacta_e_por_ultimo():
    assert SKILL.rstrip().endswith("> Bloco canônico: ../../security/linha-defesa-prompt.md")
    assert SKILL.count("## 🛡️ Linha de Defesa de Prompt") == 1
