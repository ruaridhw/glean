# Glean — root Makefile
#
# Backend: Python (uv) deployed as AWS Lambda; runs locally via FastAPI dev server
# Mobile:  Expo / React Native (npm)
#
# Usage:
#   make setup           — install all dependencies
#   make test            — run all tests
#   make lint            — lint + format everything
#   make start-backend   — FastAPI dev server on :8000
#   make start-backend-docker — Dockerized FastAPI dev server on :8000
#   make start-mobile    — Expo dev server; optional API_HOST=192.168.1.42 for phones
#   make worktree BRANCH=feature/foo — isolated worktree for a new branch

.DEFAULT_GOAL := help
SHELL         := /bin/bash

# Strip path prefix so `make worktree BRANCH=feature/foo` → .worktrees/foo
WORKTREE_DIR  := .worktrees
BRANCH        ?=
_LEAF         = $(notdir $(BRANCH))
API_HOST      ?=
API_PORT      ?= 8000
API_URL_ENV   = $(if $(API_HOST),EXPO_PUBLIC_API_URL=http://$(API_HOST):$(API_PORT),)

# ── Setup ─────────────────────────────────────────────────────────────────────

.PHONY: setup
setup: setup-backend setup-mobile  ## Install all dependencies

.PHONY: setup-backend
setup-backend:  ## Install backend Python dev dependencies
	cd backend && uv sync --dev

.PHONY: setup-mobile
setup-mobile:  ## Install mobile JS dependencies
	cd mobile && npm install

# ── Tests ─────────────────────────────────────────────────────────────────────

.PHONY: test
test: test-backend test-mobile  ## Run all tests

.PHONY: test-backend
test-backend:  ## Run backend unit tests with coverage (excludes integration tests)
	cd backend && uv run pytest -m "not integration and not soft_gate"

.PHONY: test-integration-backend
test-integration-backend:  ## Run backend integration tests (requires real OPENROUTER_API_KEY in backend/.env)
	cd backend && uv run pytest tests/integration/ -v

.PHONY: test-mobile
test-mobile:  ## Run mobile Jest tests
	cd mobile && npm test

.PHONY: test-e2e
test-e2e:  ## Run Maestro e2e tests against a running Expo dev server
	cd mobile && npm run e2e

# ── Lint & Format ─────────────────────────────────────────────────────────────

.PHONY: lint
lint: lint-backend lint-mobile  ## Lint and format all code

.PHONY: lint-backend
lint-backend:  ## ruff + black + ty + vulture
	cd backend && uv run ruff check src/ tests/ --fix
	cd backend && uv run black src/ tests/
	cd backend && uv run ty check src/
	cd backend && uv run vulture src/ vulture_whitelist.py

.PHONY: lint-mobile
lint-mobile:  ## biome + tsc + knip (via npm run check)
	cd mobile && npm run check

.PHONY: pre-commit
pre-commit:  ## Run all pre-commit hooks across the repo
	pre-commit run --all-files

# ── Dev Servers ───────────────────────────────────────────────────────────────

.PHONY: start-backend
start-backend:  ## Start FastAPI dev server on :8000 (hot reload)
	cd backend && uv run fastapi dev src/glean/main.py

.PHONY: start-backend-docker
start-backend-docker:  ## Start Dockerized FastAPI dev server on :8000 (hot reload)
	docker compose up --build backend

.PHONY: start-mobile
start-mobile:  ## Start Expo dev server; optional API_HOST=192.168.1.42 for phones
	cd mobile && $(API_URL_ENV) npm start

.PHONY: start-ios
start-ios:  ## Start Expo on iOS simulator
	cd mobile && npm run ios

.PHONY: start-android
start-android:  ## Start Expo on Android emulator (sets ANDROID_HOME, clears Metro cache)
	cd mobile && ./scripts/emu-start

# ── Git Worktrees ─────────────────────────────────────────────────────────────
# Worktrees live in .worktrees/ which is already in .gitignore.
# Each worktree gets its own branch so feature work stays fully isolated.

.PHONY: worktree
worktree:  ## Create worktree + install deps: make worktree BRANCH=feature/foo
	@[ -n "$(BRANCH)" ] || { echo "Usage: make worktree BRANCH=feature/foo"; exit 1; }
	git worktree add $(WORKTREE_DIR)/$(_LEAF) -b $(BRANCH)
	cd $(WORKTREE_DIR)/$(_LEAF)/backend && uv sync --dev
	cd $(WORKTREE_DIR)/$(_LEAF)/mobile && npm install
	@echo ""
	@echo "✔ Worktree ready at $(WORKTREE_DIR)/$(_LEAF)"
	@echo "  Verify baseline: make -C $(WORKTREE_DIR)/$(_LEAF) test"

.PHONY: worktree-list
worktree-list:  ## List all active worktrees
	git worktree list

.PHONY: worktree-remove
worktree-remove:  ## Remove a worktree + clean up node_modules + .venv: make worktree-remove BRANCH=feature/foo
	@[ -n "$(BRANCH)" ] || { echo "Usage: make worktree-remove BRANCH=feature/foo"; exit 1; }
	rm -rf $(WORKTREE_DIR)/$(_LEAF)/mobile/node_modules
	rm -rf $(WORKTREE_DIR)/$(_LEAF)/backend/.venv
	git worktree remove --force $(WORKTREE_DIR)/$(_LEAF)

.PHONY: worktree-prune
worktree-prune:  ## Prune stale worktree metadata
	git worktree prune -v

# ── Help ──────────────────────────────────────────────────────────────────────

.PHONY: help
help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'
