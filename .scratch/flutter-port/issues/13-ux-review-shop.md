Type: grilling
Status: resolved

## Question

Review the current Shop flow's user-facing behavior end to end — `mobile/app/(tabs)/shop/index.tsx`, `describe.tsx`, `review.tsx` — and decide, screen by screen, whether the current UX makes sense or should change for the Flutter port. Don't assume 1:1 parity is the goal; if something is confusing or awkward today, surface it and grill the user until there's a shared answer for what it should do instead. Record the resolved behavior for each screen (kept as-is / changed, and how).

## Answer (partial — decided so far)

### Checkout data loss — DECIDED
Today `completeCheckout` (`db/shopping.ts:163-165`, called from `pantry/review.tsx:46`) deletes **every** checked row on `is_checked = true`, not the `resolvedIds` actually written to the pantry. Check off 12 items, scan a receipt matching 4, and the other 8 vanish without ever becoming pantry stock.

**Decided**: only remove rows the receipt actually resolved into pantry items. Unmatched checked rows **stay on the list** (still checked) — nothing silently disappears. Also add an explicit **"Done shopping"** action so a receipt-less trip can be completed; today checkout is reachable *only* through the camera, so a cart otherwise persists indefinitely and must be emptied one `×` at a time.

Asking the user mid-checkout ("we couldn't match these — keep or remove?") is the preferred end state but is deferred → [ticket 21](21-later-mid-checkout-unmatched-prompt.md).

### Bugs — must not reproduce
- **`db/shopping.ts:83-89` `checkOffByIngredientIds` ignores `is_checked` and scope** — updates *every* row with a matching `ingredient_id`. A receipt containing milk checks off an unchecked milk row the user deliberately left for next time; combined with the deletion bug above, it then deletes it.
- `shop/index.tsx:43-47` — `setAdding(true)` with no `try/finally`; any DB error leaves the add button **permanently disabled** with no error shown.
- `shop/review.tsx:88-95` — decimal quantities are untypeable (`String(quantity)` + `Number(value)` round-trip); non-numeric input yields `NaN`, persisted as the literal string.
- Inconsistent numeric fallbacks between the twin review screens: `shop/review.tsx:91` → `1`, `pantry/review.tsx:91` → `0`.
- `shop/review.tsx:20` / `intake/serialization.ts:20` — unguarded `JSON.parse` on nav params white-screens a route with no back button.
- `shop/review.tsx:35` — `router.replace` leaves `describe` in the stack, so Android back resurrects it with stale text.
- `CheckoutBar` floats ~90px above the screen bottom (`AppScreen.tsx:47` padding), leaving a dead band.
- Skeleton flash on every tab focus (`shop/index.tsx:28` sets `loading = true` unconditionally).
- Manual items always carry `ingredient_id: null` (`db/shopping.ts:101`), so a receipt can never match them.

### Still open
- Should checking an item off optionally create a pantry item (making the receipt non-mandatory)?
- Should shopping items resolve to an ingredient identity on entry (fixing the never-matches problem)?
- Does the receipt scan belong to Shop or Pantry? (It currently hops tabs mid-flow.)
- One review screen or two? (`shop/review` and `pantry/review` do the same job with different looks and different button verbs.)
- Should plan-derived shopping rows be announced, and removed when the planned meal is deleted?
- Copy: "N checked" / "N items in cart" / "In your cart" — three names for one state.

### Deletes and undo — DECIDED
See [cross-cutting decisions](_cross-cutting.md): swipe-only, drop the `×` that appears on checked rows, undo snackbar on delete.

### Intake flow — DECIDED
Shares [ticket 11](11-ux-review-pantry.md)'s decision: intake is a modal task with the tab bar hidden (fixing the mid-scan capture loss), the twin review screens unify into one, and the fake progress steps are replaced with an honest indicator plus timeout and cancel.

### Manual item identity — DECIDED
**Manual shopping entries resolve to a real ingredient identity on entry**, via the same `resolveOrCreateIngredient` path intake already uses. Today they always store `ingredient_id: null` (`db/shopping.ts:101`), which is the root cause of manual items never matching a receipt — while checkout was nevertheless deleting them.

Resolving on entry means manual items participate in receipt matching, pantry shortfall maths, and the new category/expiry inference ([ticket 22](22-decide-ingredient-categorisation.md)) like everything else. Cost: a lookup on add, and occasionally an ambiguous match to handle.

### Recorded recommendations (not separately contested)
- **Announce plan-derived shopping rows.** `addShoppingGapsForRecipe` silently inserts rows on plan-add and generate (`plan/index.tsx:196`, `:260`); mention it in the confirmation snackbar.
- **Remove a planned meal's shopping rows when the meal is deleted** — they are currently orphaned. Requires per-row provenance, which the schema doesn't track today.
- **Unify the copy**: "N checked" / "N items in cart" / "In your cart" are three names for one state — pick one.
- The add-item field is currently the `SectionList` header so it **scrolls out of view** — pin it.

## Resolution
Resolved. Deferred: [ticket 21](21-later-mid-checkout-unmatched-prompt.md) (mid-checkout unmatched prompt).
