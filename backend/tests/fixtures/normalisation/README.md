# Normalisation eval set and result (#123)

How the match threshold in `glean.catalogue.normalise.MATCH_THRESHOLD` was set, and what the live eval showed.
Re-run with `cd backend && uv run python -m scripts.eval_normalisation --out /tmp/eval.json` (about 300 calls, under a cent).
Decision model: `typesafe/jev-1.14` (snapshot `-20261014`); naming LLM: `google/gemini-2.5-flash-lite`. Run on 2026-10-15.

## The set

`eval_names.json` (this directory): 109 raw names, each labelled with the catalogue item it should
resolve to (some with extra acceptable items), "no item fits" with the acceptable ingredient groups, or nonsense.

- 42 receipt lines: the printed lines in #150's receipt-photo `expected.json` files (product names only).
- 21 shopping-list names, from the shopping-parse and purchase-description eval fixtures.
- 24 recipe ingredient names, from the ingredient-parser tests and the recipe-import fixture (the local test corpus
  holds only two recipes, so this source is thin).
- 22 typed names, written to probe household items, look-alikes, typos and nonsense.

18 names equal a catalogue name or alias and never reach the decision model in production, so 91 were scored.
Each ran against a fresh copy of the seed catalogue (538 items) with an 8-item shortlist.

## Result

| Threshold | Correct | Duplicate (existing item missed) | False match |
|---|---|---|---|
| 0.30 – 0.55 | 85 | 3 | 3 |
| 0.60 | 85 | 4 | 2 |
| 0.65 – 0.75 | 87 | 4 | 0 |
| 0.80 | 84 | 7 | 0 |
| 0.90 | 78 | 13 | 0 |

**Threshold: 0.70.** Every false match in the set had a match probability of 0.63 or less ("Skyr yogurt" → natural yogurt at 0.62, "Microwave Rice" → easy cook rice at 0.63, "750g potatoes" → tinned potatoes at 0.57). 0.65–0.75 score identically, so 0.70 sits in
the middle with a margin above the highest false match. False-match rate at 0.70: **0 of 91** (95% upper bound about 3%).
Four names were missed and would create a duplicate item ("Parmigiano Reggiano", "Jacket Potatoes", "large egg yolks",
"750g potatoes"); the fix for those is an alias, which the catalogue gains as people use it.

| | Decision model + naming fallback | Naming LLM alone (same shortlist) |
|---|---|---|
| Correct | 87 / 91 | 81 / 91 |
| False matches | 0 | 7 (e.g. "Roasted Red Peppers" → frozen diced mixed peppers, "750g potatoes" → tinned potatoes) |
| Duplicates | 4 | 3 |
| Median latency per name | 0.25 s (max 0.54 s) | 0.52 s |
| Cost per name | $0.00005 | about $0.00004 (estimated from text length; the router reports no usage) |

Repeat consistency: two runs of the decision model agreed on 91 / 91 names at the threshold.
Ingredient group on names with no matching item: 92% inside the acceptable groups.

The decision model's per-name cost is comparable to the LLM alone, with fewer false matches, which is the reason for it.

## Limits worth knowing

- **All 29 ingredient groups fit in one `choice` question.** No error and no loss of accuracy at that size, so there is no
  workaround. The decisions endpoint publishes no option limit; this is the largest choice question measured.
- **Fresh herbs have no form.** The group has no forms (`not_applicable`), so coriander resolves with form `not_applicable`,
  not `fresh` as #123's acceptance criterion words it.
- **Latency.** A decision request took 0.25 s median and 0.54 s at most, with eight in flight; twenty new names end to end (twenty decision
  requests, one batched naming call) took 2 to 3 s against the 30 s request limit.
- The set is small and mostly UK supermarket names. Re-run the eval before moving the threshold.
