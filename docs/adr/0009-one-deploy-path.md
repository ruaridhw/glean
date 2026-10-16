---
status: accepted
date: 2026-10-15
---

# Prod deploys go through one script and one configuration, and manual deploys stay allowed

Both CI and hand-run deploys deploy the backend through **the same script** (`make deploy-prod` → `backend/scripts/deploy_prod.py`) reading **one parameter source** (`samconfig.toml`, with secrets resolved from Secrets Manager rather than repeated anywhere). The split-brain alternative — CI passing its own `--parameter-overrides` — had already silently dropped LangSmith tracing in prod, because a CLI override list replaces samconfig's list wholesale (#106).

Manual deploys are **not** blocked; they are made **traceable**. A hand deploy stamps the stack with the commit (`GIT_SHA` env var, stack tag, surfaced by `GET /health`), refuses a dirty tree or a `HEAD` that isn't on origin, and is logged to `~/.glean/deploy.log` when forced with `ALLOW_DIRTY=1`. A post-deploy check compares the stack against samconfig and exits nonzero on drift.

## Considered options

- **CI-only deploys, blocking hand runs.** Rejected by the owner: the ability to deploy by hand is deliberately kept, especially while iterating against prod.
- **Blocking deploys of anything but `main`.** Rejected in the same spirit; the script stamps and logs instead of forbidding.

## Consequences

- **A newer queued CI deploy replaces one still waiting for approval** (`backend-deploy-prod` concurrency group, #128), so only the latest `main` ever needs approving. A deploy already running is left to finish, because cancelling `sam deploy` mid-update leaves CloudFormation busy.
- **Any new non-secret parameter must be added to samconfig once,** not to CI; the script re-passes samconfig's list.
- **Prod is auditable:** `/health` reports the deployed commit, and every bundle in S3 was traced to a pushed commit or a named orphan in the 2026-10-15 audit (#118).
