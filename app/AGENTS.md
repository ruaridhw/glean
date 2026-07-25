# AGENTS.md

This file provides guidance to agents when working in the Glean Flutter app.
See `../AGENTS.md` for repo-wide Makefile targets and preferred tools.
`CLAUDE.md` is a compatibility symlink to this file.

## Commands

Prefer `make test-app` / `make lint-app` from the repo root. Use the commands
below for targeted runs within this directory:

```bash
flutter test test/data/pantry_repository_test.dart   # single file
flutter test --plain-name "adds an item"             # single test by name
flutter analyze                                       # must be zero errors/warnings/infos
dart format --output=none --set-exit-if-changed lib test integration_test  # check only
dart run build_runner build --delete-conflicting-outputs  # after touching drift tables
```

None of the above need an Android SDK, Java, or Xcode — they run on any
machine with the Flutter SDK, including this box. `flutter build`/`flutter
run`/the `integration_test` suite do need a real toolchain; see
`README.md` for exact commands and what's Mac-only.

## Architecture

Feature-first Flutter app: `go_router` + `flutter_riverpod` + `drift`
(SQLite), replacing the Expo/React Native app that used to live in this
repository (see git history). All app state lives on-device; the FastAPI
backend (`../backend/`) is a stateless AI processing service with no user data of
its own — see the root `FLUTTER_MIGRATION.md` for the full spec this app was
built against, and `.scratch/flutter-port/ACCEPTANCE.md` for the criteria it
was verified against.

### Module layout

```
lib/
├── main.dart                # Production entrypoint — never reaches auth_bypass.dart
├── main_e2e.dart             # integration_test entrypoint — the ONLY importer of auth_bypass.dart
├── bootstrap.dart            # Shared startup wiring both entrypoints call into
├── app.dart                  # MaterialApp.router root widget
├── data/                     # drift tables/DAOs, repositories, `providers/` (Stream/Future providers)
├── design_system/            # ThemeData, AppTokens (ThemeExtension), Haptics ladder, GleanBadge, SkeletonBox
├── router/                   # go_router table, route name/path constants, the five-tab shell
├── api/                      # Typed HTTP client + request/response models, `providers/` (command providers)
└── features/<feature>/       # Screen + its own widgets/ + its providers, one dir per tab/flow
test/                          # Unit + widget tests, mirroring lib/
integration_test/              # The one integration_test suite (app_test.dart), against main_e2e.dart
```

**House rule that's grepped for:** nothing under `lib/features/**` imports
`drift` or the API client directly — always through a provider
(`lib/data/providers/*.dart` / `lib/api/providers/*.dart`). See
`FLUTTER_MIGRATION.md` §3/§4 for the reasoning (no manual reload, no
`ref.invalidate` after a mutation, tokens via `Theme.of(context)` only).

### Auth bypass

`lib/main_e2e.dart` is the only file (besides `lib/auth/auth_bypass.dart`
itself) allowed to import it — `test/auth/auth_bypass_test.dart` scans
`lib/` to enforce this, and `test/build/release_entrypoint_test.dart`
complements it at the build-configuration level (Fastlane lanes and CI
workflows can never target `main_e2e.dart` for a release build). Never loosen
either check to get a change to pass.

### Testing

One shared in-memory `drift` fixture (`test/data/fixture.dart`,
`NativeDatabase.memory()` — works headless, no native SQLite install needed)
and one widget-test harness (`test/support/harness.dart`) that pumps a real
`GoRouter` + real database over `UncontrolledProviderScope`. Prefer both over
hand-rolled mocks; `RecordingHaptics` (also in the harness) asserts the
haptic ladder without extra setup.
