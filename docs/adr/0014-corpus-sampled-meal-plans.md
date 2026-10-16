---
status: accepted
date: 2026-10-06
---

# Meal plans are sampled from the recipe corpus, not generated freehand

Generate works from the **632-recipe corpus**, not just the user's saved recipes and never from the model's imagination (#97/#98). The backend ranks corpus recipes by how many pantry items they use, **samples at random from the top of that ranking**, applies the dietary filter *before* sampling, and shows the model only short candidate summaries (title, cuisine, time, key ingredients). The model picks and reasons; the server drops any id it didn't offer.

The owner's steer was explicit: feeding the whole corpus to the model is "a huge amount of context on every query", and the behaviour wanted is "generate five 'random' recipes from the corpus". Before this, Generate could only use saved recipes, so a small recipe box meant an empty plan — or the model inventing recipes.

## Considered options

- **Whole corpus in the prompt.** Rejected: context size, cost and latency on every generation.
- **Saved recipes only.** Rejected: with a handful saved, nothing fits the pantry.
- **Deterministic top-N.** Rejected: the same pantry would always plan the same week; sampling is what makes regeneration useful.

## Consequences

- **Near-duplicate recipes are offered at most once per plan** (≈70% ingredient overlap), because the corpus carries variants of the same dish.
- **The model is not asked for `missing_ingredients`:** it was often wrong, nothing used it, and the app computes shopping gaps from the saved recipe.
- **Every generation can legitimately differ.** That's a feature, and evals must not assert specific picks.
