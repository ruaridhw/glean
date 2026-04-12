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

- **AI processing:** Receipt OCR (Textract or vision model), ingredient normalisation, recipe import via URL, meal suggestions — all LLM calls go through OpenRouter via LangChain (default model: `anthropic/claude-sonnet-4-6`)
- **Auth:** Cognito JWT validation on every request (`verify_cognito_token` in `dependencies.py`)
- **Rate limiting:** Per-user token bucket via slowapi (20 AI requests/hour)
- **S3 buffering:** Receipt images pass through S3 before Textract; dev DB exports also use S3
- **Recipe data:** External recipe-api.com integration with local `/tmp` caching (24h search TTL, 7d detail TTL)

### Module layout

```
src/glean/
├── main.py           # FastAPI app + Mangum handler + rate limiter setup
├── config.py         # Pydantic BaseSettings (reads from .env / Secrets Manager in Lambda)
├── dependencies.py   # verify_cognito_token — JWKS fetch + jwt.decode
├── llm.py            # OpenRouter LangChain client; Feature enum; model factory helpers
├── observability.py  # Logger + Tracer (aws-lambda-powertools)
├── health/router.py  # GET /health
├── dev/router.py     # POST /dev/export-db → S3
├── receipts/         # POST /receipts/scan (image upload → Textract or vision OCR)
│                     # POST /receipts/describe (text → normalised ingredients)
├── recipe_api/       # External recipe-api.com HTTP client with /tmp caching
├── recipes/          # GET /recipes/search, GET /recipes/{id}
│                     # POST /recipes/import-url (LLM-parsed web scrape)
└── suggestions/      # POST /suggestions — LLM meal planning suggestions
```

### Auth

`verify_cognito_token(request, credentials)` is a FastAPI dependency:
- Fetches JWKS from Cognito, cached with `lru_cache`
- On unknown `kid`: cache-bust and retry once
- Validates RS256 sig, audience, issuer, expiry
- Sets `request.state.user_sub` for rate limiting key

### Receipt OCR modes

Controlled by `receipt_ocr_mode` in config (env var `RECEIPT_OCR_MODE`):
- `"textract"` (default): upload image to S3 → AWS Textract expense analysis → LLM normalisation via OpenRouter
- `"vision"`: send image directly to a vision-capable OpenRouter model (configured by `receipt_vision_model`, default `anthropic/claude-sonnet-4-6`)

### Testing

Tests override the auth dependency:
```python
app.dependency_overrides[verify_cognito_token] = lambda: "test-user-sub"
```

Conftest provides `client` (with override) and `auth_headers` fixtures.
