# Glean Backend

Stateless FastAPI backend deployed as AWS Lambda (Mangum adapter). All app state lives on-device (SQLite via expo-sqlite). The backend handles AI processing (receipt OCR, recipe import, meal-plan generation), Cognito auth, and rate limiting.

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

When `ENVIRONMENT=dev` (set in `.env`), Cognito JWT validation is bypassed and all requests authenticate as `local-dev-user`. This lets you hit the API without a real Cognito token.

### LangSmith Tracing

LangChain calls can be traced to LangSmith by setting these values in `.env`:

```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=glean
LANGCHAIN_CALLBACKS_BACKGROUND=false
```

Deployed Lambda tracing is off by default. Enable it by deploying with
`LangSmithTracing="true"` and storing the API key in Secrets Manager at
`glean/{env}/langsmith-api-key`. The backend reads that secret at runtime and
sets `LANGSMITH_API_KEY` in-process before LangChain calls are created.

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

This branch's proposed replacement client is the Flutter app at `app/`.
Production remains Expo; no Flutter cutover has happened. The planned
big-bang replacement is described in the root `FLUTTER_MIGRATION.md`. Full setup and run instructions live in
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
