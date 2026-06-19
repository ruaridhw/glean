# Glean Backend

Stateless FastAPI backend deployed as AWS Lambda (Mangum adapter). All app state lives on-device (SQLite via expo-sqlite). The backend handles AI processing (receipt OCR, recipe import, meal suggestions), Cognito auth, and rate limiting.

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
uv run black src/ tests/
```

## Running the Mobile App Locally

### Prerequisites

- Node.js 18+
- [Expo CLI](https://docs.expo.dev/get-started/set-up-your-environment/) (`npx expo`)
- **iOS Simulator:** Xcode (macOS only)
- **Android Emulator:** Android Studio with an AVD configured

### Setup

```bash
cd mobile
npm install
```

### Emulator (iOS Simulator / Android Emulator)

Start the backend first (see above), then:

```bash
npx expo start
```

Press **i** for iOS Simulator or **a** for Android Emulator. Both can reach the backend at `http://localhost:8000` (the default), so no extra config is needed.

### Physical Android Device on Local Network

A physical device can't reach `localhost`, so you need to bind the backend to your Mac's LAN IP and tell the mobile app where to find it.

1. Start the Dockerized backend from the repo root:

   ```bash
   make start-backend-docker
   ```

2. Find your Mac's LAN IP:

   ```bash
   ipconfig getifaddr en0   # e.g. 192.168.1.42
   ```

3. Start Expo with the API URL override:

   ```bash
   make start-mobile API_HOST=192.168.1.42
   ```

4. Scan the QR code with Expo Go, or press **a** if connected via USB/ADB.

Make sure your phone and Mac are on the same Wi-Fi network.
