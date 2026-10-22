# AGENTS.md

This file provides guidance to agents when working in the Glean backend.
See `../AGENTS.md` for repo-wide Makefile targets and preferred tools.
`CLAUDE.md` is a compatibility symlink to this file.

## Commands

Prefer `make test-backend` / `make lint-backend` from the repo root. Use the commands
below for targeted runs within this directory:

```bash
uv run pytest tests/test_health.py -v  # single file
uv run pytest -k "test_name"           # single test by name
uv run python scripts/seed_catalogue.py --table glean-catalogue-<env>  # idempotent catalogue seed; prod runs are the owner's
# idempotent, resumable, paced; refuses a prod table without --i-am-the-owner. Owner-run against prod.
uv run python scripts/migrate_recipe_corpus.py --table glean-recipes-<env> --bucket <recipe-cache-bucket> --dry-run
```

## Architecture

Stateless FastAPI backend deployed as AWS Lambda (Mangum adapter). All app state lives on-device, in the Flutter app's Drift SQLite database. The backend is responsible for:

- **AI processing:** Receipt OCR (Textract or vision model), ingredient normalisation, recipe import via URL, meal-plan generation — all LLM calls go through OpenRouter via LangChain and the feature-specific `LLMRouter` policy from `get_llm_router`.
- **Auth:** Cognito JWT validation on every request (`verify_cognito_token` in `dependencies.py`)
- **Rate limiting:** every paid-model route enforces `settings.rate_limit_per_hour` (default 20; deployments raise it to 60 via the template's `RateLimitPerHour` parameter) requests per hour per Cognito sub, and answers 429 past it. Counters live in memory, so the limit is **per Lambda container**, not global: a user spread across several warm containers can exceed it. Shared storage (e.g. DynamoDB) is the follow-up if that matters.
- **S3 buffering:** Receipt images pass through S3 before Textract; dev DB exports also use S3
- **Recipe data:** External recipe-api.com integration plus a durable recipe corpus. The HTTP response cache
  (24h search TTL; detail cached indefinitely) is stored via `recipe_api.blob_store`: an S3 bucket
  (`s3_recipe_cache_bucket`) in deployed environments, or the `.cache/glean_recipe_cache` filesystem tree
  locally and in tests.
- **The corpus is behind one seam.** `recipes/corpus.py`'s `RecipeCorpusStore` is what every caller uses
  (API, meal planner, scripts); behind it sits a `CorpusBackend`, chosen once per process by `RECIPE_STORE`
  (F1/#162):
  - `blobs` (default) — the S3 `corpus/` prefix: one JSON blob per recipe, a JSONL search index and the
    `_decisions/dietary.jsonl` answers, all through `recipe_api.blob_store`.
  - `dynamo` — the `glean-recipes-<env>` table (`RECIPES_TABLE`) plus a gzipped S3 projection
    (`projection/recipes-v1.json.gz` in the recipe-cache bucket) that search, summaries and planning's
    dietary decisions read, cached 5 minutes per Lambda. See `recipes/dynamo_corpus.py` for the item schema
    (`RECIPE#<id>`/`RECIPE`, `RECIPE#<id>`/`ANSWER#<question>#<criteria_hash>`, `SOURCE#<url sha>`/`RECIPE`).
  - Answers are named `dietary:<flag>` for the dietary enricher; F2's enrichers add their own question names
    to the same item shape/projection entry (`attributes`).
  - Behaviour is identical across the seam: search results, dietary exclusions and the store's interface do
    not change with the setting, which is why the API and the planner never branch on it.
  - The projection is one S3 object published by every writer, so publication is a conditional write
    (`If-Match` on the object ETag, `If-None-Match: *` to create): a writer that loses the version race
    re-reads and re-applies its change. If publication still fails it raises `ProjectionPublishError` and
    logs `scripts/build_recipe_index.py --table … --bucket …`; the table keeps the change, so the rebuild
    heals it. Readers stay on their 5-minute cache.

### Rolling back to blobs

`RECIPE_STORE=blobs` restores the corpus **as of the migration that filled the table**. Nothing in dynamo
mode writes the blobs or `_decisions/dietary.jsonl` — not an import, not a decision run — so recipes
imported and answers computed while the setting was `dynamo` are only in DynamoDB and the projection. That
is a snapshot rollback, not a two-way mirror: before flipping back, export or re-create anything that must
survive (re-import the affected URLs, re-run `scripts/compute_dietary_decisions.py`), or read straight from
the table. The migration prints the same warning at the end of every run.

### Module layout

```
src/glean/
├── main.py           # FastAPI app + Mangum handler
├── rate_limit.py     # enforce_ai_rate_limit: the per-user limit dependency for paid-model routes
├── config.py         # Pydantic BaseSettings (reads from .env / Secrets Manager in Lambda)
├── dependencies.py   # verify_cognito_token JWKS validation; get_llm_router
├── llm.py            # OpenRouter LangChain client; Feature enum; LLMRouter policy
├── decisions.py      # Glean Decisions client (DecisionClient): the only caller of /api/alpha/decisions
├── shopping/         # POST /shopping/parse-description — decision-gated segmentation, one batched parse for cache misses, per-segment parse cache
├── observability.py  # Logger + Tracer (aws-lambda-powertools)
├── health/router.py  # GET /health
├── dev/router.py     # POST /dev/export-db → S3 (db-exports/<user>/<UTC ts>/, 30-day retention)
│                     # GET /dev/backups → the caller's own backups, prepared first, with 5-minute download URLs.
│                     #   Scope is the Cognito sub only. An agent's prepared backup is a glean.db uploaded beside
│                     #   a PREPARED object (optional JSON {"note": "..."}) in the same user prefix.
├── catalogue/        # ingredient groups, section rule, catalogue item models, CatalogueStore + in-memory and DynamoDB stores, seed data,
│                     # normalise (raw names → catalogue items), POST /catalogue/normalise and GET /catalogue?since=<version> (the versioned sync the app reads; each item carries its computed `section` and its `former_ids`)
├── receipts/         # POST /receipts/scan (image upload → Textract or vision OCR)
│                     # POST /receipts/describe (text → normalised ingredients)
├── recipe_api/       # recipe-api.com HTTP client + blob_store (S3 / filesystem cache seam)
├── recipes/          # GET /recipes/search, GET /recipes/{id}
│                     # POST /recipes/import-url (LLM-parsed web scrape)
│                     # corpus.py: RecipeCorpusStore + the CorpusBackend seam (blob adapter)
│                     # dynamo_corpus.py: the glean-recipes table + projection maintenance (F1/#162)
│                     # projection.py: the gzipped S3 projection planning reads
│                     # answers.py: one decision answer (dietary now, F2's attributes later)
│                     # unit_backfill.py: one-off corpus re-parse (scripts/backfill_recipe_units.py, local fs only)
└── meal_plan/        # POST /meal-plan — LLM meal-plan generation
```

### Structured output only

Every LLM response is read through `LLMRouter.invoke` -> `invoke_structured`, which uses
`with_structured_output(schema, method="json_schema")`. Never call `.invoke` on a raw chat model and read its text;
`tests/test_llm_router_structured_output.py` pins this for every `Feature`. Put schema rules (units, categories,
ranges) in typed fields and enums, not prompt prose. Shopping units are the `ShoppingUnit` enum, which mirrors the
app's `shoppingUnits` list by hand (a test catches drift).

Callers pass `invoke` a `system` prompt and a `user` message (text, or text and `ImagePart`s) and never import
LangChain or the OpenRouter SDK. Only `llm.py` does; ruff's `TID251` rejects those imports anywhere else in `src/glean`.

### Auth

`verify_cognito_token(request, credentials)` is a FastAPI dependency:
- Fetches JWKS from Cognito, cached with `lru_cache`
- On unknown `kid`: cache-bust and retry once
- Validates RS256 sig, audience, issuer, expiry
- Returns the Cognito `sub`, which keys the per-user rate limit

### Receipt OCR modes

Controlled by `receipt_ocr_mode` in config (env var `RECEIPT_OCR_MODE`):
- `"textract"` (default): upload image to S3 → AWS Textract expense analysis → LLM normalisation via OpenRouter
- `"vision"`: send image directly to a vision-capable OpenRouter model selected by `LLMRouter` for `Feature.RECEIPT_SCAN`

### Testing

Tests override the auth dependency:
```python
app.dependency_overrides[verify_cognito_token] = lambda: "test-user-sub"
```

Conftest provides `client` (with override) and `auth_headers` fixtures, and resets the rate-limit window before every test.

### Rate limiting a new paid-model route

Add one line to the route decorator; never hand-roll a limit:

```python
from glean.rate_limit import enforce_ai_rate_limit

@router.post("/normalise", dependencies=[Depends(enforce_ai_rate_limit)])
```

Add the route to `AI_ROUTES` in `tests/test_rate_limit.py`. Requests that pass auth count against the limit even if the model call then fails; unauthenticated requests get 401 and count for nothing. Free routes (health, recipe search and get) stay unlimited.

### Dietary ground truth

Allergen and diet ground truth for processed ingredients (curry pastes, seasonings, sauces) comes from the
ingredient lists on the Tesco, Sainsbury's and Ocado online shops. A maintainer label overrides any LLM judge.
Tree nuts and peanuts are separate allergies with a flag each (`tree-nut-free`, `peanut-free`). Satay is peanut;
pine nuts, so pesto, are tree nut. Other processed ingredients, chilli crisp included, follow the retailer data with
no named exception. A `nut-free` sent by an older app build applies both.

Retailer ground truth is a dev-only helper, `scripts/grocery_ground_truth/` (Playwright lives in the `audit`
dependency group and is never imported by `src/glean`). Run it with
`uv run --group audit python -m scripts.grocery_ground_truth "korma curry paste" --n 5`; the audit's
`report --retailer-ground-truth` uses it where the judges are both unsure or disagree. Only listed ingredients
count by default, never "may contain"; a type of ingredient contains an allergen when most products read list it.
Both are `ContainsPolicy` settings. Reads are throttled (one every 2.5 s), cached under `.cache/`, and a block
page is reported as blocked, never worked around.
