---
status: accepted
date: 2026-10-14
---

# Recipe import converts US and vague measures to the app's units

Imported recipes get their measures **converted at import time**: cups, ounces, pounds and vague measures ("a knob of butter", "a handful") become grams, millilitres or counts the pantry can reason about (#120/#146). This is a deliberate carve-out from ADR 0003's "recipes keep their amounts as written": *within* a recipe, teaspoons stay teaspoons, but *at the border*, rogue measurements are normalised once so nothing downstream has to understand them.

The owner reaffirmed this when an agent stated the plainer rule: "there was some recipe conversion that was being done... even for recipes I think that still makes sense."

## Considered options

- **Store as written, convert at display or subtraction.** Rejected: every consumer would need the conversion rules, and a "0.25 pcs Cup butter" style misparse would poison the pantry maths at the worst time.
- **Reject unconvertible lines.** Rejected: import should succeed; a genuinely unconvertible amount becomes its own shopping item rather than an error (ADR 0003).

## Consequences

- **The conversion rules apply to backfills too,** including their guards: historical rows that are already legitimate ("Clove oil", "Cheddar (1/2 lb)") must survive a re-run untouched.
- **A trailing parenthetical weight after a count is the total** ("2 tomatoes (400 g)"), which the converter relies on.
- **Conversion quality is measured by the import evals,** not by inspection of individual recipes.
