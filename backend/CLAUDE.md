# CLAUDE.md

This file provides guidance to Claude Code when working in the Glean backend.

## Preferred tools

- Use `rg` for fast text and file search
- Use `rtk` when reading large files, listing directories, or running noisy commands

## Commands

```bash
uv run pytest                          # all tests with coverage
uv run pytest tests/test_health.py -v  # single file
uv run pytest -k "test_name"           # single test by name
uv run ruff check src/ tests/ --fix    # lint (auto-fix where possible)
uv run black src/ tests/               # formatting
uv run ty check src/                   # type checking
pre-commit run                         # lint + format (run after staging changes)
```

## Architecture

Stateless FastAPI backend deployed as AWS Lambda (Mangum adapter). All app state lives on-device (SQLite via expo-sqlite). The backend is responsible for:

- **AI processing:** Receipt OCR (Textract), pantry item extraction, recipe import, meal suggestions (Claude API)
- **Auth:** Cognito JWT validation on every request (`verify_cognito_token` in `dependencies.py`)
- **Rate limiting:** Per-user token bucket via slowapi (20 AI requests/hour)
- **S3 buffering:** Receipt images pass through S3 before Textract; dev DB exports also use S3

### Module layout

```
src/glean/
├── main.py           # FastAPI app + Mangum handler + rate limiter setup
├── config.py         # Pydantic BaseSettings (reads from .env / Lambda env)
├── dependencies.py   # verify_cognito_token — JWKS fetch + jwt.decode
├── observability.py  # Logger + Tracer (aws-lambda-powertools)
├── health/router.py  # GET /health
└── dev/router.py     # POST /dev/export-db → S3
```

### Auth

`verify_cognito_token(request, credentials)` is a FastAPI dependency:
- Fetches JWKS from Cognito, cached with `lru_cache`
- On unknown `kid`: cache-bust and retry once
- Validates RS256 sig, audience, issuer, expiry
- Sets `request.state.user_sub` for rate limiting key

### Testing

Tests override the auth dependency:
```python
app.dependency_overrides[verify_cognito_token] = lambda: "test-user-sub"
```

Conftest provides `client` (with override) and `auth_headers` fixtures.
