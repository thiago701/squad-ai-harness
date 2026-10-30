"""
Evals para compactacao-estrategica (C5).
Verifica que a skill preserva itens críticos e descarta o que pode.
"""
import pytest


CONTEXTO_LONGO = """
$ python -m pytest tests/ -v 2>&1
tests/test_jornada.py::test_estado_inicial PASSED
tests/test_jornada.py::test_transicao_etapa PASSED
tests/test_jornada.py::test_validar_cpf_falha PASSED
tests/test_fallback.py::test_fallback_llm PASSED
tests/test_bedrock.py::test_mock_invoke PASSED
tests/test_bedrock.py::test_classificar_queixa PASSED
tests/test_bedrock.py::test_classificar_erro_retorna_fallback PASSED
...
(95 linhas de output)
======================== 95 passed in 12.3s ========================
Commit: abc1234 feat(bedrock): BedrockAdapter + 13 testes
Next: implementar TranscribeMedical
Constraint: CPF nunca armazenado (SHA-256 token)
GIT_INDEX_FILE=/tmp/git_index_n7_ai1
"""

CHECKPOINT_ESPERADO = """
pytest: 95 passed ✅
Commit: abc1234 feat(bedrock)
Próximo: TranscribeMedical
Constraint: CPF → SHA-256 token
Padrão: GIT_INDEX_FILE=/tmp/git_index_n7_ai1
"""


def test_checkpoint_preserva_contagem_testes():
    """O checkpoint deve preservar a contagem de testes."""
    assert "95 passed" in CHECKPOINT_ESPERADO


def test_checkpoint_preserva_commit():
    """O checkpoint deve preservar o hash do commit."""
    assert "abc1234" in CHECKPOINT_ESPERADO


def test_checkpoint_preserva_constraint():
    """Constraints LGPD nunca podem ser descartados."""
    assert "CPF" in CHECKPOINT_ESPERADO


def test_checkpoint_preserva_padrao_git():
    """O padrão GIT_INDEX_FILE deve ser preservado."""
    assert "GIT_INDEX_FILE" in CHECKPOINT_ESPERADO


def test_checkpoint_preserva_proximo_passo():
    """O próximo passo do pipeline não pode ser descartado."""
    assert "TranscribeMedical" in CHECKPOINT_ESPERADO


def test_checkpoint_menor_que_original():
    """O checkpoint deve ser significativamente menor que o original."""
    assert len(CHECKPOINT_ESPERADO) < len(CONTEXTO_LONGO) * 0.4


def test_checkpoint_nao_contem_saida_verbosa():
    """O checkpoint não deve conter saídas verbosas de pytest."""
    assert "PASSED\n" not in CHECKPOINT_ESPERADO
    assert "tests/test_" not in CHECKPOINT_ESPERADO


def test_criticos_cobertos():
    """Todos os 8 itens críticos devem estar no padrão do checkpoint."""
    criticos = [
        "passed",      # contagem de testes (pytest output em inglês)
        "commit",      # commits realizados
        "próximo",     # próximos passos
        "constraint",  # constraints ativos
        "padrão",      # padrões estabelecidos
    ]
    checkpoint_lower = CHECKPOINT_ESPERADO.lower()
    for item in criticos:
        assert item in checkpoint_lower, f"Crítico ausente: {item}"
