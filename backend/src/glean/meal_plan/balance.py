"""What the scorer needs, built from a request's offered candidates, and the weeks it makes of them (V6).

`pipeline.prepare` decides what the household may be offered; this module turns that offer into the plain
inputs `meal_plan.tools` scores — the attributes V5 measured, the calories the recipe page stated, the pantry
fit V4 already weighted, the cook age and thumb V2 read, and the six-week floor's verdict — and then into the
two candidate weeks the model picks between (spec §10 V6: "prepare runs them, and plan picks between the two").

The per-recipe inputs ride the prepared plan as JSON, so a resumed session, or a `/meal-plan` call replaying
the same request, scores a week from the same numbers the run that started it saw. Nothing here reads a store
or a model: the caller hands over plain values and gets back plain values.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from glean.meal_plan.tools import (
    CandidateRecipe,
    PlanGap,
    PlanScore,
    Rating,
    ScorerWeights,
    ScoringContext,
    Term,
    chosen_vs_best_gap,
    create_candidate_meal_plans,
    score_meal_plan,
)
from glean.recipes.attributes import RecipeAttributes

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from glean.meal_plan.candidates import OfferedRecipe
    from glean.meal_plan.eligibility import RecipeHistory
    from glean.recipes.stored import StoredRecipe

# The pantry fit row is "scaled so the top recipe is about +3" (spec §6.2): the offered set's strongest
# pantry match is worth +3, and every other candidate scales below it.
PANTRY_FIT_TOP = 3.0
# How many weeks the model is offered to choose between. Two is the V6 starting point (spec §6.2).
CANDIDATE_WEEKS = 2


class RecipeFacts(BaseModel):
    """One offered recipe as the scorer reads it, in JSON so a checkpoint can carry it.

    A JSON mirror of `tools.CandidateRecipe` rather than that dataclass itself: the prepared plan is
    checkpointed, and everything in it has to survive a round trip. `attributes` are V5's G1 names, each a
    value or `unsure`; `pantry_fit` is already scaled (see `facts_from`), not the raw urgency sum.
    """

    recipe_id: str
    attributes: dict[str, str] = Field(default_factory=dict)
    calories_per_serving: float | None = Field(
        default=None, description="Stated per-serving calories; null when the recipe page states none."
    )
    pantry_fit: float = 0.0
    days_since_cooked: float | None = None
    rating: Rating | None = None
    offered_after_floor_relaxed: bool = False

    def scorer_input(self) -> CandidateRecipe:
        """The plain dataclass `score_meal_plan` takes, with the attributes typed and `unsure` where empty."""
        return CandidateRecipe(
            recipe_id=self.recipe_id,
            attributes=RecipeAttributes.from_mapping(self.attributes),
            calories_per_serving=self.calories_per_serving,
            pantry_fit=self.pantry_fit,
            days_since_cooked=self.days_since_cooked,
            rating=self.rating,
            offered_after_floor_relaxed=self.offered_after_floor_relaxed,
        )


class WeekPenalty(BaseModel):
    """One plan penalty as the model and the logs see it: which term, how much, and what it was about."""

    term: str
    points: float
    detail: str = ""


class CandidateWeek(BaseModel):
    """One scored week: the meals in order, the score, and the rows that made it up.

    `terms` carries a total per term that scored, so the model can see what the week is being credited and
    charged for rather than just a number. `penalties` names the repeats, the calories term and any missed
    protein target in words.
    """

    recipe_ids: list[str] = Field(description="The week's recipe ids, in the order the scorer filled the slots.")
    total: float = Field(description="The week's score: each recipe's fit minus the plan's penalties (spec 6.2).")
    terms: dict[str, float] = Field(
        default_factory=dict, description="What each scorer term gave the week in total; zero terms are left out."
    )
    penalties: list[WeekPenalty] = Field(default_factory=list)

    @classmethod
    def from_score(cls, score: PlanScore) -> CandidateWeek:
        """The week as data, from the breakdown `score_meal_plan` wrote."""
        return cls(
            recipe_ids=list(score.recipe_ids),
            total=score.total,
            terms={term.value: points for term in Term if (points := score.points(term))},
            penalties=[
                WeekPenalty(term=penalty.term.value, points=penalty.points, detail=penalty.detail)
                for penalty in score.penalties
            ],
        )


def stated_calories(recipe: StoredRecipe | None) -> float | None:
    """The per-serving calories the recipe's own page stated, or None when it stated none.

    Most of the corpus has no nutrition at all, and a nutrition block with no calorie figure states nothing
    rather than stating zero: zero would read as the lightest possible dinner. Labelled estimates are not
    used here — only what the page said (spec §6.1's "where nutrition exists").
    """
    nutrition = None if recipe is None else recipe.nutrition
    if nutrition is None or nutrition.calories <= 0:
        return None
    return nutrition.calories


def facts_from(
    offered: Sequence[OfferedRecipe],
    *,
    attributes: Mapping[str, RecipeAttributes],
    calories: Mapping[str, float | None],
    history: RecipeHistory,
) -> list[RecipeFacts]:
    """One `RecipeFacts` per offered recipe: the scorer's whole view of what the household may be offered.

    `offered` carries the urgency-weighted pantry fit and, for a recipe the six-week floor relaxed back in,
    how long ago it was cooked. `history` supplies every candidate's cook age and latest thumb, so the
    recency and rating rows can be scored for the fresh candidates too.
    """
    top = max((candidate.pantry_fit for candidate in offered), default=0.0)
    scale = PANTRY_FIT_TOP / top if top > 0 else 0.0
    return [
        RecipeFacts(
            recipe_id=recipe.external_id,
            attributes=attributes.get(recipe.external_id, RecipeAttributes()).as_mapping(),
            calories_per_serving=calories.get(recipe.external_id),
            pantry_fit=recipe.pantry_fit * scale,
            days_since_cooked=history.days_since_cooked.get(recipe.external_id),
            rating=_rating(history.latest_rating.get(recipe.external_id)),
            offered_after_floor_relaxed=recipe.cooked_days_ago is not None,
        )
        for recipe in offered
    ]


def scoring_context(facts: Sequence[RecipeFacts]) -> ScoringContext:
    """The context the scorer reads. Profile and chips inputs stay empty until V13 and V9 send them."""
    return ScoringContext(recipes={entry.recipe_id: entry.scorer_input() for entry in facts})


def scored_weeks(
    context: ScoringContext,
    recipe_ids: Sequence[str],
    slots: int,
    *,
    seed: int,
    weights: ScorerWeights | None = None,
) -> tuple[CandidateWeek, ...]:
    """Up to `CANDIDATE_WEEKS` distinct weeks of `slots` recipes, best first, each with its breakdown.

    This is `create_candidate_meal_plans` as `prepare` runs it, with the breakdown kept because the model is
    shown what the week is credited for and the logs record how far the model's pick fell short of the best.
    """
    plans = create_candidate_meal_plans(recipe_ids, slots, context, weights, k=CANDIDATE_WEEKS, seed=seed)
    return tuple(CandidateWeek.from_score(plan) for plan in plans)


def swap_targets(weeks: Sequence[CandidateWeek], chosen_ids: Sequence[str]) -> dict[int, str]:
    """For each slot of `chosen_ids`, the other candidate week's meal, so a card's Swap is the scorer's own.

    The other week is a whole week the scorer judged near-best, so the meal in the same slot is the swap most
    likely to keep the week balanced -- which a spare candidate taken from the end of the offer is not. Empty
    for a slot the other week has no meal for, or where its meal is already chosen.
    """
    chosen = set(chosen_ids)
    targets: dict[int, str] = {}
    for position in range(len(chosen_ids)):
        for week in weeks:
            if position >= len(week.recipe_ids):
                continue
            candidate = week.recipe_ids[position]
            if candidate not in chosen:
                targets[position] = candidate
                break
    return targets


def drift(chosen_ids: Sequence[str], best_ids: Sequence[str], context: ScoringContext) -> PlanGap:
    """How far a chosen week fell short of the scorer's best, for the line `finalise` logs (spec §6.6).

    A repeated pick is scored once: `finalise` keeps the model's list as it wrote it, and the gap is about how
    good the week is, not about the caller's list hygiene.
    """
    chosen = tuple(dict.fromkeys(chosen_ids))
    return chosen_vs_best_gap(score_meal_plan(chosen, context), score_meal_plan(best_ids, context))


def _rating(value: str | None) -> Rating | None:
    """The history's thumb as the scorer's `Rating`, or None when the cook carried none."""
    return None if value is None else Rating(value)
