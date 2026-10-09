Type: grilling
Status: resolved

## Question

Review the current Pantry flow's user-facing behavior end to end — `mobile/app/(tabs)/pantry/index.tsx`, `add.tsx`, `describe.tsx`, `manual-entry.tsx`, `review.tsx`, `scan.tsx`, `scan-progress.tsx` — and decide, screen by screen, whether the current UX makes sense or should change for the Flutter port. Don't assume 1:1 parity is the goal; if something is confusing or awkward today, surface it and grill the user until there's a shared answer for what it should do instead. Record the resolved behavior for each screen (kept as-is / changed, and how).

## Answer (partial — decided so far)

### Expiry — DECIDED (with a prerequisite)
Today expiry drives badges, the "N expiring" chip, and the Plan nudge banner — but **nothing ever writes an expiry date**; `addPantryItem` (`db/pantry.ts:75-95`) doesn't even accept one, and `upsertPantryItem:64` only sets it on insert. The UI ships as a shell.

**Decided**: infer expiry **automatically** from per-category shelf-life defaults, so the existing UI gets real data with no intake friction. Making expiry user-settable/correctable is a follow-up → [ticket 23](23-later-user-settable-expiry.md), which matters because inferred shelf life will sometimes be wrong and there is currently no edit path at all.

⚠️ **Prerequisite**: inference by category is impossible until ingredients actually *have* categories. Resolved as [ticket 22](22-decide-ingredient-categorisation.md) — the backend will return `category`/`food_group` from its parse endpoints.

### Categorisation — DECIDED via ticket 22
Currently every user-added ingredient lands in a single "Other" bucket, making grouping and filter chips useless. Fixed by [ticket 22](22-decide-ingredient-categorisation.md): the backend returns a category from the parse endpoints, drawn from the existing 23-category taxonomy. This also removes the meal-plan 422 failure mode.

### Bugs — must not reproduce
- **`review.tsx:29-57` non-atomic save.** A failure on row 3 of 5 leaves rows 1-2 persisted, shows a generic Alert, and leaves the same list on screen — and because `upsertPantryItem` *increments* (`db/pantry.ts:53`), retrying **doubles** quantities.
- **`review.tsx:91` decimals untypeable** — `parseFloat(v) || 0` round-tripping through `String(quantity)` means typing `1.5` renders `1`; clearing yields `0`.
- **`review.tsx:110` accepts zero/NaN quantities** — `acceptedItems` filters on name only (`intake/useReviewList.ts:34`), so Confirm can write `0 units` to the pantry.
- **`scan-progress.tsx:41-51` permanent hang** — `submit()`'s `fetch(data:...)`/`blob()` isn't wrapped in try/catch and isn't a mutation error, so a failure leaves the user on "Almost done…" forever, with no back button and no timeout.
- **`review.tsx:44` unconditional cross-feature write** — `checkOffByIngredientIds` mutates the shopping list even in a pantry-only flow, undisclosed to the user.
- `scan.tsx:33-38` — capture failures are silent (`if (!photo?.base64) return;`), `takePictureAsync` throwing is uncaught, and the shutter has no pressed/disabled state.
- `scan.tsx:17-27` — the permission-denied and `!permission` branches have **no back affordance at all** (the bespoke chevron only exists on the granted branch) → hard dead end after a permanent deny.
- Deleting the last item of a filtered category strands the list: filters derive from live sections (`index.tsx:291-297`) so the stale filter key matches nothing → blank body, no chip selected, only "All" recovers.
- `manual-entry.tsx:31` lowercases the name while `review.tsx:34` passes it verbatim.
- Skeleton flashes on every focus (`index.tsx:220-232` sets `loading` true each time) — the whole header, chips and Scan button vanish then repopulate.
- Tap-delete buzzes **twice** (`index.tsx:245` medium + `IconButton.tsx:38` light).

### Still open
- Do Describe and Manual entry survive? **`add.tsx` and `manual-entry.tsx` are currently unreachable dead code** — nothing routes to `/(tabs)/pantry/add`, and Describe is only reachable from the empty state, so it vanishes the moment the user owns one item.
- One delete gesture or two, and does delete get a confirm or an undo?
- Should the tab bar be hidden during scan/progress/review (making intake a modal task)? Today it's visible over the camera and a mid-scan tab tap silently loses the capture.
- Quantity editing model: inline tap-to-edit committing on blur (can't change unit, swallows invalid input) vs. an edit sheet with unit + expiry and explicit Save/Cancel.
- Is the 3-step fake progress worth keeping? It's purely time-driven (`scan-progress.tsx:54-69`), desyncs from the real request, and adds ~2.3s of guaranteed latency after the API returns.
- Cross-tab intake: keep reusing the Pantry camera from Shop via `returnTo=shop` (lights up the Pantry tab mid-Shop task) or give Shop its own route?
- `add.tsx` is off-design-system (emoji glyphs, raw `SafeAreaView`) — moot if it stays dead.

### Intake discoverability — DECIDED
All three intake modes survive, behind a single **"+" action** opening a sheet with **Scan / Describe / Manual**, available whether the pantry is empty or full. Costs one tap on the primary Scan path but makes all three permanently discoverable — Describe is genuinely useful for "bought at the market, no receipt", and Manual is the only way to add one item without a backend round-trip.

This resolves the dead code: today nothing routes to `/(tabs)/pantry/add` at all, and Describe is reachable *only* from the empty state, so it vanishes once the user owns one item.

### Deletes and undo — DECIDED
See [cross-cutting decisions](_cross-cutting.md): swipe-only (`Dismissible`), no visible trash button, undo snackbar on every destructive action. Also fixes the double-haptic on tap-delete.

### Intake flow — DECIDED
- **Intake becomes a full-screen modal task**: the tab bar is hidden across scan → progress → review, with an explicit cancel. Today the tab bar renders over the camera and a mid-scan tab tap **silently loses the capture**.
- **One review screen**, not two: `shop/review.tsx` and `pantry/review.tsx` unify into a single component (they do the same job today with different looks, different button verbs — "Add N items" vs "Confirm N items" — and inconsistent numeric fallbacks).
- **Honest progress**: replace the three fake time-based steps (`scan-progress.tsx:54-69`) with a real indeterminate indicator plus a timeout and cancel. This also removes the ~2.3s of artificial delay currently added *after* the API has already returned.

### Quantity editing — DECIDED
Replace inline tap-to-edit-commit-on-blur with a proper **edit sheet covering quantity + unit + expiry**, with explicit Save/Cancel and real validation. Today inline editing silently discards invalid input (`index.tsx:237`), can't express a unit change, and has no expiry path at all.

This is also the natural home for the expiry-correction UI deferred to [ticket 23](23-later-user-settable-expiry.md) — inferred shelf life will sometimes be wrong, and a sheet gives it somewhere to live rather than needing its own separate surface later.

### Recorded recommendations (not separately contested)
- **Cross-tab intake**: give Shop its own capture route rather than reusing the Pantry camera via `returnTo=shop`, which currently lights up the Pantry tab mid-Shop task. Moot for the tab bar itself now that intake is modal.
- Fix the **stranded filter state**: deleting the last item of a filtered category leaves a blank body with no chip selected (`index.tsx:291-300`).
- Ensure the camera's **permission-denied and pending branches have a back affordance** — today they are a hard dead end (`scan.tsx:17-27`).
- `add.tsx`'s off-design-system styling is moot: it is replaced by the `+` sheet.

## Resolution
Resolved. Deferred: [ticket 23](23-later-user-settable-expiry.md) (user-settable expiry).
