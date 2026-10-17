---
status: accepted
date: 2026-10-15
---

# Dietary policy: tree nuts and peanuts are separate concerns, and allergen ground truth comes from supermarket listings

The household's allergy drives real policy, not just filter flags:

- **Tree nuts and peanuts are tracked separately.** "Nut-free" is not one bucket: satay and chilli crisp flag peanuts and are fine for a tree-nut allergy.
- **Korma paste and tikka masala paste count as containing tree nuts,** so recipes using them are excluded from nut-free plans unless the paste is labelled nut-free. Pasanda-style seasoning is fine. This is a household risk call, not a reading of the average label.
- **Pesto is allowed for vegetarian plans,** consistent with parmesan being allowed; it stays excluded for nut-free (pine nuts), vegan and dairy-free.
- **Ground truth on whether a processed ingredient contains an allergen is the ingredient and allergen lists published on the Tesco, Sainsbury's and Ocado online shops** — checked in a real browser, since those sites block plain HTTP clients. Model output is never its own ground truth.

## Considered options

- **One "nut-free" flag.** Rejected: it wrongly excludes peanut-only dishes for a tree-nut allergy and vice versa.
- **Treat "may contain" warnings as disqualifying for everything.** Rejected: many pastes carry the warning; the policy would exclude far more than the household intends.
- **Trusting the model's own knowledge of ingredients.** Rejected: the model can't see the label on the jar; supermarket listings can.

## Consequences

- **The decision model's criteria text encodes this policy** (ADR 0010), and the corpus-wide audit re-runs when the policy or the criteria change.
- **New "does X contain Y" questions** are answered by checking the supermarket listings first and pinning the answer into the policy.
- **Diet flags the model can't evidence** (keto, paleo) are left to the model's judgement rather than faked with rules.
