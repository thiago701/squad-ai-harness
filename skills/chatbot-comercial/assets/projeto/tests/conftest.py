"""Fixtures — cada teste roda contra uma cópia real da base, em tmp_path."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.config import Config
from app.servico import Servico

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture
def config(tmp_path: Path) -> Config:
    for pasta in ("dados", "verticais", "golden"):
        shutil.copytree(RAIZ / pasta, tmp_path / pasta)
    return Config(
        tenant="teste",
        vertical="pousada",
        estabelecimento="Pousada de Teste",
        raiz=tmp_path,
        banco=tmp_path / "var" / "chatbot.db",
        dados=tmp_path / "dados",
        verticais=tmp_path / "verticais",
        golden=tmp_path / "golden",
        versoes=tmp_path / "var" / "versoes",
        painel_token="",
    )


@pytest.fixture
def servico(config: Config) -> Servico:
    servico = Servico.montar(config)
    yield servico
    servico.conexao.close()
