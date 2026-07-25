# Remediation list

> **Correction (orchestrator).** Commit `e778fe7`'s message claims R-02 and R-08 were fixed. **They
> were not.** The wiring agent stopped without reporting; I saw an empty task list, assumed it had
> finished, and wrote the commit message without verifying. The code reviewer caught it on re-read.
> Verified by grep: `addGapsForRecipe` still has one caller, `SignedOutBanner` is referenced only
> inside its own file, `checkOffResolvedIngredients` appears only in comments, and Shop's actions
> have no error handling.
>
> R-01, R-04, R-05, R-06, R-12, R-16, R-17, R-19 and the tab-switch half of R-11 **did** land and are
> independently confirmed. R-18, R-22, R-15 and the Pantry/Meals half of R-07 also landed.
>
> This is the same defect I spent the session catching in agents — claiming done without evidence —
> and the lesson is that an agent's *silence* is not completion. Verify before writing the message.


Defects found by the independent verification pass. Each must be fixed and **re-verified by an
agent that did not fix it** before the port is done.

## The pattern

Almost every finding is the same shape: **something built, tested, and correct — but never wired
up.** F-16 (the Shop describe screen) was the first instance; verification found four more.

That is the failure mode of parallel module ownership. Each wave built its own directory correctly
and to spec. The wiring *between* modules belonged to nobody in particular, and nothing failed,
because:

- the unit/widget tests exercise each piece directly, injecting what it needs, so they pass whether
  or not anything calls it in the shipped app; and
- `flutter analyze` is happy — unreferenced but exported code is not an error.

**Lesson for the remaining work: "is it implemented?" and "is it reachable?" are different
questions, and only the second one is what the user experiences.** A reachability check belongs in
the integration suite, which is the one place that exercises the app as assembled.

---

## R-01 — First-run onboarding is unreachable · FAILED AC-UX-04
**Found by:** shop-plan-settings verifier · **Severity: high** (a whole spec'd feature is absent)

`OnboardingGate` exists, is tested, and its own doc comment admits nothing uses it. The shell
builder at `lib/router/router.dart:148` constructs `AppShell(navigationShell: navigationShell)`
directly, with no gate wrapping it.

Effect: a new user never sees first-run setup. Dinners/week, servings and dietary flags stay at
defaults — which is **precisely the problem AC-UX-04 exists to fix** (§6: those values drive
meal-plan quality and today sit at defaults forever because nothing ever prompts for them). The port
reproduces the exact gap it set out to close.

**Fix:** wrap the shell with `OnboardingGate` in the router, and add a test asserting a first-run
user lands on setup while a returning user goes straight to Pantry.

## R-02 [NOT FIXED — reopened] — Manual "Add to plan" never creates shopping rows · PARTIAL AC-SHOP-05
**Found by:** shop-plan-settings verifier · **Severity: high** (functional regression)

`ShoppingRepository.addGapsForRecipe` is called **only** from the Generate path
(`lib/features/plan/providers/generate_week_controller.dart`). Adding a meal to the plan by hand
from the Meals recipe detail screen creates no shopping gaps at all.

Effect: the user plans a meal and the ingredients they lack never reach the shopping list — silently.

**Fix:** call it from the manual add-to-plan path too. Keep it idempotent: F-05 records that the RN
app's duplicate-add bug produced duplicate shopping gaps as well as duplicate plan entries, so
adding the same meal twice must not double the rows.

Also add the announcement AC-SHOP-05 asks for: rows appearing on the shopping list must be
acknowledged, not inserted silently.

## R-03 [NOT FIXED — reopened] — `checkOffResolvedIngredients` is dead code · PARTIAL AC-SHOP-04
**Found by:** shop-plan-settings verifier · **Severity: medium**

Correctly scoped and unit-tested, zero call sites in `lib/`.

**Decide, don't leave it:** either wire it to the real "check off what the receipt matched" flow, or
delete it. Note AC-SHOP-01's `resolveCheckout` is a one-shot that may make a separate tick-then-sweep
unnecessary — the data agent said as much. If so this is genuinely redundant and should go, and
AC-SHOP-04 should be marked satisfied by `resolveCheckout`'s scoping instead.

## R-04 — Onboarding state persists to a text file, outside the database
**Found by:** build-and-data verifier · **Severity: medium** (architecture violation)

`FileOnboardingStatusStore` (`lib/features/onboarding/providers/onboarding_status.dart`) writes
completed user ids to `onboarding_completed.txt` via `path_provider`, contradicting §3's "local
SQLite is the sole source of truth for user data".

**Not** a cross-user leak — it is keyed by user id, so users don't see each other's state. Its own
doc comment explains the cause: it needed a `user_config` column, and `lib/data/**` was owned by
another wave being edited concurrently, so it built a self-contained stopgap instead. Another seam
casualty.

**Fix:** add the column and back the store with `UserConfigRepository`. The doc comment claims only
the production instance in `onboardingStatusStoreProvider` needs to change — verify that holds.

## R-05 — Three unused direct dependencies · PARTIAL AC-BUILD-02
**Found by:** build-and-data verifier · **Severity: low** · **FIXED, pending re-verification**

`path`, `intl` and `collection` were declared with zero import sites. Removed; `flutter analyze`
stays clean, confirming they were genuinely unused.

## R-06 [FIXED] — §2's stack table lists no networking package
**Found by:** build-and-data verifier · **Severity: low** (spec documentation gap)

The app's entire remote layer uses `http`, which §2 never mentions. The spec is incomplete here, not
the implementation. Worth a note in `FLUTTER_MIGRATION.md` so the sanctioned-stack list matches
reality.

## R-07 [PARTIAL — Pantry/Meals only; Shop and Plan still exposed] — Delete-with-undo swallows database failures silently
**Found by:** pantry-meals verifier (beyond its criteria) · **Severity: medium**

`deletePantryItemWithUndo` (`lib/features/pantry/actions.dart:36-63`) and `deleteRecipeWithUndo`
(`lib/features/meals/actions.dart:90-140`) have no `try`/`catch` around the repository delete. A
DB-layer failure propagates as an **uncaught exception with no user-facing feedback at all** — no
snackbar, no retry, nothing.

Two reasons this matters more than it looks:

1. It is the same defect class as §11's "silent failures" — the category this port exists to
   eliminate. `saveUserConfig` failing showed the user nothing; this is that bug wearing a delete.
2. It is **inconsistent with every other mutation in the same two features**. `QuantityEditSheet`,
   `ManualEntryScreen`, `ReviewScreen` and `SavedRecipeDetail`'s add-to-plan all catch and surface.
   So the pattern is established and correct elsewhere, and the delete path just missed it — which
   is exactly the kind of inconsistency that survives review because each file looks fine alone.

Found by writing a throwaway test that forced a DB close mid-delete, i.e. a path no existing test
covered.

**Fix:** catch, surface via `GleanSnackBar`, and leave the row intact. Add a test forcing the failure,
since nothing currently exercises it.

## R-08 [NOT FIXED — reopened] — The "signed out" banner and AI gating are never mounted · PARTIAL AC-AUTH-04
**Found by:** design-auth-haptics verifier · **Severity: high** (a decided behaviour is absent)

`SignedOutBanner` and `aiFeaturesAvailableProvider` exist, are tested, and are referenced by
**nothing** in the running app. No AI-backed action is gated on auth status anywhere.

The session mechanics underneath are correct and tested — `expired` still resolves a user id, local
data stays readable, nothing routes away. But the *user-visible half* of §5's expiry decision is
missing: on expiry the user is supposed to keep reading their data behind a banner that gates only
AI-backed features. Today they'd get no banner and, presumably, a raw auth error when an AI action
fails.

**Third instance of the same seam failure** (with R-01 and F-16): built, tested, unreachable.

**Fix:** mount the banner in the shell and gate the AI-backed actions (generate, scan, describe,
import, search) on `aiFeaturesAvailableProvider`. Add a test asserting an expired session shows the
banner and disables those actions while leaving local reads working.

## R-09 — Splash → app hand-off has no fade · FAILED AC-TRN-05
**Found by:** design-auth-haptics verifier · **Severity: low** · **my own code**

`lib/bootstrap.dart:57-69` resolves the database gate with a bare `.when()` — no `AnimatedSwitcher`,
no fade. §7 requires one splash composition handing over smoothly; the RN app's unanimated pop is
explicitly one of the things being fixed. I wrote this file, and I reproduced the RN defect I was
removing.

**Fix:** cross-fade the gate's three states, reusing `GleanCrossFade`.

## R-10 — List insertion is not animated anywhere · PARTIAL AC-TRN-02
**Found by:** design-auth-haptics verifier · **Severity: low**

Removal animates (via `Dismissible`, confirmed by mutation test), but **insertion** has no animation
in Pantry, Shop or Meals. §7 asks for both, noting only Pantry animated at all in the RN app.

**Fix:** animate insertion — implicit animations or `AnimatedList` — in the three list screens.

## R-11 [FIXED in continuation] — Two haptic moments missing, one of them every tab switch · PARTIAL AC-HAP-05
**Found by:** design-auth-haptics verifier · **Severity: low**

10 of 12 named moments confirmed. Missing: **scan success/failure**, and **every tab switch**
(`lib/router/app_shell.dart` fires nothing). §7 names tab switch explicitly as a `selectionClick`.

The tab-bar one is the most-repeated interaction in the app, so it is the most noticeable omission
even though the fix is one line.

**Fix:** `selectionClick` on tab switch via the ladder; `mediumImpact` on scan success/failure.

## R-12 — Private widget-builder methods in the onboarding screen · FAILED AC-DS-14
**Found by:** design-auth-haptics verifier · **Severity: low**

`lib/features/onboarding/onboarding_screen.dart:95,142` declares `Widget _buildStep()` and
`Widget _buildFooter()` — precisely the pattern AC-DS-14 forbids. In Flutter this isn't only
tidiness: a builder method shares its parent's rebuild scope, whereas an extracted `const`-constructible
class gets its own. The rest of the codebase follows the rule, so this is a lone regression.

**Fix:** extract both into their own widget classes with `const` constructors.

## R-13 — Unjustified non-`_rounded` icons, and F-01 still live · PARTIAL AC-DS-06/07
**Found by:** design-auth-haptics verifier · **Severity: low**

Seven icons are not `_rounded` variants with no recorded justification. Separately, F-01 is still
reproducible on real screens (sign-in, onboarding): the vendored brand SVGs contain `<filter>`
elements `flutter_svg` cannot render, so it logs a warning and silently drops what is almost
certainly a drop shadow.

**Fix:** switch the seven icons to `_rounded` or justify each in a comment. For F-01, strip the
filter from the SVGs and reapply the shadow in Flutter, so the console warning goes away and the
mark renders as designed.

## R-14 — One hard cut left in recipe detail · PARTIAL AC-TRN-01
**Found by:** design-auth-haptics verifier · **Severity: low**

`saved_recipe_detail.dart`'s outer async transition is a hard cut, unlike the cross-fade pattern used
correctly everywhere else.

**Fix:** wrap it in `GleanCrossFade` like its siblings.

## R-15 [FIXED] — Undoing an earlier "Cooked" clobbers a later one's `lastUsedAt`
**Found by:** code reviewer · **Severity: medium** (correctness, not data loss)

`decrementForCook` snapshots `previousLastUsedAt` and `restoreFromCook` writes it back verbatim. With
two plan entries whose recipes share an ingredient:

1. Cook A → tomatoes' `lastUsedAt` becomes T1; delta stores the prior value (say `null`).
2. Cook B → `lastUsedAt` becomes T2; delta stores T1.
3. **Undo A** → restores `null`, discarding T2 even though B is still cooked.

Quantity restoration is fine because it is additive. `lastUsedAt` is last-writer-wins, so restoring it
out of order is wrong.

Consequence is real but bounded: `lastUsedAt` drives the pantry's longest-unused ordering **and** the
urgency scoring in meal-plan compression, so the item is ranked as less recently used than it is,
producing slightly worse suggestions. No data is lost.

**Note on a nearby non-issue, checked and cleared:** `decrementForCook` uses `.getSingleOrNull()`
filtered only on `(userId, ingredientId)`, which would *throw* rather than return null on multiple
matches. That is unreachable — `PantryItems.uniqueKeys` enforces `{userId, ingredientId}` at the DB
level (`tables.dart`), an improvement the comment notes the RN schema never had.

**Fix:** only restore `previousLastUsedAt` if no later cook has touched that ingredient — e.g. restore
it only when reversing the most recent adjustment for that ingredient, otherwise leave the current
value alone. Add a test for the two-entries-sharing-an-ingredient case, which nothing covers.

## R-16 — One screen is pushed outside `go_router`
**Found by:** code reviewer · **Severity: low** (architecture consistency)

`lib/features/meals/widgets/meals_search_panel.dart:180` pushes `RecipePreviewScreen` with a plain
`Navigator.of(context).push` + `MaterialPageRoute`, documented as deliberate in
`recipe_preview_screen.dart:3`.

It works, but it sits outside the declarative route table, so the preview has no route name, cannot
be deep-linked, does not benefit from typed params, and is invisible to the route-table tests. §2
chose `go_router` precisely so navigation lives in one declarative place.

To be clear, the `Navigator.of(context).pop()` calls in the sheets (`quantity_edit_sheet.dart`,
`pantry_add_sheet.dart`) are **not** instances of this — dismissing a modal sheet that way is
idiomatic and correct. This is only about the `push`.

**Fix:** add a route for the preview, or record a justification strong enough to stand in review.

## R-17 [FIXED] — Stale comments left across the tree
**Found by:** code reviewer · **Severity: low**

Three comments still say AUTH is "not yet built" or similar, now false. `FINDINGS.md`'s own status
tracking has also drifted behind what has been fixed.

Comments that lie are worse than no comments: the next reader trusts them. Sweep them.

## R-18 — Unit normalisation never fires, so mixed-unit additions corrupt quantities
**Found by:** tests-backend-ci verifier · **Severity: HIGH — silent user-visible data corruption**
**Status: FIXED**

**The defect predates the port.** The remediation agent checked the original:
`git show 906c9bb^:mobile/src/db/ingredients.ts` never wrote `canonical_unit` either. So the RN app
shipped this same corruption and nobody noticed — it belongs on §11's known-bugs list and was simply
never discovered during the UX review, because reading the code makes normalisation *look* wired.
Only tracing whether the field is ever **written** exposes it.

Fix as landed: a canonical unit is set on first resolution (recognised mass/volume collapses to its
base — `kg`→`g`, `l`→`ml`; count-based units are kept verbatim), and `_upsert` re-normalises an
incoming unit against the existing row's own unit, throwing `PantryUnitMismatchException` rather than
summing when no conversion exists. "2 kg then 500 g" now totals 2500 g instead of 502 kg. Recipe
import deliberately does not set it — a recipe's phrasing is not a stock-tracking unit.


`ingredients.canonicalUnit` is **only ever read, never written**. `IngredientsRepository.resolveOrCreate`
does not set it, and nothing else does, so `ingredient.canonicalUnit` is always null. `normalizeUnit`
therefore returns early (`unit_normalization.dart:90`) without converting, and
`PantryRepository.addItem` falls back to the raw unit.

`_upsert` then adds quantities while **keeping the existing row's unit**:

1. Add "2 kg flour" → row is `quantity: 2, unit: 'kg'`.
2. Add "500 g flour" → same ingredient, so it merges: `quantity: 2 + 500`, unit untouched.
3. The pantry now reads **"502 kg flour"**.

Two aggravating factors:
- It is reachable from the most ordinary action in the app — adding groceries twice in different units,
  which receipt scanning makes routine.
- The wrong quantity propagates: it feeds shopping-list shortfall maths and the urgency scoring that
  drives meal-plan generation. So one bad number quietly degrades two other features.

`normalizeUnit` itself is correct and is exactly the kg→g / L→ml / cup-of-flour-by-density logic §10
names as a **highest-value unit port** — it is simply never given a target to normalise to. And it has
**no test at all** (see R-22), which is why nothing caught it.

**Fix:** set `canonicalUnit` when an ingredient is created/resolved, and make `_upsert` refuse to merge
rows whose units are incompatible rather than adding across them — an unconvertible pair should fail
loudly, not silently sum. Add tests for the mixed-unit merge and for `normalizeUnit` directly.

## R-19 [FIXED] — The release-build auth-bypass guard has a false negative · FAILED AC-AUTH-07
**Found by:** tests-backend-ci verifier · **Severity: HIGH — the guard does not guard**

`test/build/release_entrypoint_test.dart` is the only build-level barrier stopping a release build
shipping the e2e auth-bypass entrypoint. It matches `flutter build` and `main_e2e` **on the same line**.
Both Fastfiles build via Ruby string concatenation split across two lines, so editing only the
target-flag line to `main_e2e.dart` leaves the guard **passing 5/5**. Demonstrated, then restored.

This is precisely the failure mode §5 restructured the bypass to prevent. The structural protection
(the bypass being unreachable from `main.dart`'s import graph) does still hold and is separately
tested — so this is not currently exploitable. But the second layer, the one meant to catch a build
misconfiguration, is decorative.

**Fix:** parse the whole build invocation rather than matching per line — or better, assert on the
resolved target the lane actually passes, so line formatting cannot defeat it. Then prove it by making
the two-line edit and confirming it now fails.

## R-20 [FIXED] — Live docs still describe the deleted Expo app · FAILED AC-CUT-01/02, PARTIAL AC-CI-06
**Found by:** tests-backend-ci verifier · **Severity: medium**

`backend/README.md` still documents running the Expo app in detail, including `make start-mobile`,
**which now errors**. `docs/project-status.md` still lists EAS, `EXPO_TOKEN`, jest-expo and biome as
the current stack.

My earlier exemption for `docs/superpowers/**` and the replit audit as dated historical records was
defensible; extending it to `backend/README.md` was not — that is a live document, and a documented
command that errors is a broken promise to the next reader. `docs/project-status.md` is also
presented as current state, not history.

**Fix:** update both. For the genuinely historical files, add a dated "superseded" header so a reader
knows before following their instructions.

## R-21 [FIXED] — No manual pre-release checklist exists · FAILED AC-TEST-18
**Found by:** tests-backend-ci verifier · **Severity: low**

The decision to keep airplane-mode/offline testing manual is recorded in the planning docs, but no
checklist artifact exists anywhere. A decision recorded only in a design document is not a checklist
anybody will run before a release.

**Fix:** create the checklist as a real file in the repo, covering at minimum the airplane-mode error
states the RN Maestro flow used to cover.

## R-22 [FIXED] — `normalizeUnit` has no test · PARTIAL AC-TEST-05
**Found by:** tests-backend-ci verifier · **Severity: medium**

§10 names unit normalisation (kg→g, L→ml, cup-of-flour→g by density) as a **highest-value unit port**.
`test/data/` contains no test for it. That absence is the direct reason R-18 went unnoticed.

**Fix:** port the original cases, including the density path.

## Note on the "red tree" report
The same verifier reported `flutter test` exiting 1 with 2 failures on AC-PAN-10. **Not reproducible
— the suite is green at 345/345**, confirmed with `-j 1` after all verifiers finished.

The cause was mine: I ran five verifiers concurrently in one shared worktree *and* authorised them to
temporarily break code to prove tests weren't vacuous. They saw each other's probes. Several noticed
and said so. Next time, adversarial mutation testing needs an isolated worktree per verifier.


## R-23 — A fallback unit can become an ingredient's permanent canonical unit
**Found by:** code reviewer, reviewing the R-18 fix · **Severity: medium**

The reviewer confirmed R-18's corruption fix is correct and that throwing beats silently summing. But
it found a follow-on: `review_screen.dart`'s blank-unit fallback (`_unitOrDefault` → `'units'`) can
seed an ingredient's **permanent** canonical unit on first resolution, with no in-app way to correct
it. The same change extended unit-seeding to `ShoppingRepository`, widening that surface.

Three things compound into a genuine dead end: a defaulted unit becomes permanent truth; the catch
message says "try again", which is misleading because retrying identical input fails identically; and
`addItems` commits a whole review batch in one transaction, so one bad row blocks the batch.

**Fix:** don't let a *fallback* unit seed the canonical unit — only an explicitly chosen one should.
Then give the mismatch exception a targeted message that says what actually went wrong.

## R-24 [FIXED in continuation] — Undoing both cooks oldest-first leaves a stale `lastUsedAt`
**Found by:** code reviewer, reviewing the R-15 fix · **Severity: low**

R-15's primary case is correctly fixed. Residual: undoing both cooks oldest-first leaves the
intermediate value rather than fully reverting to null. The new test documents this as expected rather
than catching it. Same low severity as the original — `lastUsedAt` only affects ordering and urgency
scoring.

**Resolution:** before deleting an older adjustment, `undoCooked` now forwards
its `previousLastUsedAt` snapshot to the immediate next live adjustment. This
preserves the snapshot chain for oldest-first and multi-cook undo order. The
regression test now requires the original `null` timestamp to be restored.
