"""Choose which corpus recipes to offer the meal-plan model.

The model never sees the whole corpus. Recipes are ranked by how many pantry
items they use (via the corpus search index), a random sample of the best
matches becomes the candidate list, and random other recipes top it up when the
pantry matches too few. Randomness keeps repeated Generate taps varied.

Dietary flags are applied here, before sampling, because the corpus carries no
dietary metadata of its own: a recipe is excluded when the stored decision for
(recipe, flag) says it probably breaks the flag, or when there is no current
decision. Flags the decision model isn't asked about (Keto, Paleo) are left to
the meal-plan model.

Those flags, the household's time cap and the meals already planned are hard
constraints: `meal_plan.eligibility` applies the six-week recency floor on top of
them and never relaxes one to satisfy the other.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from glean.meal_plan.dietary_decisions import DietaryDecisions, DietaryDecisionStore
from glean.meal_plan.eligibility import apply_recency_floor
from glean.observability import logger

if TYPE_CHECKING:
    import random
    from collections.abc import Collection, Sequence

    from glean.meal_plan.eligibility import CookedMeal
    from glean.recipes.corpus import RecipeCorpusStore
    from glean.recipes.search_index import RecipeSummary

SAMPLE_SIZE = 25
PANTRY_POOL_SIZE = 60

_EVERYTHING = 1_000_000
_TOKEN_RE = re.compile(r"\w+")
_MIN_TOKEN_LENGTH = 3
_NEAR_DUPLICATE_OVERLAP = 0.7


def sample_corpus_candidates(
    corpus: RecipeCorpusStore,
    *,
    pantry_names: Sequence[str],
    dietary_flags: Sequence[str],
    max_total_time_mins: int | None,
    exclude_external_ids: Collection[str],
    rng: random.Random,
    cooked: Sequence[CookedMeal] = (),
    slots: int = 1,
    now: datetime | None = None,
    sample_size: int = SAMPLE_SIZE,
    pool_size: int = PANTRY_POOL_SIZE,
) -> list[RecipeSummary]:
    all_recipes, _ = corpus.search(per_page=_EVERYTHING)
    excluded = set(exclude_external_ids)
    flags = [flag.strip().casefold() for flag in dietary_flags]
    decisions = DietaryDecisions(DietaryDecisionStore(corpus.store).load())
    # Hard constraints only: the recency floor is applied to what survives them, and relaxing the
    # floor must never bring back a recipe a flag, the time cap or an already-planned meal ruled out.
    eligible = {
        summary.external_id: summary
        for summary in all_recipes
        if summary.external_id not in excluded
        and _fits_time(summary, max_total_time_mins)
        and not any(decisions.excludes(summary, flag) for flag in flags)
    }
    floor = apply_recency_floor(
        eligible,
        titles={external_id: summary.title for external_id, summary in eligible.items()},
        cooked=cooked,
        now=now or datetime.now(UTC),
        slots=slots,
    )
    floor_ids = set(floor.recipe_ids)
    if floor.relaxed_floor:
        # The soft repeat rule gave way because the hard constraints left too few fresh recipes. Reported
        # so eval runs and logs can tell "no repeats" from "no repeats because the floor never relaxed".
        logger.info("recency floor relaxed", extra={"recently_cooked": len(floor.relaxed), "slots": slots})

    pantry_matches: Counter[str] = Counter()
    for name in pantry_names:
        pantry_matches.update(_recipes_using(corpus, name) & floor_ids)

    # Most pantry items used first; random order within a tier so ties don't favour any recipe.
    tie_breaks = {external_id: rng.random() for external_id in sorted(pantry_matches)}
    ranked = sorted(pantry_matches, key=lambda external_id: (-pantry_matches[external_id], tie_breaks[external_id]))
    # Recipes that came back when the floor relaxed are the least preferred, so they trail the fresh
    # ones. The scorer will instead subtract recency_penalty from their fit (spec §6.2).
    fresh = set(floor.fresh)
    preferred = [*(recipe_id for recipe_id in ranked if recipe_id in fresh)]
    preferred += [recipe_id for recipe_id in ranked if recipe_id not in fresh]
    pool = preferred[:pool_size]
    picked: list[RecipeSummary] = []
    _take_distinct(picked, [eligible[external_id] for external_id in rng.sample(pool, len(pool))], sample_size)

    if len(picked) < sample_size:
        for group in (floor.fresh, floor.relaxed):
            rest = sorted(set(group) - {summary.external_id for summary in picked})
            _take_distinct(picked, [eligible[external_id] for external_id in rng.sample(rest, len(rest))], sample_size)
    return picked


def _take_distinct(picked: list[RecipeSummary], shuffled: Sequence[RecipeSummary], limit: int) -> None:
    """Append recipes in order until `limit`, skipping near-duplicates of ones already picked."""
    for summary in shuffled:
        if len(picked) >= limit:
            return
        if not any(_near_duplicate(summary, existing) for existing in picked):
            picked.append(summary)


def _near_duplicate(a: RecipeSummary, b: RecipeSummary) -> bool:
    # The corpus holds variants of one dish (chicken breast / thigh / meat-free); offering several
    # wastes candidate slots and the model tends to pick them together.
    ingredients_a, ingredients_b = _ingredient_set(a), _ingredient_set(b)
    if not ingredients_a or not ingredients_b:
        return False
    return len(ingredients_a & ingredients_b) / len(ingredients_a | ingredients_b) >= _NEAR_DUPLICATE_OVERLAP


def _ingredient_set(summary: RecipeSummary) -> set[str]:
    return {" ".join(_TOKEN_RE.findall(name.casefold())) for name in summary.ingredient_names}


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
