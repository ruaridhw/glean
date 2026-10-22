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
- **Rate limiting:** every paid-model route enforces `settings.rate_limit_per_hour` (default 20; deployments raise it to 60 via the template's `RateLimitPerHour` parameter) requests per hour per Cognito sub, and answers 429 past it, with a `Retry-After` header holding the whole seconds until that caller's window frees a slot (the app says "try again in N minutes"). Counters live in memory, so the limit is **per Lambda container**, not global: a user spread across several warm containers can exceed it. Shared storage (e.g. DynamoDB) is the follow-up if that matters.
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
├── worker.py         # the async stack's two Lambda entry points: glean.worker.handler (SQS session
│                     #   worker) and glean.worker.dlq_handler (marks a dead-lettered session failed)
├── agent/            # the meal-plan agent as one deep module: start(session) hides LangGraph, the
│                     #   checkpointer, the graph nodes and the progress lines. The ONLY place that may
│                     #   import LangGraph (ruff TID251, like glean/llm.py for LangChain)
├── sessions/         # agent sessions: the agent_sessions item models, the in-memory and DynamoDB
│                     #   stores (owner token + lease, gzipped inputs), the SQS queue, the factories
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
│                     # corpus.py: RecipeCorpusStore + the CorpusBackend seam (blob adapter)
│                     # dynamo_corpus.py: the glean-recipes table + projection maintenance (F1/#162)
│                     # projection.py: the gzipped S3 projection planning reads
│                     # answers.py: one decision answer (dietary now, F2's attributes later)
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
POST   /meal-plan/sessions         202 {"session_id": "..."}        one paid call, rate limited
GET    /meal-plan/sessions/{id}    200 SessionView                  free, never rate limited
GET    ...?after=<cursor>          progress lines since the cursor
DELETE /meal-plan/sessions/{id}    204                              free, never rate limited
```

`SessionView` is `{session_id, status, progress, next_cursor, result, error, updated_at}`.
`status` is `queued | running | waiting_for_user | done | failed | cancelled`, and `done`, `failed` and
`cancelled` are terminal. `error` is `{code, retry_after_minutes}` with `code` one of
`no_eligible_recipes | rate_limited | model_error | worker_failed | invalid_request`.
All four routes are scoped to the caller's Cognito sub: one item is keyed `(sub, session id)`, so
another user's session is a 404 rather than a 403. `POST` refuses `source: "saved"` with a 422 —
the graph wraps the corpus pipeline only.

`result` (`MealPlanResult`, which the sync route returns too, additively) is the proposal:

```jsonc
{
  "suggestions": [{   // one per empty slot
    "recipe_id": null, "external_id": "rec_x", "title": "...", "reason": "...",
    "missing_ingredients": [], "uses_up": [{"name": "coriander", "expires_in_days": 2, "goes_off": "Thu"}],
    "reason_kind": "urgent_item | profile | feedback | balance | history | answer",
    "alternative": {  // the swap target: the same shape without its own alternative
      "recipe_id": null, "external_id": "rec_y", "title": "...", "reason": "...",
      "missing_ingredients": [], "uses_up": [], "reason_kind": "balance"
    }
  }],
  "week_summary": "One line for the week; template text when the plan is degraded.",
  "planned_alternatives": [{"external_id": "rec_planned", "alternative": {/* a suggestion */}}],
  "degraded": false   // true when finalise fell back; the UI must not treat it differently
}
```

An alternative is always an offered, eligible candidate that is not already a chosen or planned meal;
when the model's own alternative is unusable or missing, the server takes the next-best candidate.
`planned_alternatives` only covers meals already in the week that came from the corpus, because there
is no corpus recipe to show for the app's own plan entries.

How a session moves: the route writes `queued` and sends a message; the SQS worker claims it with a
conditional `queued -> running`, runs `agent.start`, and writes `done` or `failed`. Liveness is the
session's own lease, not the message's visibility: the attempt that starts a run takes an owner token
and a lease, taken once at claim and never extended, anchored to its own invocation deadline
(`now + context.get_remaining_time_in_millis() + 2 s`, see `sessions/store.py`). Every later write is
conditioned on that token, and a delivery may take over a `running` session whose lease has lapsed —
resuming it from its LangGraph checkpoint, or publishing the plan a finished checkpoint holds.

A delivery that finds a **live** owner must **raise**, never return: Lambda acknowledges a message whose
handler returns, and acknowledging nonterminal work deletes the only trigger that recovers the run if
the live attempt then dies. Only a terminal session and a run this invocation completed are
acknowledged. The queue allows three receives for that reason (one may be spent failing a duplicate),
and its 150 s visibility timeout covers the 120 s worker timeout plus up to 10 s of init
(cfn-lint E3505 is enforced, not suppressed). A crashed run therefore comes back within about 2.5
minutes, inside the app's five-minute cap. The dead-letter handler is a retry loop: it fails a session
only when it is nonterminal *and* its lease has lapsed, and **raises** when a live run still owns it, so
the dead letter is kept and retried on the dead-letter queue's own 60 s visibility timeout — a session
is failed within about a minute of its lease lapsing, at most ~3 minutes after a crash. It acknowledges
only a session that is missing, terminal, or newly failed. One run also has a 90 s budget, checked
between steps, and the model call gets only what is left of it. Never add a state machine or a
scheduler on top (ADR 0026).

How a session stops: `DELETE` calls `agent.cancel`, one status write that turns the session
`cancelled` unless it is already terminal (so a repeat delete is a no-op and the answer is always 204).
`cancelled` is terminal, which does the rest without a second mechanism: `RunGuard`'s step write is
owner-conditioned *and* requires `running`, so the next step is refused and the run stops without
writing anything (one read on the refused path only, to log a cancel as a cancel rather than as a lost
lease); `complete`/`fail` cannot resurrect or overwrite it; `claim` reports `FINISHED`, so a redelivery
or a takeover of a crashed run is acknowledged and does nothing; and the dead-letter handler treats it
as terminal. A cancel that lands between the last step and the plan write therefore still wins. A
complete run makes no reads beyond the lease design's own (the claim and each store call's check); a
cancelled one adds exactly one, at the step that notices.

- **`glean/agent` is the only module that may import LangGraph** (ruff `TID251`, per-file exempt for
  `src/glean/agent/**`). The graph is `prepare -> plan -> finalise` over `meal_plan.pipeline`, so a
  session and the sync route return the same picks for the same request and seed (the session id
  seeds the sampler). A wider graph (`plan <-> act`, questions, cancel) changes this module only.
- **`glean/sessions`** owns the item, the store rules and the queue. Every update refreshes
  `updated_at` and the TTL; `get` never writes. Progress lines are bounded (`MAX_PROGRESS_LINES`),
  and the cursor is an absolute index, so a poll is idempotent. Inputs are stored gzipped, and
  `create` refuses (422) a request whose item would not leave room for the outcome: V8's 400-row
  history with 500-character notes is a real input, and one item is 400 KB. The plan is measured
  before it is written too (64 KB is reserved for it): a plan that would overflow the item fails the
  session `model_error` instead of raising into SQS.
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
