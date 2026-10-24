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
# asks the decision model only what the corpus is missing or stale on (paid); exit 1 unless coverage is 100%.
# `make enrich-corpus` is the local/dev wrapper; prod runs are the owner's.
uv run python scripts/enrich_corpus.py --local .cache/glean_recipe_cache --dry-run
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
    re-reads and re-applies its change, and a full rebuild re-scans the table and recomputes rather than
    republishing a stale snapshot. If publication still fails it raises `ProjectionPublishError` and logs
    `scripts/build_recipe_index.py --table … --bucket …`; the table keeps the change, so the rebuild heals
    it. Readers stay on their 5-minute cache.
  - `publish(recipe)` on the store makes an already-stored recipe visible again without rewriting it. That is
    the repair path: a retried import deduped on its source URL calls it, so a 500 from a failed publish is
    healed by the retry rather than silently returning a recipe planning cannot see.
  - `answers_for(recipe_id)` is the authoritative per-recipe answer read: a consistent, paged Query on
    `pk=RECIPE#<id>` in dynamo mode (1 RCU per 4 KB of answers read — one unit for an ordinary recipe, more
    pages for a question reworded many times), a JSONL filter in blob mode. Enrichers use it to decide what is
    missing; the projection must never be their source of truth.
  - The table is the only authority for a full projection. `rebuild_projection()` (and the migration's last
    step, and `scripts/build_recipe_index.py --table`) scans it and publishes conditionally, re-scanning if
    another writer got there first; nothing publishes a document built from anywhere else.
- **Enrichment is a pipeline, not a script** (F2, ADR 0025). `recipes/enrichment/` holds:
  - `enricher.py` — what an enricher declares: each question's wording, its **confidence bar** (threshold
    plus which side is safe) and the rule that turns a raw answer into a stored value. `Enricher` is a
    `Protocol`, so V5's attribute enrichers slot in as more.
  - `runner.py` — `run_enrichment`: one `DecisionClient.decide` request per recipe carrying **every**
    question missing or stale across all enrichers, answers written through the seam per checkpoint, and
    the projection rebuilt once at the end. It decides that from `answers_for` (the authoritative read), so
    a run that died, or whose final rebuild failed, resumes instead of paying for the same answers again.
    Stale means the answer's criteria hash, the recipe's content hash or the model is no longer current.
  - `coverage.py` — the per-question coverage report (current / stale / missing / failed), printed as a
    table by `scripts/enrich_corpus.py` and readable as data.
  - `dietary.py` — the first enricher: six `noul` questions with ADR 0011's thresholds unchanged.
    `meal_plan/dietary_decisions.py` is now the read side and re-exports those questions.

### Rolling back to blobs

`RECIPE_STORE=blobs` restores the corpus **as of the migration that filled the table**. Nothing in dynamo
mode writes the blobs or `_decisions/dietary.jsonl` — not an import, not an enrichment run — so recipes
imported and answers computed while the setting was `dynamo` are only in DynamoDB and the projection. That
is a snapshot rollback, not a two-way mirror: before flipping back, export or re-create anything that must
survive (re-import the affected URLs, re-run `scripts/enrich_corpus.py`), or read straight from the table.
The migration prints the same warning at the end of every run.

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
│                     # answers.py: one decision answer (dietary now, V5's attributes later)
│                     # enrichment/ — enrichers declare questions, the runner asks one request per recipe
│                     #   enricher.py, runner.py, coverage.py, dietary.py (ADR 0025)
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
