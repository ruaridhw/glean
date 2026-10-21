# Glean — root Makefile
#
# Backend: Python (uv) deployed as AWS Lambda; runs locally via FastAPI dev server
# App:     Flutter (iOS + Android; `make start-web` for a Chrome dev loop)
#
# Usage:
#   make setup            — install all dependencies
#   make test             — run all tests
#   make lint             — lint + format everything
#   make check-web        — compile the web dev-loop target (native-only imports break it)
#   make start-backend    — FastAPI dev server on :8000
#   make start-backend-docker — the whole backend in Docker: FastAPI on :8000 plus the async
#                              stack (DynamoDB Local, ElasticMQ, the session worker)
#   make start-ios         — Flutter on iOS Simulator (macOS only)
#   make start-android     — Flutter on a running Android emulator
#   make start-web         — Flutter in a Chrome it launches, hot reload (web dev loop)
#   make e2e-tokens        — Cognito test-user tokens for the e2e entrypoint (see app/README.md)
#   make worktree BRANCH=feature/foo — isolated worktree branched from origin/main
#                                      (BASE=<parent branch> for a stacked PR)
#
# `start-ios`/`start-android` need COGNITO_DOMAIN and COGNITO_CLIENT_ID (the
# same values the old Expo app read as EXPO_PUBLIC_COGNITO_*) — see
# app/README.md for where those come from. Neither target, nor `test-app`'s
# integration counterpart, can run on a Linux box with no Android
# SDK/Java/Xcode; `setup-app`, `test-app`, `lint-app` and `start-web` can and do.
#
# Machine-local overrides (bind addresses, ports, test credentials) live in an untracked
# `.env.local` at the repo root (see .env.local.example) — never commit
# hostnames or addresses to this file.

.DEFAULT_GOAL := help
SHELL         := /bin/bash

# Strip path prefix so `make worktree BRANCH=feature/foo` → .worktrees/foo
WORKTREE_DIR  := .worktrees
BRANCH        ?=
BASE          ?= origin/main
_LEAF         = $(notdir $(BRANCH))
API_HOST      ?=
API_PORT      ?= 8000
COGNITO_DOMAIN    ?=
COGNITO_CLIENT_ID ?=
WEB_HOST          ?= 127.0.0.1
WEB_PORT          ?= 8090
WEB_DEBUG_PORT    ?= 9222
WEB_HEADLESS      ?=

# Optional, gitignored. Sets e.g. WEB_HOST/WEB_HEADLESS for a headless box
# reached over the network, and the Cognito test user for `e2e-tokens`.
-include .env.local

# Real tokens for the e2e entrypoint's bypass session (see app/README.md,
# "Calling the backend from the e2e entrypoint"). Set E2E_USERNAME and
# E2E_PASSWORD (plus AWS_PROFILE/COGNITO_CLIENT_ID) in .env.local and the
# targets below sign that test user in and pass its tokens through; leave
# them unset and the bypass session carries no token, as before.
E2E_USERNAME      ?=
E2E_PASSWORD      ?=
_E2E_DEFINES = $(if $(E2E_USERNAME),$(shell scripts/e2e_tokens.sh --dart-defines),)

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
		--dart-define=COGNITO_CLIENT_ID=$(COGNITO_CLIENT_ID) \
		$(_E2E_DEFINES)

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

# The web dev loop's only compile check. Every other app check runs on the VM,
# where `dart:ffi` exists, so a native-only import (package:drift/native.dart)
# reaching the web entrypoint would otherwise break `make start-web` silently.
.PHONY: check-web
check-web:  ## Compile the web dev-loop target (catches native-only imports in the web build)
	cd app && flutter build web --target lib/main_e2e.dart --debug

.PHONY: pre-commit
pre-commit:  ## Run all pre-commit hooks across the repo
	pre-commit run --all-files

# ── Deploy ────────────────────────────────────────────────────────────────────

.PHONY: deploy-prod
deploy-prod:  ## Deploy the backend to prod, stamped with the commit (ALLOW_DIRTY=1 to deploy a dirty/unpushed tree)
	python3 backend/scripts/deploy_prod.py

# ── Dev Servers ───────────────────────────────────────────────────────────────

.PHONY: start-backend
start-backend:  ## Start FastAPI dev server on :8000 (hot reload)
	cd backend && uv run fastapi dev src/glean/main.py

.PHONY: start-backend-docker
start-backend-docker:  ## The whole backend in Docker: FastAPI on :8000 plus the async stack
	docker compose up --build

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

# The web dev loop runs the e2e entrypoint in a Chrome that Flutter launches
# and drives itself, so hot reload reaches the page with no browser
# extension. On a headless box set WEB_HEADLESS=1 in .env.local; the page is
# still served on WEB_HOST:WEB_PORT for any browser, and Chrome's DevTools
# protocol on WEB_DEBUG_PORT is where an automation tool attaches for
# screenshots. Cognito values are placeholders unless e2e tokens are in play
# (then the real dev-pool domain/client id are needed for token refresh).
# API_BASE_URL stays on localhost (as the *browser* sees it) so the bypass's
# production-URL guard passes.
.PHONY: start-web
start-web:  ## Flutter web dev loop in Chrome (hot reload; WEB_HOST/WEB_PORT/WEB_HEADLESS in .env.local)
	cd app && flutter run -d chrome \
		--target lib/main_e2e.dart \
		--pid-file .dart_tool/start-web.pid \
		--web-hostname $(WEB_HOST) --web-port $(WEB_PORT) \
		--web-browser-debug-port $(WEB_DEBUG_PORT) \
		$(if $(WEB_HEADLESS),--web-run-headless,) \
		--dart-define=API_BASE_URL=http://localhost:$(API_PORT) \
		--dart-define=COGNITO_DOMAIN=$(if $(COGNITO_DOMAIN),$(COGNITO_DOMAIN),web-dev-loop) \
		--dart-define=COGNITO_CLIENT_ID=$(if $(COGNITO_CLIENT_ID),$(COGNITO_CLIENT_ID),web-dev-loop) \
		$(_E2E_DEFINES)

.PHONY: reload-web
reload-web:  ## Hot-reload the running `make start-web` (for agents without its terminal; `r` works there)
	@[ -f app/.dart_tool/start-web.pid ] || { echo "start-web is not running"; exit 1; }
	kill -USR1 $$(cat app/.dart_tool/start-web.pid)

.PHONY: e2e-tokens
e2e-tokens:  ## Print the Cognito test user's tokens as shell exports (needs E2E_USERNAME/E2E_PASSWORD in .env.local)
	@scripts/e2e_tokens.sh --exports

# ── Git Worktrees ─────────────────────────────────────────────────────────────
# Worktrees live in .worktrees/ which is already in .gitignore.
# Each worktree gets its own branch so feature work stays fully isolated.
# The branch starts from a freshly fetched origin/main, never from whatever is
# checked out; pass BASE=<parent branch> to stack a PR on the one below it.

.PHONY: worktree
worktree:  ## Create worktree from origin/main (or BASE=<parent>) + install deps: make worktree BRANCH=feature/foo
	@[ -n "$(BRANCH)" ] || { echo "Usage: make worktree BRANCH=feature/foo"; exit 1; }
	git fetch origin
	git worktree add -b $(BRANCH) $(WORKTREE_DIR)/$(_LEAF) $(BASE)
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
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'
