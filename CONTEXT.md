# Glean

Glean helps one household plan meals, keep track of what's in the kitchen, and shop for what's missing. This glossary covers the words for food and stock that the app, the backend and the people working on it share.

## Language

### The catalogue

**Catalogue**:
The shared, backend-owned reference list of everything a household buys, stocks or cooks with. Every device holds a synced copy.
_Avoid_: taxonomy, ingredient database, master list

**Catalogue item**:
Anything in the catalogue. It's either an ingredient or a household item.
_Avoid_: product, entry, thing

**Ingredient**:
A catalogue item you can cook with, e.g. coriander, tinned chickpeas, dried chickpeas.
_Avoid_: food item, grocery

**Household item**:
A catalogue item you buy but don't cook with, e.g. toilet roll, shampoo, birthday candles, cat food.
_Avoid_: non-food ingredient, sundry

**Ingredient group**:
The kind of thing a catalogue item is, e.g. Spices, Onions & garlic, Dairy, Tomatoes, peppers & aubergines, Household. A catalogue item takes its default rules from its group.
_Avoid_: category, "what", food category

**Form**:
The state an ingredient is sold and kept in: fresh, frozen, tinned/jarred, dried, or not applicable. Form is part of what an ingredient is: tinned chickpeas and dried chickpeas are different ingredients, because they keep, get tracked and get prepared differently.
_Avoid_: type, state, format

**Canonical name**:
The one plain name a catalogue item is known by, e.g. "coriander".
_Avoid_: display name, normalised name

**Alias**:
Any other name that means the same catalogue item, e.g. "Tesco Fresh Cut Coriander 30g" for coriander.
_Avoid_: synonym, mapping, raw name

**Provisional item**:
A catalogue item that normalisation added on its own, before anyone has curated it.
_Avoid_: provisional ingredient, draft item, LLM ingredient

**Override**:
A household's own change to a catalogue item's rules, such as a longer shelf life or a different store section, kept apart from the catalogue so a catalogue update never erases it.
_Avoid_: custom setting, user setting, preference

### Stock, lists and recipes

**Pantry item**:
One catalogue item the household has in stock, e.g. this tin of chickpeas or this bunch of coriander.
_Avoid_: stock item, inventory row

**Shopping item**:
One line on the shopping list: a catalogue item to buy, and the recipes it's needed for, if any.
_Avoid_: list entry, to-buy

**Recipe line**:
One ingredient and amount a recipe calls for, e.g. "1 × 400 g tin chickpeas". Where an ingredient comes in more than one form, the recipe line names the form it means.
_Avoid_: recipe ingredient, ingredient row

### Rules a catalogue item carries

**Tracking mode**:
How the pantry keeps track of an ingredient: counted, presence or perishable.
_Avoid_: stock type, inventory mode

**Counted**:
Tracked by quantity in its stock unit, e.g. 500 g of rice or 6 eggs.
_Avoid_: quantity-tracked

**Presence**:
Tracked only as in stock or not, with no quantity, e.g. ground cumin or soy sauce.
_Avoid_: cupboard basic, staple, untracked

**Perishable**:
Tracked as in stock or not, plus a use-by date. For things bought in a much bigger pack than one recipe needs, which then go off: fresh herbs, ginger, cream, an opened jar of curry paste.
_Avoid_: fresh, short-life

**Stock unit**:
The unit a counted ingredient's pantry quantity is kept in: grams, millilitres or a count.
_Avoid_: canonical unit, base unit

**Recipe unit**:
The unit a recipe states an amount in, kept as written for spoons and metric amounts, e.g. 1 tsp or 400 g.
_Avoid_: display unit

**Shelf life**:
How many days an ingredient keeps. There are two: **unopened**, and **once opened**.
_Avoid_: expiry period, best-before

**Opened date**:
The day a pantry item was first used. Its once-opened shelf life counts from here.
_Avoid_: open date, first-use date

**Meal-plan group**:
The broad nutritional bucket an ingredient counts towards when balancing a week: vegetables, fruit, protein, dairy, carbohydrates, fats or condiments.
_Avoid_: food group

**Store section**:
The part of a supermarket where something is found, at a level shared by every UK supermarket, e.g. Fruit & Veg, Food Cupboard, Baking, Frozen.
_Avoid_: aisle, department, category

### Normalisation

**Normalisation**:
Turning a raw name typed, scanned or imported into a catalogue item, or confirming that none fits.
_Avoid_: sanitisation, cleaning, canonicalisation

**Unmatched**:
A name normalisation has confirmed it can't identify as any catalogue item, such as a typo, kept exactly as written. A non-food name isn't unmatched: it's a household item.
_Avoid_: non-food, unknown

**Unresolved**:
A name normalisation couldn't settle this time, e.g. during a model outage. Nothing is recorded, and it's tried again later.
_Avoid_: pending, failed
