# AGENTS.md

This file provides guidance to agents when working in the Glean Flutter app.
See `../AGENTS.md` for repo-wide Makefile targets and preferred tools.
`CLAUDE.md` is a compatibility symlink to this file.

## User data safety

The owner uses the Android app for real, and the phone's SQLite file is the
only copy of their pantry, plan and shopping list (nothing syncs to the
server). On their phone, never uninstall the app, clear its data, install a
build signed with any key other than the release key, or restore a backup that
has not been verified (see below).
Updates go through Codemagic builds, which install over the top, or through
the release-key owner build (`scripts/owner_build.sh`, made on gordon) installed
with `adb install -r`, and only when all of these hold:

- the owner is present, and a verified Export diagnostics of the phone exists
  (it downloads, opens with `sqlite3`, and its row counts match);
- the build is signed with the release key and its versionCode is higher than
  the installed app's (versionCodes are minutes since 2024-01-01 UTC);
- the install is `adb install -r`, never preceded by an uninstall;
- the same install was proven first on an emulator, over a tester build holding
  data.

Once it is installed, `adb` on the phone is read-only (copy the database and log
off, stream `adb logcat -s glean`), and only when the owner asks.

- Developer-mode Settings has **Restore from backup**: it replaces the phone's
  database with one of the signed-in user's exports (or an agent-prepared
  backup, listed first and labelled). A restore on the owner's phone is allowed
  only with the owner present, and only after an Export diagnostics of that
  phone was verified (downloads, opens with `sqlite3`, row counts match). The
  restore refuses a backup from a newer schema and, on any failure, leaves the
  current database untouched; the previous database is also kept as
  `glean.sqlite.pre-restore`. Prove a restore on an emulator first.
- Any table change needs a `schemaVersion` bump, an `onUpgrade` step, a new
  schema snapshot and a frozen fixture of the old version
  (`test/data/schema_safety_test.dart` enforces this). The default is to
  migrate in place. Where a migration is impractical, a schema change may
  instead rely on export plus restore (an agent transforms a verified export
  and uploads it as a prepared backup), provided an export of the phone was
  checked first; the snapshot and fixture requirement still holds.
- Keep Android Auto Backup on (`test/android_backup_test.dart`), even though
  flutter_secure_storage's README suggests turning it off.

## Commands

Prefer `make test-app` / `make lint-app` from the repo root. Use the commands
below for targeted runs within this directory:

```bash
flutter test test/data/pantry_repository_test.dart   # single file
flutter test --plain-name "adds an item"             # single test by name
memcap flutter test --concurrency=4                   # default concurrency flakes with flutter_tester load errors on some machines
flutter analyze                                       # must be zero errors/warnings/infos
dart format --output=none --set-exit-if-changed lib test integration_test  # check only
dart run build_runner build --delete-conflicting-outputs  # after touching drift tables or API models (lib/api/models)
```

None of the above need an Android SDK, Java, or Xcode — they run on any
machine with the Flutter SDK, including this box. `flutter build`/`flutter
run`/the `integration_test` suite do need a real toolchain; see
`README.md` for exact commands and what's Mac-only.

## Architecture

Feature-first Flutter app: `go_router` + `flutter_riverpod` + `drift`
(SQLite). All user state lives on-device; the FastAPI backend (`../backend/`)
is a stateless AI processing service.

```
lib/
├── main.dart                # Production entrypoint — never reaches auth_bypass.dart
├── main_e2e.dart             # integration_test entrypoint — the ONLY importer of auth_bypass.dart
├── bootstrap.dart            # Shared startup wiring both entrypoints call into
├── app.dart                  # MaterialApp.router root widget
├── auth/                     # AuthController, Cognito client, TokenStorage; auth_bypass.dart (e2e only)
├── data/                     # drift tables, repositories/, providers/ (stream + repository providers)
├── design_system/            # ThemeData, AppTokens (ThemeExtension), Haptics, GleanSnackBar, ListSkeleton
├── router/                   # go_router table, route constants, the five-tab shell
├── api/                      # Typed HTTP client, models/ (json_serializable), providers/
└── features/<feature>/       # Screen + widgets/ + providers, one dir per tab/flow
test/                          # Unit + widget tests mirroring lib/, plus test/standards/
integration_test/              # The one integration_test suite (app_test.dart), against main_e2e.dart
```

## Catalogue sync

`ingredient_groups`, `catalogue_items`, `catalogue_aliases` and `catalogue_sync_state` hold a synced copy of the
backend catalogue (`GET /catalogue?since=<version>`). The 29 groups are seeded in the app
(`lib/data/seed/ingredient_groups.dart`) so it works before any sync; `test/data/fixtures/catalogue_groups.json`
pins that seed to the backend's output. `CatalogueSyncLifecycle` syncs in the background on launch, resume and
sign-in; a failed sync changes nothing. Pantry, Plan and Shop must keep working with zero catalogue items.

Each synced item carries the store `section` the backend computed (the app never copies the section rule) and its
`former_ids`, which sync stores in `catalogue_item_redirects`. `ingredient_overrides` holds the household's own
changes to tracking mode, stock unit, shelf lives and section, keyed by item id; sync never writes it.
`CatalogueRepository.effectiveIngredient(id)` is the one resolver: it follows redirects from a former id to the
surviving item, then takes each field from the override (the surviving id's, then a former id's), else the item,
else the group default (section: override, else synced section, else Other). Anything reading those fields goes
through it.

Each `ingredients` row carries its ingredient group (`group_id`), a nullable `catalogue_item_id` and a nullable `form`
(never defaulted). `GleanDatabase.linkIngredientsToCatalogue()` links a row to the item its name or an alias matches,
and moves the household's own store-section choice from `ingredients.store_section` into that item's
`ingredient_overrides` row; it runs in the schema upgrade and at the end of every `applyChanges`, so a catalogue that
was empty at upgrade time catches up at the first sync. A row that matches nothing stays unlinked and keeps working.

## Standards

`test/standards/house_rules_test.dart` enforces the import half of rule 1,
the colour half of rule 2, rule 3's citation patterns, and the auth-bypass
import graph (see [Auth bypass](#auth-bypass)). The test has no exemptions;
fix the code. The rest — spacing from `context.tokens`, not constructing a
repository or `GleanApiClient` in a feature, and rules 4–7 — is convention
that review checks. `flutter analyze` and `dart format` cover style.

1. **Data access only through providers.** Nothing under `lib/features/**`
   imports `package:drift`, `lib/data/database.dart`, `lib/data/tables.dart`
   or `lib/data/deletion_snapshots.dart`, and nothing constructs a repository
   or `GleanApiClient`. Read them with `ref.read(xRepositoryProvider)` /
   `ref.read(apiClientProvider)`. Importing a repository file for an
   exception type is fine.
2. **Colours and spacing come from the theme.** Outside `lib/design_system/`
   there is no `Colors.*` (except `Colors.transparent`) and no `Color(0x…)`.
   Use `Theme.of(context).colorScheme` and `context.tokens`. Camera-overlay
   colours are tokens too (`tokens.onCamera`, `tokens.cameraScrim`,
   `tokens.cameraBackdrop`).
3. **No process citations in code or tests.** Comments and test names
   explain the current constraint, not the ticket that introduced it: no
   `AC-…`, `R-nn`, `F-nn`, `FINDINGS.md`, `REMEDIATION.md`, `.scratch/`,
   "Wave" or "orchestrator" anywhere, and no React Native history in
   `lib/` (a test may still say which old bug it guards).
4. **Delete rather than wrap.** No abstract class with a single production
   implementation unless the real dependency cannot run under `flutter test`
   (today: `Haptics`, `ReceiptCameraController`). Use mocktail on the
   concrete class instead.
5. **Mutations just write.** Reads are drift `.watch()` streams; there is no
   `ref.invalidate` after a mutation and no manual reload on focus.
6. **One API call needs no controller.** Screens call
   `ref.read(apiClientProvider)` and hold their own pending flag.
7. **Destructive actions go through `GleanSnackBar.runUndoable`.** It owns
   the try/catch, undo snackbar and failure messages.

## Testing

- One in-memory drift fixture (`test/data/fixture.dart`) and one widget harness
  (`test/support/harness.dart`) that pumps a real `GoRouter` + real database.
  Use them; do not hand-roll fake repositories or databases. To make a
  repository fail, use a SQLite trigger on the fixture
  (`AppTestHarness.failInsertsOn` / `failDeletesOn`, or `db.customStatement`
  for a narrower trigger).
- Tests assert behaviour through the widget or repository seam. The only
  tests that read source or config files are `test/standards/house_rules_test.dart`
  and the platform guards (`test/android_backup_test.dart`,
  `test/auth/redirect_uri_contract_test.dart`), each of which pins a manifest
  or Cognito setting that has lost user data or broken sign-in for real.
- No golden images.
- `RecordingHaptics` in the harness asserts the haptic ladder.

## Auth bypass

`lib/main_e2e.dart` is the only file besides `lib/auth/auth_bypass.dart`
allowed to import it; `test/standards/house_rules_test.dart` enforces this.
Never loosen it.
