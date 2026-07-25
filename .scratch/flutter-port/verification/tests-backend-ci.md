# Independent verification — Testing (§10 / M), Backend (§9 / L), CI & cutover (§8 / N)

Verifier: independent agent, wrote none of this code. Method: attempt to **falsify** each
criterion. Nothing was fixed; two contract tests and two repository invariants were
deliberately broken to prove they bite, then restored exactly.

**Environment limits.** No Xcode, Android SDK, Java or Ruby on this box. `flutter build`,
`integration_test` *execution* and the Fastlane lanes are therefore `UNVERIFIABLE (needs a
Mac/SDK)` and were inspected for correctness instead. `flutter analyze`, `flutter test`
(unit+widget), `dart format`, `build_runner`, the backend suite and `pre-commit` all run here
and were executed for real.

---

## ⚠ Precondition breach — the tree is not green

ACCEPTANCE.md's rules of the loop: *"Verification runs against a green tree: `flutter analyze`
clean and `flutter test` passing are preconditions for any tick (AC-BUILD-04/05)."*

```
$ cd app && flutter analyze
No issues found! (ran in 0.5s)          # exit 0 — AC-BUILD-04 holds

$ cd app && flutter test
00:10 +341 -2: Some tests failed.        # exit 1 — AC-BUILD-05 FAILS
Failing tests:
  test/data/pantry_repository_test.dart:
    PantryRepository addItems (review-screen commit, AC-PAN-10)
    a failure partway through persists nothing, so retrying cannot double quantities
  test/features/intake/review_screen_test.dart:
    ReviewScreen save is atomic: a mid-batch failure persists nothing,
    and retrying does not double (AC-PAN-10)
```

Both failures are AC-PAN-10 (section F, Pantry — another verifier's remit), not mine. The
mechanism, for the record: `PantryRepository.addItems`
(`app/lib/data/repositories/pantry_repository.dart:223-245`) wraps the per-row loop in
`_db.transaction(...)`, but the assertion `expect(await repository.watchAll(userId).first,
isEmpty)` observes a persisted row after the rollback — i.e. the transaction does not actually
roll back what `addItem` → `_ingredients.resolveOrCreate` wrote, so AC-PAN-10's atomicity claim
is not met as tested. Reported here only because it blocks every tick below; the fix is not mine.

**Consequence:** every `CONFIRMED` below is conditional on that being fixed. I have marked
verdicts on their own merits, since the two failures are causally unrelated to sections L, M
(except AC-TEST-03/05's counts) and N.

---

## L. Backend change (§9) — verified directly

Commands run from the repo root, from a clean tree:

```
$ make test-backend
256 passed, 1 warning in 0.44s
Required test coverage of 80% reached. Total coverage: 91.12%      # exit 0

$ make lint-backend
ruff check    → All checks passed!
ruff format   → 83 files left unchanged
ty check      → All checks passed!
vulture       → (no output)                                        # exit 0, tree unchanged
```

### AC-BE-01 — CONFIRMED

All three parse endpoints return `category` per parsed ingredient, plus a derived `food_group`:

- `POST /receipts/scan` and `POST /receipts/describe` both declare
  `response_model=ScanResponse` (`backend/src/glean/receipts/router.py:17,37`) →
  `ScanResponse.items: list[ParsedIngredient]`, and `ParsedIngredient` gains
  `category` at `backend/src/glean/receipts/schemas.py:86-89` plus a `food_group`
  `@computed_field` at `:105-117`.
- `POST /shopping/parse-description` returns `ShoppingParseResponse` →
  `ShoppingProposalItem`, which now **inherits** from `ParsedIngredient`
  (`backend/src/glean/shopping/schemas.py:14`) rather than declaring its own free-form
  `category: str | None`. So all three share one field definition — the vocabulary cannot
  drift between endpoints.

Both LLM prompts are built from the taxonomy dict rather than hand-copied
(`receipts/service.py:20-22,38,47`; `shopping/service.py:16-19,31`), so prompt text cannot
drift from the `Literal` the response schema enforces.

### AC-BE-02 — CONFIRMED (no new vocabulary)

`INGREDIENT_CATEGORY_FOOD_GROUPS` (`receipts/schemas.py:11-35`) holds exactly 23 entries, and
they match `app/lib/data/seed/taxonomy.dart`'s `ingredientCategorySeeds` key-for-key and
food-group-for-food-group. Enforced two ways, not asserted:

- `backend/tests/receipts/test_schemas.py:57-64` — `test_taxonomy_has_23_categories` and
  `test_taxonomy_matches_the_mobile_client_exactly` (against a duplicated literal).
- `backend/tests/receipts/test_schemas.py:67-71` —
  `test_taxonomy_matches_ingredient_category_literal` guards the hand-written `Literal`
  (`schemas.py:41-65`, hand-written because `ty` cannot evaluate a dynamic tuple) against
  drifting from the dict.
- `app/test/data/taxonomy_contract_test.dart` — parses **both files as text** and cross-checks
  them, including an explicit `expect(backend.length, 23)`.

The only value outside the 23 is the `food_group` fallback `"other"`, which is not new
vocabulary: it is the pre-existing client-side bucket
(`app/lib/data/repositories/pantry_repository.dart:147` `_uncategorisedFoodGroup = 'other'`).

### AC-BE-03 — CONFIRMED

New-field coverage exists on all three endpoints and the suite passes (256 tests):

| Endpoint | Test |
|---|---|
| `/receipts/scan` | `tests/receipts/test_router.py:67-70` (`category`+`food_group` on both items); `:154-190` out-of-taxonomy fallback |
| `/receipts/describe` | `tests/receipts/test_router.py:143-147` |
| `/shopping/parse-description` | `tests/shopping/test_router.py:54-56` (full body equality incl. `food_group`); `:65-96` out-of-taxonomy fallback; `tests/shopping/test_service.py:58-60,95-96,99-121` |

Plus `tests/receipts/test_schemas.py` (170 lines, new) covering the derivation for all 23
categories parametrically, null-category → `"other"`, `food_group` not settable directly,
fallback observability via `caplog`, and `food_group` never null across every input shape.

### AC-BE-04 — CONFIRMED (client persists the category)

`category` survives from wire to DB, not dropped in transit:

- Wire model: `app/lib/api/models/parsed_ingredient.dart:50` reads `json['category']`.
- Both intake paths carry it into the review draft:
  `lib/features/intake/scan_progress_screen.dart:61` and
  `lib/features/intake/pantry_describe_screen.dart:35` (and
  `shop_describe_screen.dart:41`), each `category: response.items[i].category`.
- Committed to the DB: `lib/features/intake/review_screen.dart:130` (pantry,
  `category: row.category!`) and `:155` (shop) → `PantryRepository.addItem`
  (`pantry_repository.dart:186,193`) → `IngredientsRepository.resolveOrCreate`, which writes
  it (`ingredients_repository.dart:53` `category: Value(category)`) and even *upgrades* a
  previously-null category on a later sighting (`:73-82` `_upgradeCategoryIfNeeded`).
- Asserted end-to-end against a real DB at
  `app/test/features/intake/review_screen_test.dart:223-270` — a null-category row is forced
  through the category picker and the persisted row's category is read back.

### AC-BE-05 — CONFIRMED, with one benign out-of-scope change noted

`git diff main..HEAD -- backend/` touches 11 files, +415/−20. Reviewed in full:

| File | Change | §9? |
|---|---|---|
| `receipts/schemas.py` | taxonomy dict, `Literal`, `category` field, out-of-taxonomy validator, computed `food_group` | yes |
| `receipts/service.py` | both prompts list the categories, built from the dict | yes |
| `shopping/schemas.py` | `ShoppingProposalItem` inherits `category`/`food_group` instead of its own free-form field | yes |
| `shopping/service.py` | prompt lists the categories | yes |
| `tests/receipts/{test_router,test_schemas}.py`, `tests/shopping/{test_router,test_service}.py`, `tests/receipts/fixtures/receipt_claude.json` | new/updated coverage; fixture gains categories; `"bakery"`→`"grains"`, `"snacks"`→`None` to fit the taxonomy | yes |
| `vulture_whitelist.py:19` | whitelists the new Pydantic validator | yes (mechanical) |
| **`recipes/ingredient_parser.py:9-11`** | **comment-only**: repoints `mobile/src/normalization/units.ts` → `app/lib/data/util/unit_normalization.dart` | **no — cutover doc hygiene** |

The `ingredient_parser.py` hunk is the only change not sanctioned by §9. It is a **comment
repoint with zero runtime effect**, necessitated by AC-CUT-01 deleting the files the old comment
cited. I judge this in-scope for the cutover rather than a rogue behaviour change, but flag it
so the record is accurate. No route, no dependency, no auth, no rate-limit, no LLM-routing and
no other schema was touched.

One genuine behaviour change inside the §9 envelope, worth stating explicitly since it is a
*tightening*: `/shopping/parse-description`'s `category` was previously any string (the old
tests used `"bakery"`, `"snacks"`) and is now constrained to the 23-value `Literal` with
out-of-taxonomy → `null`. That is precisely what §9 asks for ("drawn from the **existing**
23-category taxonomy — not a new vocabulary"), and it strictly improves the client, whose
ingredient-category FK would reject a free-form value.

### F-07 / F-08 asymmetry — CONFIRMED end to end; the meal-plan 422 path is genuinely closed

| Field | Backend | Client | Verified |
|---|---|---|---|
| `food_group` | **non-nullable**, computed, falls back to `"other"` (`receipts/schemas.py:105-117`) | **non-nullable `String`** (`api/models/parsed_ingredient.dart:66`); `fromJson` **throws `FormatException`** on absent/empty (`:38-43`) | `tests/receipts/test_schemas.py:161-170` — `food_group` never null across all 25 input shapes |
| `category` | **nullable**, out-of-taxonomy coerced to `null` and logged (`:91-104`) | **nullable `String?`** (`parsed_ingredient.dart:76`) | `tests/receipts/test_schemas.py:104-121`; fallback is `logger.warning`-observable so it cannot silently become the common case |

The asymmetry is the right way round (F-08 records that the API agent initially had it
inverted). The 422 path is closed with no cast bypass anywhere in the chain:

`ingredient_categories` join coalesces to `'other'`
(`pantry_repository.dart:147,168`) → `PantryItemView.foodGroup` is a non-nullable `String`
(`data/models/pantry_item_view.dart:45`) → passed straight through
(`features/plan/compression.dart:78 foodGroup: item.foodGroup`, no `as`/`!`) →
`CompressedPantryItem.foodGroup` is a non-nullable `String`
(`api/models/meal_plan.dart:20`) → serialised at `:28` → backend's
`CompressedPantryItem.food_group: str` (`meal_plan/schemas.py:11`).

Directly reproduced as a regression test in both directions:
`tests/receipts/test_schemas.py:124-158` constructs a real `CompressedPantryItem` from a
`ParsedIngredient` for both a categorised (`"poultry"` → `"protein"`) and an *uncategorised*
(`None` → `"other"`) ingredient, and both pass Pydantic validation. Confirmed there is **no**
`# type: ignore`, `as String` or `!` on this path.

---

## M. Testing (§10)

### AC-TEST-01 — CONFIRMED

Exactly one in-memory fixture: `createTestDatabase()` at `app/test/data/fixture.dart:12-14`.
Grepping `NativeDatabase.memory()` across the whole `test/` tree returns that single call site.
15 files import it; `test/support/harness.dart:41` builds the widget-test harness on top of the
same fixture rather than a second one. The RN suite's five copy-pasted `makeDbMock` harnesses
have collapsed to one, as §10 required.

### AC-TEST-02 — CONFIRMED

No test asserts a query-builder call shape. `grep -n "verify\|Mock" test/data/*.dart` returns
**nothing** — every data-layer test reads outcomes back from the real in-memory DB. `mocktail`
(`app/pubspec.yaml:65`, dev-only) is used exclusively for `MockHttpClient` (12 files, HTTP
layer) and `MockAppAuthGateway`/`MockCognitoAuthClient`
(`test/auth/support/fakes.dart`). Every `verify()` call site inspected —
`test/api/glean_api_client_test.dart`, `test/features/plan/plan_screen_test.dart:507`,
`test/features/plan/generate_week_controller_test.dart:250`,
`test/auth/cognito_auth_client_test.dart` — asserts against the mocked HTTP client or auth
gateway. Mocking a network boundary is a different thing from what this criterion prohibits, and
no DB is mocked anywhere.

### AC-TEST-03 — PARTIAL (real counts differ from the plan; intent exceeded)

| Bucket | Target | Actual | Δ |
|---|---|---|---|
| Unit | 28 | **34** | +6 |
| Widget | 14 | **36** | +22 |
| Integration | 1 | **1** | 0 |
| **Total** | **43** | **71** | **+28** |

Classified by whether the file drives a widget tree (`testWidgets(` or `harness.dart`'s
`@isTest`-annotated `gleanWidgetTest(` wrapper — a naive `testWidgets(` grep undercounts by 2
files that only call the wrapper). Shared infrastructure
(`support/harness.dart`, `data/fixture.dart`, `auth/support/fakes.dart`,
`features/intake/support/fake_receipt_camera.dart`) excluded.

Reported, not accepted as a pass: the literal target in the criterion's own text is **not met**.
My judgment is that this is over-provision rather than a shortfall, and that coverage intent is
met — §10's "New coverage this spec requires" adds 10 mandatory scenarios that were never part
of the 28/14/1 Jest-derived tally and land mostly as new widget tests through `AppTestHarness`.
But the count should be corrected in ACCEPTANCE.md rather than the box ticked as if 28/14/1 were
achieved. Also note the two failing tests above mean the suite is not "every test passing and
none skipped".

### AC-TEST-04 — CONFIRMED

All 12 dropped artefacts are absent, and none has a disguised Flutter counterpart.

7 Jest files, each confirmed absent from the current tree:
`tests/shop/use-swipe-action.test.ts`, `tests/platform/haptics.test.ts`,
`tests/db/client.test.ts`, `tests/navigation/shop-routing.test.tsx`,
`src/__tests__/screens/SplashScreen.test.tsx`, `tests/flows/receipt-checkout.test.ts`,
`tests/auth/ci-auth-bypass.test.ts`.

5 Maestro helpers, filenames resolved from history (`git show 906c9bb^ --stat -- mobile/e2e`)
and all confirmed absent: `e2e/launch.yaml`, `e2e/navigate-tab.yaml`,
`e2e/grant-camera-permission.yaml`, `e2e/helpers/airplane-mode-enable.js`,
`e2e/helpers/airplane-mode-disable.js`.

The disguised-port check that mattered most: `test/design_system/swipe_to_delete_test.dart`
drives a real `tester.drag` against `Dismissible` and asserts outcomes (deleted / not deleted,
haptic fired / not), rather than reimplementing the dropped `use-swipe-action.test.ts`'s manual
`translationX`/`velocityX` threshold arithmetic. `haptics_test.dart` and
`release_entrypoint_test.dart` are the *sanctioned replacements* for the dropped
`haptics.test.ts` / `ci-auth-bypass.test.ts` (§10 asks for both at a different level); they
reference the originals only in doc comments.

### AC-TEST-05 — PARTIAL — one named port is missing

Confirmed present and faithful:

| Port | File |
|---|---|
| meal-plan compression (urgency + top-N) | `test/features/plan/compression_test.dart` |
| meals / plan / settings presentation | `test/features/meals/presentation_test.dart`, `test/features/plan/presentation_test.dart`, `test/features/settings/settings_presentation_test.dart` |
| shopping shortfall across servings | `test/data/shopping_repository_test.dart:129-311` (explicit "3 servings × 100g → 250g shortfall" case) |
| auth-mode logic | `test/auth/auth_mode_test.dart` |

**Missing: unit normalization** — the first item named in the criterion. `normalizeUnit`
(`app/lib/data/util/unit_normalization.dart:82-129`, which implements exactly the kg→g, L→ml and
cup-of-flour→g-by-density conversions the criterion lists) **is imported by no test at all**:

```
$ cd app && grep -rn "unit_normalization\|normalizeUnit" test/ integration_test/
(no output)
```

The RN original (`mobile/src/normalization/units.test.ts`) called it directly with explicit
`canonicalUnit` arguments. The nearest Flutter test,
`test/data/pantry_repository_test.dart:133-153`, goes through the repository and its own comment
documents that **no conversion occurs** — it adds flour in `kg` and asserts
`expect(items.single.unit, 'kg')`. So the lookup and density branches are covered by nothing.
This is a genuine gap against a criterion that names the port explicitly, not a technicality.

### AC-TEST-06 — CONFIRMED (non-negotiable; break/restore performed)

`test/features/shop/checkout_test.dart:36-90` asserts exactly the specified scenario — a receipt
resolving 4 of 12 checked rows removes those 4 and leaves 8.

Falsification transcript:

1. Baseline: `flutter test test/features/shop/checkout_test.dart` → 3/3 pass.
2. Regression introduced in `ShoppingRepository.resolveCheckout`
   (`app/lib/data/repositories/shopping_repository.dart`): removed the
   `ingredientId.isIn(resolvedIngredientIds)` clause, so it deletes every checked row —
   reproducing RN's `completeCheckout` data-loss bug verbatim.
3. Red: `Expected: <4>  Actual: <12>`.
4. Reverted the clause; re-ran → 3/3 pass; `git diff --stat` on that file → empty.

The test would fail if the behaviour regressed. Confirmed, not assumed.

### AC-TEST-07 — CONFIRMED (non-negotiable; break/restore performed)

`test/data/user_isolation_test.dart` — 6 tests covering pantry, recipes, plan entries and
shopping-list cross-user invisibility, plus that the *ingredient catalogue* is deliberately
shared, plus that writes scoped by `(id, userId)` cannot cross users.

Falsification transcript:

1. Baseline: 6/6 pass.
2. Regression in `PantryRepository.watchAll`
   (`app/lib/data/repositories/pantry_repository.dart`): removed
   `..where(_db.pantryItems.userId.equals(userId))`.
3. Red: 2 failures — `"user A's pantry is invisible to user B"`
   (`Expected: empty, Actual: [PantryItemView]`, i.e. a real cross-user leak) and the
   shared-ingredient test (`Bad state: Too many elements`).
4. Reverted; re-ran → 6/6 pass; `git diff --stat` on that file → empty.

### AC-TEST-08 — CONFIRMED

All five destructive actions assert **data restoration**, not merely that a snackbar appeared:

| Action | Evidence |
|---|---|
| Pantry item | `test/features/pantry/pantry_screen_test.dart:63-103` — delete, assert empty, tap Undo, assert `hasLength(1)` |
| Shopping row | `test/features/shop/shop_screen_test.dart:88-119` |
| Plan entry | `test/features/plan/plan_screen_test.dart:293-363` — undo restores the entry with `servings: 3` intact **and** the cascaded shopping row |
| Recipe | `test/features/meals/meals_screen_test.dart:77-140` — undo re-saves it; the referencing plan-entry snapshot asserted unaffected throughout (AC-MEAL-03) |
| **"Cooked" delta** | `test/features/plan/plan_screen_test.dart:365-419` — pantry quantity `500 → 300` on cook, `→ 500` exactly on undo. Repository-level equivalents at `test/data/plan_repository_test.dart:387-470`, including a floor-at-zero edge case |

### AC-TEST-09 — CONFIRMED

`test/data/plan_repository_test.dart`: week scoping `:62-95`; per-week capacity `:154-193`
(comment explicitly contrasts with RN's lifetime lockout); cooked-frees-slot `:195+`;
**rollover idempotency `:275-304`** — runs `rolloverUncookedMeals` twice and asserts
`hasLength(1)`, not 2; never-moves-cooked `:306-331`. I scrutinised the idempotency test as
instructed and it is not tautological: the implementation is an
`UPDATE ... WHERE plannedDate < currentWeekStart`, so on the second run the predicate genuinely
no longer matches the row it just moved — the test is exercising real behaviour, not a
reimplementation of it. Bidirectional week pagination at
`test/features/plan/plan_screen_test.dart:79-185` (Previous/Next, content swap asserted both
ways).

### AC-TEST-10 — CONFIRMED

Expiry inference from category: `test/data/pantry_repository_test.dart:25-42` — berries, 4-day
shelf life, exact resulting date asserted. Parsed category persists:
`test/features/intake/review_screen_test.dart:223-270` — a null-category item is forced through
the picker and `expect(saved.category, 'leafy_greens')` is read back from the real DB, with
expiry inference firing as a consequence.

### AC-TEST-11 — CONFIRMED

Preview-not-save: `test/features/meals/meals_search_test.dart:112-152` — tapping a search result
renders the preview (`Not suitable for`) while `recipes.watchSaved(...)` stays **empty**; only
the explicit bookmark tap persists. Recipe deletion (keeping the plan-entry snapshot) covered by
`test/features/meals/meals_screen_test.dart:77-140`, as above.

### AC-TEST-12 — CONFIRMED

`test/features/settings/settings_screen_test.dart:146-346`. No `find.text('Save')` anywhere in
the file (there is no Save button to tap). Slider commits once on **release**, not per drag
frame (verified via haptic call counts, which also serves AC-SET-02). The debounce test at
`:329-346` changes a value, pumps 700 ms and reads it back from the repository directly with no
button tap; `:296-327` is the counterpart asserting an invalid value never persists.

### AC-TEST-13 — CONFIRMED

`test/design_system/haptics_test.dart` asserts the three-weight ladder exists and records in
order (`:8-22`), that `heavyImpact`/`vibrate` are absent — via a scan of the implementation
source, so a future call site cannot slip in (`:24-42`, also serving AC-HAP-02) — and that
`SystemHaptics` is the production default (`:44-50`). The "right weight for the right action"
half is necessarily asserted at feature level (9 files assert specific `HapticWeight` values per
action), which is correct: the design system has no notion of "delete" or "tab switch".

### AC-TEST-14 — CONFIRMED

`test/router/route_table_test.dart` asserts structure only: branch count, unique route names,
intake routes resolving *outside* the shell, widget **type** identity per route
(`PantryScreen`, `MealsScreen`, …), and `NavigationBar` absence during intake/sign-in. F-11's
placeholder-copy problem is resolved: sweeping all of `test/router/**` for `find.text(` yields
only `tab_stack_test.dart:31` (the tab bar's own stable label, router-owned copy) and
`typed_params_test.dart:105` (a genuine error-recovery message for a missing nav param). No
`find.text('Settings screen')`-style stale assertions remain.

### AC-TEST-15 / AC-TEST-16 — CONFIRMED (source) · UNVERIFIABLE (execution — needs a Mac/SDK)

`app/integration_test/app_test.dart` runs against `main_e2e.dart` and covers, in order: launch →
five tabs visible (mirrors `smoke.yaml`'s five `assertVisible`s) → navigate each tab asserting
its own heading → **camera-permission handling** with a mandatory back affordance in whatever
permission state the device starts in (folds in `scan-progress.yaml`'s intent, AC-TEST-16 and
AC-PAN-13) → **add an item via manual entry** through the `+` sheet — the path that was dead
code in the RN app — → asserts the item appears back on Pantry via the live drift stream with no
invalidation call. Compared against `git show 906c9bb^:mobile/e2e/smoke.yaml` and
`…:mobile/e2e/scan-progress.yaml`: intent is fully covered. Correctly avoids `pumpAndSettle()`
throughout for F-13's documented reason. Cannot be executed here — no emulator or simulator.

### AC-TEST-17 — CONFIRMED

```
$ grep -rn "RouteObserver\|didPopNext\|useFocusEffect\|onFocus\|FocusEffect\|RouteAware" test/ lib/
(no output)
```

No focus/lifecycle callback is shimmed to force a reload, in tests or in app code — the shim's
reason disappeared with drift `.watch()`, as §10 predicted.

### AC-TEST-18 — FAILED

There is no manual pre-release checklist anywhere in the repository. Searched
`docs/project-status.md`, `docs/mobile-replit-reconciliation-audit.md`, `app/README.md`, root
`README.md`, and grepped the whole tree for "airplane" / "checklist" / "pre-release". The only
hits are the three **planning** documents that record the *decision* that this flow stays manual
— `FLUTTER_MIGRATION.md:314`, `.scratch/flutter-port/ACCEPTANCE.md:196`,
`.scratch/flutter-port/issues/16-test-migration-strategy.md:55`. None of them, and no other
file, is a checklist a release engineer would work through.

The criterion asks for the flow to be *"recorded as a manual pre-release checklist item"*. The
decision is recorded; the artefact does not exist. Since `mobile/e2e/manual/error-states.yaml`
was deleted with the RN app, the airplane-mode coverage has been dropped without a replacement
of any kind — this is a real gap, not a wording quibble.

### AC-TEST-19 — CONFIRMED (both contracts broken and restored)

Two contract tests, both proven to bite:

**Redirect URI** (`app/test/auth/redirect_uri_contract_test.dart`) — asserts
`CognitoAuthClient.redirectUri == 'glean://auth/callback'` **and** that
`backend/template.yaml` contains it. Broke the backend side
(`template.yaml:102` `glean://auth/callback` → `glean://auth/broken`); test went red with
`Which: does not contain '- glean://auth/callback'`. Restored via `git checkout --`; green.
The value is genuinely present at `backend/template.yaml:102` under the app client's
`CallbackURLs`.

**Taxonomy** (`app/test/data/taxonomy_contract_test.dart`) — parses the backend Python and the
Dart seed file as text and cross-checks category sets, per-category food group, and the count
of 23. Broke the client side (`app/lib/data/seed/taxonomy.dart:38`, `CategorySeed('dairy',
'dairy', 7)` → `'protein'`); test went red with
`Actual: ['dairy: backend food_group="dairy" vs flutter foodGroup="protein"']`. Restored; green.
It also self-checks its own parsers (`expect(backend.length, greaterThanOrEqualTo(20))`) so a
regex that stops matching fails loudly instead of vacuously passing — the failure mode that
made the RN suite's dropped `receipt-checkout.test.ts` tautological.

Both files verified byte-identical to `HEAD` afterwards.

---

## N. CI, release & cutover (§8)

### AC-CI-01 — CONFIRMED

`.github/workflows/flutter-ci.yml` — two Linux jobs, both `runs-on: ubuntu-latest`:
`analyze` (`:23-40`: `dart format --set-exit-if-changed`, then `flutter analyze`) and
`test` (`:42-59`: `flutter test`). Triggers at `:8-17` are `push` (branches `[main]`) and
`pull_request`, both path-filtered to `app/**` + the workflow itself.

Two jobs rather than the one the criterion's wording implies, which I judge to satisfy it — both
are Linux, both on push, and between them they run `flutter analyze` + `flutter test`. The
unit+widget scoping is correct and load-bearing: `flutter test` with no path only walks `test/`,
never the sibling `integration_test/` directory (comment at `:56-58` states this, and it is
true of Flutter's test runner).

**Caveat:** this job is currently red in substance — `flutter test` fails on the two AC-PAN-10
tests (see the precondition section above), so the workflow as written would fail on `main`
today.

### AC-CI-02 — CONFIRMED

`.github/workflows/flutter-integration.yml:32-33` — the entire trigger block is:

```yaml
on:
  workflow_dispatch:
```

No `push`, no `pull_request`, no `schedule` anywhere in the file (verified by reading all 148
lines). Exactly two jobs, correctly split:

- `ios-integration` (`:48-83`) — `runs-on: macos-latest`, boots a simulator via
  `xcrun simctl list devices available -j | jq … | head -n1` then `xcrun simctl boot`, and runs
  `flutter test integration_test/app_test.dart -d "$DEVICE_ID"`. Fails loudly if no iPhone
  simulator is found (`:70-73`) rather than silently passing.
- `android-integration` (`:85-147`) — `runs-on: ubuntu-latest` with an explicit **KVM enable**
  step (`:105-109`, the `99-kvm4all.rules` udev rule) plus an AVD cache and
  `reactivecircus/android-emulator-runner@v2` at API 35 / `x86_64` / `pixel_7`.

Neither runs on push, and the macOS job does **not** attempt Android emulation — the §8 claim
about nested virtualization is not self-contradicted. Both pass inert placeholder
`--dart-define`s (`:37-45`) so no secrets are needed.

### AC-CI-03 — CONFIRMED

`app/README.md` "Running it locally" gives both, explicitly from one machine: an iOS block
(`open -a Simulator`, `xcrun simctl list devices available`, `flutter test … -d <UDID>`) and an
Android block (`flutter test … -d emulator-5554`), prefaced by *"Both platforms are runnable from
**one Mac** — real Apple Silicon isn't subject to the CI nested-virtualization limitation
below."* The workflow header repeats it at `flutter-integration.yml:21-24`. `make test-e2e`
(`Makefile`) is the parameterised repo-root equivalent.

### AC-CI-04 — CONFIRMED

| Lane | File | Target |
|---|---|---|
| iOS → TestFlight | `app/ios/fastlane/Fastfile:29-75` (`lane :beta`) | `upload_to_testflight` `:70-74` |
| Android → Play internal | `app/android/fastlane/Fastfile:28-69` (`lane :internal`) | `upload_to_play_store(track: 'internal')` `:64-68` |

Not wired into CI — `grep -rn 'fastlane\|bundle exec' .github/workflows/` returns **nothing**.
`match` is not used: `grep -n 'match' ` on both Fastfiles hits only `pubspec.match(/…/)` (a Ruby
regex call, `ios/Fastfile:22-24`) and prose in the header comment explaining *why* `match` is
skipped. iOS uses `app_store_connect_api_key` + Xcode automatic signing; Android requires a
local `key.properties` and fails fast with a helpful message if absent
(`android/Fastfile:29-37`).

### AC-CI-05 — CONFIRMED (implemented, not merely documented)

Both lanes query the store for the highest existing build number and increment it, rather than
trusting `pubspec.yaml`'s never-bumped local `+N`:

- iOS `ios/fastlane/Fastfile:47-52` — `app_store_build_number(api_key:, version:, live: false)`
  → `previous_build_number.to_i + 1`, passed to the build as
  `--build-number=#{build_number}` (`:59-62`). `live: false` is the right choice (asks
  TestFlight, not just the live App Store).
- Android `android/fastlane/Fastfile:47-51` —
  `google_play_track_version_codes(package_name:, track:)` → `(existing_codes.max || 0) + 1`,
  passed as `--build-number=#{version_code}` (`:59-62`). The `|| 0` handles the
  first-ever-upload case.

These are real action calls inside the release lane, on the path to the build command — not
comments. Cannot be executed here (no Ruby/Bundler/fastlane, no Xcode, no Android SDK):
**UNVERIFIABLE by execution**, verified by inspection.

### AC-CI-06 — PARTIAL

The deletions are real:

```
$ find . -iname "eas.json" -o -iname "eas-build.yml" | grep -v /.git/
(no output)
```

But the criterion says *"no EAS reference remains **anywhere**"*, and one non-exempt file still
presents EAS as current infrastructure — see the AC-CUT-01 finding below:

- **`docs/project-status.md:99`** — the "Tech stack" table row `| CI/CD | GitHub Actions, OIDC, **EAS** |`. Unlike the `Mobile` row at `:91`, which was correctly annotated *"(historical, pre-cutover)"*, this row carries no such marker and reads as current state.
- **`docs/project-status.md:71`** — under a live heading *"Still needed before first deploy"*: *"Add repository secrets: … `EXPO_TOKEN` (from expo.dev/accounts)"*. That is an actionable instruction to provision an Expo credential for a pipeline that no longer exists.
- `docs/project-status.md:100-101` likewise still list `jest-expo + maestro` (Testing) and `biome (mobile)` (Linting) as current.

The remaining EAS mentions I judge **acceptable**: `app/README.md:157` and the two Fastfile
comments (`ios:39`, `android:42`) say *"replaces what EAS used to provide silently"* — prose
explaining why the increment logic exists, which is exactly what §8 asked to be documented.

### AC-CUT-01 — FAILED

`mobile/` itself is gone (`ls mobile` → `No such file or directory`), and no RN/Expo file,
`package.json`, `eas.json` or Expo workflow remains. But the criterion's second half —
*"nothing in the repo references `mobile/`"* — does not hold. Excluding the three sanctioned
historical carve-outs (`.scratch/**`, `FLUTTER_MIGRATION.md`, `docs/superpowers/**`):

**`backend/README.md` still carries a whole live RN section** — `## Running the Mobile App
Locally` (from `:72`), which is not marked historical and which a reader would follow:

- `:76` — prerequisite *"[Expo CLI](https://docs.expo.dev/…) (`npx expo`)"*
- `:74` — prerequisite *"Node.js 18+"*
- `:116` — **`make start-mobile API_HOST=192.168.1.42`** — a target that no longer exists:
  ```
  $ make -n start-mobile
  make: *** No rule to make target 'start-mobile'.  Stop.
  ```
- `:120` — *"Scan the QR code with Expo Go, or press **a** if connected via USB/ADB."*

**`docs/project-status.md`** — the EAS/`EXPO_TOKEN`/jest-expo/biome rows detailed under AC-CI-06
above, plus `:53`'s `mobile-ci.yml` entry (that one *is* correctly annotated
*"(historical; removed post-cutover)"*, so it's fine).

**`docs/mobile-replit-reconciliation-audit.md`** — an entire non-exempt document written in the
present tense about `mobile/` paths (`:20-24` screen matrix citing
`mobile/app/(tabs)/pantry/index.tsx` etc.), with `:64-65` instructing the reader to run
`make test-mobile` / `make lint-mobile`, neither of which exists:
```
$ make -n test-mobile ; make -n lint-mobile
make: *** No rule to make target 'test-mobile'.  Stop.
make: *** No rule to make target 'lint-mobile'.  Stop.
```
It carries no superseded note at all (unlike `project-status.md`).

Minor: `.gitignore:2` still ignores `mobile_replit/`, harmless but vestigial.

These are documentation-only — no code, build or CI path is affected — but AC-CUT-01 is
explicitly about dangling references, and three non-exempt files contain them, two of them
naming Makefile targets that error out.

### AC-CUT-02 — FAILED

Every documented command I could execute, with real exit codes:

| Command | Exit | Note |
|---|---|---|
| `make help` | 0 | |
| `make setup-backend` | 0 | |
| `make setup-app` | 0 | |
| `make test-backend` | 0 | 256 passed |
| `make lint-backend` | 0 | ruff/ruff-format/ty/vulture clean |
| `make test-app` (= `flutter test`) | **1** | **2 failing AC-PAN-10 tests** |
| `make lint-app` (= `dart format` + `flutter analyze`) | 0 | |
| `cd app && flutter analyze` | 0 | `No issues found!` |
| `cd app && dart format --output=none --set-exit-if-changed lib test integration_test` | 0 | `Formatted 229 files (0 changed)` |
| `cd app && dart run build_runner build --delete-conflicting-outputs` | 0 | reproducible — no tracked file changed; **but** emits `W These options have been removed and were ignored: --delete-conflicting-outputs` |
| `make worktree-list` | 0 | |
| `git worktree prune -v` | 0 | |
| `make -n test` / `-n lint` / `-n pre-commit` | 0 | |
| `make pre-commit` (via `uv tool run pre-commit run --all-files`) | 0 | 6/6 hooks passed |
| **`make start-mobile API_HOST=…`** (`backend/README.md:116`) | **2** | **`No rule to make target`** |
| **`make test-mobile`** (`docs/mobile-replit…:64`) | **2** | **`No rule to make target`** |
| **`make lint-mobile`** (`docs/mobile-replit…:65`) | **2** | **`No rule to make target`** |
| `make start-ios` / `start-android` / `test-e2e` | — | UNVERIFIABLE (no Xcode/Android SDK). `make -n` confirms the arg-guard and `--dart-define` wiring are syntactically sound and the guard message matches the documented usage |
| `make start-backend` / `start-backend-docker` | — | not run (long-running servers); Docker 29.6.2 *is* present, so `start-backend-docker` is executable in principle; recipe reads correctly |
| Fastlane `bundle exec fastlane beta` / `internal` | — | UNVERIFIABLE (no Ruby/Bundler/fastlane) |

Three documented commands **do not work at all** — the `make start-mobile` / `test-mobile` /
`lint-mobile` invocations above. Two documented commands are stale in a lesser way: the
`--delete-conflicting-outputs` flag is obsolete in the pinned `build_runner` (it warns and
ignores), and it appears in `app/README.md`, `app/AGENTS.md` and this repo's guidance.

`make test-app` failing is the AC-PAN-10 defect rather than a documentation error, but it does
falsify `app/README.md`'s claim that `flutter test` runs *"unit + widget, nothing skipped"* as a
passing command.

Also noted, not a failure: `AGENTS.md`'s worktree section describes `make worktree-remove` as
cleaning *"node_modules + .venv"*; the recipe (`Makefile`) actually removes
`app/build`, `app/.dart_tool` and `backend/.venv`. The command works — only the prose is stale.

### AC-CUT-03 — CONFIRMED

`.pre-commit-config.yaml` covers Dart formatting and analysis and drops every RN hook.

```
$ uv tool run pre-commit run --all-files
ruff (legacy alias)......................................................Passed
ruff format..............................................................Passed
typos....................................................................Passed
vulture (dead code)......................................................Passed
dart format (write)......................................................Passed
flutter analyze..........................................................Passed
exit=0
```

`git status --short` was byte-identical before and after the run — no hook rewrote anything, so
the tree really is clean by the hooks' own standard, not just by the check-only variants.
(`commit-msg-policy` is `stages: [commit-msg]` and correctly does not run in `--all-files`.)

No RN hooks remain: `grep -iE 'eslint|prettier|biome|jest|expo|npm|node|tsc|knip|guard-text'`
over the config returns nothing — notably `scripts/guard-text-imports.mjs` is gone with
`AppText` (§4).

Two cosmetic observations on the Dart hooks, neither affecting correctness:

- `dart-format` runs `dart format` in **write** mode with `pass_filenames: false`, so its
  `exclude: ^app/.*\.(g|drift|mocks)\.dart$` is decorative — the entry formats `lib test
  integration_test` wholesale, generated files included. Harmless here (generated output is
  already format-clean, per the 0-changed run above), but the exclude does not do what it looks
  like it does. Note this also means the hook *writes* rather than *checks*, so it can leave
  staged/unstaged divergence — CI's `--set-exit-if-changed` variant is the real gate.
- The `ruff` hook id is pre-commit's legacy alias (it warns `ruff (legacy alias)`); `ruff-check`
  is the current id.

### AC-AUTH-07 — FAILED (the guard has a real false-negative; demonstrated)

`app/test/build/release_entrypoint_test.dart` exists, is a normal member of the `flutter test`
suite (so it does run in AC-CI-01's push-triggered job), and 5/5 pass at HEAD. Both real
Fastfiles do pass `-t lib/main.dart` (`ios/Fastfile:61`, `android/Fastfile:61`), as
`app/README.md` claims.

But the check does not actually catch the thing it exists to catch. **Falsification transcript:**

*Attempt 1 — realistic edit, guard fails to fire.* I changed the iOS lane's actual build target
to the bypass entrypoint, preserving the file's existing two-line Ruby string concatenation:

```ruby
    sh(
      'cd ../.. && flutter build ipa --release ' \
      "-t lib/main_e2e.dart --build-number=#{build_number}",   # ← was lib/main.dart
    )
```

Result — **the guard stayed green**:
```
$ flutter test test/build/release_entrypoint_test.dart
00:00 +5: All tests passed!
```
A signed TestFlight build produced from `lib/main_e2e.dart` — precisely what AC-AUTH-07 forbids
— passes CI unnoticed.

*Attempt 2 — same edit collapsed onto one line, guard fires.* Rewriting the same command as a
single-line `sh("cd ../.. && flutter build ipa --release -t lib/main_e2e.dart …")` does trip it:
```
00:00 +0 -1: ios/fastlane/Fastfile builds lib/main.dart, never main_e2e [E]
  ios/fastlane/Fastfile has a build invocation targeting main_e2e — exactly what
  AC-AUTH-07 forbids: [sh("cd ../.. && flutter build ipa --release -t lib/main_e2e.dart …")]
```

**Root cause — two independent weaknesses that combine:**

1. The violation predicate requires `flutter build` and `main_e2e` on the **same line**
   (`release_entrypoint_test.dart:68-73` and `:107-112`, both iterating
   `contents.split('\n')`). The Fastfiles' own build commands are multi-line Ruby string
   concatenations, so the target sits on a *different* line from `flutter build` — the shape the
   real files already use is the shape the check cannot see.
2. The complementary assertion `expect(contents, contains('lib/main.dart'))` (`:55-62`) is
   satisfied by the header comment (`:56-58`) and the `UI.message("… -t lib/main.dart")` line
   (`ios:54`), not by the build command. So it stays green even once the build command no longer
   mentions `lib/main.dart` at all.

Each alone would be survivable; together they mean the guard passes on a genuinely compromised
release lane. The same-line predicate is also applied to the workflow YAMLs (`:107-112`), so a
YAML using a block scalar (`run: |`) to split a build command across lines would evade it too.

Restored: `git checkout -- app/ios/fastlane/Fastfile`; `git diff` on that file empty; test back
to 5/5.

**Secondary gap, same criterion:** `flutter-ci.yml`'s path filter is
`app/**` + `.github/workflows/flutter-ci.yml` (`:11-17`). `release_entrypoint_test.dart` scans
*every* workflow YAML (`:95-113`), but a push that adds a `main_e2e` release build to, say,
`backend-deploy.yml` matches no path filter, so the job that would catch it never runs. Fastfile
edits are covered (they live under `app/`); other workflow files are not.

---

## Counts

| Verdict | Count | Criteria |
|---|---|---|
| **CONFIRMED** | **27** | AC-BE-01, 02, 03, 04, 05; AC-TEST-01, 02, 04, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 19; AC-CI-01, 02, 03, 04, 05; AC-CUT-03 |
| **PARTIAL** | **3** | AC-TEST-03 (counts 34/36/1 vs 28/14/1), AC-TEST-05 (unit-normalization port missing), AC-CI-06 (EAS live in `docs/project-status.md`) |
| **FAILED** | **4** | AC-TEST-18, AC-CUT-01, AC-CUT-02, AC-AUTH-07 |
| **UNVERIFIABLE (needs a Mac/SDK)** | — | `integration_test` *execution* (AC-TEST-15/16 source confirmed), Fastlane lane *execution* (AC-CI-04/05 inspected) |

Total distinct criteria assessed: **34** (AC-BE-01…05 = 5, AC-TEST-01…19 = 19, AC-CI-01…06 = 6,
AC-CUT-01…03 = 3, AC-AUTH-07 = 1). 27 + 3 + 4 = 34. (An earlier pass of this table misprinted
26/33 — corrected on a second, independent tally against the criterion-by-criterion sections
above.)

**Independent cross-verification.** A second verifier pass, run in parallel and blind to this
file's contents, classified the Dart test suite and re-derived AC-TEST-01 through AC-TEST-18
from scratch. It converged exactly on the two most consequential numeric/qualitative findings —
the real bucket counts (34 unit / 36 widget / 1 integration, vs. the planned 28/14/1) and the
AC-TEST-05 gap (`normalizeUnit` imported by no test) — and reached the same verdict on every
other AC-TEST criterion, including its own independent break/restore of AC-TEST-06 and AC-TEST-07
against the same two production files. Two unrelated passes reaching identical conclusions by
different routes is the strongest evidence available here short of a third opinion.

**Blocking, in priority order:**

1. **AC-AUTH-07** — the release-entrypoint guard passes on a compromised lane. This is the one
   finding with a security consequence: it is the *only* build-level barrier between the auth
   bypass and a TestFlight/Play upload, and I demonstrated it does not hold. Fix: match against
   the whole file (or a comment-stripped, line-joined form) instead of per-line, and assert
   `lib/main.dart` appears **on a `flutter build` line**, not merely somewhere in the file.
2. **AC-BUILD-05 / precondition** — 2 failing AC-PAN-10 atomicity tests keep the tree red, which
   blocks every tick and falsifies documented commands. (Section F's remit, not mine.)
3. **AC-CUT-01 / AC-CUT-02** — three documented `make` targets don't exist; `backend/README.md`
   still documents running the deleted Expo app.
4. **AC-TEST-18** — airplane-mode coverage dropped with no replacement artefact.
5. **AC-TEST-05** — `normalizeUnit` untested.

---

## Defects no criterion covers

**D-1 — `ingredients.canonical_unit` is never written, so pantry-side unit conversion is inert.**
`IngredientsRepository.resolveOrCreate` (`app/lib/data/repositories/ingredients_repository.dart:47-56`)
inserts `canonicalName`, `apiIngredientId`, `apiName` and `category` — **not** `canonicalUnit`.
No other write to that column exists anywhere in `lib/` (grep: reads only). `StapleSeed`
(`lib/data/seed/taxonomy.dart:52-58`) has no unit field either. Consequence:
`PantryRepository.addItem` calls
`normalizeUnit(canonicalUnit: ingredient.canonicalUnit, …)` (`pantry_repository.dart:195-200`)
with a permanently-null `canonicalUnit`, which takes `normalizeUnit`'s first early return
(`unit_normalization.dart:90-96`) and stores the user's raw unit unconverted. So a pantry
holding "2 kg flour" and "500 g flour" keeps two incompatible units for one ingredient.

Note this is narrower than "the function is dead code": `PlanRepository`'s mark-cooked path
*does* pass a real unit (`plan_repository.dart:235` `canonicalUnit: pantryRow.unit`), so the
lookup and density branches genuinely execute there. The defect is that the **ingredient
catalogue never establishes a canonical unit**, which is what the RN `units.test.ts` presumed and
what AC-TEST-05's missing port would have exposed. Same root cause as the AC-TEST-05 gap;
recorded separately because fixing the test alone would not fix the behaviour.

**D-2 — `docs/mobile-replit-reconciliation-audit.md` has no superseded marker.** Unlike
`docs/project-status.md`, which was given a dated note at `:5-10`, this document still reads as
current guidance for an app that no longer exists, and instructs the reader to run two
nonexistent Make targets. Either annotate it as historical or delete it. (Contributes to
AC-CUT-01 above, but the *inconsistency* between the two docs' treatment is its own defect.)

**D-3 — the `dart-format` pre-commit hook writes instead of checks, and its `exclude` is inert.**
`.pre-commit-config.yaml`'s `dart-format` hook uses `pass_filenames: false` with
`entry: … dart format lib test integration_test`, so its
`exclude: ^app/.*\.(g|drift|mocks)\.dart$` cannot filter anything the command touches, and the
hook mutates files rather than failing on them. Harmless today (generated output is already
format-clean) but it means a developer's commit can silently differ from what they staged, and
the exclude will mislead whoever next edits the config.

**D-4 — `--delete-conflicting-outputs` is obsolete in the pinned `build_runner`.** It emits
`W These options have been removed and were ignored` and is documented in three places
(`app/README.md`, `app/AGENTS.md`, and repo guidance). Cosmetic, but it is a documented command
that prints a warning every run.

**D-5 — concurrent tree modification observed during verification (informational, not a defect
in the port).** Partway through this pass, another process modified `app/pubspec.yaml` and
`app/pubspec.lock`, dropping `path`, `intl` and `collection` as direct dependencies. I verified
this is correct and harmless — `grep -rn "package:collection\|package:intl\|package:path/" lib/
test/ integration_test/` returns nothing, so all three were genuinely unused direct deps — and I
left the change in place rather than clobbering another session's work. It is recorded only so
that this report's `git status` is not mistaken for my own edits. Note my `flutter analyze` /
`flutter test` runs predate it.

---

## Final tree state

Everything I broke, I restored. Four deliberate regressions were introduced and reverted:
`backend/template.yaml` (redirect-URI contract), `app/lib/data/seed/taxonomy.dart` (taxonomy
contract), `app/lib/data/repositories/shopping_repository.dart` (AC-TEST-06),
`app/lib/data/repositories/pantry_repository.dart` (AC-TEST-07), and
`app/ios/fastlane/Fastfile` twice (AC-AUTH-07).

```
$ git status --short
 M app/pubspec.lock          ← another session's dependency cleanup (D-5), not mine
 M app/pubspec.yaml          ← same
?? .scratch/flutter-port/REMEDIATION.md      ← another agent's file
?? .scratch/flutter-port/verification/       ← this report and its siblings
```

No tracked file that I touched differs from `HEAD`. Confirmed per-file after each restore with
`git diff --stat <path>` returning empty, and each affected test re-run green afterwards.
