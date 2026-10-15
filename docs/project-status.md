# Glean — Project Status

Last updated: 2026-05-21

**Superseded note (2026-07-25):** the Expo/React Native app this document
describes (`mobile/`) has since been replaced by a native Flutter app
(`app/`) in a big-bang cutover — see the root `FLUTTER_MIGRATION.md` for the
spec and `.scratch/flutter-port/` for the migration record. The narrative
below is kept as a historical log of the pre-cutover RN build and is not
representative of the current stack (see the corrected "Tech stack" table).

## What's been built

### Plan 01 — Foundation (`feat/plan-01-*`)
Monorepo scaffold: Expo mobile app with full SQLite schema via drizzle-orm, FastAPI AI gateway on AWS Lambda with Cognito JWT auth and rate limiting, S3 bucket for image buffering and dev exports, CloudWatch/X-Ray observability.

### Plan 02 — Pantry Management (`feat/plan-02-*`)
Full pantry management: ingredient list UI, receipt scanning via Textract + Claude normalisation, natural language purchase description, manual entry, and the shared review/confirm screen that writes to SQLite and cross-checks the shopping list.

### Plan 03 — Recipe System (`feat/plan-03-*`)
recipe-api.com integration for browsing and searching recipes, URL import via Claude parsing, SQLite recipe cache, recipe list and detail screens.

### Plan 04 — Meal Planning (`feat/plan-04-*`)
Plan tab with N configurable meal slots, single-slot AI suggestions, full-week generation via Claude, mark-as-cooked with pantry decrement, shopping list auto-population. Also: Expo 55 upgrade, Python package upgrades, design system theme tokens applied throughout.

### Plan 05 — Shopping List and Settings (`feat/plan-05-*`)
Shop tab with local SQLite shopping-list state, manual additions, checked/unchecked grouping, checkout actions, and receipt-scan handoff. Settings reads and writes user preferences including meal count, servings, dietary flags, purchase tolerance, and max active cooking time.

### Mobile Replit Full-Family Migration (`feature/mobile-replit-full-family-migration`)
Current integration base for the migrated Meals, Plan, Shop, and Settings screen families. Preserves production SQLite, auth, and backend contracts while applying the Replit-inspired visual system and focused presentation helpers.

### Local-First AI Shopping List (`feature/local-first-ai-shopping-list`)
Natural-language shopping list workflow implemented on a separate branch and rebased onto `feature/mobile-replit-full-family-migration`. The branch adds the Shop describe/review screens, mobile API hook/types, AI proposal insertion into local SQLite, and focused tests. PR #45 is open against the full-family migration branch.

### Remaining User Workflows
Tracked in `docs/superpowers/specs/2026-05-21-remaining-user-workflows-design.md`. Remaining work excludes the AI shopping-list branch and focuses on onboarding, checked-shopping-to-pantry, destructive confirmations/undo, real receipt scan progress, pull-to-refresh, swipe delete, and notification preferences.

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
- `mobile-ci.yml` — (historical; removed post-cutover) PR + push to `main`: biome + jest + Gradle build + Maestro E2E (parallel where possible); on `main` also deployed APK as GitHub Release. Replaced by `flutter-ci.yml`/`flutter-integration.yml`.

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
   - ~~`EXPO_TOKEN` (from expo.dev/accounts)~~ — no longer needed: EAS was
     removed entirely in the Flutter cutover (see the corrected "Tech stack"
     table above); Fastlane release lanes need no CI secret since they run
     from a Mac, not from CI (see `app/README.md`).
3. Merge `feat/plan-06-deploy` → `main`

---

## Branches

| Branch | Status | Notes |
|---|---|---|
| `main` | Active | Design system + pre-commit setup |
| `feature/mobile-replit-full-family-migration` | Active base | Migrated screen families and current PR base |
| `feature/local-first-ai-shopping-list` | PR open | Natural-language shopping workflow in PR #45 |
| `feat/plan-06-deploy` | In progress | CI/CD pipeline, ready to merge |

---

## Tech stack

| Layer | Technology |
|---|---|
| Mobile (historical, pre-cutover) | React Native (Expo 55), TypeScript, drizzle-orm, SQLite, Zustand, TanStack Query |
| App (current) | Flutter (Dart), go_router, flutter_riverpod, drift/SQLite — see `app/AGENTS.md` |
| Backend | Python 3.14, FastAPI, Mangum, AWS Lambda, LangChain + OpenRouter |
| Auth | AWS Cognito (JWT, RS256) |
| AI | OpenRouter via LangChain (default model: claude-sonnet-4-6) |
| OCR | AWS Textract (or vision model via OpenRouter) |
| Storage | SQLite (mobile, local-first), S3 (receipt image buffer) |
| Infra | AWS SAM, CloudFormation, CloudWatch, X-Ray |
| CI/CD | GitHub Actions, OIDC; Fastlane (release lanes, run from a Mac, not CI) — EAS is gone entirely post-cutover |
| Testing | pytest + coverage (backend); `flutter test` (unit + widget) + one `integration_test` suite (app) — jest-expo + Maestro were the pre-cutover (mobile/) equivalents |
| Linting | ruff + ty + vulture (backend); `dart format` + `flutter analyze` (app) — biome was the pre-cutover (mobile/) equivalent |
