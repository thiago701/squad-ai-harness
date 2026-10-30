"""Eval executavel de `aprendizado-continuo` -- confianca deterministica de instintos.

Lacunas cobertas (tecnica reescrita do continuous-learning-v2 do affaan-m/everything-claude-code,
`skills/continuous-learning-v2/scripts/instinct-cli.py`, commit 90606c8, licenca MIT; nenhum
codigo copiado e SEM hooks/observer):
  (1) confianca inicial pela contagem de observacoes, em faixas fixas;
  (2) reforco (+0.05/confirmacao), contradicao (-0.10) e decaimento (-0.02/semana sem ser visto);
  (3) promocao projeto->global so com 2+ projetos DISTINTOS e media >= 0.8;
  (4) pendente sem revisao: aviso no dia 23, expira no dia 30;
  (5) agrupamento de gatilhos parecidos por coeficiente de sobreposicao (nao Jaccard).
Roda contra o modulo real `scripts/confianca.py`. Saida: N/M casos; exit 1 se algum falhar.
"""

import importlib.util
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
MODULO = RAIZ / "scripts" / "confianca.py"


def carregar():
    if not MODULO.exists():
        return None
    spec = importlib.util.spec_from_file_location("confianca", MODULO)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def casos(m):
    yield "faixas iniciais 1/3/6/11 obs", [m.confianca(n) for n in (1, 3, 6, 11)] == [0.3, 0.5, 0.7, 0.85]
    yield "6 obs + 3 contradicoes = 0.4 -> hipotese", (m.confianca(6, contradicoes=3) == 0.4
                                                       and m.faixa(0.4) == "hipotese")
    yield "10 semanas sem ver tiram 0.2", m.confianca(11, semanas_sem_ver=10) == 0.65
    yield "reforco nunca passa de 0.9 nem fica < 0", (m.confianca(11, confirmacoes=10) == 0.9
                                                       and m.confianca(1, contradicoes=9) == 0.0)
    yield "12x num projeto so nao promove", not m.promover_global([("p1", 0.85)] * 12)
    yield "2 projetos media 0.82 promove", m.promover_global([("p1", 0.85), ("p2", 0.79)])
    yield "2 projetos media 0.78 nao promove", not m.promover_global([("p1", 0.8), ("p2", 0.76)])
    yield "dedup por projeto usa a maior confianca", m.promover_global([("p1", 0.5), ("p1", 0.9), ("p2", 0.8)])
    yield "pendente: ok/aviso/expirado", [m.estado_pendente(d) for d in (22, 23, 30)] == ["ok", "aviso", "expirado"]
    yield "agrupa 'when writing tests' + 'writing unit tests'", m.agrupar(
        ["when writing tests", "writing unit tests", "ao revisar PR"]) == [[0, 1], [2]]
    yield "1 palavra em comum nao agrupa", m.agrupar(["usar logs estruturados", "usar sempre UTF-8"]) == [[0], [1]]
    yield "faixas de uso", [m.faixa(c) for c in (0.49, 0.5, 0.7, 0.8)] == [
        "hipotese", "sugerir", "aplicar_com_revisao", "candidato_promocao"]


def main():
    m = carregar()
    if m is None:
        print("0/12 -- scripts/confianca.py ausente (regra so em prosa, nao decide nenhum caso)")
        return 1
    ok = 0
    total = 0
    for nome, passou in casos(m):
        total += 1
        ok += bool(passou)
        print(("PASS " if passou else "FAIL ") + nome)
    print(f"{ok}/{total}")
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
