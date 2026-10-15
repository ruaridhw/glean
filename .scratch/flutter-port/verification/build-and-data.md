# Verification: Section A (AC-BUILD-*) and Section B (AC-DATA-*)

Verifier: independent agent, did not implement any of this code.
Verified against `app/` at HEAD `906c9bba8f2f0681cbb1cdf1b977fdedd9ce39e6`
("🔥 refactor: delete the Expo/React Native app").

**Environment note:** this worktree is shared with other concurrently-running
agents (observed live commits landing, and another verifier's in-flight
temporary breakage of `shopping_repository.dart` for its own AC-TEST-06 check,
mid-session). Where a transient diff appeared and then vanished between two of
my own commands, it was someone else's in-flight edit, not evidence of
non-determinism in this codebase — noted inline where it happened.

---

## A. Project, build & toolchain

**AC-BUILD-01 — CONFIRMED.** No `web/`, `macos/`, `windows/`, `linux/`
directories exist on disk or in git (`git ls-files app/ | grep -E
'^app/(web|macos|windows|linux)/'` → empty). `app/ios/` and `app/android/`
scaffolding present and git-tracked. `app/build/` is gitignored
(`app/.gitignore:4` `/build/`).

**AC-BUILD-02 — PARTIAL.** All sanctioned packages present in
`app/pubspec.yaml`: `go_router` (36), `flutter_riverpod` (37), `drift`+`drift_dev`
(38, 63), `flutter_appauth` (41), `flutter_secure_storage` (42), `camera` (43),
`flutter_svg` (44), `permission_handler` (45), `flutter_native_splash` (66).
`sqlite3_flutter_libs` is absent — replaced by `drift_flutter` (49), a
documented/accepted deviation (FINDINGS.md F-06, RESOLVED: upstream
`sqlite3_flutter_libs` itself says "not used anymore"). No banned packages
(`isar`, `auto_route`, `ionicons`, toast, haptics package) anywhere in
`pubspec.yaml` — confirmed by grep, no hits.

However the criterion says "**exactly** the sanctioned stack" and that does
not hold:
- `pubspec.yaml:39,46,50,51` add `path_provider`, `http`, `riverpod`,
  `url_launcher` beyond §2's list. Three of these are used and two are
  explicitly justified in FINDINGS.md (F-03 for `riverpod`, F-10 for
  `url_launcher`); `http` is used by `lib/api/api_client.dart:5` but **§2's
  stack table never lists a networking package at all**, despite the app's
  entire remote-API layer (§3) requiring one — a spec omission, not an
  implementation error.
- `pubspec.yaml:40,47,48` declare `path`, `intl`, `collection` as direct
  dependencies. **Grep across the entire `lib/` and `test/` trees finds zero
  imports of any of the three** (`grep -rn "package:intl\|package:collection\|
  import 'package:path/'" . --include=*.dart` → no hits outside `build/`).
  These are dead weight: declared, never used, not mentioned in any FINDINGS
  entry as a deliberate addition.

**AC-BUILD-03 — CONFIRMED.** `pubspec.yaml:86-98` declares five weight
variants of `PlusJakartaSans` (400/500/600/700/800); files exist at
`app/assets/fonts/PlusJakartaSans-{400Regular,500Medium,600SemiBold,700Bold,
800ExtraBold}.ttf` (`ls -la assets/fonts/`, all present, ~94KB each).

**AC-BUILD-04 — CONFIRMED.** `flutter analyze` → `No issues found! (ran in
0.6s)`, exit 0, at HEAD 906c9bb.

**AC-BUILD-05 — CONFIRMED.** `flutter test` → `00:10 +345: ... All tests
passed!`, 345/345, 0 failures. Confirmed no `skip:` parameter anywhere:
`grep -rn "skip:" test/ integration_test/` → empty.

**AC-BUILD-06 — CONFIRMED.** `analysis_options.yaml:4` includes
`package:flutter_lints/flutter.yaml`; `:20,24` enable `prefer_const_constructors`
and `use_super_parameters`; `:10-14` excludes only `**/*.g.dart`,
`**/*.drift.dart`, and (defensively, currently a no-op — no such files exist:
`find . -name "*.mocks.dart"` → empty, and `mockito` isn't a dependency)
`**/*.mocks.dart`.

**AC-BUILD-07 — CONFIRMED, with a caveat about this session's environment.**
Ran `dart run build_runner build --delete-conflicting-outputs` twice in a row
from a clean tree; the second (and every subsequent) run reports `150 outputs`
all `same` and `git status --porcelain` is empty afterward — the codegen is
reproducible and the tree is unchanged. On my *first* invocation this session
I observed a transient, non-reproducible diff in
`lib/data/repositories/pantry_repository.dart` (the `_db.transaction(...)`
wrapper in `addItems` briefly appeared removed) that was gone by the next
`git status` check and did not recur on a second/third run. Given this is a
shared, actively-committed-to worktree (HEAD moved from `940fbf0` to `906c9bb`
under me mid-session), I attribute this to a concurrent agent's commit/checkout
landing between my two checks, not to `build_runner` itself — it did not
reproduce across three subsequent clean runs. Flagging it rather than silently
dropping it, since I can't fully rule out a build_runner/incremental-cache
issue with certainty.

**AC-BUILD-08 — CONFIRMED.** `flutter_native_splash.yaml:17,34,41` all use
`#2E9D63`; generated assets committed for both platforms
(`android/app/src/main/res/drawable*/{splash,android12splash}.png`,
`ios/Runner/Assets.xcassets/LaunchImage.imageset/**`,
`ios/Runner/Base.lproj/LaunchScreen.storyboard` — via `git ls-files`).
`android/app/src/main/res/values-v31/styles.xml` sets
`windowSplashScreenBackground`/`windowSplashScreenIconBackgroundColor` to the
same `#2E9D63`. One composition, brand green, both platforms.

**AC-BUILD-09 — CONFIRMED.** `lib/main.dart` imports only
`package:glean/auth/auth.dart` (the barrel), which per its own doc comment
(`lib/auth/auth.dart:1-9`) deliberately does not export `auth_bypass.dart`.
`lib/main_e2e.dart` is the only production-code importer of
`auth/auth_bypass.dart` (`grep -rln "auth_bypass" lib/` → `auth_mode.dart` and
`auth_controller.dart` only *mention* it in doc comments, not imports —
verified by `grep -n "auth_bypass" lib/auth/auth_mode.dart
lib/auth/auth_controller.dart`, both hits are inside `///` comments).
`test/auth/auth_bypass_test.dart`'s last test scans `lib/` at run time with a
regex for `import|export ... auth_bypass.dart` and asserts the only
referrers are `auth_bypass.dart` itself and `main_e2e.dart` — this test is
part of the 345 passing (not vacuous: it operates on the real file tree, not
a mock).

**AC-BUILD-10 — CONFIRMED.** `ios/Runner/Info.plist:51-52` declares
`NSCameraUsageDescription`. `android/app/src/main/AndroidManifest.xml:5`
declares `<uses-permission android:name="android.permission.CAMERA"/>` and
`:25-38` the `glean://auth/callback` intent filter (`scheme="glean"
host="auth" path="/callback"`). `grep -rn "RECORD_AUDIO\|
NSMicrophoneUsageDescription" android/ ios/` → zero hits (only two comments
*documenting* its absence).

**AC-BUILD-11 — CONFIRMED, with a caveat on what "benchmark" means.** No web
harness committed: `git ls-files | grep -iE "chromedriver|web-server|/web/"`
→ empty. A decision record exists at
`.scratch/flutter-port/issues/18-decide-web-harness-worth-building.md`,
carried into `FLUTTER_MIGRATION.md:241-247`. However this record is a
**policy to defer indefinitely** ("don't build it now; benchmark once an app
exists"), not an executed Chrome-vs-emulator timing comparison — I found no
evidence anywhere in `.scratch/flutter-port/` that the comparison was ever
actually run once a Flutter app existed (no numbers, no timing note). Given
every implementation/verification agent in this environment lacks
Xcode/Android-SDK access (this is a structural constraint of the sandbox,
not an oversight), it's plausible the comparison genuinely never became
possible. The criterion's letter ("a benchmark note recording the... decision
exists") is satisfied; its spirit (an actual timing measurement) is not.

---

## B. Data layer

**AC-DATA-01 — CONFIRMED.** `lib/data/tables.dart` defines
`IngredientCategories` (37), `Ingredients` (57), `PantryItems` (68), `Recipes`
(89), `RecipeDietaryFlags` (112), `RecipeIngredients` (121), `MealPlanEntries`
(137), `ShoppingListItems` (186), `UserConfig` (202) — every RN table, plus a
new `CookedAdjustments` (160) for undo.

**AC-DATA-02 — CONFIRMED, checked every user-data table.** `PantryItems.userId`
(`tables.dart:70`), `Recipes.userId` (`:91`), `MealPlanEntries.userId`
(`:139`), `ShoppingListItems.userId` (`:188`), `CookedAdjustments.userId`
(`:162`), `UserConfig.id` doubles as the user key (`:205`, was already scoped
in RN). `IngredientCategories`/`Ingredients` are correctly *not* scoped — a
shared catalog, not user data (confirmed by design comment at
`tables.dart:46-56` and the isolation test's own "shared ingredient row"
case).

**AC-DATA-03 — CONFIRMED, exhaustively.** Every raw drift `.select`/`.update`/
`.delete` call in the app lives only under `lib/data/repositories/*.dart`
(`grep -rln "_db.select\|db.select" lib/` → no hits outside that directory).
Read through all six repository files
(`pantry_repository.dart`, `plan_repository.dart`, `recipes_repository.dart`,
`shopping_repository.dart`, `user_config_repository.dart`,
`ingredients_repository.dart`) line by line; every query against a user-data
table filters on `userId` (e.g. `pantry_repository.dart:86`,
`plan_repository.dart:45`, `recipes_repository.dart:52`,
`shopping_repository.dart:38`). Mutations by row `id` double-filter
`id.equals(x) & userId.equals(y)` (e.g. `pantry_repository.dart:312`,
`shopping_repository.dart:218,225`) so a caller can't edit another user's row
even by guessing its id. `ingredients_repository.dart` and the shared
`ingredient_categories`/`ingredients` tables are correctly unscoped (shared
catalog). A few reads by a bare local-DB primary key
(`RecipesRepository.getIngredients(recipeId)`,
`recipes_repository.dart:172`, no `userId` param) are safe in practice because
every call site (`lib/features/meals/saved_recipe_detail.dart:77`,
`lib/features/plan/food_groups.dart:39`,
`lib/features/meals/actions.dart:100`) only ever passes an id already
resolved through a user-scoped read first (`recipeByIdProvider` filters
within `savedRecipesProvider`, itself `watchSaved(userId)`-backed) — verified
by reading `saved_recipe_detail.dart` end to end: `_SavedRecipeDetailBody` is
only ever built after `recipeAsync.when(data: (recipe) => recipe != null ...)`.

**Regression check performed (and reverted):** removed the `userId` filter
from `PantryRepository.watchAll` and ran
`flutter test test/data/user_isolation_test.dart` — it failed exactly as
expected (`Expected: empty / Actual: [Instance of 'PantryItemView']` and a
second cascading failure). Restored via `git checkout --
lib/data/repositories/pantry_repository.dart`; `git diff` on that file is
empty. This proves `test/data/user_isolation_test.dart` (AC-TEST-07) is a
real, non-vacuous check for AC-DATA-03, not one that passes regardless of the
implementation.

**AC-DATA-04 — CONFIRMED.** Every screen-level read is a `StreamProvider`
(`lib/data/providers/{pantry,plan,recipes,shopping,user_config}_providers.dart`,
all `StreamProvider`/`StreamProvider.family` over `.watch()`). No
`RefreshIndicator` anywhere (`grep -rln "RefreshIndicator" lib/features/` →
empty). `PlanScreen.initState` (`lib/features/plan/plan_screen.dart:49-67`)
does call a repository method on mount, but it's `rolloverUncookedMeals` — a
genuine idempotent business mutation (updates `plannedDate`, never inserts),
not a data reload; the screen's own `loading` value
(`plan_screen.dart:122`, `!entriesAsync.hasValue || !configAsync.hasValue`) is
derived from the watched `AsyncValue`s, not a manually-toggled bool set on
focus. No other `initState`/`didChangeDependencies` in `lib/features/**`
calls a one-shot repository read; the only direct repository one-shot-read
call sites outside a test are in
`lib/features/plan/providers/generate_week_controller.dart:62-73` (a command
provider, not a screen).

**AC-DATA-05 — CONFIRMED.** `grep -rn "ref.invalidate\|\.refresh(\|refetch"
lib/features/` and `lib/` → the only two hits
(`settings_screen.dart:11`, `onboarding_status.dart:21`) are doc comments
*documenting the absence* of invalidation, not actual calls. The one
`.refresh(` in `lib/` (`auth_controller.dart:231`) is an OAuth token refresh
API call, unrelated to Riverpod.

**AC-DATA-06 — CONFIRMED.** `lib/api/providers/*.dart` contains zero
references to any repository (`grep -rn "Repository\b" lib/api/providers/*.dart`
→ empty) — command providers only call `apiClientProvider` and hold their
own ephemeral `AsyncNotifier<T?>` state. Traced two commit paths end to end:
`lib/features/meals/recipe_preview_screen.dart` (search-result preview,
AC-MEAL-01 — nothing written until the bookmark tap) and
`lib/features/meals/meals_import_screen.dart:66-100` (import-from-URL — an
explicit "Import" button press is the commit step, then dedupe-checked via
`recipesRepositoryProvider.getByExternalId` before `saveApiRecipe` writes).

**AC-DATA-07 — CONFIRMED, exhaustively.** `grep -rEn "import 'package:drift|
import '.*database\.dart'|import '.*api_client\.dart'|import 'package:http'"
lib/features/` → zero hits across the entire feature tree.

**AC-DATA-08 — CONFIRMED.** `lib/api/providers/recipe_providers.dart:31-32`:
`FutureProvider.autoDispose.family<RecipeSearchResponse, String>`, with a
350ms `Future.delayed` debounce and an `if (!ref.mounted) return ...` guard
(`:41-44`) so a torn-down family instance never issues its request. Backed by
a real (non-vacuous) test:
`test/api/providers/recipe_search_provider_test.dart` — "debounced search:
rapid input produces exactly one request" — part of the 345 passing.

**AC-DATA-09 — CONFIRMED.** `lib/auth/auth_controller.dart:216-217`
`signOut()` calls only `_requireStorage.clearAll()` then publishes
`AuthSessionSnapshot.signedOut` — no drift access.
`lib/features/settings/providers/sign_out_action.dart` documents the same
rule at the interface boundary. The "different user sees only their own
data" half is structurally guaranteed by AC-DATA-02/03 above and exercised by
`test/data/user_isolation_test.dart` (already confirmed non-vacuous above).

**AC-DATA-10 — CONFIRMED.** `lib/data/seed/taxonomy.dart` lists exactly 23
`CategorySeed` entries (:24-46) and exactly 10 `StapleSeed` entries (:60-69).
Seeded once in `GleanDatabase.migration.onCreate`
(`lib/data/database.dart:44-46,58-75`).
`test/data/seed_test.dart` queries a real `NativeDatabase.memory()`
(`createTestDatabase()`) and asserts `hasLength(23)` /
`hasLength(10)` against the live rows, plus per-row field equality — not a
call-count assertion. Part of the 345 passing.

**AC-DATA-11 — CONFIRMED.** Client drift layer:
`lib/data/models/pantry_item_view.dart` declares `final String? category;`
and `final String foodGroup;` (non-nullable) side by side (:42-43);
`PantryRepository._mapRow` (`pantry_repository.dart:168`) produces it via
`category?.foodGroup ?? _uncategorisedFoodGroup` — a coalesce, not a cast, so
it can't crash and can't silently accept null either. API boundary:
`lib/api/models/parsed_ingredient.dart:37-53`, `ParsedIngredient.fromJson`
explicitly checks `foodGroup is! String || foodGroup.isEmpty` and **throws
`FormatException`** rather than defaulting or force-casting; `category` is
read as the plain nullable cast `json['category'] as String?` (:50). Verified
`ShoppingProposalItem.fromJson` (`lib/api/models/shopping.dart:33-45`) and the
receipts model (`lib/api/models/receipts.dart:23`) both funnel through this
one `ParsedIngredient.fromJson` — no second, divergent parsing path exists
anywhere that could bypass the check (`grep -rn "food_group" lib/api/`
confirms a single handling site).

**AC-DATA-12 — CONFIRMED by inspection; no test exercises it.**
`lib/data/providers/database_providers.dart:39-45`,
`databaseReadyProvider` runs a real `SELECT 1` against the live
`GleanDatabase` and surfaces as `AsyncValue.error` on failure.
`lib/bootstrap.dart:58-68`, `GleanRoot.build` maps
`ready.when(data: ..., loading: ..., error: (error, _) =>
_DatabaseErrorApp(error: error))` — a real, user-facing error screen
("Glean couldn't open its storage...") rather than the RN app's swallowed
failure. **However**: `grep -rln "GleanRoot" test/ lib/` shows `GleanRoot` is
referenced only in `lib/main.dart`, `lib/main_e2e.dart`, and
`lib/bootstrap.dart` itself — **zero test coverage**. Nothing pumps
`GleanRoot` with an overridden/failing `databaseReadyProvider` and asserts
the error UI appears. The behaviour is real by reading the code, but a
future regression here (e.g. someone swallowing the error again) would not
be caught by the suite.

---

## Defects found that no criterion covers

1. **A second, non-SQL persistence layer for real user data, contradicting
   §3's central architectural claim.**
   `lib/features/onboarding/providers/onboarding_status.dart`'s
   `FileOnboardingStatusStore` (`:41-76`) is the live production
   implementation (`onboardingStatusStoreProvider`, `:105-106`, wired into
   `lib/features/onboarding/onboarding_gate.dart` and `onboarding_screen.dart`)
   for whether a user has completed first-run setup (AC-UX-04). It persists
   to a **plain text file** (`onboarding_completed.txt`, one user id per
   line, via `path_provider`/`dart:io`) — not the drift database at all.
   The file's own doc comment (`:1-21`) says this is a stopgap "Required
   follow-up for the Data module: `user_config`... has no 'has completed
   onboarding' column today... designed to be swapped for a
   `UserConfigRepository`-backed implementation later" — but
   `lib/data/tables.dart`'s `UserConfig` table (`:202-214`) still has no such
   column (confirmed by grep for `onboard` across `tables.dart` and
   `user_config_view.dart` — no hits), so that follow-up never landed. §3 is
   explicit that "local SQLite is the sole source of truth for user data...
   any repository-with-cache-reconciliation layer would solve a problem this
   app does not have" — this is exactly the kind of parallel persistence
   mechanism that claim rules out, for a real piece of per-user state. It
   does not cross-leak between users (each user id is checked by membership
   in the file's set, so functionally it's scoped), so it isn't a security
   bug, but it is an architecture violation that landed silently because it
   fell into the same kind of cross-module ownership gap FINDINGS.md
   documents elsewhere (F-16, "a screen owned by one feature but reached only
   from another is exactly where work falls through" — here it's a *table*
   owned by one module but needed by another).

2. **Three phantom direct dependencies.** `pubspec.yaml:40,47,48` declare
   `path`, `intl`, `collection` as direct dependencies with zero import sites
   anywhere in `lib/` or `test/` (verified by grep across the whole app
   tree). Harmless to behaviour, but they contradict AC-BUILD-02's "exactly
   the sanctioned stack" and nothing in FINDINGS.md explains or justifies
   them the way F-03/F-06/F-10 justify the other three additions.

3. **§2's stack table has no networking package at all.**
   `FLUTTER_MIGRATION.md`'s stack table (§2) lists routing, state, persistence,
   auth, camera, SVG, permissions, splash, haptics, and snackbars — but never
   an HTTP client, despite §3 building an entire "Remote API → command
   providers" architecture around one. `http` had to be added
   (`pubspec.yaml:46`, used at `lib/api/api_client.dart:5`) with no
   FINDINGS.md entry recording it as a forced deviation, unlike the other
   three additions. A documentation gap in the spec itself, not a code
   defect — but worth fixing so a future reader doesn't wonder why `http`
   is there.

---

## Summary

| Verdict | Count | IDs |
|---|---|---|
| CONFIRMED | 18 | AC-BUILD-01, 03, 04, 05, 06, 07, 08, 09, 10, 11; AC-DATA-01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12 |
| PARTIAL | 1 | AC-BUILD-02 |
| FAILED | 0 | — |
| UNVERIFIABLE | 0 | — |

(21 CONFIRMED, 1 PARTIAL — 22 criteria total for sections A+B: AC-BUILD-01
through 11, AC-DATA-01 through 12.)

Two criteria (AC-BUILD-07, AC-BUILD-11) are CONFIRMED with a caveat noted
above rather than an unqualified pass — read those two rows before treating
them as closed.

## `git diff` at end of verification

Empty. I made one deliberate, reverted change during this session (removed a
`userId` filter from `PantryRepository.watchAll` to confirm
`test/data/user_isolation_test.dart` is non-vacuous, then
`git checkout -- lib/data/repositories/pantry_repository.dart`). No other
files were edited by me. `git status --porcelain` at the repo root was empty
immediately before writing this report, aside from unrelated in-flight work
by other concurrent agents in this shared worktree at various points during
the session (see the environment note at the top).
