"""Evals de `compressao-tool-output` — com skill x sem skill.

"Sem skill" = a saída bruta despejada no contexto (o que acontece hoje).
"Com skill" = a saída passada pelo motor de filtros.

O eval mede as duas propriedades que justificam a skill existir:
  1. ECONOMIA  — a saída comprimida é substancialmente menor;
  2. FIDELIDADE — o veredito e o sinal acionável sobrevivem à compressão.

A segunda é a que importa: economia sem fidelidade é a pior regressão possível
(build vermelho reportado como verde).
"""

import importlib.util
import pathlib
import sys

import pytest

_RAIZ = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("comprimir", _RAIZ / "scripts" / "comprimir.py")
comprimir_mod = importlib.util.module_from_spec(_spec)
# registrar ANTES de executar: @dataclass resolve o módulo via sys.modules
sys.modules["comprimir"] = comprimir_mod
_spec.loader.exec_module(comprimir_mod)


def _filtro(nome):
    avisos = []
    for f in comprimir_mod.carregar_filtros(avisos):
        if f.id == nome:
            return f
    pytest.fail(f"filtro {nome} não carregou. avisos={avisos}")


def _comprimir(texto, comando):
    avisos = []
    filtro = comprimir_mod.escolher(comprimir_mod.carregar_filtros(avisos), comando, texto, None)
    assert filtro is not None, f"nenhum filtro casou para {comando!r}"
    return comprimir_mod.comprimir(texto, filtro), filtro.id


# --------------------------------------------------------------- corpus

PYTEST_VERDE = (
    "platform linux -- Python 3.13.0, pytest-8.3.0\n"
    "rootdir: /repo\nplugins: cov-5.0.0\ncollecting ... collected 945 items\n"
    + ("." * 30 + "\n") * 30
    + "===== 945 passed in 62.11s =====\n"
)

PYTEST_VERMELHO = (
    "platform linux -- Python 3.13.0\ncollecting ... collected 945 items\n"
    + ("." * 30 + "\n") * 25
    + "FAILED tests/test_pedido.py::test_criar - AssertionError: esperado 200\n"
    "E       assert 500 == 200\n"
    "Traceback (most recent call last):\n"
    + "".join(f'  File "/usr/lib/python3.13/site-packages/x.py", line {i}, in wrapper\n' for i in range(20))
    + '  File "core/pedido.py", line 42, in criar\n'
    "===== 1 failed, 944 passed in 63.02s =====\n"
)

MAVEN_VERMELHO = (
    "".join(f"[INFO] Downloading from central: lib-{i}.jar\n" for i in range(40))
    + "[INFO] ---\n"
    "Tests run: 12, Failures: 1, Errors: 0, Skipped: 0\n"
    "[ERROR] PedidoTest.deveCriar:42 expected true\n"
    "[INFO] BUILD FAILURE\n"
)

TERRAFORM_DESTRUTIVO = (
    "aws_db_instance.main: Refreshing state...\n"
    "  # aws_db_instance.main will be destroyed\n"
    '    id = "db-1"\n    tags_all = {}\n'
    "Plan: 0 to add, 0 to change, 1 to destroy.\n"
)


# --------------------------------------------------------------- economia

@pytest.mark.parametrize(
    "bruto,comando,reducao_minima",
    [
        (PYTEST_VERDE, "pytest -q", 0.90),
        (PYTEST_VERMELHO, "pytest -q", 0.60),
        (MAVEN_VERMELHO, "mvn verify", 0.60),
    ],
)
def test_com_skill_reduz_linhas(bruto, comando, reducao_minima):
    """COM skill: redução mínima de linhas. SEM skill seria 0%."""
    saida, _ = _comprimir(bruto, comando)
    antes, depois = len(bruto.splitlines()), len(saida.splitlines())
    reducao = 1 - depois / antes
    assert reducao >= reducao_minima, f"reduziu só {reducao:.0%} (mínimo {reducao_minima:.0%})"


# --------------------------------------------------------------- fidelidade

def test_veredito_nunca_muda():
    """A trava central: verde continua verde, vermelho continua vermelho."""
    for bruto, comando in [
        (PYTEST_VERDE, "pytest -q"),
        (PYTEST_VERMELHO, "pytest -q"),
        (MAVEN_VERMELHO, "mvn verify"),
        (TERRAFORM_DESTRUTIVO, "terraform plan"),
    ]:
        saida, fid = _comprimir(bruto, comando)
        assert comprimir_mod.veredito(bruto) == comprimir_mod.veredito(saida), \
            f"filtro {fid} mudou o veredito"


@pytest.mark.parametrize(
    "bruto,comando,obrigatorios",
    [
        (PYTEST_VERMELHO, "pytest -q", ["FAILED tests/test_pedido.py::test_criar", "1 failed"]),
        (MAVEN_VERMELHO, "mvn verify", ["Tests run: 12, Failures: 1", "[ERROR] PedidoTest", "BUILD FAILURE"]),
        (TERRAFORM_DESTRUTIVO, "terraform plan", ["will be destroyed", "1 to destroy"]),
    ],
)
def test_sinal_acionavel_sobrevive(bruto, comando, obrigatorios):
    """Economia que perde o sinal é regressão, não ganho."""
    saida, fid = _comprimir(bruto, comando)
    for trecho in obrigatorios:
        assert trecho in saida, f"filtro {fid} descartou sinal: {trecho!r}"


def test_ruido_e_descartado():
    """O que a skill promete jogar fora precisa realmente sair."""
    saida, _ = _comprimir(PYTEST_VERMELHO, "pytest -q")
    assert "site-packages" not in saida, "frame de biblioteca sobreviveu"
    saida_mvn, _ = _comprimir(MAVEN_VERMELHO, "mvn verify")
    assert "Downloading from central" not in saida_mvn, "ruído de download sobreviveu"


def test_atalho_verde_nao_dispara_com_falha():
    """O bug perigoso desta classe de ferramenta: reportar verde num build vermelho."""
    saida, _ = _comprimir(PYTEST_VERMELHO, "pytest -q")
    assert "945 passed OK" not in saida
    assert "FAILED" in saida


# --------------------------------------------------------------- invariantes de filtro

def test_todo_filtro_tem_teste_inline_e_onempty():
    """Rubrica da skill: filtro sem teste ou sem onEmpty é rejeitado no carregamento."""
    avisos = []
    filtros = comprimir_mod.carregar_filtros(avisos)
    assert filtros, f"nenhum filtro carregou: {avisos}"
    for f in filtros:
        assert f.testes, f"{f.id} sem tests[]"
        assert f.regras.get("onEmpty"), f"{f.id} sem onEmpty"


def test_atalho_de_sucesso_exige_unless():
    """Trava estrutural: atalho que anuncia verde sem cláusula `unless` é rejeitado."""
    with pytest.raises(comprimir_mod.FiltroInvalido):
        comprimir_mod.Filtro.de_json({
            "id": "ruim",
            "rules": {"onEmpty": "x", "matchOutput": [{"when": "tudo", "then": "OK tudo passed"}]},
            "tests": [{"name": "t", "input": "x"}],
        })


def test_tests_inline_de_todos_os_filtros_passam():
    """Roda o --self-test embutido como parte do eval."""
    assert comprimir_mod.autoteste() == 0
