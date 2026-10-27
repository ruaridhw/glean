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
    PANTRY_FIT_TOP,
    CandidateRecipe,
    PlanGap,
    PlanScore,
    ProteinTarget,
    Rating,
    ScorerWeights,
    ScoringContext,
    Term,
    chosen_vs_best_gap,
    create_candidate_meal_plans,
    score_meal_plan,
)
from glean.recipes.attributes import Cuisine, MainProtein, RecipeAttributes

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Mapping, Sequence

    from glean.meal_plan.candidates import OfferedRecipe
    from glean.meal_plan.eligibility import RecipeHistory
    from glean.recipes.stored import StoredRecipe

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
    urgent_items: tuple[str, ...] = Field(
        default=(),
        description=(
            "The urgent pantry items this recipe uses, by name (V4's three-day rule). The pool's urgent items are "
            "the ones a week could use, and the ones it leaves out are penalised (spec 6.2, #122)."
        ),
    )
    cooked_last_week: bool = Field(
        default=False, description="Cooked in the last seven days, and back only because of 'same as last week'."
    )
    favourite: bool = Field(default=False, description="One of the profile's favourite meals (V13b).")
    loved_ingredients: tuple[str, ...] = Field(
        default=(), description="The profile's loved ingredients this recipe uses, as whole words (V13b)."
    )

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
            loved_ingredients=self.loved_ingredients,
            cooked_last_week=self.cooked_last_week,
        )


class ProfileTarget(BaseModel):
    """One of the profile's protein targets as the scorer reads it: V5's protein, and a floor, a ceiling or both."""

    protein: MainProtein
    min_per_week: int | None = None
    max_per_week: int | None = None


class ProfileScoring(BaseModel):
    """The household profile as the scorer and `pipeline.widen` read it, in JSON so a checkpoint can carry it.

    `liked_cuisines`, `avoided_cuisines` and `protein_targets` are the plan-wide inputs. `favourites` (text and
    matched recipe id) and `loved_ingredients` are kept so a recipe the agent finds later is matched the same way a
    candidate was (`meal_plan.household`). Empty without a profile, and on a checkpoint written before V13b.
    """

    liked_cuisines: list[Cuisine] = Field(default_factory=list)
    avoided_cuisines: list[Cuisine] = Field(default_factory=list)
    protein_targets: list[ProfileTarget] = Field(default_factory=list)
    favourites: list[tuple[str, str | None]] = Field(default_factory=list)
    loved_ingredients: list[str] = Field(default_factory=list)


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
    urgent_items: Mapping[str, Sequence[str]] | None = None,
    last_week: Collection[str] = frozenset(),
    favourites: Collection[str] = frozenset(),
    loved: Mapping[str, tuple[str, ...]] | None = None,
) -> list[RecipeFacts]:
    """One `RecipeFacts` per offered recipe: the scorer's whole view of what the household may be offered.

    `offered` carries the urgency-weighted pantry fit and, for a recipe the six-week floor relaxed back in,
    how long ago it was cooked. `history` supplies every candidate's cook age and latest thumb, so the
    recency and rating rows can be scored for the fresh candidates too. `urgent_items` is V4's name per recipe
    of the pantry items going off within three days it uses, which is what the week either uses or is charged
    for leaving (spec 6.2, #122). `last_week` are the recipes the "same as last week" chip lifted the floor for.
    `favourites` and `loved` are the profile's matches (`meal_plan.household`): the favourite recipe ids, and per
    recipe the loved ingredients it uses.
    """
    scale = pantry_fit_scale(candidate.pantry_fit for candidate in offered)
    return [
        RecipeFacts(
            recipe_id=recipe.external_id,
            attributes=attributes.get(recipe.external_id, RecipeAttributes()).as_mapping(),
            calories_per_serving=calories.get(recipe.external_id),
            pantry_fit=recipe.pantry_fit * scale,
            days_since_cooked=history.days_since_cooked.get(recipe.external_id),
            rating=_rating(history.latest_rating.get(recipe.external_id)),
            offered_after_floor_relaxed=recipe.cooked_days_ago is not None,
            urgent_items=tuple((urgent_items or {}).get(recipe.external_id, ())),
            cooked_last_week=recipe.external_id in last_week,
            favourite=recipe.external_id in favourites,
            loved_ingredients=(loved or {}).get(recipe.external_id, ()),
        )
        for recipe in offered
    ]


def pantry_fit_scale(raw_fits: Iterable[float]) -> float:
    """What one raw urgency-weighted pantry fit is multiplied by, so the strongest of `raw_fits` scores +3.

    Kept on the prepared plan, so a recipe the agent finds later (V7) is scaled by the same factor as the
    candidates it is compared with, rather than being made the top of a pool of its own.
    """
    top = max(raw_fits, default=0.0)
    return PANTRY_FIT_TOP / top if top > 0 else 0.0


def scoring_context(
    facts: Sequence[RecipeFacts],
    *,
    chips: Collection[str] = frozenset(),
    urgent_items_already_used: Sequence[str] = (),
    profile: ProfileScoring | None = None,
) -> ScoringContext:
    """The context the scorer reads: the facts, the week's chips, what is already being used up, and the profile.

    `urgent_items_already_used` are the urgent items a meal already in the week uses: the week is not charged for
    leaving those out, because it is not leaving them out. `profile` adds the cuisines and protein targets; the
    favourite and loved-ingredient matches are already on the facts.
    """
    profile = profile or ProfileScoring()
    return ScoringContext(
        recipes={entry.recipe_id: entry.scorer_input() for entry in facts},
        favourite_recipe_ids=frozenset(entry.recipe_id for entry in facts if entry.favourite),
        liked_cuisines=frozenset(profile.liked_cuisines),
        avoided_cuisines=frozenset(profile.avoided_cuisines),
        protein_targets=tuple(
            ProteinTarget(target.protein, min_per_week=target.min_per_week, max_per_week=target.max_per_week)
            for target in profile.protein_targets
        ),
        chips=frozenset(chips),
        urgent_item_uses={entry.recipe_id: entry.urgent_items for entry in facts if entry.urgent_items},
        urgent_items_already_used=tuple(urgent_items_already_used),
    )


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


def swap_targets(
    weeks: Sequence[CandidateWeek], chosen_ids: Sequence[str], *, swappable: Collection[str] | None = None
) -> dict[int, str]:
    """For each slot of `chosen_ids`, the other candidate week's meal, so a card's Swap is the scorer's own.

    The other week is a whole week the scorer judged near-best, so the meal in the same slot is the swap most
    likely to keep the week balanced -- which a spare candidate taken from the end of the offer is not.
    `swappable` narrows what may be offered: a recipe the six-week floor relaxed back in is a fallback for the
    week itself, not a swap worth handing the household (V2's floor). Empty for a slot the other week has no
    usable meal for, or where its meal is already chosen.
    """
    chosen = set(chosen_ids)
    targets: dict[int, str] = {}
    for position in range(len(chosen_ids)):
        for week in weeks:
            if position >= len(week.recipe_ids):
                continue
            candidate = week.recipe_ids[position]
            if candidate not in chosen and (swappable is None or candidate in swappable):
                targets[position] = candidate
                break
    return targets


def unused_urgent_items(week: CandidateWeek) -> tuple[str, ...]:
    """The urgent items the week leaves unused, in name order: the rows its `unused_urgent_item` penalty names."""
    return tuple(penalty.detail for penalty in week.penalties if penalty.term == Term.UNUSED_URGENT_ITEM.value)


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
