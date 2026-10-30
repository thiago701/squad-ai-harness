PY ?= python3
install:
	$(PY) -m pip install --quiet "fastapi>=0.139" "pydantic>=2" pytest pytest-cov httpx ruff mypy
check: lint types test
lint:
	$(PY) -m ruff check src tests
types:
	$(PY) -m mypy src
test:
	$(PY) -m pytest -q --cov=src --cov-fail-under=90
run:
	PYTHONPATH=src $(PY) -m uvicorn taskbox_api.adaptadores.api:aplicacao --port 8000
