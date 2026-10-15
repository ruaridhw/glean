---
status: accepted
date: 2026-10-15
---

# The pantry tracks most cupboard goods by presence, not quantity

Every catalogue item has a **tracking mode**:
- **Counted** items keep a quantity in their stock unit (meat, veg, dairy, pasta, rice and grains, tins).
- **Presence** items are just "have it or not" (spices, dried herbs, sauces, oils, baking basics).
- **Perishable** items are presence plus a use-by date. Those are things bought in a much bigger pack than one recipe needs that then go off: fresh herbs, ginger, cream, an opened jar.

Recipes keep their amounts as written, and teaspoons stay teaspoons. But the pantry never does arithmetic on presence or perishable items, so a recipe's "1 tsp cumin" against a 40 g jar can't fail or show "4.92892 ml". A needed but missing spice appears on the shopping list as "ground cumin, for 1 tsp".

## Consequences

- **A recipe never subtracts from presence or perishable stock.** Cooking only sets a perishable item's opened date, and its once-opened shelf life counts from then.
- **Mode is set per group, overridable per ingredient,** because perishability cuts across groups: ginger is root veg, yet perishable.
- **Conversions:** counted items convert within one dimension, or through a known density. An unconvertible recipe amount becomes its own shopping item rather than an error.
