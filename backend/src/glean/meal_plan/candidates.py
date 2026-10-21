"""Choose which corpus recipes to offer the meal-plan model.

The model never sees the whole corpus. Recipes are ranked by the urgency-weighted fit of
the pantry items they use (via the corpus search index), a random sample of the best
matches becomes the candidate list, and random other recipes top it up when the pantry
matches too few. Randomness keeps repeated Generate taps varied.

Two rules stop a perishable going off unused. A recipe using an item that expires within
`URGENT_EXPIRY_DAYS` is always in the candidate list, whatever the sampling picks (bounded
by `GUARANTEE_MAX`, which only changes *which* recipes are offered, never how many). And
every pantry match counts for as much as the item's urgency score, not as a flat one, so a
recipe using the most urgent item outranks one using several unfussy staples.

Dietary flags are applied here, before sampling, because the corpus carries no dietary
metadata of its own: a recipe is excluded when the stored decision for (recipe, flag) says
it probably breaks the flag, or when there is no current decision. Flags the decision
model isn't asked about (Keto, Paleo) are left to the meal-plan model.

Those flags, the household's time cap and the meals already planned are hard
constraints: `meal_plan.eligibility` applies the six-week recency floor on top of them and
never relaxes one to satisfy the other. The guarantee is narrower than either: it draws only
from the fresh recipes the floor left, so it never revives a recipe a hard constraint or the
six-week floor dropped, and relaxed recipes still only fill what the fresh ones leave.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from glean.meal_plan.dietary_decisions import DietaryDecisions, DietaryDecisionStore
from glean.meal_plan.eligibility import apply_recency_floor
from glean.observability import logger

if TYPE_CHECKING:
    import random
    from collections.abc import Collection, Iterable, Mapping, Sequence

    from glean.meal_plan.eligibility import CookedMeal
    from glean.recipes.corpus import RecipeCorpusStore
    from glean.recipes.search_index import RecipeSummary

SAMPLE_SIZE = 25
PANTRY_POOL_SIZE = 60
# An item expiring within this many days must reach the model, whatever the sampling picks.
URGENT_EXPIRY_DAYS = 3
# Cap on guaranteed inclusions: 10 of a 25-recipe sample leaves the rest of the list free to vary
# between Generate taps, and keeps the prompt the same size it was before the guarantee existed.
GUARANTEE_MAX = 10

_EVERYTHING = 1_000_000
_TOKEN_RE = re.compile(r"\w+")
_MIN_TOKEN_LENGTH = 3
_NEAR_DUPLICATE_OVERLAP = 0.7


@dataclass(frozen=True)
class OfferedRecipe:
    """One corpus recipe handed to the meal-plan model.

    `cooked_days_ago` is set only for a recipe the recency floor relaxed back in: it was cooked that
    recently and is offered as a fallback, which the prompt tells the model to prefer against. The
    scorer will read the same age to apply `eligibility.recency_penalty`.
    """

    summary: RecipeSummary
    cooked_days_ago: float | None = None

    @property
    def external_id(self) -> str:
        return self.summary.external_id

    @property
    def title(self) -> str:
        return self.summary.title


@dataclass(frozen=True)
class PantryItem:
    """One item of the pantry slice the request carries.

    `urgency_score` is the app's urgency for the item; an item the caller knows only by name weighs 1,
    which is how every pantry match counted before urgency weighting. `expires_in_days` is the whole
    number of days until the item goes off, or None when the expiry date is unknown -- the server
    cannot recover it from `urgency_score`.
    """

    name: str
    urgency_score: float | None = None
    expires_in_days: int | None = None

    @property
    def is_urgent(self) -> bool:
        """Whether this item goes off soon enough that a recipe using it must be offered."""
        return self.expires_in_days is not None and self.expires_in_days <= URGENT_EXPIRY_DAYS

    @property
    def weight(self) -> float:
        """How much one recipe using this item counts towards that recipe's pantry fit."""
        return 1.0 if self.urgency_score is None else self.urgency_score


def sample_corpus_candidates(
    corpus: RecipeCorpusStore,
    *,
    pantry: Sequence[PantryItem],
    dietary_flags: Sequence[str],
    max_total_time_mins: int | None,
    exclude_external_ids: Collection[str],
    rng: random.Random,
    cooked: Sequence[CookedMeal] = (),
    slots: int = 1,
    now: datetime | None = None,
    sample_size: int = SAMPLE_SIZE,
    pool_size: int = PANTRY_POOL_SIZE,
    guarantee_max: int = GUARANTEE_MAX,
) -> list[OfferedRecipe]:
    """Up to `sample_size` distinct corpus recipes to offer the meal-plan model.

    Recipes using a pantry item that goes off within `URGENT_EXPIRY_DAYS` are always included (up to
    `guarantee_max` of them) and lead the list. `cooked` is the household's history window and `slots`
    the number of meals this request plans; together they drive `eligibility.apply_recency_floor`.
    Recipes it relaxed back in are offered last, so they reach the candidate list only after every
    fresh recipe, and they are never guaranteed: the floor comes first.
    """
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

    fit = _pantry_fit(corpus, pantry, floor_ids)
    fresh = set(floor.fresh)
    # Random order within a tier so ties don't favour any recipe, drawn in id order so one seed is enough.
    tie_breaks = {external_id: rng.random() for external_id in sorted(fit)}
    guarantee_limit = min(guarantee_max, sample_size)

    # Most pantry fit first; random order within a tier so ties don't favour any recipe.
    ranked = sorted(fit, key=lambda external_id: (-fit[external_id].weight, tie_breaks[external_id]))
    # Recipes that came back when the floor relaxed are the least preferred: they trail the fresh ones
    # and never displace one, so a week with enough fresh recipes never offers a recent repeat. The
    # scorer will instead subtract recency_penalty from their fit (spec §6.2).
    fresh_ranked = [recipe_id for recipe_id in ranked if recipe_id in fresh]
    relaxed_ranked = [recipe_id for recipe_id in ranked if recipe_id not in fresh]
    picked: list[RecipeSummary] = []
    # Guaranteed first, so neither the random sample nor a relaxed recipe can crowd an urgent fresh
    # recipe out of the list. Only the fresh partition: the guarantee is applied after the six-week
    # floor and can never undo it, so a recipe the household cooked recently is never forced back in --
    # even in a week where the floor had to relax, where it is sampled alongside every other relaxed
    # recipe and can only take a slot the fresh ones left empty.
    urgent = [recipe_id for recipe_id, entry in fit.items() if entry.urgent and recipe_id in fresh]
    urgent.sort(key=lambda recipe_id: (-fit[recipe_id].weight, tie_breaks[recipe_id]))
    _take_distinct(picked, [eligible[recipe_id] for recipe_id in urgent], guarantee_limit)

    for group, pantry_ranked in ((floor.fresh, fresh_ranked), (floor.relaxed, relaxed_ranked)):
        _fill_from(picked, pantry_ranked[:pool_size], eligible=eligible, rng=rng, sample_size=sample_size)
        _fill_from(
            picked,
            set(group) - set(pantry_ranked[:pool_size]),
            eligible=eligible,
            rng=rng,
            sample_size=sample_size,
        )
    relaxed = set(floor.relaxed)
    return [
        OfferedRecipe(
            summary=summary,
            cooked_days_ago=(floor.days_since_cooked[summary.external_id] if summary.external_id in relaxed else None),
        )
        for summary in picked
    ]


def _fill_from(
    picked: list[RecipeSummary],
    recipe_ids: Iterable[str],
    *,
    eligible: Mapping[str, RecipeSummary],
    rng: random.Random,
    sample_size: int,
) -> None:
    """Append shuffled `recipe_ids` to `picked` until `sample_size`, skipping near-duplicates."""
    remaining = sorted(set(recipe_ids) - {summary.external_id for summary in picked})
    if not remaining or len(picked) >= sample_size:
        return
    _take_distinct(picked, [eligible[recipe_id] for recipe_id in rng.sample(remaining, len(remaining))], sample_size)


@dataclass(frozen=True)
class _PantryFit:
    """How one recipe fits the pantry: the urgency-weighted sum and the urgent items it uses."""

    weight: float
    urgent: tuple[PantryItem, ...]


def _pantry_fit(
    corpus: RecipeCorpusStore, pantry: Sequence[PantryItem], recipe_ids: Collection[str]
) -> dict[str, _PantryFit]:
    """Urgency-weighted pantry fit per recipe, for the recipes in `recipe_ids`."""
    wanted = set(recipe_ids)
    total: dict[str, float] = {}
    urgent: dict[str, list[PantryItem]] = {}
    for item in pantry:
        for external_id in _recipes_using(corpus, item.name) & wanted:
            total[external_id] = total.get(external_id, 0.0) + item.weight
            if item.is_urgent:
                urgent.setdefault(external_id, []).append(item)
    return {
        external_id: _PantryFit(weight=weight, urgent=tuple(urgent.get(external_id, ())))
        for external_id, weight in total.items()
    }


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
