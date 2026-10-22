---
status: accepted
date: 2026-10-22
---

# Recipe enrichment is a pipeline of declarative enrichers behind one runner

Everything the planner needs to know about a recipe beyond its own text — whether it breaks a dietary flag, its main protein, its active time — costs a decision-model call. Enrichment is therefore a first-class backend package, `recipes/enrichment/` (spec 6.1, F2), not a script per derived fact:

- **Enrichers declare questions.** An enricher is one family of questions ("dietary", "attributes", "active time"). Each question carries the wording handed to the decision model, its criteria, its confidence bar and the rule that turns a raw answer into a stored value. An enricher never asks, batches or stores anything itself.
- **The runner asks once per recipe.** For each recipe it collects every question that is missing or stale *across all enrichers* and sends them in one `DecisionClient.decide` request. A recipe with nothing to ask makes no request.
- **Every answer is its own item,** keyed `(recipe, question, criteria hash)` in #162's store. A question is **stale** when its criteria hash changed (the wording was edited), when the recipe's content hash changed (title or ingredients were edited), or when the answer came from another model than the pinned one. So editing one question's wording re-asks only that question, still as one request per recipe, and stored answers survive a deploy that changed nothing.
- **Confidence bars decide what a question accepts.** No answer is accepted because it is the top option. Each question states a threshold *and which side of it is safe*: a dietary question is safe at a low probability, so its 0.3 is an exclusion threshold applied when planning reads the answer (ADR 0011); an attribute question is safe at a high probability, so 0.8 is a floor under which `unsure` is stored. The bar is declared where the question is, so the runner, the coverage report and a reviewer read one fact.
- **It is a producer, run by the owner,** after a corpus import, a question rewording or a model bump — never inside a request (spec 7). `make enrich-corpus` and `scripts/enrich_corpus.py` are the entry points; the script refuses a prod table or bucket without `--i-am-the-owner`, needs the decision API key in the environment, and exits non-zero unless every recipe has a current answer to every question, which is the deploy gate. A scheduled run is parked (spec 9).

## Considered options

- **A script per derived fact** (what the dietary producer was). Rejected: each new fact re-implements staleness, batching, checkpointing and reporting, and every one of them spends its own model request per recipe.
- **One decision request for a batch of recipes.** Rejected: the request carries one `state` (one recipe), and a thousand-recipe batch would be one failure away from losing everything.
- **Rebuilding the projection per recipe.** Rejected: the runner writes answers in checkpoints and rebuilds the projection once at the end, because a per-recipe rebuild is one S3 write per paid call.
- **Storing a `unsure`/label value on the answer item now.** Deferred to V5 with the attribute questions that need it: today's answer item carries a probability, and dietary's stored value is exactly that.

## Consequences

- **The stored answers are the checkpoint.** A run that stops partway has written what it got, so the next run asks only what is left; no progress file can drift from the store.
- **V5's attributes join the same request.** Declaring protein, carb, dish type, cuisine, whole-food and active-time questions adds them to the per-recipe request without touching the runner.
- **Adding an enricher is a coverage question, not a schema one.** The coverage report is per question (current / stale / missing / failed) plus the count of recipes that state an active time.
- **The corpus is never trusted to be complete.** With no ingredient rules to fall back on, a recipe missing a current dietary answer is excluded under that flag; running enrichment is part of shipping a corpus change.
