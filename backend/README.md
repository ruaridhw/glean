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

A run that dies mid-graph is recoverable: the worker that owns a session renews its lease as the graph
moves, and the queue hands the message out again about two minutes after a crash, when a new attempt
takes the lease over and resumes from the LangGraph checkpoint. That is well inside the app's
five-minute cap, which is why the app shows `stalled` only when the network, not the worker, gave up.

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
