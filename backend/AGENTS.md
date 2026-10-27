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
# measures the attributes against an independent labeller's labels and picks each bar (paid enrich step, then
# a free compare). The sample and its v5-check/ answers live outside the repo; `make check-attributes SAMPLE=...`.
uv run python scripts/check_recipe_attributes.py enrich --sample <sample-dir>
uv run python scripts/check_recipe_attributes.py compare --sample <sample-dir>
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
  - Answers are named `dietary:<flag>`, `attribute:<name>` and `active_time:bucket`; every enricher's answers
    share the same item shape, and a projection entry carries the attributes derived from them (`attributes`).
    A `noul` answer is its probability; a `choice`/`score` answer also carries the value it accepted
    (`RecipeAnswer.value`, `unsure` below its bar).
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
    Each question carries the `DecisionModel` its bar was measured on (#216): the runner refuses, before any
    request or write, a client asking or accepting any other model, and stores only a served identity that
    model covers.
  - `coverage.py` — the per-question coverage report (current / stale / missing / failed), printed as a
    table by `scripts/enrich_corpus.py` and readable as data.
  - `dietary.py` — the first enricher: six `noul` questions with ADR 0011's thresholds unchanged, owned by
    `CALIBRATED_DIETARY` (the model and cutoffs as one reviewed `DietaryCalibration`).
    `meal_plan/dietary_decisions.py` is now the read side and re-exports those questions.
  - `attributes.py` — five questions per recipe: `choice` for `main_protein`, `main_carb`, `dish_type` and
    `cuisine`, `score` for `whole_food`. Accepted only at the attribute's bar (0.8 by default, per-attribute
    tunable, never below 0.7), otherwise stored `unsure`.
    Its bars, and active time's, are for `ATTRIBUTE_BAR_MODEL` (the model the 50-recipe check asked), so
    those questions accept no other model's answers, as dietary's do under its calibration.
  - `active_time.py` — one `score` over the method, with the stated prep and total times as hints, answering
    with one of G1's five buckets. Below its bar it stores `unsure`, and the filter falls back to total time.
  - `projection_attributes.py` — `attributes_from_answers`: how a recipe's current answers become the
    attributes its projection entry carries. Both the full rebuild and the incremental answer write use it.
  - An enricher may add `state(recipe)` for what it needs beyond title and ingredients (the method, the
    stated times). The runner merges it only for the families it is asking, so a dietary-only run sends no
    method text.
  - `recipes/attributes.py` is the shared contract: the G1 enums, the `unsure` member each allows, the frozen
    `RecipeAttributes` model and the time-cap rule (`fits_time_cap`), plus the projection entry's typed
    accessor (`ProjectedRecipe.recipe_attributes`).

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
├── screening.py      # the injection screen: one pinned `noul` question at SCREEN_BAR (0.9), fails closed;
│                     #   every household free text a model reads goes through it first
├── profile/          # POST /profile/interview — the taste interview (spec §6.4): five fixed openers, then up
│                     #   to two model-chosen follow-ups, capped at 7 questions. Stateless: the app sends the
│                     #   transcript and draft profile each turn. Screened answers go to the model as data in
│                     #   typed fields; a dropped answer never does. Favourite meals are matched to corpus
│                     #   recipes by title. HouseholdProfile is versioned JSON, stored on the device
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
│                     # attributes.py: the G1 attribute contract (enums, RecipeAttributes, the time-cap rule)
│                     # corpus.py: RecipeCorpusStore + the CorpusBackend seam (blob adapter)
│                     # dynamo_corpus.py: the glean-recipes table + projection maintenance (F1/#162)
│                     # projection.py: the gzipped S3 projection planning reads
│                     # answers.py: one decision answer (dietary now, V5's attributes later)
│                     # enrichment/ — enrichers declare questions, the runner asks one request per recipe
│                     #   enricher.py, runner.py, coverage.py, dietary.py, attributes.py, active_time.py,
│                     #   projection_attributes.py (ADR 0025)
│                     # unit_backfill.py: one-off corpus re-parse (scripts/backfill_recipe_units.py, local fs only)
└── meal_plan/        # POST /meal-plan — LLM meal-plan generation, saved mode and corpus mode
                      # /meal-plan/sessions (POST, GET) — the async agent session routes
                      # pipeline.py: corpus mode as prepare -> choose -> finalise, the three steps the
                      #   sync route runs in order; the agent graph runs prepare and finalise as its
                      #   first and last nodes, and widens a prepared week with what its tools found
                      # tools.py: the planner's framework-free tools -- get_eligible_recipes (hard
                      #   constraints, the floor, a narrowing-only RecipeFilter, the urgent guarantee,
                      #   ranking), get_recipes, score_meal_plan, create_candidate_meal_plans; and
                      #   FeedbackChip + CHIP_PREDICATES, the one place a week's chip becomes a predicate
                      #   or a scorer term (weights in ScorerWeights); quick weeknights, comfort food and
                      #   guests (NARROWING_CHIPS, chip_narrows) narrow the sampler's offer while three
                      #   fresh recipes per slot pass, else fall back to their +2 (logged either way)
                      # feedback.py: the week's human feedback (V9) -- screen_feedback runs the note
                      #   through the injection screen (dropped, never raw, when it fails or cannot be
                      #   asked; the chips still apply), and prompt_payload is the only feedback a prompt
                      #   carries: the chips with their meanings and an accepted note as data in its own
                      #   field. The result's `feedback_note` says used / not_a_preference / unavailable.
                      #   The note is screened BEFORE the graph runs (agent.runtime) and before the sync
                      #   route's traced code: graph input, state, checkpoints and traces carry only
                      #   `without_note(request)` and the ScreenedFeedback. A chip the backend does not
                      #   know is ignored with a warning, not a 422
                      # household.py: the household profile as planning reads it (V13b). The request's
                      #   `profile` (schemas.PlanningProfile: lists <= 20 x 60 code points, favourites 120, habits and household
                      #   <= 500, the newest 20 notes <= 200; past that a 422, never a clip) is used three ways:
                      #   disliked ingredients are a hard constraint beside the dietary decisions, in the sampler
                      #   and get_eligible_recipes, before the floor (whole words, plurals folded, "nut" never hits
                      #   "nutmeg"; counts per dislike logged, never text); favourites, cuisines (CUISINE_ALIASES to
                      #   V5's enum, unknown ignored and counted), loved ingredients and protein targets are scorer
                      #   terms (balance.ProfileScoring rides the prepared plan, so widen and swaps score alike),
                      #   and rank the offer: fresh eligible favourites are offered with last week's dinners, and
                      #   each liked cuisine or protein minimum reserves a few places (pipeline.PROFILE_RESERVE);
                      #   and `household_profile` in the prompt carries the enum fields always and the free text
                      #   only as screen_profile passed it (each field its own screen, in parallel, each failing closed). Like the
                      #   week's note, the profile's prose is screened before the graph and the sync route's traced
                      #   code, which then hold `without_profile_text(request)` and the ScreenedProfile
                      # eligibility.py: the six-week recency floor, pure and store-free (the future
                      #   `get_eligible_recipes` core). Corpus mode never re-offers a recipe cooked in the
                      #   last 42 days unless honouring that leaves fewer than three recipes per slot; the
                      #   hard constraints (dietary decisions, planned meals, time cap) are applied first
                      #   and never relax. history comes in on the request as `cooked_history`, carrying
                      #   each cook's rating and note: a recipe whose latest rating is thumbs down never
                      #   comes back, floor or no floor, and a cook's note never reaches a prompt (only the
                      #   week's note does, and only through feedback.py's screen).
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
POST   /meal-plan/sessions/{id}/messages  202 {"session_id", "swap_id", "note_dropped"}  one paid call, rate limited
DELETE /meal-plan/sessions/{id}    204                              free, never rate limited
```

`SessionView` is `{session_id, status, progress, next_cursor, result, error, swap, question, updated_at}`;
`question` is `{question, options, why}` while the status is `waiting_for_user`, otherwise null.
`status` is `queued | running | waiting_for_user | done | failed | cancelled`, and `done`, `failed` and
`cancelled` are terminal. `error` is `{code, retry_after_minutes}` with `code` one of
`no_eligible_recipes | rate_limited | model_error | worker_failed | invalid_request`.
All five routes are scoped to the caller's Cognito sub: one item is keyed `(sub, session id)`, so
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
complete run makes no reads beyond the lease design's own (the claim and each store call's check) except
one per later agent turn: a `plan` turn after a tool has no line to write, so it reads the session before
its paid model call, and a cancel that landed while the tool ran stops the run there. A takeover reads
once more at its first step, so it does not repeat the progress line of the node the crash interrupted. A
cancelled run adds at most one more read, at the step that notices.

- **`glean/agent` is the only module that may import LangGraph** (ruff `TID251`, per-file exempt for
  `src/glean/agent/**`). The graph is `prepare -> plan <-> act -> finalise` (V7). `prepare` and
  `finalise` are `meal_plan.pipeline`'s, so the sync route and a session offer the same candidates and
  validate a week the same way (the session id seeds the sampler). `plan` is the only LLM node and
  answers a typed `NextAction` (`agent/actions.py`: `call_tool` with typed arguments, `ask_household`, or `propose`)
  through structured output, never provider tool-calling. `act` runs the tool through
  `agent/adapters.py` over the framework-free `meal_plan.tools`, writes the tool's progress line
  first, and widens the week with any recipe the tool found. The budget lives in the graph state: at
  most 8 tool calls and the run's 90 s. A spent budget, a model or tool error, or an answer that
  keeps nothing ends in the scorer's best week with template reasons (`degraded: true`), so once
  `prepare` has run a session never ends `model_error`. `finalise` logs each session's tool calls,
  invalid answers, fallback reason and drift from the scorer's best (CloudWatch `SessionToolCalls`,
  `SessionInvalidActions`, `SessionDrift`). Asking the household is `ask_household` (V11, below).
- **Household messages.** `POST .../messages` takes one union discriminated on `type`
  (`sessions.models.HouseholdMessage`): `{"type": "swap", "slot", "note", "week"}` (V10),
  `{"type": "answer", "option", "note"}` and `{"type": "skip"}` (V11). The route branches on the type
  before any status check, screens any note with `glean.screening` before anything stores it (fail
  closed: only the screened text, and why a note was dropped, are ever stored or passed on), then calls
  `agent.resume(session_id, message)`, which stores the message on the item and re-enqueues the session.
  It answers 202 `MessageAccepted {session_id, swap_id | null, note_dropped}`. An answer or a skip needs
  `waiting_for_user` (else 409).
- **Swaps (V10).** A swap needs a proposal (`done`, or a `failed` that still holds one) and no swap
  running: the status is the lock, so a second swap is a 409, except over a swap queued at least
  `STALE_QUEUED_SWAP_SECONDS` ago that no delivery ever took (the route died before dispatching it),
  which is marked failed and replaced. `week` is the card ids the app shows, after any local swap or Undo:
  it must have one id per card, only ids this proposal offered, none twice, with `slot` among them (else
  422), and the swap locks and scores against it. A planned meal is never a slot (422, ADR 0020). A queue
  that will not take the message fails the session as create does; the proposal stays and the next swap
  is accepted. Every delivery goes through `agent.start`, which decides from the item the claim won, in
  `_run`'s order: a pending answer or skip (V11), a pending swap, a finished graph (publish), then as
  before. So a stale first-run message runs the queued swap and can never publish the old week. A swap
  invokes the session's own LangGraph thread with the swap: `swap_start -> swap_plan <-> act ->
  swap_finalise`, where the screened note reaches the model only as `swap_note`, the model may use up to
  3 tools, and proposes one replacement. The replacement is kept only if it is eligible, not planned and
  not in the week, its alternatives or anything swapped out before; otherwise it is the scorer's best
  (`pipeline.replacement`). A swap always ends `done`: with nothing left to swap in, or on a bug, the
  proposal is written back unchanged and the swap reads `no_replacement` or `failed`.
  `SessionView.swap` is the newest swap (`state`, `note`: `none | used | dropped`, `replacement`); a
  swap on a failed or cancelled session reads `failed`. Undo swap is the app's own; it is why the app
  sends `week`.
- **The agent's one question (V11).** `ask_household{question, options, why}` is the third `NextAction`.
  `act` calls LangGraph's `interrupt()`; the runtime parks the session `waiting_for_user` with the question
  (clipped to `MAX_QUESTION_CHARS`, `MAX_OPTIONS` x `MAX_OPTION_CHARS`) and **no owner and no lease**, and
  counts `SessionsAsked`. A second question is refused like an unparseable answer, so the agent plans. An
  answer must name an offered option, carry a note, or both (else 422). `agent.resume` stores the reply with
  one conditional `waiting_for_user -> queued` write (a duplicate, late or post-cancel answer is a 409) and
  re-enqueues the session; its delivery claims it like a fresh run, and `_run`'s first branch continues the
  graph with `Command(resume=reply)`. The answer reaches the next turn like a tool result, under `data`. A
  crash after that resumes with the same stored reply; a crash between the interrupt and the park re-parks
  from the checkpoint without a model call; a late copy of the first message finds the session parked
  (`ClaimResult.WAITING`) and is acknowledged; the dead-letter handler leaves a parked session alone
  (`AbandonResult.WAITING`).
  Accepted, as on `create`: a request that dies between `resume`'s `answer` write and its send leaves the
  session `queued` with no message until its TTL; the app's fresh five-minute cap then shows `stalled` and
  Retry starts again. The note limit (`MAX_NOTE_CHARS`) is in code points, the unit the app clips by.
- **The 90 s are working time.** No attempt exists while the household thinks, so no clock runs; the
  working seconds spent before the question ride the graph state (`working_seconds`) and the resuming
  attempt's budget starts that much spent (`RunBudget.carry`). A household that never answers leaves the
  session parked until the 24 h TTL expires the item. Checkpoints live twice the session TTL
  (`agent.checkpoint.checkpoint_ttl_seconds`), because nothing rewrites a parked run's checkpoint and a
  late answer's resume must still find the interrupt; the app polls again only after it
  sends its answer, so its five-minute `stalled` cap never counts the wait.
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

When a route is only sometimes paid, charge through `charge_ai_request(user_sub, settings)` from a
route-level dependency instead of picking another limiter — `profile/router.py`'s
`enforce_interview_rate_limit` skips the interview's first turn, which calls no model at all. There is
still one limit and one implementation.

### Free text a model will read goes through the screen

Any user-typed free text that a model will read — interview answers now, feedback and swap notes later — is
first passed to `glean.screening.screen(text, decision_client=...)`. It asks the pinned decision model one
`noul` question and returns the text only at `SCREEN_BAR` (0.9); below the bar, or on a timeout or a broken
answer, it returns nothing and the caller drops the text and tells the user ("Couldn't use that answer").
Fail-closed is the point: the uncertain outcome is not to use the text.

Pass text to the model as data in a typed field, never as instructions, and re-screen what a stateless
endpoint is asked to use again rather than trusting a transcript it did not screen itself — including any
draft profile the client hands back, whose free text is not sent to the model at all. Screens are cached per
container (bounded, ten-minute TTL, an outage is never cached) and a request's screens run concurrently under
an 8 s budget: at most seven decision calls and one model turn per request, ~18 s against the 30 s cap.

A finished `HouseholdProfile` is **not** screened as a whole: its free text is the client's own data,
merged back after the model call. The interview only guarantees that the text it sent the model was
screened. Any route that hands a profile to a model later — sessions, eligibility, the scorer, feedback
notes — screens that free text first or sends only the enum fields (`spice_tolerance`, `protein_targets`).
Planning does both (`meal_plan.household.screen_profile`): the enum fields always reach `household_profile`, and its
free text text by text (each list entry, habits, household, each note), each screened on its own through
`screening.screen_many` and dropped alone if it fails.

The 0.9 bar is not yet calibrated on real traffic. The question and bar are pinned by
`tests/profile/test_screening.py`; measure a change with
`uv run python -m scripts.eval_screening --out /tmp/screening-eval.json` against the 80-note synthetic set in
`tests/fixtures/screening_calibration.json` (paid, 80 decision calls).

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
