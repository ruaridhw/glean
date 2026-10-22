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

The corpus scripts (`import_recipe_corpus.py`, `compute_dietary_decisions.py`, `build_recipe_index.py`) take
the same `--table` switch; `--bucket` / `--cache-dir` says where the blobs (or, with `--table`, the projection)
live.

Every change is published to the projection with an S3 conditional write, so two Lambdas importing at once
cannot drop each other's recipe. If a publish fails outright the store raises and logs the repair command
(`scripts/build_recipe_index.py --table … --bucket …`); the table keeps the change. The migration's last step
is that same full rebuild — a scan of the table, not a document built from the blobs — so a recipe imported
while it ran is kept; add a few minutes for the scan to the migration's estimate.

**Rolling back to `blobs` is a snapshot rollback.** Nothing in dynamo mode writes the blobs or the dietary
JSONL, so recipes imported and answers computed while `RECIPE_STORE=dynamo` are not in them. Re-import those
recipes and re-run `compute_dietary_decisions.py` before flipping back if they must survive; the migration
prints the same warning.

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

This builds the production backend image and starts FastAPI on `http://localhost:8000`, bound to all interfaces inside the container. The image installs only runtime dependencies, runs as a non-root user, and starts with `uvicorn`. The Compose service loads `backend/.env` when present and sets `ENVIRONMENT=dev` for local auth bypass.

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
