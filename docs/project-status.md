# Glean — Project Status

Last updated: 2026-04-09

## What's been built

### Plan 01 — Foundation (`feat/plan-01-*`)
Monorepo scaffold: Expo mobile app with full SQLite schema via drizzle-orm, FastAPI AI gateway on AWS Lambda with Cognito JWT auth and rate limiting, S3 bucket for image buffering and dev exports, CloudWatch/X-Ray observability.

### Plan 02 — Pantry Management (`feat/plan-02-*`)
Full pantry management: ingredient list UI, receipt scanning via Textract + Claude normalisation, natural language purchase description, manual entry, and the shared review/confirm screen that writes to SQLite and cross-checks the shopping list.

### Plan 03 — Recipe System (`feat/plan-03-*`)
recipe-api.com integration for browsing and searching recipes, URL import via Claude parsing, SQLite recipe cache, recipe list and detail screens.

### Plan 04 — Meal Planning (`feat/plan-04-*`)
Plan tab with N configurable meal slots, single-slot AI suggestions, full-week generation via Claude, mark-as-cooked with pantry decrement, shopping list auto-population. Also: Expo 55 upgrade, Python package upgrades, design system theme tokens applied throughout.

### Plan 06 — Deployment & CI/CD (`feat/plan-06-deploy`)
End-to-end deployment pipeline. Current branch, not yet merged.

**Infrastructure (`infra/`)**
- `bootstrap.yaml` — CloudFormation: GitHub Actions OIDC provider + IAM deploy roles (`GleanDeployRoleProd`, `GleanDeployRoleDev`)
- `bootstrap.sh` — One-time setup script (already run; outputs saved to `infra/.bootstrap-outputs`)

**Backend changes**
- `backend/template.yaml` — `Environment` parameter replaces hardcoded API key params; Secrets Manager IAM policy added
- `backend/samconfig.toml` — SAM `prod` and `dev` environment configs
- `backend/src/glean/config.py` — `SecretsManagerSource`: custom pydantic-settings source that fetches `openrouter_api_key` and `recipe_api_key` from AWS Secrets Manager at Lambda startup (no-op locally, uses `.env` as fallback)

**GitHub Actions**
- `backend-ci.yml` — PR: ruff lint + pytest + SAM validate (parallel)
- `backend-deploy.yml` — Push to `main` → prod (GitHub Environment gate); `workflow_dispatch` → dev
- `mobile-ci.yml` — PR + push to `main`: biome + jest + Gradle build + Maestro E2E (parallel where possible); on `main` also deploys APK as GitHub Release

---

## AWS bootstrap status

Bootstrap stack `glean-bootstrap` deployed to `eu-west-2`. Outputs saved locally to `infra/.bootstrap-outputs` (gitignored).

**Secrets Manager** (eu-west-2):
- `glean/prod/openrouter-api-key` ✅
- `glean/prod/recipe-api-key` ✅

**Still needed before first deploy:**
1. Create GitHub Environment `prod` at `github.com/ruaridhw/glean/settings/environments`
   - Add secret `AWS_ROLE_ARN` (value in `infra/.bootstrap-outputs`)
   - Enable required-reviewer protection
2. Add repository secrets:
   - `AWS_ROLE_ARN_DEV` (value in `infra/.bootstrap-outputs`)
   - `EXPO_TOKEN` (from expo.dev/accounts)
3. Merge `feat/plan-06-deploy` → `main`

---

## Branches

| Branch | Status | Notes |
|---|---|---|
| `main` | Active | Design system + pre-commit setup |
| `feat/plan-04-mobile` | Complete | Latest merged feature work |
| `feat/plan-06-deploy` | In progress | CI/CD pipeline, ready to merge |

---

## Tech stack

| Layer | Technology |
|---|---|
| Mobile | React Native (Expo 55), TypeScript, drizzle-orm, SQLite, Zustand, TanStack Query |
| Backend | Python 3.14, FastAPI, Mangum, AWS Lambda, LangChain + OpenRouter |
| Auth | AWS Cognito (JWT, RS256) |
| AI | OpenRouter via LangChain (default model: claude-sonnet-4-6) |
| OCR | AWS Textract (or vision model via OpenRouter) |
| Storage | SQLite (mobile, local-first), S3 (receipt image buffer) |
| Infra | AWS SAM, CloudFormation, CloudWatch, X-Ray |
| CI/CD | GitHub Actions, OIDC, EAS |
| Testing | pytest + coverage (backend), jest-expo + maestro (mobile) |
| Linting | ruff + black (backend), biome (mobile) |
