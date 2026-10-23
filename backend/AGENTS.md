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
```

## Architecture

Stateless FastAPI backend deployed as AWS Lambda (Mangum adapter). All app state lives on-device, in the Flutter app's Drift SQLite database. The backend is responsible for:

- **AI processing:** Receipt OCR (Textract or vision model), ingredient normalisation, recipe import via URL, meal-plan generation — all LLM calls go through OpenRouter via LangChain and the feature-specific `LLMRouter` policy from `get_llm_router`.
- **Auth:** Cognito JWT validation on every request (`verify_cognito_token` in `dependencies.py`)
- **Rate limiting:** every paid-model route enforces `settings.rate_limit_per_hour` (default 20; deployments raise it to 60 via the template's `RateLimitPerHour` parameter) requests per hour per Cognito sub, and answers 429 past it, with a `Retry-After` header holding the whole seconds until that caller's window frees a slot (the app says "try again in N minutes"). Counters live in memory, so the limit is **per Lambda container**, not global: a user spread across several warm containers can exceed it. Shared storage (e.g. DynamoDB) is the follow-up if that matters.
- **S3 buffering:** Receipt images pass through S3 before Textract; dev DB exports also use S3
- **Recipe data:** External recipe-api.com integration plus a durable recipe corpus. Both the HTTP response cache (24h search TTL; detail cached indefinitely) and the corpus are stored via `recipe_api.blob_store`: an S3 bucket (`s3_recipe_cache_bucket`) in deployed environments, or the `.cache/glean_recipe_cache` filesystem tree locally and in tests.

### Module layout

```
src/glean/
├── main.py           # FastAPI app + Mangum handler
├── worker.py         # the async stack's two Lambda entry points: glean.worker.handler (SQS session
│                     #   worker) and glean.worker.dlq_handler (marks a dead-lettered session failed)
├── agent/            # the meal-plan agent as one deep module: start(session) hides LangGraph, the
│                     #   checkpointer, the graph nodes and the progress lines. The ONLY place that may
│                     #   import LangGraph (ruff TID251, like glean/llm.py for LangChain)
├── sessions/         # agent sessions: the agent_sessions item models, the in-memory and DynamoDB
│                     #   stores, the SQS queue + visibility lease, and the local factories
├── dev/              # local-only helpers: the queue consumer for Docker Compose, a stub meal-plan
│                     #   model, and the dev router
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
│                     # unit_backfill.py: one-off corpus re-parse (scripts/backfill_recipe_units.py, local fs only)
└── meal_plan/        # POST /meal-plan — LLM meal-plan generation, saved mode and corpus mode
                      # /meal-plan/sessions (POST, GET) — the async agent session routes
                      # pipeline.py: corpus mode as prepare -> choose -> finalise, the three steps the
                      #   sync route runs in order and the agent graph runs as its three nodes
                      # eligibility.py: the six-week recency floor, pure and store-free (the future
                      #   `get_eligible_recipes` core). Corpus mode never re-offers a recipe cooked in the
                      #   last 42 days unless honouring that leaves fewer than three recipes per slot; the
                      #   hard constraints (dietary decisions, planned meals, time cap) are applied first
                      #   and never relax. history comes in on the request as `cooked_history`, carrying
                      #   each cook's rating and note: a recipe whose latest rating is thumbs down never
                      #   comes back, floor or no floor, and the note never reaches a prompt (screening it
                      #   is the feedback screen's job, which does not exist yet).
```

### Structured output only

Every LLM response is read through `LLMRouter.invoke` -> `invoke_structured`, which uses
`with_structured_output(schema, method="json_schema")`. Never call `.invoke` on a raw chat model and read its text;
`tests/test_llm_router_structured_output.py` pins this for every `Feature`. Put schema rules (units, categories,
ranges) in typed fields and enums, not prompt prose. Shopping units are the `ShoppingUnit` enum, which mirrors the
app's `shoppingUnits` list by hand (a test catches drift).

Callers pass `invoke` a `system` prompt and a `user` message (text, or text and `ImagePart`s) and never import
LangChain or the OpenRouter SDK. Only `llm.py` does; ruff's `TID251` rejects those imports anywhere else in `src/glean`.

### Agent sessions (the async meal plan)

`POST /meal-plan/sessions` returns at once and the plan is made out of process (ADR 0026). The
synchronous `POST /meal-plan` stays, shares `meal_plan.pipeline` and goes in a follow-up PR.

```
POST /meal-plan/sessions           202 {"session_id": "..."}        one paid call, rate limited
GET  /meal-plan/sessions/{id}      200 SessionView                  free, never rate limited
GET  ...?after=<cursor>            progress lines since the cursor
```

`SessionView` is `{session_id, status, progress, next_cursor, result, error, updated_at}`.
`status` is `queued | running | waiting_for_user | done | failed`; `result` is `MealPlanResult`
(the sync route's shape, `uses_up` included) and `error` is `{code, retry_after_minutes}` with
`code` one of `no_eligible_recipes | rate_limited | model_error | worker_failed | invalid_request`.
Both routes are scoped to the caller's Cognito sub: one item is keyed `(sub, session id)`, so
another user's session is a 404 rather than a 403. `POST` refuses `source: "saved"` with a 422 —
V1's graph wraps the corpus pipeline only.

How a session moves: the route writes `queued` and sends a message; the SQS worker claims it with a
conditional `queued -> running` (a duplicate delivery finds it running and drops), runs
`agent.start`, and writes `done` or `failed`. Liveness is the queue lease: a 60 s visibility timeout
renewed every 20 s, and the dead-letter queue's handler marks a session `worker_failed` once SQS gives
up. Never add a state machine or a scheduler on top (ADR 0026).

- **`glean/agent` is the only module that may import LangGraph** (ruff `TID251`, per-file exempt for
  `src/glean/agent/**`). The graph is `prepare -> plan -> finalise` over `meal_plan.pipeline`, so a
  session and the sync route return the same picks for the same request and seed (the session id
  seeds the sampler). A wider graph (`plan <-> act`, questions, cancel) changes this module only.
- **`glean/sessions`** owns the item, the store rules and the queue. Every update refreshes
  `updated_at` and the TTL; `get` never writes. Progress lines are bounded (`MAX_PROGRESS_LINES`),
  and the cursor is an absolute index, so a poll is idempotent.
- **`AGENT_RUNNER=inline`** (unit tests, evals, `make start-backend` on the host) runs the agent in
  the request against the in-memory store and saver. Deployed and Compose run `queue`.
  `make start-backend-docker` brings up DynamoDB Local, ElasticMQ, the worker and a bootstrap that
  builds them from `template.yaml`.

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
