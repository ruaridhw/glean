Type: grilling
Status: resolved

## Question

Review the current Meals flow's user-facing behavior end to end — `mobile/app/(tabs)/meals/index.tsx`, `[id].tsx`, `import.tsx`, `search.tsx` — and decide, screen by screen, whether the current UX makes sense or should change for the Flutter port. Don't assume 1:1 parity is the goal; if something is confusing or awkward today, surface it and grill the user until there's a shared answer for what it should do instead. Record the resolved behavior for each screen (kept as-is / changed, and how).

## Answer (partial — decided so far)

### Library curation — DECIDED
The recipe library becomes something the user deliberately curates. Three changes that hang together:
- Tapping a search result **previews** it (navigates to detail); it does **not** save.
- The bookmark icon in the detail header (`meals/[id].tsx:58` — currently a dead `View`) becomes the **real save/unsave toggle**.
- Saved recipes become **deletable** (swipe-to-delete, consistent with Pantry). Note: no `deleteRecipe` exists anywhere in `src/db/recipes.ts` today — the library is currently append-only.
- When a recipe is deleted, **keep any plan entry** referencing it (it snapshots what you're cooking); just lose the link back.

### Recorded without contest (clear-cut fixes)
- Add proper **empty** and **no-results** states to search (today: blank `FlatList`, no message — `search.tsx:118-136`).
- **Dedupe both** search and import, and say "already saved" rather than silently. Today search dedupes by `external_id`, import doesn't dedupe at all (`schema.ts:34-48` has no unique index; `saveRecipe` always inserts).
- Fix the saved-list skeleton flashing over the Search segment (`index.tsx:106` checks `loading` before `tab`).
- Back affordance: `search.tsx`/`import.tsx` have none (rely on OS back). Flutter's `AppBar` auto-inserts one when the route can pop — resolves itself.
- Unify loading language on skeletons (detail uses a bare `ActivityIndicator`, lists use skeletons).
- Kill the fake search pill on the Saved/Search segment (`index.tsx:111-118`) — a pill that looks like an input but is a link, with a real input one screen later.

### Still open
- Search placement: a real inline search UI inside the Search segment vs. today's pushed screen.
- After "Add to plan": where the user lands, and whether the button becomes "In plan".
- Whether `source_url` (attribution), `nutrition`, and `not_suitable_for` (allergen-ish, currently never displayed) get surfaced.
- Whether plan-full / already-planned checks happen *before* navigating.

### Bugs — must not reproduce
- **`plan/index.tsx:206-212` duplicate-add**: `add_recipe_id` is never cleared and the re-add runs inside `useFocusEffect`, so leaving Plan and returning re-adds the recipe — duplicate plan entries *and* duplicate shopping gaps accumulate. Decision: record as must-not-reproduce; do not fix in the RN app being deleted.
- `[id].tsx:30-33` — cold-start deep link to a missing recipe calls `router.back()` with nothing to pop → permanent spinner.
- `[id].tsx:26-45` uses `useEffect([id])` not `useFocusEffect`, so "to buy" badges go stale after pantry changes.
- `recipes.ts:49-56` `getRecipeByExternalId` skips `attachDietaryFlags` (latent inconsistency).

### Recipe data surfacing — DECIDED
- **Surface `not_suitable_for`** prominently on the recipe detail screen. Withholding stored allergen information from someone deciding what to cook is the one omission in this flow with real-world consequences — it is currently stored and displayed nowhere (`presentation.ts:27-31` uses only cuisine + dietary flags).
- **Surface `source_url`** as tappable attribution for imported recipes — both a credit obligation when ingesting third-party content and a useful "open the original" affordance.
- **Nutrition stays unshown** for now (stored but needs design work, and its shape may be inconsistent across sources).
- Also: the detail header currently reads a static **"Recipe"** — show the dish name.

### Recorded recommendations (not separately contested)
- **Search placement**: put a real inline search input inside the Search segment and drop the separate pushed screen plus the fake search pill, so there is one search affordance instead of three.
- **After "Add to plan"**: stay on the recipe with a snackbar confirmation rather than jumping to the Plan tab, and reflect state on the button ("In plan"). This also avoids the current wasted trip where the user is navigated to Plan *before* being told the plan is full (`plan/index.tsx:192`).
- Check plan-full / already-planned **before** navigating.

## Resolution
Resolved. Remaining deferred items live in [ticket 24](24-later-plan-transparency-preflight.md) (plan-generation transparency) — nothing outstanding for this flow.
