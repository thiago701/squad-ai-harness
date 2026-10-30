"""
Eval de testes baseados em propriedade (PBT) — especialista-qualidade.

Critério de ganho (definido ANTES da edição do SKILL.md, 13/10/2026):
  1. Parte executável (independente do SKILL.md): um mini-harness stdlib com semente fixa
     e encolhimento mostra o valor da técnica sobre 3 defeitos plantados — a bateria de
     exemplos "típica" pega 0/3; as propriedades das famílias do §PBT pegam 3/3, com
     contra-exemplo reproduzível pela semente e encolhido ao mínimo.
  2. Parte textual: o hub precisa ensinar a técnica (quando usar, famílias de propriedade,
     construir em vez de reimplementar, gerador sem trava artificial, semente + contra-exemplo
     promovido a teste de exemplo) sem estourar o orçamento de tokens e sem tocar a
     Linha de Defesa. Vermelho no SKILL.md 1.0; verde no 1.1.

Técnica reescrita a partir de dubzzz/fast-check, skills/javascript-testing-expert (MIT).
Rodar: python -m pytest skills/especialista-qualidade/evals/eval_propriedades.py -q
"""
import pathlib
import random

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SKILL = (RAIZ / "SKILL.md").read_text(encoding="utf-8")
BASELINE_BYTES = 19002  # SKILL.md 1.0 medido em 13/10/2026
ORCAMENTO_BYTES = 2600  # teto do acréscimo (~650 tokens)


# --------------------------------------------------------------------------------------
# Mini-harness PBT (stdlib): geração com semente, encolhimento guloso, contra-exemplo.
# --------------------------------------------------------------------------------------
def _encolher_lista(xs, falha, encolher_item):
    """Encolhimento guloso: remove itens e reduz cada item enquanto a falha persistir."""
    mudou = True
    while mudou:
        mudou = False
        for i in range(len(xs)):
            cand = xs[:i] + xs[i + 1:]
            if falha(cand):
                xs, mudou = cand, True
                break
        if mudou:
            continue
        for i, item in enumerate(xs):
            for menor in encolher_item(item):
                cand = xs[:i] + [menor] + xs[i + 1:]
                if falha(cand):
                    xs, mudou = cand, True
                    break
            if mudou:
                break
    return xs


def checar(gerar, propriedade, encolher_item, semente=1310, execucoes=200):
    """Devolve None se a propriedade vale; senão o contra-exemplo já encolhido."""
    rng = random.Random(semente)

    def falha(x):
        try:
            return not propriedade(x)
        except Exception:  # exceção também é falha da propriedade
            return True

    for _ in range(execucoes):
        x = gerar(rng)
        if falha(x):
            return _encolher_lista(x, falha, encolher_item)
    return None


def _int_menores(n):
    passo = 1 if n > 0 else -1
    return [v for v in dict.fromkeys((0, n // 2, n - passo)) if abs(v) < abs(n)]


def _str_menores(s):
    return [s[:i] + s[i + 1:] for i in range(len(s))]


def _gen_ints(rng):  # sem trava artificial de tamanho/faixa além do necessário
    return [rng.randint(-1000, 1000) for _ in range(rng.randint(0, 12))]


def _gen_strs(rng):
    alfabeto = "ab;\\ x"
    return ["".join(rng.choice(alfabeto) for _ in range(rng.randint(0, 6)))
            for _ in range(rng.randint(0, 5))]


# --------------------------------------------------------------------------------------
# Três defeitos plantados, cada um caçado por uma família diferente de propriedade.
# --------------------------------------------------------------------------------------
def codificar(itens):  # DEFEITO: não escapa o separador
    return ";".join(itens)


def decodificar(texto):
    return [] if texto == "" else texto.split(";")


def remover_duplicados(xs):  # DEFEITO: perde a ordem original
    return sorted(set(xs))


def busca_binaria(xs, alvo):  # DEFEITO: nunca examina o último elemento
    lo, hi = 0, len(xs) - 1
    while lo < hi:
        meio = (lo + hi) // 2
        if xs[meio] == alvo:
            return True
        if xs[meio] < alvo:
            lo = meio + 1
        else:
            hi = meio
    return False


def _exemplos_tipicos():
    """Bateria de exemplos que um autor escreveria à mão (caminho feliz + bordas óbvias)."""
    return [
        decodificar(codificar(["a", "b"])) == ["a", "b"],
        decodificar(codificar(["x y"])) == ["x y"],
        decodificar(codificar([])) == [],
        remover_duplicados([1, 1, 2]) == [1, 2],
        remover_duplicados([]) == [],
        remover_duplicados([3, 5, 9]) == [3, 5, 9],
        busca_binaria([1, 3, 5, 7, 9], 5) is True,
        busca_binaria([1, 3, 5, 7, 9], 4) is False,
        busca_binaria([], 1) is False,
    ]


# família "combinação de funções" (ida-e-volta)
def _prop_ida_volta(itens):
    return decodificar(codificar(itens)) == itens


# família "entrada restrita construída": sem duplicados -> resultado é a própria entrada
def _prop_sem_dup(xs):
    unicos = list(dict.fromkeys(xs))  # construída, não filtrada
    return remover_duplicados(unicos) == unicos


# família "oráculo mais simples": busca binária ≡ busca linear em lista ordenada
def _prop_oraculo(xs):
    ordenada = sorted(xs)
    alvo = ordenada[-1] if ordenada else 0
    return busca_binaria(ordenada, alvo) == (alvo in ordenada)


CACADAS = [
    ("ida-e-volta", _gen_strs, _prop_ida_volta, _str_menores),
    ("entrada-construida", _gen_ints, _prop_sem_dup, _int_menores),
    ("oraculo-simples", _gen_ints, _prop_oraculo, _int_menores),
]


def test_exemplos_tipicos_nao_pegam_nenhum_dos_3_defeitos():
    assert all(_exemplos_tipicos()), "a bateria de exemplos deveria passar (defeitos invisíveis a ela)"


@pytest.mark.parametrize("nome,gerar,prop,menores", CACADAS, ids=[c[0] for c in CACADAS])
def test_propriedade_pega_o_defeito(nome, gerar, prop, menores):
    contra = checar(gerar, prop, menores)
    assert contra is not None, f"propriedade {nome} deveria falsificar o defeito plantado"


@pytest.mark.parametrize("nome,gerar,prop,menores", CACADAS, ids=[c[0] for c in CACADAS])
def test_contra_exemplo_reproduzivel_pela_semente(nome, gerar, prop, menores):
    assert checar(gerar, prop, menores, semente=7) == checar(gerar, prop, menores, semente=7)


@pytest.mark.parametrize("nome,gerar,prop,menores", CACADAS, ids=[c[0] for c in CACADAS])
def test_contra_exemplo_encolhido_vira_teste_de_exemplo(nome, gerar, prop, menores):
    contra = checar(gerar, prop, menores)
    assert len(contra) <= 2, f"{nome}: contra-exemplo não encolheu: {contra!r}"
    assert not prop(contra), "o contra-exemplo fixo precisa reproduzir a falha como teste de exemplo"


def test_placar_exemplos_vs_propriedades():
    pegos_exemplos = sum(1 for ok in _exemplos_tipicos() if not ok)
    pegos_props = sum(1 for _, g, p, m in CACADAS if checar(g, p, m) is not None)
    assert (pegos_exemplos, pegos_props) == (0, 3)


# --------------------------------------------------------------------------------------
# Parte textual — o hub ensina a técnica (vermelho no 1.0, verde no 1.1).
# --------------------------------------------------------------------------------------
def _secao_pbt():
    ini = SKILL.find("## Testes Baseados em Propriedade")
    assert ini != -1, "hub sem seção '## Testes Baseados em Propriedade'"
    fim = SKILL.find("\n## ", ini + 5)
    return SKILL[ini:fim].lower()


def test_hub_tem_secao_pbt():
    _secao_pbt()


@pytest.mark.parametrize("familia", [
    "independente da entrada", "derivada da entrada", "entrada construída",
    "ida-e-volta", "oráculo mais simples"])
def test_hub_nomeia_as_familias_de_propriedade(familia):
    assert familia in _secao_pbt(), f"família ausente: {familia}"


def test_hub_manda_construir_e_proibe_reimplementar():
    s = _secao_pbt()
    assert "construa" in s and "reimplement" in s


def test_hub_proibe_trava_artificial_no_gerador():
    s = _secao_pbt()
    assert "trava artificial" in s and "filter" in s and "map" in s


def test_hub_semente_e_contra_exemplo_promovido():
    s = _secao_pbt()
    assert "semente" in s and "contra-exemplo" in s and "teste de exemplo" in s


def test_hub_gatilho_sempre_nunca_e_complementaridade():
    s = _secao_pbt()
    assert "sempre" in s and "nunca" in s and "complementa" in s


def test_hub_cita_ferramenta_por_stack():
    s = _secao_pbt()
    assert all(t in s for t in ("jqwik", "hypothesis", "fast-check"))


def test_hub_registra_procedencia_mit():
    assert "fast-check" in SKILL and "MIT" in SKILL and "javascript-testing-expert" in SKILL


def test_orcamento_de_tokens():
    tamanho = len(SKILL.encode("utf-8"))
    assert tamanho <= BASELINE_BYTES + ORCAMENTO_BYTES, f"hub cresceu demais: {tamanho} B"


def test_linha_de_defesa_intacta_e_por_ultimo():
    ini = SKILL.find("## 🛡️ Linha de Defesa de Prompt")
    assert ini != -1
    bloco = SKILL[ini:]
    assert all(f"\n{n}. **" in bloco for n in range(1, 7))
    assert "> Bloco canônico: ../../security/linha-defesa-prompt.md" in bloco
    assert "\n## " not in bloco[5:], "Linha de Defesa deve continuar sendo a última seção"
