---
status: accepted
date: 2026-10-15
---

# Classify catalogue items by ingredient group plus form, with form part of the item's identity

Each catalogue item has **one ingredient group**: today's 23 food categories plus Baking, Drinks, Snacks & treats, Household, Health & beauty, Baby, Pet and Other, all with plain-English names. Where it applies, an ingredient also has **a form**: fresh, frozen, tinned/jarred, dried, or not applicable. Form is part of what an ingredient is, so tinned chickpeas and dried chickpeas are different ingredients: they differ in shelf life once opened, in how they're tracked, and in prep. A recipe line names the form it means.

## Considered options

- **A single list of groups mixing kind and form** (Tins & jars and Frozen as groups beside Nightshades). Rejected: tinned tomatoes fit two groups at once, and tins or frozen food have no single food group.
- **The 23 categories and a second, independent group list.** Rejected: every item would carry two overlapping labels that can contradict each other.
- **Form as a property of each tin or bag in stock**, with one "chickpeas" ingredient. Rejected: shelf life, tracking and store section would then have to be worked out per pantry item, and a shopping list could confuse fresh tomatoes with tinned.

## Consequences

- **Food group comes from the ingredient group alone.** Each ingredient group maps to exactly one food group, which the meal plan uses to balance the week. "Food group" keeps its name.
- **Store section and shelf-life defaults come from group and form together.** An ingredient never has a default from form alone: flour isn't "dried" for shelf-life purposes.
- **"Stock & gravy" isn't a separate group** (it's part of sauces and condiments), and **dairy isn't split**. Cream and soft cheese are perishable through per-ingredient overrides.
- **Renames from the old categories:** nightshades → Tomatoes, peppers & aubergines; alliums → Onions & garlic; brassicas → Cabbage & broccoli; oils_fats → Oils & fats.
