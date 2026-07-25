# Cross-wave findings

Issues surfaced by porting agents that don't belong to one wave. Recorded here so they
survive context compaction and get resolved before the final review, rather than being
lost in an agent report.

Status: `OPEN` needs action · `RESOLVED` done · `ACCEPTED` deliberate, no action

---

## F-01 — Brand SVGs contain `<filter>` elements `flutter_svg` cannot render
**Status:** OPEN · surfaced by: design-system agent · affects: AC-DS-07

All three vendored brand SVGs (`app/assets/brand/glean-b1-{icon,splash-logo,adaptive-foreground}.svg`)
contain `<filter>` elements that `flutter_svg` 2.3.0 does not support. It logs
`unhandled element <filter/>`, skips the filter and renders the rest. Almost certainly
drops an authored drop-shadow.

Not a crash, but it is a **silent visual regression against the RN app** and it spams the
console. Options: bake the shadow into the path/gradient at export time, or drop the filter
from the SVG and reapply it in Flutter (`BoxShadow`/`DropShadow`) where the mark is used.
Decide during the polish/verification wave — do not leave the warning in place.

## F-02 — Spec names a brand asset that does not exist
**Status:** RESOLVED (spec inaccuracy, not a code problem) · affects: AC-DS-07

`FLUTTER_MIGRATION.md` §2 cites `assets/source/glean-mark.svg`. No such file exists; the real
assets are the three `glean-b1-*.svg` files. Code uses the real ones and documents it.
The spec line is wrong, not the implementation.

## F-03 — `Override` is not importable from `flutter_riverpod` 3.3.2
**Status:** RESOLVED · surfaced by: design-system agent

**Resolution (orchestrator):** `riverpod` was promoted from a transitive to a **direct**
dependency in `app/pubspec.yaml`, so `import 'package:riverpod/misc.dart';` now gives the
`Override` type without tripping `depend_on_referenced_packages`. `List<Override>` can be
spelled explicitly again; the inline-literal workaround is no longer needed anywhere.
Verified: `misc.dart` does export `Override`; `riverpod.dart` does not.

The original diagnosis and the AUTH agent's correction are kept below for context.

---


`ProviderScope.overrides` documents its element type as `Override`, but that name does not
resolve as an import from `flutter_riverpod` 3.3.2, so a `List<Override>` cannot be written
explicitly. Worked around by letting the list literal infer. Harmless, but if a later wave
needs the explicit type, import it from `package:riverpod` directly rather than re-deriving
the workaround.

**Correction (AUTH agent):** the "import it from `package:riverpod` directly" suggestion
above doesn't actually work — `riverpod` is only a *transitive* dependency here (pulled in by
`flutter_riverpod`), not a direct one in `app/pubspec.yaml`, so importing
`package:riverpod/misc.dart` (the one entrypoint that does export `Override`) trips the
`depend_on_referenced_packages` lint, and `pubspec.yaml` is orchestrator-owned so no other
wave can add the dependency itself. The only clean fix is the original one: never spell
`Override`/`List<Override>` anywhere, and always construct the overrides list as an inline
literal at the exact `ProviderScope`/`ProviderContainer` call site (so Dart infers the
element type from the parameter's declared type) rather than from a variable or a
function with a declared return type. `test/features/meals/test_harness.dart:30` currently
writes `overrides: <Override>[...]` and fails `flutter analyze` with `non_type_as_type_argument`
as a result — drop the explicit `<Override>` type argument there (`overrides: [...]`) to fix it;
not touched here since it's outside the AUTH module's owned files.

## F-04 — Flutter has no `text-transform: uppercase`
**Status:** ACCEPTED · surfaced by: design-system agent

The RN `sectionLabel` style relied on CSS-style uppercasing. Flutter's `TextStyle` has no
equivalent, so any screen wanting that look must call `.toUpperCase()` on the string.
Documented in `theme.dart`. Feature agents must not reintroduce a wrapper widget for this.

## F-05 — `add_recipe_id` has no routing equivalent, by design
**Status:** ACCEPTED · surfaced by: router agent · affects: AC-MEAL-08, AC-PLAN-11

The RN app passed `add_recipe_id` as a nav param and re-added the recipe inside
`useFocusEffect`, which is the **duplicate-plan-entry bug** (§11): leaving the Plan tab and
returning re-added the recipe every time. §6 instead requires staying on the recipe after
"Add to plan" with the button reflecting "In plan", so add-to-plan is a same-screen mutation
with **no navigation and no param**. The Plan wave must not reintroduce the param.

## F-06 — `sqlite3_flutter_libs` is end-of-life upstream
**Status:** RESOLVED · affects: AC-BUILD-02

Its own pub description reads *"Not used anymore, update to version 3.x of package:sqlite3"*.
Native sqlite comes via `drift_flutter` instead. A forced deviation from the spec's literal
package list in §2; `drift_flutter` is the drift team's current Flutter integration package.

## F-07 — `category` stays nullable while `food_group` does not
**Status:** RESOLVED · affects: AC-BE-01, AC-DATA-11

The backend's first cut let an out-of-taxonomy LLM value coerce `category` to null, which made
`food_group` null too and left the meal-plan 422 reachable — the exact failure §9 exists to
remove. Now `food_group` is non-nullable and falls back to `"other"` (already a client-side
bucket, so zero client work), while `category` stays nullable to stay honest about an unknown
fine-grained category. Consequence the Pantry wave must handle: **expiry inference cannot fire
for a null category**, so it must degrade gracefully rather than assume a category is present.

## F-08 — The parse-endpoint contract is deliberately asymmetric
**Status:** RESOLVED · affects: AC-BE-04, AC-DATA-11, AC-PAN-01

**Every wave touching parsed ingredients must model it this way:**

| Field | Nullability | On absence |
|---|---|---|
| `food_group` | **non-nullable `String`** | contract violation — throw |
| `category` | **nullable `String?`** | fine, degrade |

The asymmetry is the point. `food_group` is what `POST /meal-plan` validates non-nullably, so it
is the field whose absence caused the 422; it always resolves, worst case to `"other"`.
`category` is finer-grained (pantry grouping detail, per-category shelf life) and its absence
degrades acceptably.

The API agent initially had this exactly inverted — `category` required and throwing, `food_group`
absent from the model altogether — which would have failed an entire 20-item receipt parse on one
unclassifiable item, i.e. worse than the bug §9 set out to fix. Corrected. Watch for this
inversion recurring in the data layer and the Pantry/Shop review flows.

## F-09 — Landing a real Meals screen breaks pre-existing router-owned tests that hard-code its placeholder
**Status:** RESOLVED (superseded by F-11) · surfaced by: meals agent · affects: AC-TEST-14, AC-MEAL-07/12

Landing the real `MealsScreen`/`SavedRecipeDetail` initially broke several `test/router/*.dart`
tests two ways: (1) a missing `theme:` in those tests' bare `MaterialApp.router(...)` — see F-11,
which covers this precisely (`StatefulShellRoute.indexedStack` builds every tab branch eagerly, so
this hits router tests that look unrelated to Meals too, e.g. `auth_redirect_test.dart`); and
(2) several assertions hard-coded the placeholder copy ("Meals screen", "Search recipes", "Recipe
42") this wave was explicitly asked to replace.

**Re-verified after F-11's fix landed: `flutter test test/router` now passes 21/21.** Both the
theme wiring (via `test/support/harness.dart`'s `AppTestHarness`) and the placeholder-text
assertions have already been updated by other agents — no action remains here. Left as a record of
what broke and why, since the same two-part collision (missing theme + stale placeholder-text
assertions) will recur for Pantry/Plan/Shop/Settings as their own waves land real screens; F-11's
`AppTestHarness` prevents the theme half project-wide, and the placeholder-text half needs the same
per-tab swap `test/router/*.dart` already did for Meals.

Additionally, `AppRoutes.mealsSearch` (`/meals/search`) is now **intentionally dead**: AC-MEAL-07
requires one inline search affordance inside the Meals tab's Search segment, not a separate pushed
screen, so nothing in `lib/features/meals/**` navigates to this route any more. The route itself
still exists in `router.dart` (out of this wave's remit) pointing at a stub `MealsSearchScreen`
that says as much. Recommended: the router owner should prune `AppRoutes.mealsSearch` and its
`GoRoute` entry once this wave lands, and drop `MealsSearchScreen`.

## F-10 — No `url_launcher` dependency for AC-MEAL-05's tappable source-url attribution
**Status:** RESOLVED · surfaced by: meals agent · affects: AC-MEAL-05, AC-SET-04

**Resolution (orchestrator):** `url_launcher` added to `app/pubspec.yaml`. Two waves hit this
independently — Meals for `source_url` attribution and Settings for Terms/Privacy — and in both
cases the clipboard fallback satisfied the criterion's letter while missing its point. §2's
package list was never meant to be exhaustive about utility packages; two acceptance criteria
genuinely require opening an external URL. Both waves have been asked to swap to `launchUrl`.

Original finding below.

**Meals side done:** `_SourceAttribution` in
`lib/features/meals/widgets/recipe_detail_view.dart` now calls
`launchUrl(uri, mode: LaunchMode.externalApplication)` instead of copying to the clipboard, with a
snackbar only on failure (bad URL or nothing installed to handle it). `flutter analyze`/`flutter
test` for `lib/features/meals` and `test/features/meals` stay clean — no test taps this row, so no
platform-channel mock was needed for `url_launcher` itself.

`pubspec.yaml` is orchestrator-owned (module contract), and §2 of the spec doesn't list
`url_launcher` among the sanctioned packages. AC-MEAL-05 asks for `source_url` to be "tappable
attribution" for imported recipes; with no way to open a browser, `RecipeDetailView`'s
`_SourceAttribution` row (`lib/features/meals/widgets/recipe_detail_view.dart`) instead copies the
link to the clipboard via `package:flutter/services.dart` (no new dependency) and shows a
confirmation snackbar. This satisfies "tappable" and "attribution" literally, but not "open the
original" in spirit. Recommended: add `url_launcher` to `pubspec.yaml` and swap the tap handler for
`launchUrl(Uri.parse(sourceUrl))` — a one-line change once the dependency exists.

## F-11 — `app.dart` doesn't wire `gleanLightTheme`, and it's no longer harmless
**Status:** RESOLVED

**Resolution (orchestrator), two parts:**

1. **Production:** `lib/app.dart` now defaults `theme` to `gleanLightTheme` and the bare
   `ColorScheme.fromSeed` fallback is **deleted**. A theme without the brand tokens was never a
   useful degradation — it is a crash one frame later — so the only default is the real one.
2. **Tests:** added `app/test/support/harness.dart` (`AppTestHarness`) as shared infrastructure.
   It pumps the real `goRouterProvider` over an in-memory drift database with `gleanLightTheme`
   applied, a `RecordingHaptics` by default, and a deliberately unroutable API base URL, plus
   `pumpAt()` and `dispose()`. It generalises the pattern the Meals agent had independently
   arrived at. **Every feature widget test should use it** rather than building its own — this
   finding recurring once per feature is exactly what it prevents.

A related consequence, also being fixed: `test/router/**` asserted on **placeholder screen copy**
(`find.text('Settings screen')`), which breaks as each real screen lands. Those assertions are
being made structural instead — routing correctness must not depend on any screen's copy.

Original finding below.

**Status:** OPEN · surfaced by: AUTH agent · affects: AC-DS-02/03, `test/router/**`, every feature screen

`lib/app.dart`'s own doc comment already flags this as a known gap: `GleanApp.theme` defaults to a
bare `ThemeData(colorScheme: ColorScheme.fromSeed(...))` fallback because design-system didn't exist
yet when it was written, with a note to wire `gleanLightTheme` in "once it does."

Design-system has landed since, and its `context.tokens` extension (`lib/design_system/tokens.dart`)
is not merely cosmetically wrong without it — it's a hard crash. `AppTokensX.tokens` asserts
`Theme.of(this).extension<AppTokens>() != null`, and Flutter's test binding runs with assertions
enabled, so **any widget that reads `context.tokens` while mounted under a theme with no
`AppTokens` extension throws an `AssertionError` during build** (verified directly: a bare
`MaterialApp(home: Builder(builder: (c) => Text('${c.tokens.spacing.md}')))` throws). This is not
theoretical — `test/router/*.dart` pumps `MaterialApp`/`MaterialApp.router` **with no `theme:` at
all**, bypassing `GleanApp`/`app.dart` entirely, and:

- `SignInScreen` (AUTH, this wave) uses `context.tokens` — throws under that harness.
- `SettingsScreen` and the onboarding flow (Settings wave) already use `context.tokens`
  throughout — same landmine, already present before this wave touched anything.

Running `flutter test test/router` today shows failures in `auth_redirect_test.dart`,
`route_table_test.dart` (`sign-in resolves outside the shell`, `each tab branch root renders its
placeholder`), `tab_stack_test.dart`, and `error_handling_test.dart`. Some of those (e.g. Settings'
placeholder text no longer matching `find.text('Settings screen')` because a real screen now
exists) are a separate, unrelated staleness issue in the same test file — but the sign-in one **is**
this theme crash, confirmed by isolating `SignInScreen` alone under a themeless `MaterialApp` in a
throwaway test.

**Fix (not made here — `lib/app.dart` and `test/router/**` are Router-owned, not AUTH's):**
1. `lib/app.dart`: pass `theme: gleanLightTheme` (from `package:glean/design_system/design_system.dart`)
   instead of the bare fallback.
2. `test/router/*.dart`: every `MaterialApp`/`MaterialApp.router(...)` construction needs
   `theme: gleanLightTheme` too, since those tests build their own widget tree independent of
   `GleanApp`.

Until this lands, **any** feature screen using `context.tokens` will fail when exercised through
the router's own test harnesses — this is not specific to AUTH's `SignInScreen`, and will resurface
for Meals/Plan/Pantry/Shop the moment their real screens replace today's plain-text placeholders.

## F-12 — drift stream cleanup hangs widget tests under FakeAsync
**Status:** OPEN (needs the harness note applied per-wave) · surfaced by: meals agent
**Affects:** every feature widget test that touches a drift stream

`testWidgets` runs inside a FakeAsync zone. drift's `StreamQueryStore` defers stream-cancellation
cleanup through a **real** `Timer.run()`, which FakeAsync never services. The symptom is either a
hang or:

```
A Timer is still pending even after the widget tree was disposed.
Pending timers: Timer (duration: 0:00:00.000000, periodic: false)
```

The zero duration is the tell — it is `Timer.run()`, **not** an app-level debounce. Two waves hit
this independently and one initially mistook it for a leaked auto-save timer.

**Fix:** wrap any direct `repository.watchXxx(...).first` (or similar stream read) in a widget test
with `tester.runAsync(...)`, which escapes the FakeAsync zone so the cleanup timer can fire. This
is a **test-harness** issue, not a production defect — no fix belongs in `lib/`.

Watch for the misdiagnosis: an auto-save or debounce timer in the widget under test is the obvious
suspect and the wrong one. Check the pending timer's *duration* first — a real debounce shows its
configured duration, this shows zero.
