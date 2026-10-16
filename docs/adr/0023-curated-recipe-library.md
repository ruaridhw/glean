---
status: accepted
date: 2026-10-06
---

# The recipe library is deliberately curated: preview before save, and everything saved can be deleted

Search results are **previewed, not silently saved**: tapping a result opens it, and an explicit save/unsave toggle is what adds it to the library. Saved recipes are **deletable** — a library that can only grow isn't a library. Deleting a recipe keeps any plan entry that references it: the entry snapshots what you're cooking and just loses the link. "Add to plan" happens **in place** on the recipe screen, with the button reflecting "In plan" — no navigation, and nothing left behind that can re-add the recipe on a later visit to Plan.

**Source links are hidden.** Surfacing `source_url` as tappable attribution was tried, and in practice it kicked the user into the source's own app demanding a sign-in (Gousto) — attribution isn't worth that trap.

## Considered options

- **Tap-to-save directly from search.** Rejected: a stray tap permanently pollutes the library the plan draws from.
- **Keep the external "View source" link.** Rejected after use: the hand-off experience was worse than the attribution was worth.
- **Forbid deleting planned recipes.** Rejected: the snapshot semantics make deletion safe.

## Consequences

- **Import dedupes like search does** — "already saved" is said out loud, never silently swallowed.
- **Allergen suitability (`not_suitable_for`) is shown prominently** on the recipe; it is stored precisely so someone deciding what to cook can see it, and withholding it is the one omission with real-world consequences (ADR 0011).
- **The library's quality is a feature:** generation quality (ADR 0014) depends on the corpus and saved recipes being things the user actually cooks.
