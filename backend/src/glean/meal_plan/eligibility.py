"""The recency floor: leave out recipes the household cooked in the last six weeks.

This is the core of the spec's future `get_eligible_recipes` tool. The session's
hard constraints (dietary decisions, the time cap, meals already planned) are
applied by the caller first and are never relaxed; the floor is the only soft
rule, and it relaxes only when honouring it would starve the week — fewer than
three eligible recipes per slot — in which case recently cooked recipes come
back ranked last, carrying the recency penalty the scorer will apply once it
exists.

Deliberately store-free and framework-free: the planner graph, the evals and the
MCP server all call this with plain values, and it unit-tests on synthetic
corpora without the recipe corpus.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

# Six weeks. Only cooked meals count, and only the cook relative to the request.
RECENCY_FLOOR_DAYS = 42
# The floor gives way rather than leaving the week unfillable: three recipes offered per slot.
MIN_ELIGIBLE_PER_SLOT = 3

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
    stored, so `title` is the fallback identity.
    """

    title: str
    cooked_at: datetime
    recipe_id: str | None = None


@dataclass(frozen=True)
class EligibleRecipes:
    """What the floor leaves of the hard-constraint-passing recipes.

    `fresh` is never cooked in the window. `relaxed` came back because the floor gave
    way; they are ordered least-preferred last, so a caller with no scorer ranks
    candidates by appending `relaxed` after `fresh`.
    """

    fresh: tuple[str, ...]
    relaxed: tuple[str, ...]

    @property
    def relaxed_floor(self) -> bool:
        """Whether recently cooked recipes are back in play for this request."""
        return bool(self.relaxed)

    @property
    def recipe_ids(self) -> tuple[str, ...]:
        return (*self.fresh, *self.relaxed)


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
    last_cooked = _last_cooked_days(cooked, now=now)
    fresh: list[str] = []
    recent: list[tuple[str, float]] = []
    for recipe_id in ids:
        days = _days_since_cooked(recipe_id, titles.get(recipe_id, ""), last_cooked)
        if days is not None and days <= window_days:
            recent.append((recipe_id, days))
        else:
            fresh.append(recipe_id)

    if len(fresh) >= slots * min_per_slot:
        return EligibleRecipes(fresh=tuple(fresh), relaxed=())
    # Least penalised first, so the most recently cooked of all lands last. Within one penalty
    # band the longer-ago cook is the less repetitive pick.
    relaxed = tuple(
        recipe_id for recipe_id, _ in sorted(recent, key=lambda item: (-recency_penalty(item[1]), -item[1], item[0]))
    )
    return EligibleRecipes(fresh=tuple(fresh), relaxed=relaxed)


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


def _last_cooked_days(cooked: Iterable[CookedMeal], *, now: datetime) -> dict[str, float]:
    """Key every cook by recipe id, or by title when the row has none, keeping the most recent."""
    latest: dict[str, datetime] = {}
    for meal in cooked:
        days = _days_between(meal.cooked_at, now)
        for key in _keys_for(meal):
            if key not in latest or days < _days_between(latest[key], now):
                latest[key] = meal.cooked_at
    return {key: _days_between(cooked_at, now) for key, cooked_at in latest.items()}


def _keys_for(meal: CookedMeal) -> list[str]:
    if meal.recipe_id:
        return [f"id:{meal.recipe_id}"]
    return [f"title:{_normalise_title(meal.title)}"]


def _days_since_cooked(recipe_id: str, title: str, last_cooked: Mapping[str, float]) -> float | None:
    days = last_cooked.get(f"id:{recipe_id}")
    if days is None and title:
        days = last_cooked.get(f"title:{_normalise_title(title)}")
    return days


def _normalise_title(title: str) -> str:
    return " ".join(title.split()).casefold()


def _days_between(earlier: datetime, later: datetime) -> float:
    return (later - _as_aware_utc(earlier)).total_seconds() / 86_400


def _as_aware_utc(value: datetime) -> datetime:
    # The app sends ISO datetimes from local DateTime values, so they can arrive naive; they are stored as UTC.
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
