---
status: accepted
date: 2026-10-15
---

# Classify catalogue items by ingredient group plus form, with form part of the item's identity

Each catalogue item has **one ingredient group**: 29 groups today, all with plain-English names. The food groups derive from the original 23-category taxonomy (with fruit merged into one **Fruit** group and **Nuts & seeds** pulled out on its own), plus Baking, Drinks, Snacks & treats, Household, Health & beauty, Baby, Pet and Other. The principles behind which distinctions earned a group are in ADR 0013. Where it applies, an ingredient also has **a form**: fresh, frozen, tinned/jarred, dried, or not applicable. Form is part of what an ingredient is, so tinned chickpeas and dried chickpeas are different ingredients: they differ in shelf life once opened, in how they're tracked, and in prep. A recipe line names the form it means.

## Considered options

- **A single list of groups mixing kind and form** (Tins & jars and Frozen as groups beside Nightshades). Rejected: tinned tomatoes fit two groups at once, and tins or frozen food have no single food group.
- **The 23 categories and a second, independent group list.** Rejected: every item would carry two overlapping labels that can contradict each other.
- **Form as a property of each tin or bag in stock**, with one "chickpeas" ingredient. Rejected: shelf life, tracking and store section would then have to be worked out per pantry item, and a shopping list could confuse fresh tomatoes with tinned.

## Consequences

- **Food group comes from the ingredient group alone.** Each ingredient group maps to exactly one of eight food groups — vegetables, fruit, protein, dairy, carbohydrates, fats, condiments and **other** — which the meal plan uses to balance the week. "Other" (drinks, snacks and the non-food groups) doesn't count towards that balance; it names what the backend already fell back to. "Food group" keeps its name. Nuts & seeds count as protein and are shelved in Food Cupboard.
- **Store section and shelf-life defaults come from group and form together** (unopened and once opened alike). An ingredient never has a default from form alone: flour isn't "dried" for shelf-life purposes. Once-opened shelf life depends on form too: an opened bag of dried pulses keeps for months, not an opened tin's three days.
- **"Stock & gravy" isn't a separate group** (it's part of sauces and condiments), and **dairy isn't split**. Dairy is perishable by default (ADR 0003), with tinned and whole-pack items counted through per-ingredient overrides.
- **Renames from the old categories:** nightshades → Tomatoes, peppers & aubergines; alliums → Onions & garlic; brassicas → Cabbage & broccoli; oils_fats → Oils & fats.
