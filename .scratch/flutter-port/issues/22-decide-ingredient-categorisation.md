Type: grilling
Status: resolved

## Question

Surfaced by [ticket 11](11-ux-review-pantry.md) and [ticket 14](14-ux-review-plan.md), and **blocking** the expiry-inference decision in ticket 11.

**Nothing in the app ever assigns an ingredient category.** `db/pantry.ts:81` calls `resolveOrCreateIngredient({ canonical_name })` omitting `category`, and `ParsedIngredient` (`api/types.ts:6-12`) carries no category field — the backend's parse endpoints don't return one. So every newly-created ingredient gets `category: null` → `food_group` null → `getPantryCategoryMeta` returns `"other"` (`pantry/presentation.ts:47`). Only the 10 staples seeded in `db/seed.ts:5-16` have real categories.

Three separate features are broken by this one gap:

1. **Pantry grouping and filter chips degenerate to a single "Other" bucket** for everything the user actually adds.
2. **Meal-plan generation 422s.** `food_group` is nullable client-side but the backend declares it non-nullable (`meal_plan/schemas.py:11`), so any uncategorised ingredient reaching the compressed top-15 fails Pydantic validation → the user sees a generic "Could not generate meal plan". The `as Parameters<typeof compressPantry>[0]` cast at `plan/index.tsx:238` is precisely what silences the type error.
3. **Expiry inference has no basis.** Ticket 11 decided to infer expiry automatically, but per-category shelf-life defaults require a category to infer from.

Decide how ingredients get categorised — noting this likely requires the narrow backend-change exception the effort reserved.

## Answer

**The backend returns `category` (and therefore `food_group`) from its ingredient-parsing endpoints.** This is a deliberate, narrow use of the backend-change exception the effort reserved — justified because one small change unblocks three separately-broken features including a crash, and because the LLM already identifies each ingredient while parsing, so classifying it against the existing 23-category taxonomy (`db/ingredient-categories.ts`, seeded by `db/seed.ts`) is nearly free.

Scope of the backend change:
- `POST /receipts/scan`, `POST /receipts/describe`, and `POST /shopping/parse-description` add a category (and food group) per parsed ingredient, drawn from the **existing** 23-category taxonomy — not a new vocabulary.
- The client's `ParsedIngredient` type (`api/types.ts:6-12`) gains the field, and the Flutter equivalent of `resolveOrCreateIngredient` persists it instead of dropping it.
- Once categories are reliably present, `food_group` stops being nullable on the client, which removes the `plan/index.tsx:238` cast and the 422 failure mode outright.

Rejected alternative: client-side categorisation by name lookup — would mean shipping and maintaining a food taxonomy inside the app, and would still miss unusual ingredients.
Rejected alternative: dropping pantry grouping/filter chips for a flat list — cheaper, but discards a real feature and leaves expiry inference with no basis.

### Unblocks
- Pantry grouping + filter chips become meaningful (ticket 11).
- Meal-plan generation stops 422-ing on uncategorised items (ticket 14).
- Per-category shelf-life defaults become possible, so ticket 11's automatic expiry inference is implementable.

### Note for the spec
This is the **only** backend change sanctioned by this effort. It should be called out explicitly in `FLUTTER_MIGRATION.md` as a prerequisite, since the Flutter client depends on it for three features and it must ship before or with the port.
