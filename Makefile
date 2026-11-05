.DEFAULT_GOAL := help
.PHONY: help install lint format typecheck test cov security web ci api demo eval clean

help: ## Liste les commandes
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

install: ## Installe les dépendances (Python et front)
	uv sync --locked --all-groups
	cd web && npm ci

lint: ## ruff : lint et format
	uv run ruff check .
	uv run ruff format --check .

format: ## Corrige le format
	uv run ruff check --fix .
	uv run ruff format .

typecheck: ## mypy
	uv run mypy

test: ## pytest (les tests du sandbox exigent Docker)
	uv run pytest

cov: ## pytest avec couverture
	uv run pytest --cov --cov-report=term

security: ## bandit et pip-audit
	uv run bandit -q -r src -c pyproject.toml
	uv export --no-dev --no-hashes --frozen --no-emit-project -o /tmp/requirements.txt
	uv run pip-audit -r /tmp/requirements.txt --disable-pip --no-deps

web: ## Types et build du front
	cd web && npm run typecheck && npm run build

ci: lint typecheck cov security web ## Tout ce que fait la CI, en local

api: ## API de démonstration sur :8000
	uv run agent-data serve

demo: ## API + tunnel public (make demo FRONT=https://….vercel.app)
	./scripts/demo.sh $(FRONT)

eval: ## Évaluation sur les cas de référence (LLM + sandbox réels)
	uv run python scripts/run_eval.py

clean: ## Supprime les caches
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage coverage.xml web/.next
