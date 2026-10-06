"""Choose which corpus recipes to offer the meal-plan model.

The model never sees the whole corpus. Recipes are ranked by how many pantry
items they use (via the corpus search index), a random sample of the best
matches becomes the candidate list, and random other recipes top it up when the
pantry matches too few. Randomness keeps repeated Generate taps varied.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import random
    from collections.abc import Collection, Sequence

    from glean.recipes.corpus import RecipeCorpusStore
    from glean.recipes.search_index import RecipeSummary

SAMPLE_SIZE = 25
PANTRY_POOL_SIZE = 60

_EVERYTHING = 1_000_000
_TOKEN_RE = re.compile(r"\w+")
_MIN_TOKEN_LENGTH = 3


def sample_corpus_candidates(
    corpus: RecipeCorpusStore,
    *,
    pantry_names: Sequence[str],
    max_total_time_mins: int | None,
    exclude_external_ids: Collection[str],
    rng: random.Random,
    sample_size: int = SAMPLE_SIZE,
    pool_size: int = PANTRY_POOL_SIZE,
) -> list[RecipeSummary]:
    all_recipes, _ = corpus.search(per_page=_EVERYTHING)
    excluded = set(exclude_external_ids)
    eligible = {
        summary.external_id: summary
        for summary in all_recipes
        if summary.external_id not in excluded and _fits_time(summary, max_total_time_mins)
    }

    pantry_matches: Counter[str] = Counter()
    for name in pantry_names:
        pantry_matches.update(_recipes_using(corpus, name) & eligible.keys())

    # Most pantry items used first; random order within a tier so ties don't favour any recipe.
    tie_breaks = {external_id: rng.random() for external_id in sorted(pantry_matches)}
    ranked = sorted(pantry_matches, key=lambda external_id: (-pantry_matches[external_id], tie_breaks[external_id]))
    pool = ranked[:pool_size]
    picked = rng.sample(pool, min(sample_size, len(pool)))

    if len(picked) < sample_size:
        remaining = sorted(eligible.keys() - set(picked))
        picked += rng.sample(remaining, min(sample_size - len(picked), len(remaining)))
    return [eligible[external_id] for external_id in picked]


def _recipes_using(corpus: RecipeCorpusStore, pantry_name: str) -> set[str]:
    """Recipes matching any meaningful word of a pantry item ("tinned tomatoes" → "tomato")."""
    matched: set[str] = set()
    for token in _TOKEN_RE.findall(pantry_name.casefold()):
        if len(token) < _MIN_TOKEN_LENGTH:
            continue
        hits, _ = corpus.search(q=_singular_prefix(token), per_page=_EVERYTHING)
        matched.update(hit.external_id for hit in hits)
    return matched


def _singular_prefix(token: str) -> str:
    # Search matches word prefixes, so trimming a plural suffix also matches the singular.
    if token.endswith("es") and len(token) > 4:
        return token[:-2]
    if token.endswith("s") and len(token) > 3:
        return token[:-1]
    return token


def _fits_time(summary: RecipeSummary, max_total_time_mins: int | None) -> bool:
    return (
        max_total_time_mins is None or summary.total_time_mins is None or summary.total_time_mins <= max_total_time_mins
    )
