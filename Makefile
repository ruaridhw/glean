# Glean — root Makefile
#
# Backend: Python (uv) running as AWS Lambda (SAM)
# Mobile:  Expo / React Native (npm)
#
# Usage:
#   make setup           — install all dependencies
#   make test            — run all tests
#   make lint            — lint + format everything
#   make start-backend   — SAM local API on :3000
#   make start-mobile    — Expo dev server
#   make worktree BRANCH=feature/foo — isolated worktree for a new branch

.DEFAULT_GOAL := help
SHELL         := /bin/bash

# Strip path prefix so `make worktree BRANCH=feature/foo` → .worktrees/foo
WORKTREE_DIR  := .worktrees
BRANCH        ?=
_LEAF         = $(notdir $(BRANCH))

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
test-backend:  ## Run backend tests with coverage
	cd backend && uv run pytest

.PHONY: test-mobile
test-mobile:  ## Run mobile Jest tests
	cd mobile && NODE_OPTIONS=--experimental-vm-modules npx jest

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
lint-mobile:  ## biome + tsc + knip
	cd mobile && npx biome check --write .
	cd mobile && npx tsc --noEmit
	cd mobile && npx knip

.PHONY: pre-commit
pre-commit:  ## Run all pre-commit hooks across the repo
	pre-commit run --all-files

# ── Dev Servers ───────────────────────────────────────────────────────────────

.PHONY: start-backend
start-backend:  ## Start backend locally via SAM on port 3000
	cd backend && sam local start-api

.PHONY: start-mobile
start-mobile:  ## Start Expo dev server (choose platform in browser)
	cd mobile && npx expo start

.PHONY: start-ios
start-ios:  ## Start Expo on iOS simulator
	cd mobile && npx expo start --ios

.PHONY: start-android
start-android:  ## Start Expo on Android emulator (sets ANDROID_HOME)
	cd mobile && ANDROID_HOME=$$HOME/Library/Android/sdk \
		PATH=$$HOME/Library/Android/sdk/platform-tools:$$HOME/Library/Android/sdk/emulator:$$PATH \
		npx expo start --android --clear

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
worktree-remove:  ## Remove a worktree: make worktree-remove BRANCH=feature/foo
	@[ -n "$(BRANCH)" ] || { echo "Usage: make worktree-remove BRANCH=feature/foo"; exit 1; }
	git worktree remove --force $(WORKTREE_DIR)/$(_LEAF)

.PHONY: worktree-prune
worktree-prune:  ## Prune stale worktree metadata
	git worktree prune -v

# ── Help ──────────────────────────────────────────────────────────────────────

.PHONY: help
help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'
