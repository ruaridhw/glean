# Glean (Flutter)

The Glean mobile app: Flutter, targeting iOS and Android. A web target is
also committed, but only as a local dev loop for eyeballing UI changes in
Chrome — see [Web dev loop](#web-dev-loop) below; nothing ships to the web.
Replaces the Expo/React Native app that used to live in this repository
(see git history).

## Setup

```bash
flutter pub get
```

Or from the repo root: `make setup-app`.

## Everyday commands

```bash
flutter analyze                                                            # must print "No issues found!"
flutter test                                                                # unit + widget, nothing skipped
dart format --output=none --set-exit-if-changed lib test integration_test  # check only; drop --output=none --set-exit-if-changed to write fixes
dart run build_runner build --delete-conflicting-outputs                   # after touching a drift table
```

All four run on any machine with the Flutter SDK — no Android SDK, Java, or
Xcode needed. `NativeDatabase.memory()` (the drift test fixture) also works
headless as long as a system `libsqlite3` is present.

Repo-root equivalents: `make test-app`, `make lint-app`, `make setup-app`.

## Running the app

Needs three `--dart-define` values every entrypoint requires
(`lib/bootstrap.dart`'s `GleanConfig.assertComplete()` fails loudly at
startup otherwise): `API_BASE_URL`, `COGNITO_DOMAIN`, `COGNITO_CLIENT_ID`.
`COGNITO_DOMAIN`/`COGNITO_CLIENT_ID` come from the deployed backend stack
(SAM output `CognitoDomain` / the User Pool Client id — see
`../backend/template.yaml`) or your own Cognito setup for local dev.

```bash
# iOS Simulator
open -a Simulator
flutter run \
  --dart-define=API_BASE_URL=http://localhost:8000 \
  --dart-define=COGNITO_DOMAIN=<from backend stack output> \
  --dart-define=COGNITO_CLIENT_ID=<from backend stack output>

# Android emulator (already running)
flutter run \
  --dart-define=API_BASE_URL=http://10.0.2.2:8000 \
  --dart-define=COGNITO_DOMAIN=<from backend stack output> \
  --dart-define=COGNITO_CLIENT_ID=<from backend stack output>
```

Repo-root equivalents: `make start-ios COGNITO_DOMAIN=... COGNITO_CLIENT_ID=...`
/ `make start-android COGNITO_DOMAIN=... COGNITO_CLIENT_ID=...`
(`API_HOST=192.168.x.x` for a physical device over Wi-Fi against
`make start-backend-docker`).

**None of this — `flutter build`, `flutter run`, the emulator/simulator
itself — runs on a plain Linux box with no Android SDK/Java/Xcode.** That's
expected; it's a Mac (for iOS) / a machine with the Android SDK (for
Android) concern. `flutter analyze` and `flutter test` above are the
exception and were verified on exactly such a box.

## Integration tests

The one `integration_test` suite (`integration_test/app_test.dart`) ports
the Expo app's `e2e/smoke.yaml` (see git history) intent: launch, all five
tabs visible, navigate each, camera-permission handling on the Scan screen,
and add an item via manual entry (dead code in the RN app — reachable here
from the `+` sheet).
It runs against `lib/main_e2e.dart`, never `lib/main.dart` — that's where the
e2e auth bypass lives, and it cannot compile into `lib/main.dart`'s import
graph at all (`test/standards/house_rules_test.dart` enforces this; see
`AGENTS.md`). This file only *compiles* in CI's push-triggered job
(`flutter analyze` covers `integration_test/` too) — actually running it
needs a booted simulator/emulator, which is a `workflow_dispatch`-gated CI
job (`.github/workflows/flutter-integration.yml`) or a local Mac.

### Running it locally

Both platforms are runnable from **one Mac** — real Apple Silicon isn't
subject to the CI nested-virtualization limitation below.

```bash
# iOS Simulator
open -a Simulator
xcrun simctl list devices available          # find a device id (UDID)
flutter test integration_test/app_test.dart \
  -d <UDID> \
  --dart-define=API_BASE_URL=http://127.0.0.1:8000 \
  --dart-define=COGNITO_DOMAIN=<placeholder-is-fine> \
  --dart-define=COGNITO_CLIENT_ID=<placeholder-is-fine>

# Android emulator (already booted, e.g. via Android Studio's Device Manager)
flutter test integration_test/app_test.dart \
  -d emulator-5554 \
  --dart-define=API_BASE_URL=http://10.0.2.2:8000 \
  --dart-define=COGNITO_DOMAIN=<placeholder-is-fine> \
  --dart-define=COGNITO_CLIENT_ID=<placeholder-is-fine>
```

`COGNITO_DOMAIN`/`COGNITO_CLIENT_ID` can be any non-empty placeholder here:
`lib/main_e2e.dart` seeds auth from `bypassAuthSnapshot()` and never calls
its `CognitoAuthClient`, so these values are only read by the startup
non-empty/loopback assertions, never dialled for real. Repo-root
equivalent: `make test-e2e COGNITO_DOMAIN=... COGNITO_CLIENT_ID=...`.

### Running it in CI

`.github/workflows/flutter-integration.yml`, `workflow_dispatch`-gated (never
on push): two separate jobs, iOS Simulator on a `macos-latest` runner and
Android emulator on `ubuntu-latest` with KVM. **Deliberately not one
combined macOS job** — GitHub-hosted macOS runners cannot run the Android
emulator with hardware acceleration (nested virtualization is unsupported on
the current arm64 image, and a request to lift this was closed "not
planned"; see the workflow file's header comment). Trigger it from the Actions tab or `gh workflow run flutter-integration.yml`.

## CI

- **`.github/workflows/flutter-ci.yml`** — the only job that runs
  automatically (on push/PR touching `app/**`, `codemagic.yaml` or
  `.github/workflows/**`): format check, `flutter analyze`, `flutter test`,
  and a guard that no release path references `main_e2e.dart`. No device
  involved.
- **`.github/workflows/flutter-integration.yml`** — `workflow_dispatch` only;
  see [Integration tests](#integration-tests) above.

## Release (Fastlane)

**Before a release build, work through
[`../docs/pre-release-checklist.md`](../docs/pre-release-checklist.md)** — airplane-mode error
states, both `integration_test` platform runs, and (for a first submission to either store)
signing/build-number gotchas no automated test catches.

**Android** test builds come from Codemagic's `android-test-distribution`
workflow (`../codemagic.yaml`), started by hand and distributed through
Firebase App Distribution. See
[`../docs/ANDROID_TEST_DISTRIBUTION.md`](../docs/ANDROID_TEST_DISTRIBUTION.md).
Its first step, `scripts/validate_release_config.py`, rejects missing or
malformed configuration before any build work.

**iOS** uses `ios/fastlane/` (TestFlight), **run from a Mac, never from CI**.
No `match`: one Mac, one signer, so Xcode's own "Automatically manage
signing" (already on) is adequate; adopt `match` only once a second
signer/machine needs the same certificates.

The lane requires non-secret production configuration and validates it before
querying the store or building. Supply your deployed public values; localhost,
HTTP and missing configuration are rejected:

```bash
export API_BASE_URL=https://<production-api-host>
export COGNITO_DOMAIN=<production-cognito-host>   # bare hostname, no https://
export COGNITO_CLIENT_ID=<public-app-client-id>

# iOS — needs an App Store Connect API key (see ios/fastlane/Fastfile's header)
cd ios && ASC_KEY_ID=... ASC_ISSUER_ID=... ASC_KEY_CONTENT=... \
  bundle exec fastlane beta
```

The validator's tests (`python3 -m unittest discover -s scripts -p 'test_*.py'`)
run in CI without signing or uploading.

**Build-number auto-increment** replaces what EAS used to provide silently
(`appVersionSource: "remote"`, `autoIncrement: true`): both lanes ask the
respective store for the highest build number/version code already uploaded
and increment it (`app_store_build_number` for iOS; every Android Play track,
including custom tracks, discovered through Supply and queried with
`google_play_track_version_codes`) rather than trusting
`pubspec.yaml`'s local `+N`, which is never bumped by hand. Both lanes pass
`-t lib/main.dart` explicitly — never `lib/main_e2e.dart` (a CI grep step in
`flutter-ci.yml` enforces this).

## Local persistence and regression coverage

Drift schema v2 preserves corpus identity after recipe deletion, reversible
cook-history links, and meal-owned shopping requirements. Existing v1 gaps
retain their old shortfall meaning; new requirements are aggregated for display
and allocate pantry stock only once. `test/data/fixtures/schema_v1.sql` is a
frozen **Flutter v1** database fixture, not Expo data migration.

Planning uses the viewed week, rechecks current capacity transactionally, and
retains excess rollover meals in their original week. Warm Monday/resume
rollover is clock-driven. Destructive Undo restores full row identity and linked
gaps/cooking state. The shell's connectivity banner mirrors Expo's network
presence message; it does not claim Internet reachability.

Mocked plugin boundaries do not substitute native camera, secure-storage,
Cognito or haptics verification.

## Splash screen

One composition, brand green (`#2E9D63`), configured in
`flutter_native_splash.yaml` from the vendored
`assets/brand/glean-b1-splash-logo.svg` — rasterized once to
`assets/brand/glean-b1-splash-logo.png` (a lossless conversion at 2048×2048,
since the source is a vector) because `flutter_native_splash` needs a raster
image. Regenerate after editing either file:

```bash
dart run flutter_native_splash:create
```

This works headless (verified on this box) and writes native assets under
`android/app/src/main/res/**` and
`ios/Runner/Assets.xcassets/LaunchImage.imageset/**` /
`ios/Runner/Base.lproj/LaunchScreen.storyboard` — commit whatever it changes.

Launcher icons are committed assets. The legacy `mipmap-*/ic_launcher.png`
(API < 26) is rendered from `assets/brand/glean-b1-icon.svg`; its generator,
`scripts/generate_launcher_icons.py`, was removed, so recover it from git history
if it needs regenerating.

The Android adaptive icon (API 26+) is
`res/mipmap-anydpi-v26/ic_launcher.xml`: a solid `#2E9D63` background
(`values/ic_launcher_background.xml`, the same green as `AppColors.primary`) plus
`mipmap-*/ic_launcher_foreground.png` and `ic_launcher_monochrome.png` (themed
icons, Android 13+). The foreground PNGs are `assets/brand/glean-b1-adaptive-foreground.svg`
rasterised on a 108dp canvas per density (108/162/216/324/432 px) with the mark
scaled to 92% so every opaque pixel sits inside the 66dp safe-zone circle; the
monochrome PNGs are the same shape in plain white. There is no
`android:roundIcon`, so no separate round variant.

## Web dev loop

`web/` exists so the app can run in Chrome with hot reload for quick visual
checks, without a Mac, an emulator or a build. It runs `lib/main_e2e.dart`
(the auth bypass, since Cognito sign-in via `flutter_appauth` has no web
support) against the real drift/SQLite layer, which on web needs the two
assets in `web/`: `sqlite3.wasm` and `drift_worker.js`.

```bash
make start-web        # from the repo root
```

Flutter launches and drives its own Chrome, so hot reload reaches the page
with no browser extension: edit Dart, press `r` in that terminal (`R` for a
hot restart), or run `make reload-web` from another shell, which signals the
pid file `flutter run` writes. That is how an agent that started the server
in the background reloads it. On a laptop the window opens in front of you;
resize it to a phone shape (or use the DevTools device toolbar at 390×844).
The in-browser database persists across restarts and reloads, so onboarding
and seeded data survive.

On a headless or remote box, put these in an untracked `.env.local` at the
repo root; the Makefile includes it when present:

```
WEB_HOST=<address the browser can reach>   # default 127.0.0.1
WEB_PORT=8090
WEB_HEADLESS=1                             # Chrome runs headless
```

Chrome's DevTools protocol then listens on `WEB_DEBUG_PORT` (default 9222)
on loopback; an automation tool attaches there to screenshot and drive the
very tab Flutter is hot-reloading, and any other browser can open
`http://WEB_HOST:WEB_PORT/` too (that tab needs a refresh after a reload).
Never commit hostnames or addresses to the Makefile or this file.

For agents driving the tab: Flutter renders to a canvas, so the DOM is empty
until the hidden "Enable accessibility" placeholder is clicked (`page
.locator('flt-semantics-placeholder').dispatchEvent('click')`). Flutter then
mirrors its semantics tree into the DOM, exposing headings, labels and roles
for locators. Those nodes are a transparent overlay above the canvas and
overlap each other, so Playwright's actionability check reports the target
as obscured; click with `{force: true}`.

### What web does and doesn't cover

- **Covers:** layout, spacing, theme and design-system work, navigation, the
  tabs, manual entry, pantry/plan/shop screens, anything backed by the local
  database, and (with e2e tokens, below) the AI-backed flows against a local
  backend. `defaultTargetPlatform` is the host OS on web, but the design
  system is Material-everywhere with no platform branching, so this is moot.
- **Doesn't cover:** camera (receipt scan), real Cognito sign-in, secure
  storage, haptics, connectivity. Those stay on a real device: the Codemagic
  build on the owner's phone, and the emulator/simulator `integration_test`
  jobs in CI, remain the pre-merge visual check for anything they touch.
- `flutter test --platform chrome` is **not** part of this loop; Flutter marks
  it deprecated/internal.

### Calling the backend from the e2e entrypoint

Without tokens the bypass session cannot call an AI endpoint, so the
**Review items** screen after a scan/describe is unreachable. To reach it,
`lib/main_e2e.dart` accepts the real tokens of a dedicated Cognito test user
as `--dart-define=E2E_ACCESS_TOKEN/E2E_ID_TOKEN/E2E_REFRESH_TOKEN` (all three
or none). The bypass then signs in as that user, refreshes through the real
dev Cognito domain, and a local backend configured with the dev pool ids
verifies the tokens against the pool's public keys. Nothing changes in the
backend and no verification is skipped.

One-time, with AWS credentials for the account, create the user in the
**dev** pool (ids are the `glean-api-dev` stack's outputs):

```bash
scripts/e2e_user.sh <dev UserPoolId> e2e-test-user '<password>'
```

Then in `.env.local` (never committed):

```
E2E_USERNAME=e2e-test-user
E2E_PASSWORD=<password>
COGNITO_CLIENT_ID=<dev UserPoolClientId>
COGNITO_DOMAIN=<dev CognitoDomain>
```

With those set, `make start-web` and `make test-e2e` sign the user in via
`USER_PASSWORD_AUTH` (`scripts/e2e_tokens.sh`, no AWS credentials needed) and
pass the tokens through; `make e2e-tokens` prints them as exports for a
hand-run `flutter` command. Point `make start-backend` at the dev pool with
the same ids in `backend/.env`, plus an `OPENROUTER_API_KEY` that is kept
separate from the production key so test spend is visible on its own.

The test user owns no server-side data (all state is on-device), and the
`isProductionApiBaseUrl` guard still refuses to start the e2e entrypoint
against anything but a loopback backend.

### Pinned web assets

`web/sqlite3.wasm` must match the `sqlite3` version in `pubspec.lock` and
`web/drift_worker.js` the `drift` version. When either dependency is bumped,
re-download both from their GitHub releases:

```bash
curl -sSL -o web/sqlite3.wasm \
  https://github.com/simolus3/sqlite3.dart/releases/download/sqlite3-<ver>/sqlite3.wasm
curl -sSL -o web/drift_worker.js \
  https://github.com/simolus3/drift/releases/download/drift-<ver>/drift_worker.js
```
