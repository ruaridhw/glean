# Glean (Flutter)

The Glean mobile app: Flutter, targeting iOS and Android only (no web/desktop
scaffolding is committed — see [Web target](#web-target-deferred) below).
Replaces the Expo/React Native app that used to live in this repository
(see git history). Full spec: the root `../FLUTTER_MIGRATION.md`.

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
graph at all (`test/auth/auth_bypass_test.dart` enforces this; see
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
`lib/main_e2e.dart` seeds auth from `bypassAuthSnapshot()` and never
constructs a `CognitoAuthClient`, so these values are only read by the
startup non-empty/loopback assertions, never dialled for real. Repo-root
equivalent: `make test-e2e COGNITO_DOMAIN=... COGNITO_CLIENT_ID=...`.

### Running it in CI

`.github/workflows/flutter-integration.yml`, `workflow_dispatch`-gated (never
on push): two separate jobs, iOS Simulator on a `macos-latest` runner and
Android emulator on `ubuntu-latest` with KVM. **Deliberately not one
combined macOS job** — GitHub-hosted macOS runners cannot run the Android
emulator with hardware acceleration (nested virtualization is unsupported on
the current arm64 image, and a request to lift this was closed "not
planned"; see the workflow file's header comment and
`.scratch/flutter-port/research/build-release-macos-ci.md` for the full
trail). Trigger it from the Actions tab or `gh workflow run flutter-integration.yml`.

## CI

- **`.github/workflows/flutter-ci.yml`** — the only job that runs
  automatically (on push/PR to `app/**`): format check, `flutter analyze`,
  `flutter test`. No device involved.
- **`.github/workflows/flutter-integration.yml`** — `workflow_dispatch` only;
  see [Integration tests](#integration-tests) above.
- **`test/build/release_entrypoint_test.dart`** — a build-*configuration*
  guard (not a re-check of the source import graph, which
  `test/auth/auth_bypass_test.dart` already owns): scans the Fastlane
  Fastfiles and every workflow YAML for a release-shaped build command
  (`flutter build`/`gradlew assemble*`) naming `main_e2e`, and fails if it
  finds one.

## Release (Fastlane)

`ios/fastlane/` (TestFlight) and `android/fastlane/` (Play internal track) —
**run from a Mac, never from CI**. No `match`: one Mac, one signer, so
Xcode's own "Automatically manage signing" (already on) is adequate; adopt
`match` only once a second signer/machine needs the same certificates.

```bash
# iOS — needs an App Store Connect API key (see ios/fastlane/Fastfile's header)
cd ios && bundle exec fastlane beta \
  ASC_KEY_ID=... ASC_ISSUER_ID=... ASC_KEY_CONTENT=...

# Android — needs android/key.properties (one-time keystore setup — see
# android/fastlane/Fastfile's header) and a Play service-account JSON
cd android && PLAY_STORE_JSON_KEY="$(cat service-account.json)" bundle exec fastlane internal
```

Neither lane can run on this box (no Ruby/Bundler/fastlane, no Xcode, no
Android SDK) — they're authored and reviewed for correctness, not executed
here.

**Build-number auto-increment** replaces what EAS used to provide silently
(`appVersionSource: "remote"`, `autoIncrement: true`): both lanes ask the
respective store for the highest build number/version code already uploaded
and increment it (`app_store_build_number` for iOS,
`google_play_track_version_codes` for Android) rather than trusting
`pubspec.yaml`'s local `+N`, which is never bumped by hand. Both lanes pass
`-t lib/main.dart` explicitly — never `lib/main_e2e.dart`
(`test/build/release_entrypoint_test.dart` enforces this).

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

## Web target: deferred

No Flutter web harness is committed (confirm with `flutter create --list-samples`
style checks if in doubt — there's no `web/` directory here and `.metadata`
lists only `root`, `android`, `ios` platforms). It was only ever a candidate
*local* dev-loop convenience: worth building only if driving Chrome proves
meaningfully faster than driving a real emulator for an agent's
test-and-iterate loop, which couldn't be measured before a Flutter app
existed. Now that one does, the benchmark is: time an agent driving Chrome
vs. an agent driving an Android emulator/iOS Simulator through the same
representative interaction (e.g. the pantry manual-add flow this
`integration_test` suite covers). Build the web harness only if Chrome wins
meaningfully — otherwise leave this section as the record of why not.

If it's ever built:

```bash
flutter drive -d web-server --web-browser-flag="--window-size=390,844"
```

with a version-matched headless `chromedriver` on the `PATH`. Note
`flutter test --platform chrome` is **not** the right tool for this —
Flutter's own tooling marks it deprecated/internal. Also note
`defaultTargetPlatform` resolves to the *host* OS on web (Linux in CI, not
iOS/Android), so platform-adaptive gestures, theming, and native plugins
would not be faithfully exercised through it — largely moot here since the
design system is Material-everywhere on both real platforms already (no
Cupertino, no platform-adaptive branching to miss).
