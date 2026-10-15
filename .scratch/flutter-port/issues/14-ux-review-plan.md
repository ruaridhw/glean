Type: grilling
Status: resolved

## Question

Review the current Plan flow's user-facing behavior — `mobile/app/(tabs)/plan/index.tsx` — and decide whether the current UX makes sense or should change for the Flutter port. Note: this file has uncommitted local changes on the `fix/mobile-native-bundle-smoke` branch in the original worktree as of this map's creation — check the latest state on `main` (or wherever that work has landed) rather than assuming the version in this planning branch's history is current. Don't assume 1:1 parity is the goal; if something is confusing or awkward today, surface it and grill the user until there's a shared answer for what it should do instead.

## Answer (partial — decided so far)

### Plan scope — DECIDED
Today "This Week" is a lie: `getMealPlanEntries` (`db/plan.ts:8-21`) has **no date filter**, `planned_date` is written but never read, cooked meals occupy slots forever, and `getMealPlanCount` (`db/plan.ts:23-26`) counts *lifetime* entries — so after a few weeks of use "Plan full" (`plan/index.tsx:191`) blocks adding any meal, permanently.

**Decided**:
- The plan is **week-scoped**. Filter entries to the week so the title is honest and the plan auto-resets.
- **Cooked meals stay visible** within their week (keeps the satisfaction loop) but stop counting toward "left to plan".
- **Week pagination**: the user can page backward and forward between weeks — so last week's cooked meals remain viewable today. This makes `planned_date` load-bearing at last, and means capacity is per-week, not lifetime.

Open sub-question: what happens to *uncooked* meals when a week ends — roll forward, or leave them in the past week?

### Bugs — must not reproduce
- **`plan/index.tsx:257-263` half-writes the plan.** The `onSuccess` loop awaits `addMealPlanEntry` with no try/catch. `mealPlanEntries.recipe_id` has a real FK (`schema.ts:80-82`) with `PRAGMA foreign_keys = ON`, so a hallucinated/stale `recipe_id` throws. React Query's `onError` does **not** fire for a throw inside `onSuccess` — so earlier suggestions are already committed, `showSuccess`/`load()` never run, and the user sees *nothing happen*.
- **`plan/index.tsx:238` — uncategorised pantry items make generation 422.** `food_group` is nullable client-side but the backend declares it non-nullable (`meal_plan/schemas.py:11`). Any uncategorised ingredient in the top-15 → Pydantic 422 → generic "Could not generate meal plan". The `as Parameters<...>` cast on that line is what silences the type error. **Directly caused by the categorisation gap** — see [ticket 22](22-decide-ingredient-categorisation.md).
- `plan/index.tsx:205-212` — `add_recipe_id` never cleared → duplicate entries + duplicate shopping gaps on every refocus (same bug recorded in ticket 12).
- `plan/index.tsx:289-298` — Generate is **not disabled while pending**; a double-tap fires two mutations that each computed `emptySlots` from the same stale state, overfilling past `meals_per_week`.
- `plan/index.tsx:243,250` — `food_groups: []` and `food_group_coverage: {}` are **hardcoded empty**, so the backend prompt's "balance food group coverage across the week" rule (`meal_plan/service.py:20`) is permanently inert. A silently dead feature on both sides of the wire.
- `preferred_servings` is configurable in Settings but **ignored** — `addMealPlanEntry` hardcodes `servings: 1` (`db/plan.ts:28`).

### Still open
- Should generation replace or top up? (Currently additive — fills empty slots only. A "re-roll" needs a replace mode.)
- Surface the backend's `reason` and `missing_ingredients` per suggestion, or drop them? They're returned (`api/types.ts:101-102`) and **thrown away** (`plan/index.tsx:257-261`), so the user gets titles with no explanation.
- Per-suggestion accept/reject before commit, or commit-all (current)?
- Pre-flight contract: block/warn Generate when the pantry is empty, saved recipes < slots, or offline? Today it proceeds with `pantry: []` and `recipe_history: []`.
- Do slots map to specific days? (Numbering is positional — "1" means "first added", not Monday.)
- Is "Cooked" undoable? It irreversibly decrements pantry quantities with no toast and no undo.
- Should the plan honour `preferred_servings`, and should servings be per-entry editable?
- What should the expiry nudge banner *do*? It's below the fold and inert.
- Latency/cancellation: `api/client.ts` sets **no timeout** on an LLM round-trip, and feedback is a text swap ("Generate" → "Generating") with no spinner.

### Deletes, undo, and "Cooked" — DECIDED
See [cross-cutting decisions](_cross-cutting.md): swipe-only (drop the always-visible close-circle), undo snackbar on delete, **and "Cooked" becomes undoable** — which requires storing the pantry decrement delta so it can be reversed.

### Generation transparency — DEFERRED
`reason` and `missing_ingredients` stay hidden for the initial port; surfacing them, plus the pre-flight guard (empty pantry / no saved recipes / offline) and the missing client timeout, are deferred to [ticket 24](24-later-plan-transparency-preflight.md).

Note: [ticket 22](22-decide-ingredient-categorisation.md) removes the *other* silent generation failure (the uncategorised-ingredient 422), so v1's remaining exposure is generating with too few saved recipes.

### Re-generation — DECIDED
**Top-up only**, as today: generation fills empty slots and never replaces existing entries. No "regenerate all" and no per-suggestion accept/reject in the port. Rejecting a plan wholesale therefore means deleting meals individually — acceptable given deletes now carry an undo snackbar.

### Week rollover — DECIDED
**Uncooked meals roll forward automatically** into the new week, so nothing planned is lost when a week turns over. Cooked meals stay in their original week (visible via week pagination).

Implementation details to settle during execution:
- **Repeated rollover**: a meal uncooked for several weeks keeps rolling. Recommended: allow it indefinitely — the per-week capacity check naturally limits accumulation, since rolled-forward meals occupy slots. Consider surfacing how long something has been carried.
- Rollover must be idempotent (a meal must not be duplicated by rolling forward twice), which matters given the current codebase's history of duplicate-insert bugs.

### Slot numbering — still open (low stakes)
Slots are numbered positionally today, so "1" means "first added", not Monday. Recommendation: **drop the numbers** for a plain list, since day mapping is out of scope (it would force decisions about skipped days and drag-reordering). Flagged rather than decided — say if you'd rather keep numbering.

## Resolution
Resolved apart from the low-stakes slot-numbering note above. Deferred items: [ticket 24](24-later-plan-transparency-preflight.md).
