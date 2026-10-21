# Glean

Glean turns the food you already have into dinners you can actually make.
Scan a receipt or describe what is in the kitchen to stock your pantry, plan
your week around those ingredients, then shop only for the gaps.

It is a local-first Flutter app (`app/`) with a stateless FastAPI backend
(`backend/`). Pantry, recipes, meal plans and shopping state live on the
device in SQLite (`drift`); the backend handles AI-assisted receipt parsing,
recipe import, meal-plan generation, auth validation and rate limiting, and
keeps no user data. The owner runs the Android app day to day, with
release-signed builds delivered through Codemagic to Firebase App
Distribution (see `docs/ANDROID_TEST_DISTRIBUTION.md`). iOS builds and runs
locally but is not distributed yet.

## What It Does

- **Stock your pantry fast:** turn a receipt scan or a plain-language
  description of your food into reviewable pantry items.
- **Know what you have:** track quantities, categories and expiry dates.
- **Find meals worth cooking:** search or import recipes and save the ones
  worth cooking again.
- **Plan around your kitchen:** build a weekly dinner plan from saved recipes
  and what is already in the pantry.
- **Shop with purpose:** missing ingredients become the shopping list, and
  checking them off moves them into the pantry.

One rule runs through all of it: review before saving. AI can propose pantry
or shopping items, but nothing changes on the device until you confirm it.

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

For AWS CLI access (deploys, `infra/` scripts), keep the IAM user's access key
in a 1Password item with fields `access key id` and `secret access key`, set
`OP_AWS_ITEM=op://<vault>/<item>` in `.env.local`, and run:

```bash
make aws-profile   # then: export AWS_PROFILE=glean
```

The `glean` profile reads the key through `op` on every call, so it is never
written to `~/.aws/credentials`. On a machine without 1Password signed in, also
set `OP_SSH_HOST` to a Mac with the 1Password app: `op` then runs there over
SSH and asks for Touch ID on the Mac when it is locked.

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
