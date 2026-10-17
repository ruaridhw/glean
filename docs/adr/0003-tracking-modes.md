---
status: accepted
date: 2026-10-15
---

# The pantry tracks most cupboard goods by presence, not quantity

Every catalogue item has a **tracking mode**:
- **Counted** items keep a quantity in their stock unit. A typical recipe uses most or all of a typical pack: meat, tins (400 g tomatoes and beans, 400 ml coconut milk), a ball of mozzarella. Staples used up over several meals, like pasta, rice and grains, are counted too.
- **Presence** items are just "have it or not". A recipe uses only a small fraction of the pack, and it keeps: spices, dried herbs, soy and fish sauce, vinegar, oils, condiment jars, baking basics.
- **Perishable** items are presence plus a use-by date. Those are things bought in a much bigger pack than one recipe needs that then go off: fresh herbs, bread, ginger, milk, cream, cheese, an opened jar.

Recipes keep their amounts as written, and teaspoons stay teaspoons. But the pantry never does arithmetic on presence or perishable items, so a recipe's "1 tsp cumin" against a 40 g jar can't fail or show "4.92892 ml". A needed but missing spice appears on the shopping list as "ground cumin, for 1 tsp".

## Consequences

- **A recipe never subtracts from presence or perishable stock.** Cooking only sets a perishable item's opened date, and its once-opened shelf life counts from then.
- **Mode is set per group, overridable per ingredient,** because perishability cuts across groups: ginger is root veg, yet perishable.
- **Conversions:** counted items convert within one dimension, or through a known density. An unconvertible recipe amount becomes its own shopping item rather than an error.
- **Once-opened shelf life depends on form, like unopened.** An opened tin keeps about 3 days, but an opened bag of dried pulses or pasta, or a frozen pack, keeps months. Groups with forms carry one once-opened value per form; groups without forms carry one value. Individual items override it (hard cheese keeps weeks, milk days).
- **Dairy is perishable by default.** Milk, butter, cheese and yoghurt carry a use-by date. Tinned or whole-pack items (evaporated milk, halloumi, mozzarella) are counted by override, and ghee, which keeps, is presence.
- **Food always has a shelf life; non-food has none.** The user may not enter a use-by date, so every perishable food item has a default unopened life and, where a pack gets opened, a once-opened life. Household, Health & beauty and non-edible baby and pet items never expire: the group rule is "no shelf life", not a large number. Edible baby and pet items (formula, pet food) are food and carry shelf lives through overrides.
