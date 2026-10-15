# Glean — root Makefile
#
# Backend: Python (uv) deployed as AWS Lambda; runs locally via FastAPI dev server
# App:     Flutter (iOS + Android)
#
# Usage:
#   make setup            — install all dependencies
#   make test             — run all tests
#   make lint             — lint + format everything
#   make start-backend    — FastAPI dev server on :8000
#   make start-backend-docker — Dockerized FastAPI server on :8000
#   make start-ios         — Flutter on iOS Simulator (macOS only)
#   make start-android     — Flutter on a running Android emulator
#   make worktree BRANCH=feature/foo — isolated worktree for a new branch
#
# `start-ios`/`start-android` need COGNITO_DOMAIN and COGNITO_CLIENT_ID (the
# same values the old Expo app read as EXPO_PUBLIC_COGNITO_*) — see
# app/README.md for where those come from. Neither target, nor `test-app`'s
# integration counterpart, can run on a Linux box with no Android
# SDK/Java/Xcode; `setup-app`, `test-app` and `lint-app` can and do.

.DEFAULT_GOAL := help
SHELL         := /bin/bash

# Strip path prefix so `make worktree BRANCH=feature/foo` → .worktrees/foo
WORKTREE_DIR  := .worktrees
BRANCH        ?=
_LEAF         = $(notdir $(BRANCH))
API_HOST      ?=
API_PORT      ?= 8000
COGNITO_DOMAIN    ?=
COGNITO_CLIENT_ID ?=

# ── Setup ─────────────────────────────────────────────────────────────────────

.PHONY: setup
setup: setup-backend setup-app  ## Install all dependencies

.PHONY: setup-backend
setup-backend:  ## Install backend Python dev dependencies
	cd backend && uv sync --dev

.PHONY: setup-app
setup-app:  ## Install Flutter package dependencies
	cd app && flutter pub get

# ── Tests ─────────────────────────────────────────────────────────────────────

.PHONY: test
test: test-backend test-app  ## Run all tests

.PHONY: test-backend
test-backend:  ## Run backend unit tests with coverage (excludes integration tests)
	cd backend && uv run pytest -m "not integration and not soft_gate"

.PHONY: test-integration-backend
test-integration-backend:  ## Run backend integration tests (requires real OPENROUTER_API_KEY in backend/.env)
	cd backend && uv run pytest tests/integration/ -v

.PHONY: test-app
test-app:  ## Run Flutter unit + widget tests
	cd app && flutter test

.PHONY: test-e2e
test-e2e:  ## Run the integration_test suite (needs a booted simulator/emulator; see app/README.md)
	@[ -n "$(COGNITO_DOMAIN)" ] && [ -n "$(COGNITO_CLIENT_ID)" ] || { echo "Usage: make test-e2e COGNITO_DOMAIN=... COGNITO_CLIENT_ID=... [API_HOST=10.0.2.2]"; exit 1; }
	cd app && flutter test integration_test/app_test.dart \
		--dart-define=API_BASE_URL=http://$(if $(API_HOST),$(API_HOST),localhost):$(API_PORT) \
		--dart-define=COGNITO_DOMAIN=$(COGNITO_DOMAIN) \
		--dart-define=COGNITO_CLIENT_ID=$(COGNITO_CLIENT_ID)

# ── Lint & Format ─────────────────────────────────────────────────────────────

.PHONY: lint
lint: lint-backend lint-app  ## Lint and format all code

.PHONY: lint-backend
lint-backend:  ## ruff + ty + vulture
	cd backend && uv run ruff check src/ tests/ --fix
	cd backend && uv run ruff format src/ tests/
	cd backend && uv run ty check src/
	cd backend && uv run vulture src/ vulture_whitelist.py

.PHONY: lint-app
lint-app:  ## dart format (writes fixes) + flutter analyze
	cd app && dart format lib test integration_test
	cd app && flutter analyze

.PHONY: pre-commit
pre-commit:  ## Run all pre-commit hooks across the repo
	pre-commit run --all-files

# ── Dev Servers ───────────────────────────────────────────────────────────────

.PHONY: start-backend
start-backend:  ## Start FastAPI dev server on :8000 (hot reload)
	cd backend && uv run fastapi dev src/glean/main.py

.PHONY: start-backend-docker
start-backend-docker:  ## Start Dockerized FastAPI server on :8000
	docker compose up --build backend

.PHONY: start-ios
start-ios:  ## Start Flutter on iOS Simulator (macOS only; needs COGNITO_DOMAIN/COGNITO_CLIENT_ID)
	@[ -n "$(COGNITO_DOMAIN)" ] && [ -n "$(COGNITO_CLIENT_ID)" ] || { echo "Usage: make start-ios COGNITO_DOMAIN=... COGNITO_CLIENT_ID=..."; exit 1; }
	open -a Simulator
	cd app && flutter run \
		--dart-define=API_BASE_URL=http://$(if $(API_HOST),$(API_HOST),localhost):$(API_PORT) \
		--dart-define=COGNITO_DOMAIN=$(COGNITO_DOMAIN) \
		--dart-define=COGNITO_CLIENT_ID=$(COGNITO_CLIENT_ID)

.PHONY: start-android
start-android:  ## Start Flutter on a running Android emulator (needs COGNITO_DOMAIN/COGNITO_CLIENT_ID)
	@[ -n "$(COGNITO_DOMAIN)" ] && [ -n "$(COGNITO_CLIENT_ID)" ] || { echo "Usage: make start-android COGNITO_DOMAIN=... COGNITO_CLIENT_ID=..."; exit 1; }
	cd app && flutter run \
		--dart-define=API_BASE_URL=http://$(if $(API_HOST),$(API_HOST),10.0.2.2):$(API_PORT) \
		--dart-define=COGNITO_DOMAIN=$(COGNITO_DOMAIN) \
		--dart-define=COGNITO_CLIENT_ID=$(COGNITO_CLIENT_ID)

# ── Git Worktrees ─────────────────────────────────────────────────────────────
# Worktrees live in .worktrees/ which is already in .gitignore.
# Each worktree gets its own branch so feature work stays fully isolated.

.PHONY: worktree
worktree:  ## Create worktree + install deps: make worktree BRANCH=feature/foo
	@[ -n "$(BRANCH)" ] || { echo "Usage: make worktree BRANCH=feature/foo"; exit 1; }
	git worktree add $(WORKTREE_DIR)/$(_LEAF) -b $(BRANCH)
	cd $(WORKTREE_DIR)/$(_LEAF)/backend && uv sync --dev
	cd $(WORKTREE_DIR)/$(_LEAF)/app && flutter pub get
	@echo ""
	@echo "✔ Worktree ready at $(WORKTREE_DIR)/$(_LEAF)"
	@echo "  Verify baseline: make -C $(WORKTREE_DIR)/$(_LEAF) test"

.PHONY: worktree-list
worktree-list:  ## List all active worktrees
	git worktree list

.PHONY: worktree-remove
worktree-remove:  ## Remove a worktree + clean up build artefacts + .venv: make worktree-remove BRANCH=feature/foo
	@[ -n "$(BRANCH)" ] || { echo "Usage: make worktree-remove BRANCH=feature/foo"; exit 1; }
	rm -rf $(WORKTREE_DIR)/$(_LEAF)/app/build $(WORKTREE_DIR)/$(_LEAF)/app/.dart_tool
	rm -rf $(WORKTREE_DIR)/$(_LEAF)/backend/.venv
	git worktree remove --force $(WORKTREE_DIR)/$(_LEAF)

.PHONY: worktree-prune
worktree-prune:  ## Prune stale worktree metadata
	git worktree prune -v

# ── Help ──────────────────────────────────────────────────────────────────────

.PHONY: help
help:  ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'
