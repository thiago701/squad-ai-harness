"""
Eval da Auditoria de Cobertura do review — tech-lead-review 1.3.

Critério de ganho (definido ANTES da edição do SKILL.md, 18/10/2026):
  1. Parte executável: 9 relatórios de review sobre o mesmo diff (3 arquivos alterados).
     O aceite de hoje (basta ter veredito) é comparado com `scripts/checar_cobertura.py`.
     Métrica: "tudo coberto" FALSO aceito (relatório sem cobertura declarada, com arquivo
     omitido, lacuna sem motivo, categoria sem status ou APROVADO apesar de lacuna).
     Ingênuo: 6/9; checador: 0/9 — e zero rejeição indevida dos 3 relatórios honestos.
  2. Parte textual: o hub declara a seção de cobertura (revisado × não revisado com motivo,
     status por categoria, lacuna ⇒ NAO_VERIFICADO), registra a procedência Apache-2.0 e
     sobe para 1.3 sem estourar o teto residente de 5000 tokens (ceil(bytes/4) do corpo).
     Vermelho no 1.2; verde no 1.3.

Técnica reescrita da fase "Pre-Conclusion Audit" de getsentry/skills, skills/find-bugs
(Apache-2.0, @f57ada2). Rodar: python -m pytest skills/tech-lead-review/evals/eval_cobertura.py -q
"""
import importlib.util
import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SKILL = (RAIZ / "SKILL.md").read_text(encoding="utf-8")
_spec = importlib.util.spec_from_file_location("checar_cobertura", RAIZ / "scripts" / "checar_cobertura.py")
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

ALTERADOS = ["src/pagamento.py", "src/repo.py", "src/gen/schema.py"]
CATS_LIMPAS = "\n".join(f"- {c}: limpo" for c in
                        ("simplicidade", "performance", "custo", "segurança", "negócio", "arquitetura"))


def _rel(revisado="src/pagamento.py, src/repo.py, src/gen/schema.py", nao="nenhum",
         cats=CATS_LIMPAS, veredito="APROVADO", com_secao=True):
    if not com_secao:
        return f"## Review\nNenhum achado relevante.\n\nVeredito: {veredito}\n"
    return (f"## Review\nNenhum achado relevante.\n\n### Cobertura\nRevisado: {revisado}\n"
            f"Não revisado: {nao}\nCategorias:\n{cats}\n\nVeredito: {veredito}\n")


# (nome, relatório, deve_aceitar)
CENARIOS = [
    ("completo-limpo", _rel(), True),
    ("achado-bloqueante-completo", _rel(cats=CATS_LIMPAS.replace("segurança: limpo", "segurança: achado"),
                                        veredito="REQUER NOVO ROUND"), True),
    ("lacuna-honesta", _rel(revisado="src/pagamento.py, src/repo.py",
                            nao="src/gen/schema.py (motivo: código gerado)", veredito="NAO_VERIFICADO"), True),
    ("sem-secao-nenhum-achado", _rel(com_secao=False), False),
    ("arquivo-omitido", _rel(revisado="src/pagamento.py, src/repo.py"), False),
    ("nao-revisado-sem-motivo", _rel(revisado="src/pagamento.py, src/repo.py", nao="src/gen/schema.py",
                                     veredito="NAO_VERIFICADO"), False),
    ("categoria-sem-status", _rel(cats=CATS_LIMPAS.replace("- segurança: limpo\n", "")), False),
    ("aprovado-com-lacuna", _rel(revisado="src/pagamento.py, src/repo.py",
                                 nao="src/gen/schema.py (motivo: código gerado)"), False),
    ("categoria-nao-verificada-sem-motivo",
     _rel(cats=CATS_LIMPAS.replace("performance: limpo", "performance: não verificado"),
          veredito="NAO_VERIFICADO"), False),
]


def aceite_ingenuo(relatorio, _alterados):
    """Hoje (1.2): o relatório só precisa trazer um veredito."""
    return bool(re.search(r"^Veredito:", relatorio, re.M))


def _placar(fn):
    falsos = sum(1 for _, r, ok in CENARIOS if fn(r, ALTERADOS) and not ok)
    indevidos = sum(1 for _, r, ok in CENARIOS if ok and not fn(r, ALTERADOS))
    return falsos, indevidos


def _checador(r, alt):
    return mod.validar(r, alt)[0]


@pytest.mark.parametrize("nome,relatorio,certo", CENARIOS, ids=[c[0] for c in CENARIOS])
def test_checador_decide_cada_relatorio(nome, relatorio, certo):
    assert _checador(relatorio, ALTERADOS) is certo, mod.validar(relatorio, ALTERADOS)[1]


def test_placar_tudo_coberto_falso():
    assert (_placar(aceite_ingenuo), _placar(_checador)) == ((6, 0), (0, 0))


def test_rejeicao_explica_o_motivo():
    _, motivos = mod.validar(_rel(revisado="src/pagamento.py, src/repo.py"), ALTERADOS)
    assert any("src/gen/schema.py" in m for m in motivos)


# --------------------------------------------------------------------------------------
# Parte textual (vermelho no 1.2, verde no 1.3).
# --------------------------------------------------------------------------------------
def _secao_cobertura():
    ini = SKILL.find("### Auditoria de Cobertura")
    assert ini != -1, "hub sem a seção de Auditoria de Cobertura"
    fim = SKILL.find("\n### ", ini + 5)
    return SKILL[ini:fim].lower()


def test_hub_declara_revisado_e_nao_revisado_com_motivo():
    s = _secao_cobertura()
    assert "não revisado" in s and "motivo" in s and "categoria" in s


def test_hub_nenhum_achado_nao_e_tudo_coberto():
    s = _secao_cobertura()
    assert "nenhum achado" in s and "nao_verificado" in s


def test_hub_aponta_script_e_reference():
    s = _secao_cobertura()
    assert "scripts/checar_cobertura.py" in s and "references/auditoria-cobertura.md" in s
    assert (RAIZ / "references" / "auditoria-cobertura.md").exists()


def test_procedencia_apache():
    assert "getsentry/skills" in SKILL and "find-bugs" in SKILL and "Apache-2.0" in SKILL
    ref = (RAIZ / "references" / "auditoria-cobertura.md").read_text(encoding="utf-8")
    assert "f57ada2" in ref and "Apache-2.0" in ref


def test_versao_1_3():
    assert 'version: "1.3"' in SKILL


def test_teto_residente_5000_tokens():
    corpo = SKILL.split("\n---\n", 1)[1] if SKILL.startswith("---") else SKILL
    tokens = -(-len(corpo.encode("utf-8")) // 4)
    assert tokens <= 5000, f"corpo residente {tokens} tokens"


def test_linha_de_defesa_continua_por_ultimo():
    ini = SKILL.find("Linha de Defesa de Prompt")
    assert ini != -1 and SKILL.rfind("\n## ", 0, ini) == SKILL.rfind("\n## ")
