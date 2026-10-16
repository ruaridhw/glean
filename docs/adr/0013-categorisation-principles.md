---
status: accepted
date: 2026-10-15
---

# Categorisation follows household usefulness, not taxonomy for its own sake

The catalogue's groups are chosen by what the household needs the app to *do*, not by botanical or retail correctness. The principles, generalised from the seed-data review:

- **A distinction earns a group only where it changes behaviour.** Fruit is one group ("Fruit"), because splitting berries from stone fruit only bought slightly better default shelf lives — and each fruit item carries its own anyway. Vegetables stay split (onions & garlic; cabbage & broccoli; tomatoes, peppers & aubergines; roots; leafy greens) because the split helps the planner balance the week and orders the shopping list.
- **Allergy visibility beats tidiness.** Nuts & seeds are their own group, pulled out of Snacks & treats, because the household's nut allergy (ADR 0011) makes nuts something you must be able to spot and filter, wherever a supermarket happens to shelve them.
- **Names are plain English.** Nightshades, alliums and brassicas became Tomatoes, peppers & aubergines, Onions & garlic, and Cabbage & broccoli; "cabbage and broccoli family" lost the "family".
- **"Other" is a first-class fallback,** not a failure: drinks, snacks and non-food groups map to an "other" food group that doesn't count towards week balance — naming what the backend already did.
- **Defaults must survive a kitchen sniff-test.** Shelf-life defaults are per group *and* form (dried staples keep for months once opened; frozen keeps in the freezer), with per-ingredient overrides for outliers like hard cheese. Seed data is reviewed against real experience, and corrections are expected to keep arriving.

## Considered options

- **Botanically faithful groups.** Rejected: it put apples under "stone fruit" and bought nothing the app uses.
- **Matching one supermarket's aisles.** Rejected: store sections stay a level above any single chain's layout ("Fruit & Veg", "Meat & Fish", "Food Cupboard"), because layouts differ between supermarkets.

## Consequences

- **Proposing a new group needs a behavioural justification:** what does the app do differently because this group exists?
- **Merges are safe by construction:** renamed or merged items keep their old ids as aliases, so household overrides follow them (ADR 0001).
- **The full current group and food-group lists live in ADR 0002**, kept up to date as the record of the model.
