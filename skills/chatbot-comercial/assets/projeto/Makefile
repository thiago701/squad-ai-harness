SHELL := /bin/bash
PY ?= python3
N7_AI_CORE_PATH ?= ../squad-ai-core

.DEFAULT_GOAL := ajuda

ajuda:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS=":.*?## "} {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

instalar: ## instala o projeto + squad-ai-core em modo editável
	$(PY) -m pip install -e "$(N7_AI_CORE_PATH)"
	$(PY) -m pip install -e ".[dev]"

up: ## sobe o chatbot (indexa a base e serve HTTP)
	$(PY) -m app.main

seed: ## (re)indexa a base de conhecimento a partir de dados/
	$(PY) scripts/seed_rag.py

eval: ## roda o golden set e publica a taxa de acerto
	$(PY) scripts/eval_rag.py --publicar

teste: ## suíte + cobertura (gate 80%)
	$(PY) -m pytest --cov=app --cov-report=term-missing --cov-fail-under=80

lint: ## ruff
	$(PY) -m ruff check app tests scripts

verificar: lint teste eval ## bateria completa antes de commit/PR

docker-up: ## sobe via docker compose (VPS)
	docker compose up -d --build

docker-logs: ## acompanha os logs
	docker compose logs -f chatbot

limpar: ## remove banco, versões e caches locais
	rm -rf var .pytest_cache .ruff_cache .coverage htmlcov

.PHONY: ajuda instalar up seed eval teste lint verificar docker-up docker-logs limpar
