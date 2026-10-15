# Cross-cutting UX decisions

Decisions that span multiple flow tickets (11–15), recorded once here and referenced from each.

## Destructive actions: swipe-only + undo snackbar — DECIDED

Today every list row in Pantry, Shop **and** Plan carries *two* delete affordances (swipe-left plus a visible trash/`×` button), with **no confirmation and no undo anywhere**. Marking a meal "Cooked" also irreversibly decrements pantry quantities with no toast and no undo (`plan/index.tsx:214-218`).

**House rule for the Flutter app:**
- **One gesture per row** — `Dismissible` swipe only. Drop the redundant visible trash/`×` buttons (`pantry/index.tsx:155-162`, `shopping-list-components.tsx:139-147`, `plan/index.tsx:153-160`).
- **Every destructive action shows an undo snackbar**, not a confirm dialog — fewer taps than confirming, and recoverable.
- Applies uniformly to: pantry item delete, shopping row delete, plan entry delete, and **"Cooked"** — which requires storing the pantry delta so it can be reversed.
- Implementation note: this pairs with [ticket 08](08-decide-component-architecture.md)'s `SnackBar`/`ScaffoldMessenger` decision, and `Dismissible` replaces the hand-rolled `SwipeDeleteRow`.

## Local data is scoped to the user — DECIDED

Today only `user_config` is keyed by user sub (`schema.ts:108-109`). `pantry_items`, `recipes`, `meal_plan_entries` and `shopping_list_items` have **no user column**, so signing in as a different account inherits the previous user's groceries while their settings silently reset.

**Decided**: add a user-scoping column to all user-data tables in the new `drift` schema. Because [no data migrates from the RN app](../map.md) (already settled), this is essentially free to do now and expensive to retrofit later. Sign-out therefore does **not** need to wipe the DB — a different user simply sees their own (empty) data, and re-authenticating after token expiry doesn't destroy work.

## First-run onboarding — DECIDED

Today there is **none**: a new user lands on an empty Pantry (`pantry/index.tsx:269-278`) and never learns the pantry→meals→plan→shop loop, nor that Settings values steer meal-plan quality.

**Decided**: a **short first-run setup** capturing the few settings that make generation good — dinners per week, default servings, dietary flags — ending by pointing at receipt-scan to fill the pantry. This front-loads config that otherwise stays at defaults forever, and teaches the loop implicitly. Should be skippable.

Related: Settings copy must state that these values drive meal-plan generation, give the cooking-time field a "minutes" unit, and surface its 1–480 bound before it's violated (`settings/index.tsx:284-294`).
