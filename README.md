# Glean

This branch contains Glean's proposed local-first Flutter replacement with a
stateless FastAPI backend. **Production is still the Expo app**; the Flutter
port has not landed or passed native/visual cutover verification. The app
stores user state on device with SQLite (`drift`), while the backend handles
AI-assisted receipt parsing, recipe import, meal-plan generation, auth
validation, and rate limiting.

## Project Layout

```text
backend/   FastAPI backend, managed with uv, deployed with Mangum on AWS Lambda
app/       Flutter app (iOS + Android), managed with the Flutter/Dart SDK
Makefile   Common setup, test, lint, and dev-server commands
```

## Prerequisites

- Docker Desktop
- Python 3.14+
- uv
- Flutter SDK (see `app/pubspec.yaml`'s `environment.sdk` for the Dart
  constraint this app is built against)
- Xcode + an iOS Simulator, and/or Android Studio + an Android emulator, for
  running the app on a device — see `app/README.md` for exact setup. Building
  and running the app needs a Mac (or a Mac for iOS, plus a machine with the
  Android SDK for Android); linting and testing need neither.

## Setup

Install backend and app dependencies:

```bash
make setup
```

Create backend environment variables:

```bash
cp backend/.env.example backend/.env
```

Fill in real API keys in `backend/.env` when using endpoints that call external services.

## Run Locally

Start the backend without Docker:

```bash
make start-backend
```

Start the backend with the production Docker image:

```bash
make start-backend-docker
```

Run the app on a simulator/emulator (see `app/README.md` for where
`COGNITO_DOMAIN`/`COGNITO_CLIENT_ID` come from, and for the Android/iOS setup
these need):

```bash
make start-ios     COGNITO_DOMAIN=... COGNITO_CLIENT_ID=...   # macOS only
make start-android COGNITO_DOMAIN=... COGNITO_CLIENT_ID=...   # needs a running emulator
```

The default API URL is `http://localhost:8000` for iOS Simulator and
`http://10.0.2.2:8000` for the Android emulator (its alias for the host's
localhost) — both point at the plain `make start-backend` server above with
no extra flags.

## Test on a Phone Over Wi-Fi

A physical phone cannot reach your laptop's `localhost`. Start the
Dockerized backend, find your laptop's Wi-Fi IP, then pass it through
`API_HOST`.

```bash
make start-backend-docker
ipconfig getifaddr en0
make start-android API_HOST=192.168.4.51 COGNITO_DOMAIN=... COGNITO_CLIENT_ID=...
```

Your phone and laptop must be on the same Wi-Fi network. If your IP changes,
rerun `ipconfig getifaddr en0` and restart with the new `API_HOST`.

## Useful Commands

```bash
make test          # backend and app tests (unit + widget; not integration_test — see app/README.md)
make lint          # backend and app lint/format checks
make pre-commit    # all configured pre-commit hooks
make help          # list Make targets
```
