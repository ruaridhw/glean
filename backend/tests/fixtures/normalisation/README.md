# Normalisation eval set and result (#123)

How the match threshold in `glean.catalogue.normalise.MATCH_THRESHOLD` was set, and what the live eval showed.
Re-run with `cd backend && uv run python -m scripts.eval_normalisation --out /tmp/eval.json` (about 450 calls, a few cents).
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

Decision-stage sweep (run 1):

| Threshold | Correct | Duplicate (existing item missed) | False match |
|---|---|---|---|
| 0.30 – 0.55 | 85 | 3 | 3 |
| 0.60 | 85 | 4 | 2 |
| 0.65 – 0.75 | 87 | 4 | 0 |
| 0.80 | 84 | 7 | 0 |
| 0.90 | 78 | 13 | 0 |

**Threshold: 0.70.** That is the decision-stage result (run 1; run 2 below). Every false match at this stage had a
match probability of 0.63 or less ("Skyr yogurt" → natural yogurt at 0.62, "Microwave Rice" → easy cook rice at 0.63,
"750g potatoes" → tinned potatoes at 0.57). 0.65–0.75 score identically, so 0.70 sits in the middle with a margin above the
highest false match. At 0.70: 87 correct, 4 duplicates (existing item missed), 0 false matches of 91.

The decision model's probabilities drift a little between runs. In run 2 "coriander plant pot" (a household item) was
matched to coriander, which run 1 had rejected at 0.58; it is the one false match in the pipeline numbers below. The
kind guard didn't stop it because the decision put the pot in the fresh herbs group. Treat 0 of 91 as "about 1 in 100".

### The whole pipeline against the LLM alone (run 2, threshold 0.70, the 91 scored names)

The full service ran over the set in batches of 20, each against a fresh seed catalogue, with the real batched naming
call. The LLM-only baseline gets the same shortlist and one call per name: pick a candidate, or give a new canonical name
and a group, or say it is nonsense. Same grading for both.

| | Decision model + naming fallback | Naming LLM alone |
|---|---|---|
| Correct | 86 | 82 |
| Duplicate (existing item missed) | 3 | 5 |
| False match | 1 | 4 |
| Created in a group of the wrong kind or group | 0 | 0 |
| Nonsense given an item | 0 | 0 |
| Unresolved | 1 | 0 |
| Latency | 20 names in at most 1.4 s (one naming call per batch) | 0.54 s median per name, one call each |
| Cost per name | $0.000045 (decisions plus naming) | about $0.00004 (estimated from text length) |

- The unresolved name is "Bloo Power Active Lemon Rim Blocks": the decision put it in a food group, naming returned the
  name of an existing household item, and the kind guard refused to link a household name across kinds. That is the
  intended safe failure, and a retry tries again.
- The three duplicates ("Parmigiano Reggiano", "Jacket Potatoes", "large egg yolks") are catalogue gaps; each becomes an
  alias after one use. The naming fallback made no wrong-group or kind errors on the names it created, and gave all
  three nonsense names the unmatched outcome.
- Decision stage repeat consistency: two runs agreed on 90 of 91 names at the threshold (the flip is the pot above).
- Decision stage median latency 0.25 s; ingredient group inside the acceptable groups on 92% of names with no matching item.

The decision model costs about the same as the LLM alone and made fewer false matches (1 against 4) and fewer
duplicates (3 against 5).

## Limits worth knowing

- **All 29 ingredient groups fit in one `choice` question.** No error and no loss of accuracy at that size, so there is no
  workaround. The decisions endpoint publishes no option limit; this is the largest choice question measured.
- **Fresh herbs have no form.** The group has no forms (`not_applicable`), so coriander resolves with form `not_applicable`,
  not `fresh` as #123's acceptance criterion words it.
- **Latency.** A decision request took 0.25 s median and 0.54 s at most, with eight in flight. A batch of twenty names end to end
  (twenty decision requests, one naming call) took 1.4 s at most in the eval and 2 to 3 s for twenty new names in the live smoke
  test, against the 30 s request limit.
- The set is small and mostly UK supermarket names. Re-run the eval before moving the threshold.
