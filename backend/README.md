# Glean Backend

Stateless FastAPI backend deployed as AWS Lambda (Mangum adapter). All app state lives on-device, in the Flutter app's SQLite database (Drift). The backend handles AI processing (receipt OCR, recipe import, meal-plan generation), Cognito auth, and a per-user rate limit on the AI routes (`RATE_LIMIT_PER_HOUR`, default 20 in code and raised to 60 in deployments through the `RateLimitPerHour` template parameter; in-memory, so per Lambda container rather than global).

## Local Development

### Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)

### Setup

```bash
cp .env.example .env   # fill in real API keys
uv sync --dev
```

### Running

```bash
uv run fastapi dev src/glean/main.py
```

The server starts at `http://localhost:8000` with hot reload.

When `ENVIRONMENT=dev` (set in `.env`) and the server runs locally, Cognito JWT validation is bypassed and all requests authenticate as `local-dev-user`. This lets you hit the API without a real Cognito token. A deployed function always verifies tokens, whatever its `ENVIRONMENT`.

### Recipe corpus store

The recipe corpus (bodies, search index, stored dietary decisions) sits behind `RecipeCorpusStore`, and
`RECIPE_STORE` picks the store the process opens:

- `blobs` (default) — the S3 `corpus/` prefix, or `.cache/glean_recipe_cache/corpus` locally.
- `dynamo` — the `glean-recipes-<env>` table (`RECIPES_TABLE`) plus a gzipped S3 projection at
  `projection/recipes-v1.json.gz` in the recipe-cache bucket, which search and meal planning read instead of
  scanning the table. Lambdas trust the projection for 5 minutes.

Both behave identically; nothing else in the backend changes with the setting. The owner-run migration that
fills the table is idempotent, resumable and paced to the table's 5 WCU, and refuses a `prod` table without
`--i-am-the-owner`:

```bash
uv run python scripts/migrate_recipe_corpus.py --table glean-recipes-dev --bucket glean-recipe-cache-dev-<account> --dry-run
uv run python scripts/build_recipe_index.py --table glean-recipes-dev --bucket glean-recipe-cache-dev-<account>  # rebuild the projection
```

The corpus scripts (`import_recipe_corpus.py`, `enrich_corpus.py`, `build_recipe_index.py`) take the same
`--table` switch; `--bucket` / `--local` says where the blobs (or, with `--table`, the projection) live.

### Recipe enrichment

Everything planning needs to know about a recipe beyond its own text — whether it breaks a dietary flag,
its main protein, carb, dish type, cuisine and whole-food level, and how long it really takes to cook — is
one decision-model answer per question, stored as its own item beside the recipe (ADR 0025).
`recipes/enrichment/` is the pipeline: enrichers declare their questions and confidence bars, and one
runner asks every recipe only what is missing or stale, in a single request per recipe. The three families
are `dietary` (six `noul` questions, ADR 0011's thresholds unchanged), `attributes` (four `choice` questions
and one `score`) and `active-time` (one `score`, answered as one of five minute buckets).

**Confidence bars.** No answer is accepted because it is the top option. A dietary answer is its
probability, and its threshold decides exclusions when planning reads it. An attribute's answer stores the
value it accepted, and only at or above its bar; below the bar it stores `unsure`, which is a real answer:
the recipe is not re-asked, and the scorer gives it no variety credit and no penalty. Attribute and
active-time bars start at 0.8, may be tuned per attribute from a labelled sample, and may never be declared
below 0.7 — a declaration below the floor is an error, not a quiet weakening. Active time below its bar
falls back to total time in the household's time filter, as the filter did before V5.

**The stated time is prep time.** Q3 found the field the corpus calls an active time is really schema.org
`prepTime` (35% of recipes, median 10 minutes against a 35-minute median total), so it is now
`StoredRecipe.prep_time_mins` — old bodies still carry it as `active_time_mins` and read unchanged — and
active time is estimated for every recipe instead. The public recipe response keeps its `active_time_mins`
field for the app and still carries the stated time until the app is served the enriched one.

**The projection carries the attributes.** Every recipe's entry in the projection has all six, `unsure`
where nothing has been enriched, derived from the recipe's current answers on every rebuild and every answer
write (`recipes/enrichment/projection_attributes.py`). Planning reads the entry, and the household's time
cap compares the active-time bucket's **upper** bound — a 60-minute traybake with 10 minutes of work fits a
20-minute cap, and a `60+` bucket never fits any cap.

The model is a paid external service, so this is a producer you run, never something a request triggers, and
`make enrich-corpus` only ever touches the local corpus. It needs `OPENROUTER_API_KEY` in the environment
(`--dry-run` needs no key and makes no calls):

```bash
make enrich-corpus ENRICH_ARGS=--dry-run   # what would be asked, from .cache/glean_recipe_cache
make enrich-corpus                         # fill the local corpus; exit 1 unless coverage is 100%

# anywhere, with an explicit source
uv run python scripts/enrich_corpus.py --local .cache/glean_recipe_cache --workers 8
```

`make enrich-corpus` always passes `--local-only`, which makes the CLI refuse a `--table`, `--bucket` or
`--i-am-the-owner` outright — not just the prod ones, and not even for a dry run — so the dev target cannot
be walked towards a remote store. The CLI also rejects abbreviated flags, so `--tab` is not `--table`.

The owner runs it against prod by hand after a corpus import, a question rewording or a model bump. The
script refuses a table or bucket whose name contains `prod` unless `--i-am-the-owner` is passed, and exits
non-zero unless every recipe has a current answer to every question — an unasked question excludes the
recipe, so full coverage is the deploy gate:

```bash
uv run python scripts/enrich_corpus.py --table glean-recipes-prod \
    --bucket glean-recipe-cache-prod-<account> --i-am-the-owner
```

The run prints a per-question coverage table (current / stale / missing / failed / unsure, requests made,
how many current answers are labelled and how many are stored `unsure`, and how many recipes state a prep
time), writes answers in checkpoints so an interrupted run resumes where it stopped, and rebuilds the
projection once at the end. `--enricher dietary` (or `attributes`, or `active-time`) narrows it.

The number of requests is the corpus times whatever is stale, not the corpus times the questions: a fresh
migration answered under the current wording asks for nothing, an imported or edited recipe costs one
request, a reworded question costs one request per recipe, and a model bump costs one request per recipe
for every question. A checkpoint writes only the answers that run has produced, not the whole run again,
and the final rebuild is a consistent scan of the table rather than another pay-per-call run — which is why
it happens once at the end and not per recipe.

Answers are written to the table as the run goes, so **a run that dies, or whose final projection rebuild
fails, has still paid for and kept everything it finished**: the next run reads the answers out of the
store and asks only for the rest. If a rebuild failed, the projection planning reads is stale until it is
repaired — `scripts/build_recipe_index.py --table glean-recipes-<env> --bucket <recipe-cache-bucket>` — and
that repair needs no new model call.

#### Measuring the attributes and choosing their bars

The bars ship at 0.8 because that is G1's starting point; they are chosen from a labelled sample, the same
discipline as the dietary audit. The sample is a directory of exported recipe bodies and an independent
labeller's labels, both **outside this repo** (recipe text is third-party, ADR 0016). The tool runs the
enrichers over the sample through the usual runner at G1's floor (0.7) so every answer keeps its top option,
then replays every bar from 0.7 to 0.95 and reports, per attribute, the accuracy of the answers each bar
accepts, its coverage, a confusion table, and the bar that earns the best accuracy:

```bash
# adopt the chosen bar by editing DEFAULT_ATTRIBUTE_BAR or a per-attribute entry in AttributeEnricher.bars
make check-attributes SAMPLE=<sample-dir>          # paid: needs OPENROUTER_API_KEY

# the same two steps by hand; compare makes no model calls and needs no key
uv run python scripts/check_recipe_attributes.py enrich --sample <sample-dir>
uv run python scripts/check_recipe_attributes.py compare --sample <sample-dir>
```

Answers land at `<sample-dir>/../v5-check/answers.json` and labels are read from
`<sample-dir>/../v5-check/opus-labels.json`, so a sample exported as `v5-sample/` keeps its results in
`v5-check/` beside it. The labels file maps each recipe id to its six attributes (`active_time_bucket` for
the bucket), optionally with a per-attribute `confidence` and a `note`; an `unsure` label carries no truth
and a label that names no G1 value is reported rather than guessed.

Every change is published to the projection with an S3 conditional write, so two Lambdas importing at once
cannot drop each other's recipe. If a publish fails outright the store raises and logs the repair command
(`scripts/build_recipe_index.py --table … --bucket …`); the table keeps the change. The migration's last step
is that same full rebuild — a scan of the table, not a document built from the blobs — so a recipe imported
while it ran is kept; add a few minutes for the scan to the migration's estimate.

**Rolling back to `blobs` is a snapshot rollback.** Nothing in dynamo mode writes the blobs or the dietary
JSONL, so recipes imported and answers computed while `RECIPE_STORE=dynamo` are not in them. Re-import those
recipes and re-run `scripts/enrich_corpus.py` before flipping back if they must survive; the migration prints
the same warning.

### LangSmith Tracing

LangChain calls can be traced to LangSmith by setting these values in `.env`:

```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=glean
LANGCHAIN_CALLBACKS_BACKGROUND=false
```

Deployed Lambda tracing is off by default; prod turns it on via
`LangSmithTracing="true"` in `samconfig.toml`. Store the API key in Secrets Manager at
`glean/{env}/langsmith-api-key`. The backend reads that secret at runtime and
sets `LANGSMITH_API_KEY` in-process before LangChain calls are created.

### Deploying to prod

**If the change touches `infra/bootstrap.yaml`, re-apply the bootstrap stack first.** The deploy role's
permissions live there, and CloudFormation creates the tables, queues and Lambdas with that role's
credentials, so a release that adds a resource fails until the role can manage it:

```bash
ALERT_EMAIL=<the same address as last time> infra/bootstrap.sh
```

That re-applies `glean-bootstrap` (the GitHub OIDC provider, `GleanDeployPolicyProd` and the DynamoDB budget).
Pass the same `AlertEmail` as before, or the budget alert gains a second subscriber.

Prod is deployed from CI on every push to `main` that touches `backend/`. For a manual deploy:

```bash
make deploy-prod                  # stops unless the tree is clean and HEAD is on a freshly fetched origin/main or upstream branch
ALLOW_DIRTY=1 make deploy-prod    # hotfix: deploys anyway, stamped <sha>-dirty and logged
```

Both paths run `backend/scripts/deploy_prod.py`, which deploys `samconfig.toml`'s `[prod]` parameters (the single
source of deploy parameters), stamps the commit on the stack (tag `commit`) and the Lambda (`GIT_SHA`), then checks
the live stack parameters and every parameter-fed Lambda environment variable (including `LANGSMITH_TRACING` and `LANGSMITH_ENDPOINT`) against `samconfig.toml` and reports any mismatch. `GET /health`
returns that stamp as `commit`. Manual deploys are logged to `~/.glean/deploy.log` when dirty (`GLEAN_DEPLOY_LOG`
overrides the path).

The Google OAuth client id and secret are never passed as parameters: the template resolves them from Secrets
Manager (`glean/{env}/google-oauth-client-id` and `glean/{env}/google-oauth-client-secret`), so the deploying
identity needs `secretsmanager:GetSecretValue` on them.

### Running with Docker

From the repo root:

```bash
make start-backend-docker
```

This brings up the whole backend: FastAPI on `http://localhost:8000` and the async stack behind
`POST /meal-plan/sessions`.

| Service | What it is |
| --- | --- |
| `backend` | The production image, serving the API. `ENVIRONMENT=dev` bypasses Cognito and loads `backend/.env` when present. |
| `worker` | The same image, running `glean.dev.worker_loop`: a queue consumer over ElasticMQ with the model stubbed (`AGENT_LLM_STUB=1`), so a run costs nothing. |
| `dynamodb-local` | `amazon/dynamodb-local`, in memory. |
| `elasticmq` | An SQS stand-in for the session queue. |
| `bootstrap` | Builds the tables, the queue and its dead-letter queue **from `template.yaml`**, then seeds four sample recipes into the shared corpus. Runs once, before the API and worker. |

A whole session, end to end:

```bash
curl -s localhost:8000/meal-plan/sessions -H 'content-type: application/json' -d '{
  "source": "corpus", "pantry": [{"id": 1, "name": "coriander", "quantity": 50, "unit": "g", "urgency_score": 150}],
  "purchase_tolerance": 0.3, "meals_per_week": 3, "dietary_flags": [], "max_active_time_mins": null
}' | jq -r .session_id | xargs -I{} curl -s localhost:8000/meal-plan/sessions/{} | jq
```

Set `AGENT_LLM_STUB=0` on the worker to use the real model instead, which needs `OPENROUTER_API_KEY`
in `backend/.env`.

A run that dies mid-graph is recoverable: the attempt that owns a session takes a lease at claim and
never extends it, measured against its own invocation deadline rather than a constant, and the queue
(150 s visibility) hands the message out again about 2.5 minutes after a crash. The new attempt takes
the lapsed lease over and resumes from the LangGraph checkpoint. That is inside the app's five-minute
cap, which is why the app shows `stalled` only when the network, not the worker, gave up. A delivery
that finds another attempt still running fails rather than returning, so the message it was holding is
never deleted unfinished — on the dead-letter queue too, where the handler raises while a live run owns
the session and retries every 60 s until it can fail it.

Only the containers can reach `dynamodb-local` and `elasticmq`. `make start-backend` runs on the
host, so it cannot enqueue: set `AGENT_RUNNER=inline` in `backend/.env` to run sessions in the
request instead of on a worker. That mode is also what unit tests and evals use, and it keeps
sessions in memory and the checkpointer in process.

### Testing

```bash
uv run pytest                          # all tests with coverage
uv run pytest tests/test_health.py -v  # single file
uv run pytest -k "test_name"           # by name
```

### Linting & Formatting

```bash
pre-commit run          # after staging changes
uv run ruff check src/ tests/ --fix
uv run ruff format src/ tests/
```

## Running the App Locally

The client is the Flutter app at `app/`. Full setup and run instructions live in
`app/README.md` and the root `README.md`; the short version, from the repo
root, once the backend above is running:

```bash
make start-ios     COGNITO_DOMAIN=... COGNITO_CLIENT_ID=...   # macOS only
make start-android COGNITO_DOMAIN=... COGNITO_CLIENT_ID=...   # needs a running emulator
```

Both default to pointing at the plain `make start-backend` server above
(`http://localhost:8000` for iOS Simulator, `http://10.0.2.2:8000` — the
emulator's alias for the host's localhost — for Android). `COGNITO_DOMAIN`/
`COGNITO_CLIENT_ID` come from the deployed backend stack's SAM outputs (or
your own Cognito setup for local dev) — see `app/README.md`.

### Physical Device on Local Network

A physical phone can't reach your laptop's `localhost`. Start the
Dockerized backend, find your laptop's Wi-Fi IP, then pass it through
`API_HOST`:

```bash
make start-backend-docker
ipconfig getifaddr en0   # e.g. 192.168.1.42
make start-android API_HOST=192.168.1.42 COGNITO_DOMAIN=... COGNITO_CLIENT_ID=...
```

Your phone and laptop must be on the same Wi-Fi network. If your IP changes,
rerun `ipconfig getifaddr en0` and restart with the new `API_HOST`.
