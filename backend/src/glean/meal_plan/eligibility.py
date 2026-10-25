"""The recency floor: leave out recipes the household cooked in the last six weeks.

This is the core of the spec's future `get_eligible_recipes` tool. The session's
hard constraints (dietary decisions, the time cap, meals already planned) are
applied by the caller first and are never relaxed; the floor is the only soft
rule, and it relaxes only when honouring it would starve the week — fewer than
three eligible recipes per slot — in which case recently cooked recipes come
back ranked last, carrying the recency penalty the scorer will apply once it
exists.

A thumbs-down rating joins the hard constraints: a recipe whose latest rating is
thumbs down is left out here and never comes back through the floor, so "not
that again" sticks until the household clears or flips the thumb. "Latest rating"
is CONTEXT.md's term: the thumb on the most recent *rated* cook, whichever way it
points, so a later thumbs up cancels an older thumbs down. Cooking a recipe again
without rating it does not silently undo the verdict. The app sends the cook that
carries this verdict when it is older than the history window, and resolves it by
the same id-then-title rule this module uses, so both sides read one recipe's
cooks the same way.

Deliberately store-free and framework-free: the planner graph, the evals and the
MCP server all call this with plain values, and it unit-tests on synthetic
corpora without the recipe corpus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

# Six weeks. Only cooked meals count, and only the cook relative to the request.
RECENCY_FLOOR_DAYS = 42
# The floor gives way rather than leaving the week unfillable: three recipes offered per slot.
MIN_ELIGIBLE_PER_SLOT = 3

# The thumbs-down value of the request's rating vocabulary (`schemas.Rating`). Only the exclusion lives
# here: the thumbs-up positive term belongs to the scorer.
RATING_DOWN = "down"

# Scorer weights for the recency term (spec §6.2, "Scorer weights"). They live here so the
# floor's ordering of relaxed recipes and the future scorer's penalty cannot drift apart.
PENALTY_WITHIN_FLOOR = -8.0
PENALTY_WEEKS_7_TO_9 = -3.0
PENALTY_WEEKS_10_TO_12 = -1.0


@dataclass(frozen=True)
class CookedMeal:
    """One cooked meal from the household's history window.

    `recipe_id` is the corpus recipe id, which the app keeps as the plan entry's
    `externalIdSnapshot`. It is null for meals cooked before that snapshot was
    stored, so `title` is the fallback identity. `rating` is the thumb the
    household left on this cook, or None when they left none; the note that can
    accompany it is never carried here, because nothing on the planning path
    reads one.
    """

    title: str
    cooked_at: datetime
    recipe_id: str | None = None
    rating: str | None = None


@dataclass(frozen=True)
class EligibleRecipes:
    """What the floor leaves of the hard-constraint-passing recipes.

    `fresh` is never cooked in the window. `relaxed` came back because the floor gave
    way; they are ordered least-preferred last, so a caller with no scorer ranks
    candidates by appending `relaxed` after `fresh`. `days_since_cooked` is the age of
    the most recent matching cook for every recipe the history mentions, so the caller
    can rank with `recency_penalty` instead of the two lists.

    `disliked` is what the rating check dropped: recipes whose latest rating is thumbs down. It is
    reported so a caller can log a deliberate exclusion rather than a mysteriously short list.
    `latest_rating` is the remaining recipes' latest thumb, which the scorer's positive rating term
    will read once it exists.
    """

    fresh: tuple[str, ...]
    relaxed: tuple[str, ...]
    # Days since the most recent matching cook, for every eligible recipe the history mentions (fresh
    # recipes included, so the scorer can call recency_penalty on them). Unmatched recipes have no entry.
    days_since_cooked: Mapping[str, float]
    disliked: tuple[str, ...] = ()
    latest_rating: Mapping[str, str] = field(default_factory=dict)

    @property
    def relaxed_floor(self) -> bool:
        """Whether recently cooked recipes are back in play for this request."""
        return bool(self.relaxed)

    @property
    def recipe_ids(self) -> tuple[str, ...]:
        return (*self.fresh, *self.relaxed)


@dataclass(frozen=True)
class RecipeHistory:
    """A household's history resolved against one set of recipe ids, for the floor and for the scorer.

    Both keys are recipe ids, matched by id or by title exactly as the floor matches them, so V6's scorer reads
    a cook's age and its latest thumb the same way the floor did when it decided what to offer.
    """

    days_since_cooked: Mapping[str, float]
    latest_rating: Mapping[str, str]


def recipe_history(
    recipe_ids: Iterable[str],
    *,
    titles: Mapping[str, str],
    cooked: Iterable[CookedMeal],
    now: datetime,
) -> RecipeHistory:
    """How long ago each of `recipe_ids` was cooked, and the thumb on its latest rated cook.

    A recipe the history never mentions has no entry in either map, which is what "never cooked" means; a cook
    with no rating leaves the last thumb standing. The scorer's recency and rating terms read this, and
    `apply_recency_floor` decides from it, so the two cannot disagree about one history.
    """
    ids = list(dict.fromkeys(recipe_ids))
    latest = _latest_cooks(cooked, now=now)
    return RecipeHistory(
        days_since_cooked=MappingProxyType(
            {
                recipe_id: days
                for recipe_id in ids
                if (days := _days_since_cooked(recipe_id, titles, latest)) is not None
            }
        ),
        latest_rating=MappingProxyType(
            {
                recipe_id: rating
                for recipe_id in ids
                if (rating := _latest_rating(recipe_id, titles, latest)) is not None
            }
        ),
    )


@dataclass(frozen=True)
class _LatestCook:
    """The housekeeping one identity key's cooks leave: how long ago, and the newest thumb on one."""

    days_since: float
    rated_at: datetime | None
    rating: str | None


def apply_recency_floor(
    eligible_ids: Iterable[str],
    *,
    titles: Mapping[str, str],
    cooked: Iterable[CookedMeal],
    now: datetime,
    slots: int,
    window_days: int = RECENCY_FLOOR_DAYS,
    min_per_slot: int = MIN_ELIGIBLE_PER_SLOT,
) -> EligibleRecipes:
    """Split `eligible_ids` (already filtered by the hard constraints) into fresh and relaxed.

    `titles` maps each eligible recipe id to its title, for history rows that carry no id.
    """
    ids = list(dict.fromkeys(eligible_ids))
    history = recipe_history(ids, titles=titles, cooked=cooked, now=now)
    # Thumbs down is a hard constraint, like a dietary flag: the floor hedges about repeats, never about
    # a recipe the household said not to cook again, so these are dropped before it relaxes.
    disliked = tuple(recipe_id for recipe_id in ids if history.latest_rating.get(recipe_id) == RATING_DOWN)
    kept = [recipe_id for recipe_id in ids if recipe_id not in set(disliked)]
    # A dropped recipe is not eligible, so it carries no age or rating into what the floor reports.
    kept_ids = set(kept)
    ages = {recipe_id: days for recipe_id, days in history.days_since_cooked.items() if recipe_id in kept_ids}
    ratings = {recipe_id: rating for recipe_id, rating in history.latest_rating.items() if recipe_id in kept_ids}
    fresh = [recipe_id for recipe_id in kept if recipe_id not in ages or ages[recipe_id] > window_days]
    recent = [
        (recipe_id, ages[recipe_id]) for recipe_id in kept if recipe_id in ages and ages[recipe_id] <= window_days
    ]
    days_since_cooked = MappingProxyType(ages)
    latest_rating = MappingProxyType(ratings)

    if len(fresh) >= slots * min_per_slot:
        return EligibleRecipes(
            fresh=tuple(fresh),
            relaxed=(),
            days_since_cooked=days_since_cooked,
            disliked=disliked,
            latest_rating=latest_rating,
        )
    # Least penalised first, so the most recently cooked of all lands last. Within one penalty
    # band the longer-ago cook is the less repetitive pick.
    relaxed = tuple(
        recipe_id for recipe_id, _ in sorted(recent, key=lambda item: (-recency_penalty(item[1]), -item[1], item[0]))
    )
    return EligibleRecipes(
        fresh=tuple(fresh),
        relaxed=relaxed,
        days_since_cooked=days_since_cooked,
        disliked=disliked,
        latest_rating=latest_rating,
    )


def recency_penalty(days_since_cooked: float | None) -> float:
    """The scorer's recency term for a recipe cooked `days_since_cooked` days ago.

    Negative, so it lowers a recipe's fit. Never cooked scores flat.
    """
    if days_since_cooked is None:
        return 0.0
    if days_since_cooked <= RECENCY_FLOOR_DAYS:
        return PENALTY_WITHIN_FLOOR
    if days_since_cooked <= RECENCY_FLOOR_DAYS + 21:
        return PENALTY_WEEKS_7_TO_9
    if days_since_cooked <= RECENCY_FLOOR_DAYS + 42:
        return PENALTY_WEEKS_10_TO_12
    return 0.0


# The thumbs-up scorer term belongs here, beside the recency one: +1 once the cook is older than the
# floor, per spec §6.2's Ratings row. It has no effect yet because no scorer exists; `latest_rating` on
# `EligibleRecipes` is the input it will read. Thumbs down never needs a weight -- it is excluded above.


def _latest_cooks(cooked: Iterable[CookedMeal], *, now: datetime) -> dict[str, _LatestCook]:
    """Key every cook by recipe id, or by title when the row has none, keeping the most recent.

    Age and rating are taken separately: a later unrated cook must not erase an earlier thumb, so the
    rating comes from the newest *rated* cook while the age comes from the newest cook of any kind.
    """
    newest: dict[str, datetime] = {}
    newest_rating: dict[str, tuple[datetime, str]] = {}
    for meal in cooked:
        # Normalise before comparing: one recipe's rows can mix a UTC-stamped backup row with a local
        # one, and naive and aware datetimes do not order against each other.
        cooked_at = _as_aware_utc(meal.cooked_at)
        for key in _identity_keys(meal):
            if key not in newest or cooked_at > newest[key]:
                newest[key] = cooked_at
            if meal.rating is not None and (key not in newest_rating or cooked_at > newest_rating[key][0]):
                newest_rating[key] = (cooked_at, meal.rating)
    latest: dict[str, _LatestCook] = {}
    for key, cooked_at in newest.items():
        rated = newest_rating.get(key)
        latest[key] = _LatestCook(
            days_since=_days_between(cooked_at, now),
            rated_at=None if rated is None else rated[0],
            rating=None if rated is None else rated[1],
        )
    return latest


def _identity_keys(meal: CookedMeal) -> list[str]:
    """The keys one cook can match an eligible recipe by: its corpus id, or its title when it has none."""
    return [f"id:{meal.recipe_id}"] if meal.recipe_id else [f"title:{_normalise_title(meal.title)}"]


def _keys_for(recipe_id: str, title: str) -> list[str]:
    # A title only matches rows that carried no id (older plan entries), and only for a recipe we know
    # the title of; every cook row is additionally keyed by its own id when it has one.
    return [f"id:{recipe_id}"] if not title else [f"id:{recipe_id}", f"title:{_normalise_title(title)}"]


def _days_since_cooked(recipe_id: str, titles: Mapping[str, str], latest: Mapping[str, _LatestCook]) -> float | None:
    """The most recent cook of this recipe, however the history rows identify it.

    A recipe is matched both by id and by title, because older plan entries carry no recipe id
    snapshot. The newest match wins: an old id-matched cook must not hide yesterday's title-only one.
    """
    matches = [latest[key].days_since for key in _keys_for(recipe_id, titles.get(recipe_id, "")) if key in latest]
    return min(matches) if matches else None


def _latest_rating(recipe_id: str, titles: Mapping[str, str], latest: Mapping[str, _LatestCook]) -> str | None:
    """The thumb on the most recent *rated* cook of this recipe, however the rows identify it.

    Only rated cooks count, so an unrated cook after a thumbs down leaves the verdict standing. Titles
    match exactly as they do for age, so an entry cooked before the app kept a corpus id is still the
    same recipe.
    """
    rated = [
        (cook.rated_at, cook.rating)
        for key in _keys_for(recipe_id, titles.get(recipe_id, ""))
        if key in latest and (cook := latest[key]).rated_at is not None
    ]
    if not rated:
        return None
    return max(rated, key=lambda item: item[0])[1]


def _normalise_title(title: str) -> str:
    return " ".join(title.split()).casefold()


def _days_between(earlier: datetime, later: datetime) -> float:
    return (later - _as_aware_utc(earlier)).total_seconds() / 86_400


def _as_aware_utc(value: datetime) -> datetime:
    # Requests are normalised at the schema boundary; this defends the arithmetic for other callers
    # (the graph, the evals, the MCP server) whose datetimes may still arrive naive. UTC, never local.
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
