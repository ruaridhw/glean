# AGENTS.md

Root guidance for the Glean project. Sub-directories carry their own `AGENTS.md`
for deeper context. `CLAUDE.md` files are compatibility symlinks to these files.

## Environment caveat

- Explicit `/opt/homebrew/bin/...`, Android SDK, and command-runner notes are
  known-good for Codex on macOS.
- Other agents or platforms should adapt paths to their environment while
  preserving the same intent.
- On the owner's Mac, develop in worktrees under
  `/Users/ruaridhw/Documents/dev/glean/.worktrees`, not in ad-hoc copies
  elsewhere.

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
app/       — Flutter app (iOS + Android)
Makefile   — unified task runner for both sub-projects
```

`app/` replaced the Expo/React Native app previously in this repository;
see `app/AGENTS.md`, and git history for the deleted app's source.

## Module design

Build **deep modules**: a small, stable interface (the module's public
functions or class) over a substantial implementation, so callers depend on
what a module does, not how it does it.

- **Libraries stay behind one module's interface.** Wrap each framework or
  third-party library once, inside the module that uses it, and give callers
  that module's own types. Replacing the library then changes one module, not
  its callers. `DecisionClient.decide(state, questions)` in
  `backend/src/glean/decisions.py` is the pattern: callers pass a plain mapping
  and the module's own question types, and never see the HTTP call, tracing or
  response validation behind it.
- **Each piece of state has one owning module.** Other code reads and changes
  it through that module's interface. A library's internal state, such as an
  agent framework's checkpoints, is the owning module's implementation detail;
  callers read the state the module exposes instead.

## Makefile

Run `make help` from the repo root to see all targets. Prefer `make` over running
sub-project commands directly when both are equivalent.

### Common targets

```bash
make setup            # install all dependencies (backend + app)
make test             # run all tests (backend + Flutter unit/widget)
make lint             # lint + format everything
make pre-commit       # run all pre-commit hooks

make start-backend    # FastAPI dev server on :8000 (hot reload)
make start-backend-docker # Dockerized FastAPI dev server on :8000 (hot reload)
make start-ios        # Flutter on iOS Simulator (macOS only)
make start-android    # Flutter on a running Android emulator
make test-e2e         # Flutter integration_test suite (needs a booted simulator/emulator)
```

`start-ios`/`start-android`/`test-e2e` need `COGNITO_DOMAIN=... COGNITO_CLIENT_ID=...`
— see `app/README.md` for where those values come from. None of the three can
run without an Android SDK/Java/Xcode toolchain (a Mac, for both platforms);
`setup-app`, `test-app` and `lint-app` need none of that and run anywhere,
including a plain Linux box.

### Worktrees

```bash
make worktree BRANCH=feature/foo        # create isolated worktree from origin/main + install deps
make worktree BRANCH=feature/bar BASE=feature/foo  # stacked PR: branch from the parent branch
make worktree-list                       # list active worktrees
make worktree-remove BRANCH=feature/foo # remove worktree + clean node_modules + .venv
make worktree-prune                      # prune stale git metadata
```

## Planning and PR workflow

- **Plans are ephemeral.** Plans, scratch notes and review ledgers live under
  `/tmp` and are never committed. (`docs/*` being gitignored hides plan files;
  it does not make committing them acceptable.)
- **UI/UX changes pass a design gate.** Before building a ticket that adds or
  changes a screen or interaction, make two or three options for each affected
  screen (HTML wireframes, or a clickable prototype for a multi-step flow) and
  serve them in Plannotator for the owner to annotate. Build from the option
  the owner picks, with their annotations. Like plans, the options live under
  `/tmp`.
- **Worktrees start from `origin/main`.** `make worktree` fetches `origin` and
  branches from `BASE`, which defaults to `origin/main`, so a stale checkout
  never becomes the base. For a stacked PR pass `BASE=<parent branch>`.
- **One PR per issue; a lane ships as a stack.** Related issues form a stack of
  PRs, each based on the PR below it (the bottom PR is based on `main`).
- **Keep branch history linear.** To pick up changes from `main` or a parent
  PR, rebase onto it (`git rebase origin/main`, or
  `git rebase --onto <parent> <old parent head>` for a stacked PR) and push
  with `git push --force-with-lease`. Never merge `main` or a parent branch
  into a PR branch. Make new commits rather than amending or squashing. When a
  parent PR changes, rebase every PR above it, bottom first.
- **Merging a stack.** `delete_branch_on_merge` is on, so GitHub deletes each
  head branch on merge and retargets the PR above it to `main` itself. Use
  GitHub's native stacked-PR merge, bottom PR first, with a merge commit:
  1. `gh pr merge` refuses stacked PRs; call the async endpoint and poll the
     uuid it returns (`pending` -> `merged`):
     `gh api -X PUT repos/ruaridhw/glean/pulls/<n>/merge-async -f merge_method=merge`
     then `gh api repos/ruaridhw/glean/pulls/<n>/merge-async/<uuid> --jq .status`.
  2. Wait for the retargeted PR's checks to re-run against `main`, then merge
     it the same way. Repeat up the stack.
  3. If the PRs are not a native stack, merge the bottom PR normally and
     retarget the next one (`gh pr edit <n> --base main`, or the REST API
     `PATCH /pulls/<n>` if `gh` errors) before any branch is deleted.

## Git branch hygiene

**Deleting a remote branch — order of precedence.** Before deleting a remote
branch, retarget any open PRs that use it as their **base** onto the new base
(e.g. `main`) first. Deleting a branch that is the base of open PRs
**auto-closes** those PRs, and GitHub will not let you reopen or re-base them
while the base is gone — you'd have to recreate the branch to recover them.

So when winding down an integration branch:

1. Retarget every open PR based on it (`gh pr edit <n> --base main`, or the REST
   API `PATCH /pulls/<n>` if `gh` errors), and rebase each onto the new base.
2. **Then** delete the branch.

Never delete first — the auto-close is easy to trigger and awkward to undo.
