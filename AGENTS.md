# AGENTS.md

Root guidance for the Glean project. Sub-directories carry their own `AGENTS.md`
for deeper context. `CLAUDE.md` files are compatibility symlinks to these files.

## Environment caveat

- Explicit `/opt/homebrew/bin/...`, Android SDK, and command-runner notes are
  known-good for Codex on macOS.
- Other agents or platforms should adapt paths to their environment while
  preserving the same intent.

## Preferred tools

- Use `/opt/homebrew/bin/rg` for fast text and file search. In the Codex
  command runner, bare `rg` can resolve to BSD `grep`; use the explicit path or
  `rtk rg ...`.
- Use `/opt/homebrew/bin/rtk` when reading large files, listing directories, or
  running noisy commands. Bare `rtk` normally resolves correctly, but prefer the
  explicit path when debugging command-resolution issues.

## Project layout

```
backend/   — Python / FastAPI, deployed as AWS Lambda (uv)
mobile/    — Expo / React Native (npm)
Makefile   — unified task runner for both sub-projects
```

## Makefile

Run `make help` from the repo root to see all targets. Prefer `make` over running
sub-project commands directly when both are equivalent.

### Common targets

```bash
make setup            # install all dependencies (backend + mobile)
make test             # run all tests
make lint             # lint + format everything
make pre-commit       # run all pre-commit hooks

make start-backend    # FastAPI dev server on :8000 (hot reload)
make start-backend-docker # Dockerized FastAPI dev server on :8000 (hot reload)
make start-mobile     # Expo dev server; add API_HOST=192.168.1.42 for phone testing
make start-ios        # Expo on iOS simulator
make start-android    # Expo on Android emulator (wraps mobile/scripts/emu-start)
```

### Worktrees

```bash
make worktree BRANCH=feature/foo        # create isolated worktree + install deps
make worktree-list                       # list active worktrees
make worktree-remove BRANCH=feature/foo # remove worktree + clean node_modules + .venv
make worktree-prune                      # prune stale git metadata
```
