# Independent verification — Cross-cutting UX, Shop, Plan, Settings

Scope: `AC-UX-*` (E), `AC-SHOP-*` (H), `AC-PLAN-*` (I), `AC-SET-*` (J). Verifier did not
write any of this code. Method: read the implementation and its tests, ran the relevant
`flutter test` targets, and for the highest-stakes criterion (AC-SHOP-01) temporarily
reintroduced the original RN bug to confirm the test suite would actually catch it.

Environment: `flutter analyze` → 0 issues. Full `flutter test` → 345 tests, all passing
(both checked as preconditions per ACCEPTANCE.md's rules-of-the-loop).

**Note on the working tree**: this worktree is shared with other concurrent verifier
agents (observed other files change/revert live, e.g. `pantry_repository.dart`,
`swipe_to_delete.dart`, an untracked `_scratch_lastused_test.dart` — none of that is
mine). My own probe touched exactly one file (`app/lib/data/repositories/shopping_repository.dart`);
see AC-SHOP-01 below for what I did there. Confirmed clean afterward — see final section.

---

## E. UX — cross-cutting

- **AC-UX-01 — CONFIRMED.** Exactly one delete affordance (swipe/`Dismissible`, via
  `SwipeToDeleteRow`) on every row in all three lists, verified by reading the row
  widgets directly, not just the tests:
  - Pantry: `app/lib/features/pantry/widgets/pantry_item_row.dart:28-34` — `SwipeToDeleteRow`
    wraps a `Card`/`InkWell` whose only `onTap` opens the quantity sheet; no second
    delete icon anywhere in the row or in `quantity_edit_sheet.dart` (grepped for
    "delete" — no hits).
  - Shop: `app/lib/features/shop/widgets/shopping_row.dart:7-10` — doc comment names the
    exact RN bug ("this row's swipe *and* a separate '×' `Pressable` on checked rows")
    and confirms it isn't reproduced; the row itself has no delete control, only
    tap-to-toggle.
  - Plan: `app/lib/features/plan/widgets/plan_slot_row.dart:25-32` — `SwipeToDeleteRow`
    wraps `_FilledSlotRow`, which has only a "Cooked?" button, no delete button.
  - Confirmed by test: `shop_screen_test.dart` "swipe-to-delete removes a row with undo",
    `plan_screen_test.dart` "swipe-to-delete removes the entry and cascades its shopping row".

- **AC-UX-02 — CONFIRMED.** Enumerated every destructive action and its undo path, and
  confirmed no confirm dialogs exist anywhere (`grep -rn "AlertDialog\|showDialog\|Alert.alert" lib/`
  → zero hits in the whole app):
  - Pantry delete: `pantry/actions.dart:36-` `deletePantryItemWithUndo` → `GleanSnackBar.showUndo`.
  - Shopping row delete: `shop/actions.dart:36-59` `deleteShoppingItemWithUndo` → `showUndo`.
  - Plan entry delete: `plan/actions.dart:67-99` `deleteEntryWithUndo` → `showUndo` (falls
    back to a plain, non-undoable snackbar only in the one case where undo is structurally
    impossible — the entry's recipe was itself already deleted, so there's no recipe id
    left to re-add with).
  - Recipe delete: `meals/actions.dart:90-` `deleteRecipeWithUndo` → `showUndo`.
  - "Cooked" (a destructive-to-pantry-stock action): `plan/actions.dart:25-44`
    `markCookedWithUndo` → `showUndo`, reversing the pantry delta exactly (AC-UX-03).

- **AC-UX-03 — CONFIRMED, and thoroughly.** `PlanRepository.markCooked`/`undoCooked`
  (`app/lib/data/repositories/plan_repository.dart:184-325`) record the exact delta applied
  per ingredient in a `cooked_adjustments` table (`amountDeducted`, `unit`,
  `previousLastUsedAt`) and reverse it precisely on undo. Verified against the database
  with three tests in `test/data/plan_repository_test.dart:348-470`, including the exact
  case called out in the brief — **the floor-at-zero case**: pantry has 100g, recipe wants
  400g, `markCooked` floors the decrement to the 100g actually available, and `undoCooked`
  restores exactly 100g (not 400g) — "over-restoring would invent stock that was never
  actually there" (line 435-436). All three tests pass.

- **AC-UX-04 — FAILED.** The first-run setup screen is fully built
  (`app/lib/features/onboarding/onboarding_screen.dart`) — three short, skippable steps
  (dinners/servings/dietary flags), a "Skip" on every step, ends by routing to
  `AppRoutes.intakeScan` — and its integration seam (`OnboardingGate`,
  `app/lib/features/onboarding/onboarding_gate.dart`) is fully built and independently
  tested (`test/features/onboarding/*`). **But it is never wired into the router.**
  `onboarding_gate.dart`'s own doc comment says so explicitly: "nothing in `lib/router/**`
  currently mounts this... Until that one-line change lands, `OnboardingScreen` is fully
  built and tested in isolation... but unreachable through real navigation." Confirmed by
  reading `app/lib/router/router.dart:142-148`: the shell branch builder calls
  `AppShell(navigationShell: navigationShell)` directly, not
  `OnboardingGate(child: AppShell(...))`. `grep -rn "OnboardingGate" lib/` finds the class
  definition and its own doc-comment self-reference, and nothing else — no import, no
  call site, anywhere in `lib/`. **No new user in the shipped app will ever see this
  screen.** This is a straight regression against the spec ("A short, skippable first-run
  setup captures dinners/week, servings and dietary flags") — the feature exists in the
  codebase but not in the product.

- **AC-UX-05 — CONFIRMED.** `app/lib/features/settings/settings_screen.dart:173-177` —
  "These preferences steer how Glean plans your meals each week." is always visible above
  the controls. `app/lib/features/settings/widgets/max_time_field.dart:31-33,57-58` — the
  bound ("Leave blank for no limit, or enter 1–480 minutes.") is shown as `helperText`
  unconditionally, before any violation, replaced by `errorText` only once actually out of
  range; the field also carries a `min` suffix (a standard abbreviation of minutes; the
  helper text spells out "minutes" in full). Tested:
  `test/features/settings/settings_screen_test.dart:282-296` ("shows the minutes unit and
  the 1-480 bound before it is violated") — passes.

## H. UX — Shop

- **AC-SHOP-01 — CONFIRMED, with an active regression check.**
  `ShoppingRepository.resolveCheckout` (`app/lib/data/repositories/shopping_repository.dart:232-244`)
  deletes only rows that are both `isChecked == true` **and** `ingredientId` in the
  receipt's `resolvedIngredientIds` — everything else (checked-but-unmatched,
  never-checked) is left untouched in one `DELETE ... WHERE` statement, so there's no
  window where an unmatched row could be swept up.
  - Tested at the DB level (`test/data/shopping_repository_test.dart:53-90`) and at the
    widget level with the **exact 12/4/8 scenario** from the brief
    (`test/features/shop/checkout_test.dart:36-90`): 12 manually-added, all-checked items,
    4 resolved by "receipt", asserts `removedCount == 4`, the 4 gone from the rendered
    list, the other 8 still rendered, and `shopping.watchAll(...)` returning exactly 8
    rows. Ran it: passes.
  - **Verified the test would catch the old bug returning.** I temporarily reverted
    `resolveCheckout` to the RN behaviour (delete every checked row regardless of match —
    dropped the `ingredientId.isIn(...)` clause) and reran both tests:
    ```
    Expected: <4>
      Actual: <12>
    ```
    Both `shopping_repository_test.dart`'s and `checkout_test.dart`'s AC-SHOP-01 tests
    failed exactly as expected. Restored the file immediately after; confirmed
    `git diff` on that file is empty and `flutter test` on both files passes again.

- **AC-SHOP-02 — CONFIRMED.** `ShopCheckoutBar` (`app/lib/features/shop/widgets/shop_checkout_bar.dart:78-95`)
  renders a "Done shopping" button alongside "Scan receipt" whenever any item is checked,
  wired to `completeCheckoutWithoutReceipt` (`shop/actions.dart:67-84`,
  `ShoppingRepository.completeCheckoutWithoutReceipt`,
  `shopping_repository.dart:246-251`), which removes every checked row with undo. Tested
  in `test/features/shop/checkout_test.dart:92-130` — passes, including the undo restoring
  both items.

- **AC-SHOP-03 — CONFIRMED.** `ShoppingRepository.addManualItem`
  (`shopping_repository.dart:64-90`) resolves through `IngredientsRepository.resolveOrCreate`
  before insert; `ShoppingListItemView.ingredientId` is non-nullable (schema-enforced, not
  just convention) — `shopping_repository_test.dart` and `checkout_test.dart:132-164`
  assert the resolved id is real (`greaterThan(0)`) and that the same item can later be
  matched and removed by `resolveCheckout`. Passes.

- **AC-SHOP-04 — PARTIAL.** `ShoppingRepository.checkOffResolvedIngredients`
  (`shopping_repository.dart:193-210`) is correctly implemented and correctly unit-tested
  in isolation — scoped to `userId`, and only ever flips `isChecked: false → true`
  (`test/features/shop/scoped_checkoff_test.dart`, both tests pass: never touches another
  user's row; never re-affects an already-checked row). **However, this method is never
  called anywhere in the app.** `grep -rn "checkOffResolvedIngredients" lib/` finds only
  its own definition and one doc-comment reference in `shop/actions.dart:20` — no
  production call site. The receipt-checkout flow that actually ships
  (`app/lib/features/intake/review_screen.dart:123-146`, `_confirmPantry`) calls
  `resolveCheckout` directly and never calls `checkOffResolvedIngredients` first. Net
  effect: **a shopping row the user left unchecked is never resolved by a matching
  receipt at all** — `resolveCheckout` requires `isChecked == true` to remove a row, and
  nothing in the shipped app ever sets that flag from a receipt match. This is safer than
  the RN bug (favours leaving data alone over over-deleting), but it means the "scoped
  check-off" feature described by AC-SHOP-04 exists only as tested, dead code — the
  criterion's invariant holds trivially because the operation never fires in production.

- **AC-SHOP-05 — FAILED (on the wording of the decided behaviour) / PARTIAL overall.**
  Two components were decided in `issues/13-ux-review-shop.md`: (1) announce plan-derived
  rows in "the confirmation snackbar" and (2) rows are inserted "on plan-add and generate"
  (unchanged from RN, per FLUTTER_MIGRATION.md §6 Shop). What's actually shipped:
  - A persistent "From plan" tag is rendered on every plan-derived row
    (`shopping_row.dart:49-58`, `presentation.dart:38`'s `isPlanDerived`) — good, and
    tested (`test/features/shop/plan_rows_test.dart`, passes).
  - **But the confirmation snackbar never mentions it.** Generate's own success message
    is a bare `GleanSnackBar.show(context, 'Week generated')`
    (`app/lib/features/plan/plan_screen.dart:113`) — no mention of shopping rows added.
    `test/features/plan/generate_week_controller_test.dart` only asserts the shopping row
    exists in the DB, never that anything announces it. The `plan_rows_test.dart` doc
    comment itself concedes this: "the insertion-time snackbar itself is the Plan
    feature's job, not this one's" — but Plan's snackbar doesn't do it either. No test
    anywhere asserts a shopping-list-specific announcement string.
  - **More seriously: manual "Add to plan" from the Meals recipe detail screen never
    creates shopping gap rows at all.** `grep -rn "addGapsForRecipe" lib/` finds exactly
    one call site — `generate_week_controller.dart:189-196` (the Generate path). The
    manual add-to-plan handler
    (`app/lib/features/meals/saved_recipe_detail.dart:169-201`, `_onAddToPlan`) calls
    `planRepository.addEntry` and shows "Added to plan" — it never calls
    `ShoppingRepository.addGapsForRecipe`. `test/features/meals/add_to_plan_test.dart`
    confirms this: it asserts the plan entry is created but never touches
    `ShoppingRepository` or asserts anything about the shopping list. This is a genuine
    functional regression against the decided behaviour ("addShoppingGapsForRecipe...on
    plan-add and generate") — a user who manually adds a recipe to their plan (rather
    than using Generate) gets no shopping-list gap-fill for its missing ingredients at
    all, where the RN app did this (buggily silent, but present) on both paths. See also
    the "defect no criterion covers" note at the end.

- **AC-SHOP-06 — CONFIRMED.** Schema-level cascade:
  `shopping_list_items.sourceMealPlanEntryId` has `onDelete: KeyAction.cascade`
  (`app/lib/data/tables.dart:195-199`), so `PlanRepository.deleteEntry` removes the plan
  entry's shopping rows automatically. Tested twice: `test/features/shop/plan_rows_test.dart`
  (deleting the entry live-updates the Shop screen with no `ref.invalidate`) and
  `test/features/plan/plan_screen_test.dart:293-` (swipe-delete cascades the row). Both pass.

- **AC-SHOP-07 — CONFIRMED.** One phrase throughout: `cartCountLabel`/`toBuyCountLabel`
  (`shop/presentation.dart`) used consistently in the chip row, section headers and the
  checkout bar. `test/features/shop/shop_screen_test.dart:38-68` explicitly asserts
  `find.text('N checked')` is absent and the unified phrasing is present everywhere.
  Passes.

- **AC-SHOP-08 — CONFIRMED.** `ShopAddField` (`shop_add_field.dart`) is placed by
  `ShopScreen` above the scrollable `ShopListSection`, not as a list header
  (`shop_screen.dart:106-127`). Tested with 30 items and a scroll gesture
  (`shop_screen_test.dart:122-149`) — the field stays mounted and a late add still lands.
  Passes.

- **AC-SHOP-09 — CONFIRMED.** `_ShopAddFieldState._submit`
  (`shop_add_field.dart:48-69`) wraps the mutation in `try/catch/finally`: any exit path
  resets `_adding`, and a caught error sets a visible inline message
  ('Could not add "$name". Try again.'). Tested with a repository that always throws
  (`test/features/shop/add_item_test.dart:62-106`) — asserts the error text renders, the
  spinner is gone, the button's `onPressed` is non-null again, and a retry is possible.
  Passes.

- **AC-SHOP-10 — CONFIRMED.** `ShopCheckoutBar` sits as the last child of a
  `SafeArea(top: false)`-wrapped column with only `tokens.spacing.sm` (8dp) of bottom
  padding (`shop_checkout_bar.dart:44-50`) — nowhere near RN's ~90px dead band.
  `Scaffold.resizeToAvoidBottomInset: true` on `ShopScreen` (`shop_screen.dart:80`) keeps
  the pinned add field above the keyboard. Both tested directly:
  `shop_screen_test.dart:122-169` — "the pinned add field stays visible with a long list"
  and "...is not covered when the keyboard is up" (simulates a 300px `viewInsets` and
  asserts the field's bottom position is above it). Both pass.

## I. UX — Plan

- **AC-PLAN-01 — CONFIRMED.** `PlanRepository.watchWeek`/`getWeek`
  (`plan_repository.dart:36-79`) filter `plannedDate` between `startOfWeek`/`endOfWeek`.
  Tested: `test/data/plan_repository_test.dart` "watchWeek only returns entries within the
  given week" — passes.

- **AC-PLAN-02 — CONFIRMED.** `PlanScreen._goToPreviousWeek`/`_goToNextWeek`
  (`plan_screen.dart:69-79`) page `_weekStart` ±7 days in both directions; last week's
  cooked meals remain reachable (`plan_repository_test.dart` "Pagination: last week's
  entries remain reachable by paging back" line 88-93). Passes.

- **AC-PLAN-03 — CONFIRMED.** `uncookedCountForWeek` excludes `cookedAt.isNull()` rows
  from the capacity count, while `watchWeek` includes cooked entries in what's rendered
  (`plan_repository.dart:91-111`). Tested explicitly:
  `plan_repository_test.dart:195-242` "cooked meals free up their slot" — asserts the
  cooked entry stays visible (`hasLength(2)`) while capacity frees up by 1. Passes.

- **AC-PLAN-04 — CONFIRMED, explicitly checked against the exact failure mode named in the
  brief.** `remainingCapacityForWeek` (`plan_repository.dart:118-132`) derives capacity
  from `mealsPerWeek - uncookedCountForWeek(...)` **for the given week only**.
  `test/data/plan_repository_test.dart:154-193` "is per-week, not lifetime" fills week 1 to
  capacity (`remainingCapacityForWeek` → 0) and explicitly asserts week 2's capacity is
  still the full 2 — "A week that was full a while ago has no bearing on this week —
  unlike RN's lifetime count, which locked out every future add." Passes.

- **AC-PLAN-05 — CONFIRMED.** `rolloverUncookedMeals` (`plan_repository.dart:163-182`)
  `UPDATE`s `plannedDate` on uncooked entries dated before the target week — it never
  `INSERT`s, so a second run finds nothing left to move (the updated rows are now inside
  the target week and no longer match the `<` filter). Tested three ways
  (`plan_repository_test.dart:246-331`): moves correctly, **running it twice does not
  duplicate** (explicit idempotency test), and never moves a cooked entry. All three pass.
  Also exercised live in `plan_screen_test.dart:180-224` (screen's own `initState` fires
  rollover on every mount; a repeat call still yields exactly 1 entry).

- **AC-PLAN-06 — CONFIRMED (by construction; no dedicated named test).**
  `GenerateWeekController._persist` (`generate_week_controller.dart:157-206`) only ever
  calls `addEntry` (insert) for the slots computed from `remainingCapacityForWeek`, which
  already accounts for existing entries — there is no delete/replace code path anywhere in
  the generation flow. No test is titled "top-up only," but every generation test
  (`generate_week_controller_test.dart`) only ever observes net-new entries added on top of
  what existed.

- **AC-PLAN-07 — CONFIRMED.** `servings` has no default in `PlanRepository.addEntry`
  (`plan_repository.dart:134-152`, a required named parameter) — it cannot silently
  default to 1. `PlanGenerateButton` sources it from
  `configAsync.requireValue.preferredServings` (`generate_button.dart:40`) and
  `SavedRecipeDetail._onAddToPlan` from the same config value
  (`saved_recipe_detail.dart:140-142`). Tested at both the data layer
  (`plan_repository_test.dart:96-114`, servings=6 round-trips) and through the real
  network+persist path (`generate_week_controller_test.dart:78-148`, servings=4 lands on
  the inserted entry). Both pass.

- **AC-PLAN-08 — CONFIRMED.** `GenerateWeekController._generate`
  (`generate_week_controller.dart:75-102`) builds real `foodGroupsForRecipe` per saved
  recipe and `foodGroupCoverageForWeek` from the actual week's entries, and puts them in
  the request body. Tested by capturing the literal outgoing HTTP body:
  `generate_week_controller_test.dart:78-148` asserts
  `capturedBody['recipe_history'][0]['food_groups'] == ['protein']` for a chicken-breast
  recipe resolved to the `poultry` category — not an empty list/map. Passes.

- **AC-PLAN-09 — CONFIRMED.** `GenerateWeekController.generate` guards
  `if (state.isLoading) return;` (`generate_week_controller.dart:43`), and
  `PlanGenerateButton`'s `onPressed` is `null` while `pending`
  (`generate_button.dart:34-41`) — belt-and-braces. Tested with a real concurrent
  double-call: `generate_week_controller_test.dart:208-263` fires two `generate()` calls
  without awaiting the first, then asserts the mocked HTTP client was called exactly once
  and exactly one entry landed. Passes.

- **AC-PLAN-10 — CONFIRMED.** `_persist` (`generate_week_controller.dart:157-206`)
  validates every suggestion's `recipe_id` against the user's saved recipes **before**
  any insert, and wraps the insert loop in try/catch with a compensating delete of
  everything already inserted on any other failure — so either the whole batch lands or
  none of it does. Tested with a hallucinated id following a real one in the same
  response: `generate_week_controller_test.dart:150-206` asserts the controller state has
  an error and **neither** suggestion was persisted (proving whole-batch abort, not a
  skip-the-bad-one filter). Passes.

- **AC-PLAN-11 — CONFIRMED via widget test**, though the mechanism that produced the RN
  bug (`add_recipe_id` as a nav param, re-added inside a focus effect) doesn't exist in
  this codebase by design (FINDINGS.md F-05: add-to-plan is a same-screen mutation with no
  nav param at all) — the criterion's letter ("navigating away from Plan and back cannot
  re-add a recipe... verified by a widget test") is nonetheless satisfied and tested:
  `test/features/plan/plan_screen_test.dart:226-266` taps Plan → Meals → Plan and asserts
  the week stays empty. Passes. The Meals-side companion
  (`test/features/meals/add_to_plan_test.dart:79-115`) also asserts re-visiting a recipe
  already in the plan reports "Already in your plan" rather than duplicating. Passes.

- **AC-PLAN-12 — CONFIRMED, non-vacuously.** `_PlanProgressRing` uses
  `TweenAnimationBuilder<double>` (`plan_progress_card.dart:83-116`, 600ms,
  `easeOutCubic`). `test/features/plan/plan_progress_card_test.dart:42-73` changes
  `planned` from 0→1, pumps only 150ms into the 600ms sweep, and asserts the rendered
  fraction is strictly between 0.0 and 0.5 — "a teleporting ring would already read 0.5
  here; a genuinely static one would still read 0.0." This directly falsifies a teleport
  and directly falsifies a no-op animation. Passes.

- **AC-PLAN-13 — CONFIRMED.** `_FilledSlotRow` wraps both the leading status circle and
  the trailing "Cooked?" pill in `AnimatedSwitcher` (`plan_slot_row.dart:99-122, 150-161`,
  220ms, scale/fade transitions respectively) rather than a hard conditional swap.
  Exercised in `plan_screen_test.dart` ("marking cooked decrements pantry, transitions to
  a checkmark..."). Passes.

- **AC-PLAN-14 — CONFIRMED.** No `jsonDecode`/`JSON.parse`-equivalent on any route
  parameter anywhere in `lib/` (checked broadly: `grep -rn "jsonDecode" lib/` only turns up
  legitimate DB-column deserialization and API-response parsing, never route `extra`).
  `go_router` `extra` payloads are typed objects checked with `is`
  (`app/lib/router/router.dart:84-134`, e.g. `extra is ScanArgs`), each falling back to a
  `RouteErrorScreen` rather than crashing on a bad cast. The one string-typed param
  (recipe id) is guarded with `int.tryParse` at the router's own `redirect:` before the
  screen builder ever runs (`router.dart:186-195`).

## J. UX — Settings & auth

- **AC-SET-01 — CONFIRMED.** No "Save settings" control anywhere
  (`settings_screen.dart` — every control's `onChanged`/`onCommitted` calls `_persist`
  directly). Debounced for free text (`max_time_field`, 500ms `Timer` in
  `_onMaxTimeChanged`, `settings_screen.dart:139-147`); sliders persist only via
  `onCommitted`, called from `Slider.onChangeEnd` (release), never `onChanged` (drag
  frame) — see `tolerance_card.dart:54-65` and `integer_slider_control.dart:55-67`.
  Tested: `test/features/settings/settings_screen_test.dart:146-190` finds no "Save"
  text anywhere, drags a slider through 3 steps asserting no commit haptic fires
  mid-drag, then releases and asserts exactly one commit — plus the persisted value in
  the DB. Passes.

- **AC-SET-02 — CONFIRMED.** Same evidence as above — `Slider.onChanged` in both
  `tolerance_card.dart` and `integer_slider_control.dart` only calls the local
  display-state callback (`setState`), never a persist call; only `onChangeEnd` persists.
  The same test (`settings_screen_test.dart:146-190`) proves this by asserting zero
  `mediumImpact` (commit) haptics fire during the multi-step drag and exactly one fires on
  release.

- **AC-SET-03 — CONFIRMED.** `_persist` (`settings_screen.dart:115-126`) wraps the save in
  try/catch and shows `GleanSnackBar.show(context, 'Could not save your settings. Try
  again.')` on failure — RN's `saveUserConfig` showed nothing. Tested with an
  always-throwing repository override:
  `settings_screen_test.dart:257-279` — asserts the error text renders and that a failed
  save never fires the success/commit haptic. Passes.

- **AC-SET-04 — CONFIRMED, with a caveat worth flagging.** `LegalLinksSection`
  (`legal_links_section.dart`) renders two real `ListTile`s, each calling
  `url_launcher` via `linkOpenerProvider` on tap, with a snackbar if the link fails to
  open. Tested (`settings_screen_test.dart` "Terms and Privacy (AC-SET-04)" — both "are
  tappable and each open a real URL" and "surfaces an error if the link fails to open" —
  pass). **Caveat**: the URLs are acknowledged placeholders
  (`legal_links_section.dart:7-15`, `https://glean.app/legal/terms-of-service` /
  `.../privacy-policy`) — "No hosted Terms of Service / Privacy Policy page exists
  anywhere for Glean yet... swap them for the real hosted URLs once they exist." This
  satisfies the criterion's technical requirement (real tappable links, not plain text)
  but the destination pages themselves don't exist yet; flagged in the code itself as
  pre-launch follow-up, not something this port could have done differently.

- **AC-SET-05 — CONFIRMED.** Landing tab: `goRouterProvider`'s
  `initialLocation: AppRoutes.pantry.path` (`router.dart:63`). Sign-in: `sign_in_screen.dart`
  offers exactly one method, "Sign in with Google" (line 89), no other provider.

---

## Summary

| Verdict | Count | IDs |
|---|---|---|
| CONFIRMED | 27 | AC-UX-01/02/03/05, AC-SHOP-01/02/03/06/07/08/09/10, AC-PLAN-01–14, AC-SET-01/02/03/04/05 |
| PARTIAL | 2 | AC-SHOP-04, AC-SHOP-05 |
| FAILED | 1 | AC-UX-04 |
| UNVERIFIABLE | 0 | — |

30 criteria in scope. 27 fully confirmed with evidence, 2 partial (both in Shop, both
involving `addGapsForRecipe`/`checkOffResolvedIngredients` — see below), 1 failed
outright (AC-UX-04, onboarding unreachable).

### Defects worth flagging beyond a single criterion label

1. **AC-UX-04 is not a partial gap, it's a complete miss in production.** The onboarding
   screen and its gate are fully built and independently tested, but nothing wires
   `OnboardingGate` around the router's shell — `onboarding_gate.dart`'s own doc comment
   says as much. A new user today gets no first-run setup at all; `dinners`/`servings`/
   `dietaryFlags` sit at compile-time defaults until the user finds Settings themselves.
   This is the single highest-value fix among everything found here — it's a one-line
   change (`OnboardingGate(child: AppShell(navigationShell: navigationShell))` in
   `router.dart:148`) sitting behind fully-tested code that never got wired in.

2. **Manual "Add to plan" silently drops the shopping-gap-fill feature.** Only the
   Generate path calls `ShoppingRepository.addGapsForRecipe`
   (`generate_week_controller.dart:189-196`); `SavedRecipeDetail._onAddToPlan`
   (`saved_recipe_detail.dart:169-201`) does not. FLUTTER_MIGRATION.md §6 Shop and
   `issues/13-ux-review-shop.md` both describe this as an existing behaviour ("on plan-add
   and generate") that the port should merely *announce* better, not remove from one of
   the two paths. No test in either the Meals or Shop suite exercises this combination
   (`test/features/meals/add_to_plan_test.dart` never touches `ShoppingRepository`), which
   is exactly the "seam nobody owned" pattern FINDINGS.md F-16 already flagged once for
   the Shop describe screen — it appears to have recurred here between Meals and
   Shop/Plan.

3. **`checkOffResolvedIngredients` is dead code.** Built to spec for AC-SHOP-04 and
   unit-tested correctly in isolation, but has zero call sites in `lib/`. Whether this is
   intentional (the redesigned `resolveCheckout` no longer needs a separate check-off
   step) or an integration gap like #2 above is not documented anywhere — worth an
   explicit decision either to wire it in or delete it, rather than leaving tested,
   unreachable code sitting next to a criterion that name-checks it.

### `git diff` confirmation

My only intentional edit was a temporary, immediately-reverted change to
`app/lib/data/repositories/shopping_repository.dart` (see AC-SHOP-01) to prove the test
suite catches a regression. Direct diff on that specific file, checked repeatedly after
restoring it:

```
$ git diff -- app/lib/data/repositories/shopping_repository.dart
(empty)
```

I made no other edits. This worktree has other verifier agents active concurrently
(observed unrelated files — `pantry_repository.dart`, `swipe_to_delete.dart`, an
untracked `_scratch_lastused_test.dart` — changing and reverting live during this
session); a repo-wide `git status` at any given instant may show their in-flight work,
not mine.
