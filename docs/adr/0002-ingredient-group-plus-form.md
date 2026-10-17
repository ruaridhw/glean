---
status: accepted
date: 2026-10-15
---

# Classify catalogue items by ingredient group plus form, with form part of the item's identity

Each catalogue item has **one ingredient group**: today's food categories, with the four fruit categories (citrus, tropical fruit, stone fruit, berries) merged into one **Fruit** group, plus Baking, Nuts & seeds, Drinks, Snacks & treats, Household, Health & beauty, Baby, Pet and Other (29 in all), all with plain-English names. Where it applies, an ingredient also has **a form**: fresh, frozen, tinned/jarred, dried, or not applicable. Form is part of what an ingredient is, so tinned chickpeas and dried chickpeas are different ingredients: they differ in shelf life once opened, in how they're tracked, and in prep. A recipe line names the form it means.

## Considered options

- **A single list of groups mixing kind and form** (Tins & jars and Frozen as groups beside Nightshades). Rejected: tinned tomatoes fit two groups at once, and tins or frozen food have no single food group.
- **The 23 categories and a second, independent group list.** Rejected: every item would carry two overlapping labels that can contradict each other.
- **Form as a property of each tin or bag in stock**, with one "chickpeas" ingredient. Rejected: shelf life, tracking and store section would then have to be worked out per pantry item, and a shopping list could confuse fresh tomatoes with tinned.

## Consequences

- **Food group comes from the ingredient group alone.** Each ingredient group maps to exactly one food group, which the meal plan uses to balance the week. "Food group" keeps its name. Drinks, Snacks & treats and the non-food groups map to the food group **other**, which doesn't count towards the week's balance. Nuts & seeds count as protein and are shelved in Food Cupboard.
- **Store section and shelf-life defaults come from group and form together** (unopened and once opened alike). An ingredient never has a default from form alone: flour isn't "dried" for shelf-life purposes.
- **"Stock & gravy" isn't a separate group** (it's part of sauces and condiments), and **dairy isn't split**. Dairy is perishable by default (ADR 0003), with tinned and whole-pack items counted through per-ingredient overrides.
- **Renames from the old categories:** nightshades → Tomatoes, peppers & aubergines; alliums → Onions & garlic; brassicas → Cabbage & broccoli; oils_fats → Oils & fats.
- **One Fruit group, not subgroups.** Fruit subgroups would be botanical labels (is an apple a stone fruit?), and what really differs between fruits is shelf life, which lives on the items: berries keep about 4 days, citrus 14, apples 30. The group's own default is a generic week for fruit the catalogue doesn't know yet. Vegetable groups stay as they are.
