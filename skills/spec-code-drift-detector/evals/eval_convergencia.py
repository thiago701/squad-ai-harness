"""Eval executavel de `spec-code-drift-detector` -- camada de convergencia.

Mede as 3 lacunas absorvidas (tecnica de github/spec-kit `/converge`, commit 3238fa9, MIT):
  (1) taxonomia de divergencia em 4 classes: ausente / parcial / contradiz / nao-pedido;
  (2) "[x] em tasks.md nao e evidencia" -- a evidencia e codigo/teste;
  (3) backlog de divergencias append-only e idempotente (rodar 2x nao duplica).
Roda contra o script real (`scripts/spec-drift-check.py`) e o modulo `scripts/convergencia.py`.
"""

import importlib.util
import pathlib
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "scripts" / "spec-drift-check.py"
MODULO = RAIZ / "scripts" / "convergencia.py"


def carregar():
    spec = importlib.util.spec_from_file_location("convergencia", MODULO)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def escrever(base, nome, texto):
    caminho = base / nome
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(texto, encoding="utf-8")
    return caminho


def rodar(base, spec="FR1 FR2\n", src="FR1 FR2\n", tests="FR1 FR2\n", tasks=None, extra=()):
    escrever(base, "spec.md", spec)
    escrever(base, "src/App.java", src)
    escrever(base, "test/AppTest.java", tests)
    args = [sys.executable, str(SCRIPT), "--spec", str(base / "spec.md"),
            "--src", str(base / "src"), "--tests", str(base / "test"),
            "--out", str(base / "drift-report.md")]
    if tasks is not None:
        args += ["--tasks", str(escrever(base, "tasks.md", tasks))]
    proc = subprocess.run(args + list(extra), capture_output=True)
    relatorio = (base / "drift-report.md").read_text(encoding="utf-8")
    return proc, relatorio


# ---------------------------------------------------------------- lacuna 1: taxonomia
def test_quatro_classes_canonicas():
    assert carregar().CLASSES == ("ausente", "parcial", "contradiz", "nao-pedido")


def test_classificar_cobre_as_quatro_classes_e_convergido():
    c = carregar().classificar
    assert c(na_spec=True, tem_codigo=False, tem_teste=False) == "ausente"
    assert c(na_spec=True, tem_codigo=True, tem_teste=False) == "parcial"
    assert c(na_spec=True, tem_codigo=True, tem_teste=True, contradiz=True) == "contradiz"
    assert c(na_spec=False, tem_codigo=True, tem_teste=False) == "nao-pedido"
    assert c(na_spec=True, tem_codigo=True, tem_teste=True) is None


def test_cli_classifica_ausente_e_parcial(tmp_path):
    proc, rel = rodar(tmp_path, spec="FR1 FR2 FR3\n", src="FR1 FR2\n", tests="FR1\n")
    assert proc.returncode == 3
    assert "FR2 (parcial)" in rel and "FR3 (ausente)" in rel
    assert "FR1 (" not in rel


def test_cli_detecta_codigo_nao_pedido(tmp_path):
    proc, rel = rodar(tmp_path, spec="FR1\n", src="FR1 FR9\n", tests="FR1\n")
    assert proc.returncode == 3
    assert "FR9 (nao-pedido)" in rel


# ---------------------------------------------------- lacuna 2: [x] nao e evidencia
def test_tarefa_marcada_sem_evidencia_vira_drift(tmp_path):
    tasks = "- [x] T001 implementar FR1\n- [x] T002 implementar FR3\n"
    proc, rel = rodar(tmp_path, spec="FR1 FR2 FR3\n", src="FR1 FR2\n", tests="FR1 FR2\n", tasks=tasks)
    assert proc.returncode == 3
    assert "T002" in rel and "FR3" in rel
    assert "T001" not in rel


def test_tarefa_marcada_com_evidencia_converge(tmp_path):
    proc, rel = rodar(tmp_path, tasks="- [x] T001 FR1\n- [ ] T002 FR2\n")
    assert proc.returncode == 0, rel
    assert "DRIFT-FREE" in rel


# ------------------------------------------- lacuna 3: backlog append-only/idempotente
def test_backlog_idempotente_rodar_duas_vezes_nao_duplica(tmp_path):
    backlog = tmp_path / "backlog.md"
    extra = ["--backlog", str(backlog)]
    rodar(tmp_path, spec="FR1 FR2 FR3\n", src="FR1 FR2\n", tests="FR1\n", extra=extra)
    primeiro = backlog.read_bytes()
    rodar(tmp_path, spec="FR1 FR2 FR3\n", src="FR1 FR2\n", tests="FR1\n", extra=extra)
    assert backlog.read_bytes() == primeiro
    texto = primeiro.decode("utf-8")
    assert texto.count("FR2 (parcial)") == 1 and texto.count("FR3 (ausente)") == 1


def test_backlog_append_only_preserva_conteudo_e_itens_resolvidos(tmp_path):
    backlog = escrever(tmp_path, "backlog.md", "# notas do time\n- [x] FR3 (ausente) resolvido antes\n")
    original = backlog.read_text(encoding="utf-8")
    rodar(tmp_path, spec="FR1 FR2 FR3\n", src="FR1 FR2\n", tests="FR1\n", extra=["--backlog", str(backlog)])
    novo = backlog.read_text(encoding="utf-8")
    assert novo.startswith(original)
    assert novo.count("FR3 (ausente)") == 1
    assert "FR2 (parcial)" in novo[len(original):]


def test_backlog_limpo_nao_cria_nem_altera(tmp_path):
    backlog = tmp_path / "backlog.md"
    proc, _ = rodar(tmp_path, extra=["--backlog", str(backlog)])
    assert proc.returncode == 0
    assert not backlog.exists()


def test_achado_manual_contradiz_entra_no_backlog(tmp_path):
    backlog = tmp_path / "backlog.md"
    extra = ["--backlog", str(backlog), "--achado", "FR1:contradiz:retorna 500 em vez de 404"]
    proc, rel = rodar(tmp_path, extra=extra)
    assert proc.returncode == 3
    assert "FR1 (contradiz)" in backlog.read_text(encoding="utf-8")


def test_stdout_cp1252_seguro_e_skill_documenta(tmp_path):
    proc, _ = rodar(tmp_path, spec="FR1 FR2 FR3\n", src="FR1 FR2 FR9\n", tests="FR1\n")
    proc.stdout.decode("ascii")
    skill = (RAIZ / "SKILL.md").read_text(encoding="utf-8")
    for termo in ("nao-pedido", "append-only", "3238fa9", "MIT"):
        assert termo in skill
