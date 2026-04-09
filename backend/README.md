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

1. Start the backend on all interfaces:

   ```bash
   uv run fastapi dev src/glean/main.py --host 0.0.0.0
   ```

2. Find your Mac's LAN IP:

   ```bash
   ipconfig getifaddr en0   # e.g. 192.168.1.42
   ```

3. Start Expo with the API URL override:

   ```bash
   EXPO_PUBLIC_API_URL=http://192.168.1.42:8000 npx expo start
   ```

4. Scan the QR code with Expo Go, or press **a** if connected via USB/ADB.

Make sure your phone and Mac are on the same Wi-Fi network.
