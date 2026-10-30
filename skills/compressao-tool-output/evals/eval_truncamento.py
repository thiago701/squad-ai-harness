"""Eval de `compressao-tool-output` -- invariante de erro e teto de caracteres.

(1) Bug: o corte head/tail (`_cortar`) ignorava `preserve.errorPatterns`; a linha so
    sobrevivia se tambem casasse `includePatterns`. git-status (`fatal:`) e docker-build
    (`returned a non-zero code`) perdiam o erro do meio de saidas longas.
(2) Absorcao (tecnica reescrita do SWE-agent/mini-swe-agent, commit 04d809c, MIT): teto
    duro de caracteres aplicado por ultimo, cabeca + cauda, com a contagem EXATA do que foi
    omitido e a dica de refazer o comando de forma mais seletiva. Sem ele, uma saida feita
    so de linhas protegidas (ex.: 5 mil linhas de ERROR) passava inteira para o contexto.
"""

import importlib.util
import pathlib
import re
import sys

_RAIZ = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("comprimir", _RAIZ / "scripts" / "comprimir.py")
mod = importlib.util.module_from_spec(_spec)
sys.modules["comprimir"] = mod
_spec.loader.exec_module(mod)


def _filtro(nome):
    for f in mod.carregar_filtros([]):
        if f.id == nome:
            return f
    raise AssertionError(nome)


def _omitidos(saida):
    achado = re.search(r"\((\d+) caracteres omitidos", saida)
    return int(achado.group(1)) if achado else None


def test_erro_protegido_no_meio_sobrevive_ao_corte_git_status():
    texto = "On branch main\n" + "".join(f"x{i}\n" for i in range(100)) + "fatal: bad object HEAD\n" \
        + "".join(f"y{i}\n" for i in range(100))
    assert "fatal: bad object HEAD" in mod.comprimir(texto, _filtro("git-status"))


def test_erro_protegido_no_meio_sobrevive_ao_corte_docker():
    texto = "".join(f"#5 passo {i}\n" for i in range(100)) \
        + "The command '/bin/sh -c make' returned a non-zero code: 2\n" \
        + "".join(f"#6 passo {i}\n" for i in range(100))
    assert "returned a non-zero code: 2" in mod.comprimir(texto, _filtro("docker-build"))


def test_teto_nao_mexe_no_que_cabe():
    for tamanho in (50, 9_999, 10_000):
        texto = "a" * tamanho
        assert mod.teto_caracteres(texto, 10_000) == texto


def test_teto_corta_cabeca_e_cauda_com_contagem_exata():
    for tamanho in (10_001, 200_000):
        texto = "".join(f"{i:07d}\n" for i in range(tamanho // 8 + 1))[:tamanho]
        saida = mod.teto_caracteres(texto, 10_000)
        assert saida.startswith(texto[:5_000]) and saida.endswith(texto[-5_000:])
        assert _omitidos(saida) == tamanho - 10_000
        assert "seletiva" in saida
        assert len(saida) < 10_000 + 200


def test_saida_so_de_erros_protegidos_respeita_o_teto_e_o_veredito():
    texto = "".join(f"ERROR: falha no item {i} " + "z" * 40 + "\n" for i in range(5_000))
    filtro = _filtro("generic-output")
    saida = mod.comprimir(texto, filtro)
    assert len(saida) < 10_000 + 200
    assert _omitidos(saida) is not None
    assert "item 4999" in saida
    assert mod.veredito(saida) == mod.veredito(texto) == "VERMELHO"


def test_filtro_pode_baixar_o_teto_e_skill_documenta():
    filtro = _filtro("generic-output")
    filtro.regras = dict(filtro.regras, maxChars=2_000)
    saida = mod.comprimir("".join(f"ERROR {i}\n" for i in range(2_000)), filtro)
    assert len(saida) < 2_000 + 200
    skill = (_RAIZ / "SKILL.md").read_text(encoding="utf-8")
    for termo in ("maxChars", "04d809c", "MIT", "omitidos"):
        assert termo in skill
