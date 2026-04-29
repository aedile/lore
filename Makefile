# =============================================================================
# Makefile — lore-eligibility build targets
#
# Usage:
#   make              show this help message
#   make build        build Docker image (lore-eligibility:latest)
#   make ci-local     run all local CI gates (mirrors GitHub Actions)
#   make merge-pr     merge a PR via the programmatic gate (make merge-pr PR=N)
#   make lint         run ruff, mypy, bandit, vulture
#   make test         run unit tests with coverage
# =============================================================================

.DEFAULT_GOAL := help

IMAGE_NAME ?= lore-eligibility
IMAGE_TAG  ?= latest

# ---------------------------------------------------------------------------
# help — list available targets (default)
# ---------------------------------------------------------------------------
.PHONY: help
help: ## Show this help message
	@echo "lore-eligibility — available make targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ---------------------------------------------------------------------------
# build — build the production Docker image
# ---------------------------------------------------------------------------
.PHONY: build
build: ## Build the lore-eligibility:latest Docker image
	docker build --tag $(IMAGE_NAME):$(IMAGE_TAG) --file Dockerfile .

# ---------------------------------------------------------------------------
# ci-local — run all local CI gates (mirrors GitHub Actions)
# ---------------------------------------------------------------------------
.PHONY: ci-local
ci-local: ## Run all local CI gates — mirrors the GitHub Actions pipeline
	bash scripts/ci-local.sh

# ---------------------------------------------------------------------------
# merge-pr — programmatic PR merge gate (Rule 12)
#
# Usage: make merge-pr PR=<number>
# NEVER use bare 'gh pr merge' — it bypasses the CI gate.
# ---------------------------------------------------------------------------
.PHONY: merge-pr
merge-pr: ## Merge a PR via the CI gate (usage: make merge-pr PR=<number>)
	bash scripts/merge-pr.sh $(PR)

# ---------------------------------------------------------------------------
# lint — static analysis (ruff, mypy, bandit, vulture)
# ---------------------------------------------------------------------------
.PHONY: lint
lint: ## Run ruff, mypy, bandit, and vulture static analysis
	poetry run ruff check src/ tests/
	poetry run ruff format --check src/ tests/
	poetry run mypy src/
	poetry run bandit -c pyproject.toml -r src/
	python3 scripts/vulture_pydantic_plugin.py > .vulture_generated.py
	poetry run vulture src/ .vulture_whitelist.py .vulture_generated.py --min-confidence 60

# ---------------------------------------------------------------------------
# test — unit tests with coverage (Gate #1)
# ---------------------------------------------------------------------------
.PHONY: test
test: ## Run unit tests with coverage (--cov-fail-under=95)
	# NOTE: Do NOT add -W error here. The filterwarnings = ["error"] in
	# pyproject.toml already converts all warnings to errors. Passing -W
	# error on the command line overrides the config-file ignore filters
	# (cpython warning filter precedence rule).
	poetry run pytest tests/unit/ --cov=src/lore_eligibility --cov-fail-under=95

# ---------------------------------------------------------------------------
# test-integration — integration tests (requires live infrastructure)
# ---------------------------------------------------------------------------
.PHONY: test-integration
test-integration: ## Run integration tests (requires PostgreSQL)
	poetry run pytest tests/integration/ -v --no-cov

# ---------------------------------------------------------------------------
# mutmut — mutation testing on security-critical modules (developer tool)
# ---------------------------------------------------------------------------
.PHONY: mutmut
mutmut: ## Run mutation testing on security modules (developer exploration tool)
	bash scripts/mutmut-security.sh

# ---------------------------------------------------------------------------
# mutmut-gate — mutation testing gate (CI gate enforcement)
#
# Thresholds:
#   threshold_security = 60  (shared/security/ modules)
#   threshold_auth = 50      (bootstrapper/auth.py + token_blocklist.py)
# ---------------------------------------------------------------------------
.PHONY: mutmut-gate
mutmut-gate: ## Run mutation testing gate — fails if score below threshold
	bash scripts/mutmut-gate.sh

# ---------------------------------------------------------------------------
# assert-density — assertion density check on test files
# ---------------------------------------------------------------------------
.PHONY: assert-density
assert-density: ## Check assertion density in test files
	poetry run python scripts/assert_density_check.py \
		--baseline scripts/assert_density_baseline.txt \
		$(shell find tests/ -name "test_*.py" -not -path "*/\.*")

# ---------------------------------------------------------------------------
# doc-audit — documentation accuracy audit
# ---------------------------------------------------------------------------
.PHONY: doc-audit
doc-audit: ## Verify README.md accuracy — checks for stale phrases and broken doc references
	poetry run python scripts/doc_audit.py

# ---------------------------------------------------------------------------
# dev — start development stack (postgres + pgbouncer + app with --reload)
#
# Runs the full stack inside docker compose. The override file
# (docker-compose.override.yml) adds --reload to the app command and
# bind-mounts src/ for hot reload. The entrypoint.sh waits for postgres
# and runs `alembic upgrade head` before starting uvicorn.
#
# Foreground: ctrl-C to stop. Use `make dev-down` to clean up volumes.
# ---------------------------------------------------------------------------
.PHONY: dev
dev: ## Start development stack (foreground): postgres + pgbouncer + app with hot-reload
	docker compose up

# ---------------------------------------------------------------------------
# dev-detached — same as dev but in background
# ---------------------------------------------------------------------------
.PHONY: dev-detached
dev-detached: ## Start development stack (background)
	docker compose up -d

# ---------------------------------------------------------------------------
# dev-down — stop development services
# ---------------------------------------------------------------------------
.PHONY: dev-down
dev-down: ## Stop and remove development containers
	docker compose down

# ---------------------------------------------------------------------------
# dev-db-only — bring up only postgres + pgbouncer (for running pytest
# integration tests on the host that need a live DB)
# ---------------------------------------------------------------------------
.PHONY: dev-db-only
dev-db-only: ## Bring up postgres + pgbouncer with host port 5432 exposed (for host-side pytest)
	docker compose -f docker-compose.yml -f docker-compose.dev-db.yml up -d postgres pgbouncer

# ---------------------------------------------------------------------------
# prototype-test — run the prototype/ test suite (overrides production
# coverage gate; prototype/ runs under the relaxed harness profile)
# ---------------------------------------------------------------------------
.PHONY: prototype-test
prototype-test: ## Run prototype/ tests (relaxed harness; coverage gate skipped)
	poetry run pytest prototype/tests/ -o addopts="--tb=short"

# ---------------------------------------------------------------------------
# prototype-demo — run the full panel demo against the running dev DB
# ---------------------------------------------------------------------------
.PHONY: prototype-demo
prototype-demo: ## Run the full panel demo (requires `make dev-db-only` first)
	poetry run python -m prototype demo

# ---------------------------------------------------------------------------
# prototype-h2 — run the H2 Splink snippet (panel hands-on artifact)
# ---------------------------------------------------------------------------
.PHONY: prototype-h2
prototype-h2: ## Run the H2 Splink near-duplicate detection snippet
	poetry run python -m prototype.snippets.h2_splink_demo
