PY ?= python3
install:
	$(PY) -m pip install --quiet pytest pytest-cov ruff mypy
check: lint types test
lint:
	$(PY) -m ruff check src tests
types:
	$(PY) -m mypy src
test:
	$(PY) -m pytest -q --cov=src --cov-fail-under=90
run:
	PYTHONPATH=src $(PY) -m taskbox.adaptadores.cli listar
