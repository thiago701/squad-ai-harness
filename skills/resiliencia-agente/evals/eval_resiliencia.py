"""Evals de `resiliencia-agente` — com skill x sem skill.

Skill de doutrina: o que ela entrega é uma REGRA DE DECISÃO. O eval tem dois lados.

  (a) COMPORTAMENTO — a regra, implementada como função de referência derivada do
      SKILL.md, produz a classificação certa nos casos que mais custam caro.
      "Sem skill" é o comportamento ingênuo (`retry em tudo`), que os testes reprovam.

  (b) DOUTRINA — o SKILL.md realmente declara os discriminadores. Uma skill de
      doutrina cuja regra sumiu do texto não ensina nada ao agente, por mais que a
      função de referência aqui continue verde.
"""

import pathlib

import pytest

_RAIZ = pathlib.Path(__file__).resolve().parent.parent
HUB = (_RAIZ / "SKILL.md").read_text(encoding="utf-8")
# A skill que o agente realmente consome = hub + tudo que o hub linka.
SKILL = HUB + "\n".join(
    p.read_text(encoding="utf-8") for p in sorted((_RAIZ / "references").glob("*.md"))
)

DISJUNTOR, COOLDOWN, LOCKOUT, TERMINAL, NENHUMA = (
    "disjuntor", "cooldown", "lockout", "terminal", "nenhuma",
)


def classificar(erro: str, repetiu: bool = False) -> str:
    """Função de referência — a taxonomia da §4 do SKILL.md em código."""
    sistemico = {"timeout", "503", "502", "504", "500", "conexao_recusada"}
    credencial = {"401", "403", "credencial_invalida", "permissao_negada"}
    terminal = {"credito_esgotado", "conta_banida", "credencial_expirada"}
    do_modelo = {"quota_modelo", "modelo_inexistente", "contexto_insuficiente"}
    deterministico = {"arquivo_nao_existe", "prompt_invalido", "teste_falhou", "json_malformado"}

    if erro in terminal:
        return TERMINAL
    if erro in deterministico:
        return NENHUMA
    if erro in do_modelo:
        return LOCKOUT
    if erro in credencial:
        return TERMINAL if repetiu else COOLDOWN
    if erro in {"429", "rate_limit", "quota_janela"}:
        return COOLDOWN
    if erro in sistemico:
        return DISJUNTOR
    return COOLDOWN  # desconhecido: a camada mais barata e reversível


def backoff(base_s: float, nivel: int) -> float:
    return base_s * 2 ** nivel


# ------------------------------------------------------- (a) comportamento

@pytest.mark.parametrize(
    "erro,esperado",
    [
        ("timeout", DISJUNTOR),
        ("503", DISJUNTOR),
        ("429", COOLDOWN),
        ("rate_limit", COOLDOWN),
        ("quota_modelo", LOCKOUT),
        ("contexto_insuficiente", LOCKOUT),
        ("credito_esgotado", TERMINAL),
        ("conta_banida", TERMINAL),
        ("arquivo_nao_existe", NENHUMA),
        ("teste_falhou", NENHUMA),
    ],
)
def test_erro_vai_para_a_camada_certa(erro, esperado):
    assert classificar(erro) == esperado


def test_rate_limit_nunca_abre_disjuntor():
    """Erro de classificação nº1: derruba um especialista saudável."""
    for erro in ("429", "rate_limit", "quota_janela"):
        assert classificar(erro) != DISJUNTOR


def test_erro_deterministico_nao_entra_em_retry():
    """Erro de classificação nº2: queima tokens em loop e esconde o bug."""
    for erro in ("arquivo_nao_existe", "prompt_invalido", "teste_falhou", "json_malformado"):
        assert classificar(erro) == NENHUMA, "retry sobre erro determinístico é custo puro"


def test_credencial_persistente_vira_terminal():
    """Erro de classificação nº3: tentar para sempre um caminho que não volta sozinho."""
    assert classificar("401", repetiu=False) == COOLDOWN
    assert classificar("401", repetiu=True) == TERMINAL


def test_quota_de_modelo_nao_derruba_o_especialista():
    """A razão de a camada 3 existir: degradar, não parar."""
    assert classificar("quota_modelo") == LOCKOUT
    assert classificar("quota_modelo") not in (DISJUNTOR, COOLDOWN)


def test_backoff_e_exponencial_e_zera_no_sucesso():
    assert backoff(3, 0) == 3
    assert backoff(3, 3) == 24
    assert backoff(3, 0) < backoff(3, 1) < backoff(3, 2)


def test_sem_skill_o_comportamento_ingenuo_reprova():
    """Baseline SEM skill: 'toda falha vira retry'. Explicita o delta."""
    ingenuo = lambda erro, repetiu=False: COOLDOWN
    divergem = [e for e in ("timeout", "quota_modelo", "credito_esgotado", "teste_falhou")
                if ingenuo(e) != classificar(e)]
    assert len(divergem) == 4, "a skill precisa discordar do ingênuo em todos os 4 casos caros"


# ------------------------------------------------------- (b) doutrina no texto

@pytest.mark.parametrize(
    "trecho",
    [
        "MEIO_ABERTO",                      # estado de sonda
        "preguiçosa",                       # recuperação por leitura, não por timer
        "anti-manada",                      # guarda de falhas concorrentes
        "Estados terminais ≠ cooldown",     # a distinção que evita o loop infinito
        "não pertence a nenhuma camada",    # a regra que mais economiza
        "Retry-After",                      # dica do upstream vence backoff local
    ],
)
def test_skill_declara_o_discriminador(trecho):
    assert trecho in SKILL, f"a skill (hub + references) perdeu o discriminador: {trecho!r}"


@pytest.mark.parametrize(
    "trecho",
    [
        "Escale, não repita",               # erro determinístico: a regra que mais economiza
        "Estados terminais ≠ cooldown",     # o loop infinito que ninguém percebe
        "A regra de ouro",                  # retry só vale com chance diferente de dar certo
    ],
)
def test_hub_carrega_as_regras_criticas(trecho):
    """Regra crítica em `references/` é regra que o agente pode não ler.

    O hub é carregado por ativação; o reference só se o agente seguir o link.
    O que evita queimar tokens em loop precisa estar no hub.
    """
    assert trecho in HUB, f"regra crítica fora do hub (só em references?): {trecho!r}"


def test_resiliencia_nao_relaxa_os_gates():
    """Invariante de segurança: degradar caminho nunca é permissão para pular gate."""
    assert "nunca são pulados por resiliência" in HUB
    assert "para e escala" in HUB


def test_todo_reference_e_linkado_do_hub():
    """Reference não-linkado é invisível ao agente (padrao-skill.md §4)."""
    for ref in sorted((_RAIZ / "references").glob("*.md")):
        assert ref.name in HUB, f"reference órfão: {ref.name}"
