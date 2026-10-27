"""The planner's tools: find the eligible recipes, read them, score a week, and offer k balanced weeks.

Framework-free and pure (spec 6.2, "Tools"): plain typed functions over plain data, with no graph, store or
network import, so the agent graph, the evals (6.6) and the MCP server all call the same code through thin
adapters. Feasibility is decided upstream — dietary decisions, the time cap, meals already planned and the
six-week floor all happen in `get_eligible_recipes` — so everything after it is a score, never a filter.

`get_eligible_recipes` and `get_recipes` (V7) read an `EligibilityContext`: the corpus as plain rows, plus the
session's hard constraints. The caller builds it from whatever store holds the corpus (`pipeline.tool_context`),
so the tools never read one, and a synthetic corpus is enough to test them.

A plan's score is each recipe's fit minus the plan's penalties, one weight per row of the scorer table
(spec 6.2, "Scorer weights"). Every one of those numbers is a starting guess, so they live in `ScorerWeights`
and no term hard-codes its own. A recipe whose attributes are `unsure` earns no variety credit and no penalty,
and every row of the table is scored: the table has no heartiness term, because G1 dropped richness.
"""

from __future__ import annotations

import random
import re
from collections import Counter, deque
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal

from glean.meal_plan.candidates import GUARANTEE_MAX, PantryItem, mentions_item, near_duplicate_ingredients
from glean.meal_plan.eligibility import apply_recency_floor
from glean.meal_plan.eligibility import recency_penalty as _recency_penalty
from glean.meal_plan.household import disliked_recipe_ids
from glean.recipes.attributes import (
    UNSURE,
    ActiveTimeBucket,
    Cuisine,
    DishType,
    MainCarb,
    MainProtein,
    RecipeAttributes,
    WholeFood,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Mapping, Sequence
    from datetime import datetime

    from glean.meal_plan.eligibility import CookedMeal

__all__ = [
    "CHIP_PREDICATES",
    "HEALTHIER_CHIP",
    "LIGHTER_CHIP",
    "MAX_FILTER_LIMIT",
    "NARROWING_CHIPS",
    "CandidateRecipe",
    "CorpusRecipe",
    "DuplicateRecipeIds",
    "EligibilityContext",
    "EligibleRecipe",
    "EligibleRecipes",
    "FeedbackChip",
    "FilterRejected",
    "PlanGap",
    "PlanPenalty",
    "PlanScore",
    "Predicate",
    "PredicateField",
    "PredicateOp",
    "ProteinTarget",
    "Rating",
    "RecipeCard",
    "RecipeDetails",
    "RecipeFilter",
    "RecipeScore",
    "ScorerWeights",
    "ScoringContext",
    "Term",
    "TermScore",
    "UnknownRecipeIds",
    "chip_narrows",
    "chosen_vs_best_gap",
    "chosen_vs_best_ratio",
    "create_candidate_meal_plans",
    "distinct_main_carbs",
    "distinct_main_proteins",
    "get_eligible_recipes",
    "get_recipes",
    "score_meal_plan",
]


class FeedbackChip(StrEnum):
    """The week's chips (spec 6.5, "Human feedback"), as the app sends them.

    What each one does to the week is decided in this module and nowhere else. A chip either pays the "Human
    feedback match" +2 through its predicate (`CHIP_PREDICATES`) or through a fact about the recipe's history,
    or it changes one row of the table:

    - `quick_weeknights`: narrows the offer to V5's time-cap rule at 30 minutes (`chip_narrows`), else +2 for 30
      minutes hands-on or less (`QUICK_WEEKNIGHT_MINS`).
    - `use_up_the_fridge`: pantry fit, urgency-weighted already, is doubled (`use_up_the_fridge_multiplier`).
    - `something_new`: +2 for a recipe the household's history never mentions.
    - `healthier`: doubles whole food (`healthier_multiplier`), with no predicate, so it never pays twice.
    - `comfort_food`: narrows the offer to the warming dish types (`COMFORT_DISH_TYPES`), else +2 for one.
    - `lighter`: turns on the calories row against the fixed reference, with no predicate either.
    - `guests`: narrows the offer to dishes that serve a table (`GUEST_DISH_TYPES`), else +2 for one. It does not
      change servings: the app sets those when the week is added, and the request carries none.

    A narrowing chip (`NARROWING_CHIPS`) narrows only while at least three fresh recipes per slot pass it; when
    fewer would, the offer stays whole and the chip pays its +2 here instead (owner decision 2026-10-25). The
    sampler (`candidates.sample_corpus_candidates`) applies it and logs which happened.
    - `same_as_last_week`: +2 for a recipe cooked in the last seven days. The six-week floor would leave those
      out, so this chip lifts it for them alone (`pipeline`), and never for a thumbs-down recipe.
    """

    QUICK_WEEKNIGHTS = "quick_weeknights"
    USE_UP_THE_FRIDGE = "use_up_the_fridge"
    SOMETHING_NEW = "something_new"
    HEALTHIER = "healthier"
    COMFORT_FOOD = "comfort_food"
    LIGHTER = "lighter"
    GUESTS = "guests"
    SAME_AS_LAST_WEEK = "same_as_last_week"


# The two chips the scorer reads by name in rows of their own.
HEALTHIER_CHIP = FeedbackChip.HEALTHIER.value
LIGHTER_CHIP = FeedbackChip.LIGHTER.value

# Six, nine and twelve weeks, in days: the recency bands' boundaries.
SIX_WEEKS_DAYS = 42
NINE_WEEKS_DAYS = 63
TWELVE_WEEKS_DAYS = 84

# The filter's `limit` (spec 6.2): one call returns at most this many recipes, and asking for more is refused.
MAX_FILTER_LIMIT = 120
# A summary card's key ingredients: as many as the model's candidate list shows (`pipeline`).
_KEY_INGREDIENTS = 12
_WORD_RE = re.compile(r"\w+")

# Two floats closer than this are the same score, so a "swap" between them is not an improvement.
_SCORE_EPSILON = 1e-9
# The local search stops after this many improving passes, and after this many plan evaluations, which is what
# bounds the tool's time: a 120-recipe pool's neighbourhood is far more than one plan needs to settle.
_MAX_LOCAL_SEARCH_PASSES = 8
_MAX_SWAP_EVALUATIONS = 2000
# Attempts per plan offered: each one blocks a recipe of the plan before it, so the plans differ by construction.
_PLANS_ATTEMPTS_PER_PLAN = 4

# Values that earn nothing when they repeat, one set per entry of `_REPEAT_TERMS`. An unknown attribute is not
# evidence of sameness, so `unsure` is exempt everywhere. The catch-all values are exempt too: a dish built around
# no protein cannot repeat one (`none`), `mixed` says it is not built around any one protein, and two different
# dishes both typed `other` are not the same dish. A dish built around no carb is still a repeated carb choice,
# and the spec's carb row carries no exemption, so only the protein row exempts `none` (owner decision
# 2026-10-25, from the V6 eval's carb-gate misses).
_REPEAT_EXEMPT: tuple[frozenset[str], ...] = (
    frozenset({UNSURE, "none", "mixed"}),
    frozenset({UNSURE}),
    frozenset({UNSURE, "other"}),
    frozenset({UNSURE}),
)


class Term(StrEnum):
    """One row of the scorer table. A breakdown names these, so the evals and logs can read a term by name."""

    PANTRY_FIT = "pantry_fit"
    FAVOURITE = "favourite"
    LIKED_CUISINE = "liked_cuisine"
    LOVED_INGREDIENT = "loved_ingredient"
    AVOIDED_CUISINE = "avoided_cuisine"
    FEEDBACK_CHIP = "feedback_chip"
    RECENCY = "recency"
    RATING = "rating"
    WHOLE_FOOD = "whole_food"
    REPEAT_MAIN_PROTEIN = "repeat_main_protein"
    REPEAT_MAIN_CARB = "repeat_main_carb"
    REPEAT_DISH_TYPE = "repeat_dish_type"
    REPEAT_CUISINE = "repeat_cuisine"
    LIGHTER = "lighter"
    PROTEIN_TARGET = "protein_target"
    UNUSED_URGENT_ITEM = "unused_urgent_item"


# The active-time buckets as the minutes they span, so a predicate can compare the end that can promise it.
# The buckets themselves belong to the recipe attribute contract (`recipes/attributes.py`); this is the
# predicate's own view of them, and it goes when that module grows a lower bound to match its upper one.
_ACTIVE_TIME_RANGE: dict[str, tuple[int | None, int | None]] = {
    ActiveTimeBucket.UP_TO_15.value: (0, 15),
    ActiveTimeBucket.FROM_15_TO_30.value: (15, 30),
    ActiveTimeBucket.FROM_30_TO_45.value: (30, 45),
    ActiveTimeBucket.FROM_45_TO_60.value: (45, 60),
    ActiveTimeBucket.OVER_60.value: (60, None),
}

# "Quick weeknights": hands-on time at most this many minutes, the bucket boundary G1 drew at half an hour.
QUICK_WEEKNIGHT_MINS = 30
# "Comfort food": the warming, filling dish shapes. Roasts and traybakes are left to guests, and a stir fry, a
# salad or a handheld is a weeknight dish, not a comfort one.
COMFORT_DISH_TYPES = (DishType.PIE_OR_BAKE, DishType.SOUP_OR_STEW, DishType.CURRY, DishType.PASTA_DISH)
# "Guests": dishes that are made whole and served at the table: a roast or traybake, a pie, a curry, a paella.
GUEST_DISH_TYPES = (DishType.ROAST_OR_TRAYBAKE, DishType.PIE_OR_BAKE, DishType.CURRY, DishType.RICE_DISH)
# The chips that narrow the offer when the pool can afford it (owner decision 2026-10-25): the ones with a clear rule.
NARROWING_CHIPS = (FeedbackChip.QUICK_WEEKNIGHTS, FeedbackChip.COMFORT_FOOD, FeedbackChip.GUESTS)
# "Same as last week": a cook this recent counts as last week's.
LAST_WEEK_DAYS = 7

# The repeat terms, in the order `_Scorer.repeat_values` gives their attribute values.
_REPEAT_TERMS = (Term.REPEAT_MAIN_PROTEIN, Term.REPEAT_MAIN_CARB, Term.REPEAT_DISH_TYPE, Term.REPEAT_CUISINE)


class Rating(StrEnum):
    """A thumb on a cooked meal (spec 6.5). Only cooked meals are rated, so a rating always has an age."""

    UP = "up"
    DOWN = "down"


@dataclass(frozen=True, slots=True)
class ScorerWeights:
    """Every weight in one place, each comment naming the row of the scorer table it comes from.

    The table's own words: these numbers are guesses. They shape every plan more than anything else in the
    system, so a change to one is reported before and after on the eval dataset.
    """

    # "Pantry fit": the caller sends the urgency-weighted sum, already scaled so the top recipe is about +3.
    pantry_fit: float = 1.0
    # "Profile affinity": +2 favourite match.
    favourite: float = 2.0
    # "Profile affinity": +1 liked cuisine.
    liked_cuisine: float = 1.0
    # "Profile affinity": +1 for a loved ingredient match, however many of them one recipe matched.
    loved_ingredient: float = 1.0
    # "Profile affinity": -2 avoided cuisine. Disliked ingredients are a hard exclusion upstream, not a weight.
    avoided_cuisine: float = -2.0
    # "Human feedback match": +2 per chip the recipe satisfies.
    feedback_chip: float = 2.0
    # "Recency": -8 if cooked in the last 6 weeks, and only when the six-week floor had to relax.
    recency_relaxed: float = -8.0
    # "Recency": -3 in weeks 7-9.
    recency_weeks_7_to_9: float = -3.0
    # "Recency": -1 in weeks 10-12.
    recency_weeks_10_to_12: float = -1.0
    # "Ratings": thumbs down, -8 whatever its age.
    rating_down: float = -8.0
    # "Ratings": thumbs up, +1 once past six weeks.
    rating_up_after_six_weeks: float = 1.0
    # "Same main_protein twice": the table's first guess was -3 per extra occurrence. The owner set -5 on
    # 2026-10-25 after the V6 eval's weight sweep: -5 passes every pool-passable protein gate (16/16, against
    # 15/16 at -3). On its own it costs one carb gate, which the whole-food change below recovers.
    repeat_main_protein: float = -5.0
    # "Same main_carb twice": -2 per extra.
    repeat_main_carb: float = -2.0
    # "Same dish_type twice": -2 per extra.
    repeat_dish_type: float = -2.0
    # "Same cuisine twice": -1 per extra.
    repeat_cuisine: float = -1.0
    # "Whole food": the table's first guess was +1 for `whole`, 0 for `mixed` and 0 for `processed`. The owner
    # set +0.5 on 2026-10-25 because +1 outvoted variety: at -5 protein, +1 holds 19/22 carb gates where +0.5
    # holds 20/22, and the protein gates stay 16/16 either way.
    whole_food: float = 0.5
    # "Whole food": the "healthier" chip multiplies it. The chip doubled whole food (x2: +1 per whole recipe, the
    # chip's own share +0.5); the owner doubled the chip's own weight on 2026-10-25, so its share is +1 and a whole
    # recipe earns 0.5 x 3 = +1.5 under the chip. It has no predicate in `CHIP_PREDICATES`, so it pays once.
    healthier_multiplier: float = 3.0
    # "Pantry fit": the "use up the fridge" chip doubles it, so a recipe using the week's urgent items outbids the
    # +2 of any one other chip. A guess like the rest of the table.
    use_up_the_fridge_multiplier: float = 2.0
    # "'Lighter' chip": the table's -1 per recipe above `lighter_reference_kcal`, doubled to -2 by the owner on
    # 2026-10-25 after the V9 eval showed -1 barely moved a week. Only while the chip is on.
    lighter: float = -2.0
    # That reference: the corpus median of STATED per-serving calories, 672 kcal. Derived from the 2026-10-24 prod
    # corpus export, where 362 of its 632 recipes state nutrition on their own page (the labeller's estimates for
    # the other 270 are excluded); their median is 672.5, rounded down to 672. Owner decision 2026-10-25: a fixed
    # reference, not the week's own median, so a plan can no longer make itself look light by choosing light
    # recipes, which the V6 eval saw it do.
    lighter_reference_kcal: int = 672
    # "Protein targets from the profile": -4 per miss, such as fish at least once.
    protein_target_miss: float = -4.0
    # A plan-level row of the owner's adding (decision 2026-10-25), in the shape of the protein-target one: -4
    # per urgent pantry item (expiring within V4's three days) that a candidate recipe uses and the week does
    # not. The V6 eval found the need: once attributes exist, pantry fit -- worth at most +3 and spread across
    # the staples every recipe uses -- cannot beat a repeat penalty, so urgent coverage fell from 10/10 to 8/10
    # and the h08 salmon recipe lost at +2.45 fit against a -5 second-fish penalty. This row targets #122's
    # criterion directly, without inflating pantry fit against variety.
    unused_urgent_item: float = -4.0


@dataclass(frozen=True, slots=True)
class CandidateRecipe:
    """One candidate recipe exactly as the scorer needs it: all plain data, no lookup of its own.

    `pantry_fit` is the caller's already urgency-weighted, already scaled figure; `days_since_cooked` is None for
    a recipe the household has never cooked; `offered_after_floor_relaxed` says the six-week floor was lowered to
    offer it, which is the only case the recency row's -8 applies; `loved_ingredients` are the profile's loved
    ingredients this recipe was matched to upstream. `cooked_last_week` is set only when the "same as last week"
    chip lifted the floor for this recipe, whose recent cook then no longer counts in `days_since_cooked`.
    """

    recipe_id: str
    attributes: RecipeAttributes = field(default_factory=RecipeAttributes)
    calories_per_serving: float | None = None
    pantry_fit: float = 0.0
    days_since_cooked: float | None = None
    rating: Rating | None = None
    offered_after_floor_relaxed: bool = False
    loved_ingredients: tuple[str, ...] = ()
    cooked_last_week: bool = False


@dataclass(frozen=True, slots=True)
class ProteinTarget:
    """One line of the profile's `protein_targets` (spec 6.4): a protein, and a floor, a ceiling, or both."""

    protein: MainProtein
    min_per_week: int | None = None
    max_per_week: int | None = None


class PredicateField(StrEnum):
    """The attribute a predicate reads. The filter's allowlist, and the scorer's, is these six."""

    MAIN_PROTEIN = "main_protein"
    MAIN_CARB = "main_carb"
    DISH_TYPE = "dish_type"
    CUISINE = "cuisine"
    WHOLE_FOOD = "whole_food"
    ACTIVE_TIME = "active_time"


class PredicateOp(StrEnum):
    """The operators a filter may use.

    `lte`/`gte` compare minutes, so they are active_time's alone, and they compare the right end of the bucket:
    `lte N` against its upper bound, `gte N` against its lower bound.
    """

    IN = "in"
    NOT_IN = "not_in"
    LTE = "lte"
    GTE = "gte"


@dataclass(frozen=True, slots=True)
class Predicate:
    """The spec's filter predicate, as the scorer evaluates it against one recipe's attributes.

    A chip maps to a predicate (V9); the scorer asks it whether the recipe satisfies the chip. The filter's own
    Predicate has the same field/op/values shape, so the filter can adopt this type rather than duplicate it.
    """

    field: PredicateField
    op: PredicateOp
    values: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.op in (PredicateOp.LTE, PredicateOp.GTE):
            if self.field is not PredicateField.ACTIVE_TIME:
                raise ValueError(f"{self.op.value} compares minutes, so it only applies to active_time")
            if len(self.values) != 1 or _minutes(self.values[0]) is None:
                raise ValueError(f"{self.op.value} takes exactly one number of minutes, not {self.values!r}")

    def matches(self, attributes: RecipeAttributes) -> bool:
        """Whether these attributes satisfy the predicate.

        An attribute that isn't known satisfies nothing, `not_in` included: an unknown value is not evidence of
        anything, so it must not earn a chip. Every chip pays +2 for a match, and most of the corpus is not
        enriched yet, so a `not_in` predicate read the other way would pay every un-enriched recipe.
        """
        if self.op in (PredicateOp.LTE, PredicateOp.GTE):
            limit = _minutes(self.values[0])
            lower, upper = _ACTIVE_TIME_RANGE.get(attributes.active_time.value, (None, None))
            if limit is None or lower is None:
                return False
            if self.op is PredicateOp.GTE:
                return lower >= limit
            # A bucket with no upper bound, like "60+", cannot be certified as coming under any limit.
            return upper is not None and upper <= limit
        value = attributes.as_mapping()[self.field.value]
        if value == UNSURE:
            return False
        values = {candidate.casefold() for candidate in self.values}
        return value in values if self.op is PredicateOp.IN else value not in values


@dataclass(frozen=True, slots=True)
class ScoringContext:
    """Everything the scorer reads, built by the caller from the session: no store, no profile read, no model.

    `recipes` holds one `CandidateRecipe` per candidate id. `urgent_item_uses` is V4's per-recipe urgent items:
    the items in the offered pool that go off within three days, so "the pool can use this item" is what makes
    leaving it unused a penalty. `urgent_items_already_used` are the ones a meal already in the week uses, which
    cannot be left unused and so are never charged. The rest are the optional profile inputs (spec 6.4) and the
    week's feedback chips (`FeedbackChip` values). `chip_predicates` defaults to `CHIP_PREDICATES`; a chip the
    scorer does not know earns nothing.
    """

    recipes: Mapping[str, CandidateRecipe] = field(default_factory=dict)
    favourite_recipe_ids: frozenset[str] = frozenset()
    liked_cuisines: frozenset[Cuisine] = frozenset()
    avoided_cuisines: frozenset[Cuisine] = frozenset()
    protein_targets: tuple[ProteinTarget, ...] = ()
    chips: frozenset[str] = frozenset()
    chip_predicates: Mapping[str, Predicate] = field(default_factory=lambda: CHIP_PREDICATES)
    urgent_item_uses: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    urgent_items_already_used: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TermScore:
    """What one term gave one recipe, positive or negative."""

    term: Term
    points: float


@dataclass(frozen=True, slots=True)
class RecipeScore:
    """One recipe's contribution: its terms, and their sum."""

    recipe_id: str
    terms: tuple[TermScore, ...]

    @property
    def total(self) -> float:
        return sum(term_score.points for term_score in self.terms)


@dataclass(frozen=True, slots=True)
class PlanPenalty:
    """What one term took off the plan, and which recipes (or which target) it took it from."""

    term: Term
    points: float
    recipe_ids: tuple[str, ...] = ()
    detail: str = ""


@dataclass(frozen=True, slots=True)
class PlanScore:
    """A whole week: every recipe's terms, and the penalties the week as a whole earned."""

    recipes: tuple[RecipeScore, ...]
    penalties: tuple[PlanPenalty, ...] = ()

    @property
    def total(self) -> float:
        """The plan's score: each recipe's fit, minus the plan's penalties."""
        return sum(recipe.total for recipe in self.recipes) + sum(penalty.points for penalty in self.penalties)

    @property
    def recipe_ids(self) -> tuple[str, ...]:
        return tuple(recipe.recipe_id for recipe in self.recipes)

    def points(self, term: Term) -> float:
        """Everything this one term gave or took, across the week."""
        from_recipes = sum(
            term_score.points for recipe in self.recipes for term_score in recipe.terms if term_score.term is term
        )
        return from_recipes + sum(penalty.points for penalty in self.penalties if penalty.term is term)

    @property
    def absolute_points(self) -> float:
        """How much scoring is at stake here: every term's magnitude, the penalties included.

        A plan's total is a signed sum, and it crosses zero when penalties cancel the fits, so this is the stable
        measure of how much was scored: what the eval's "within 15%" gate is read against (`PlanGap`).
        """
        points = [term_score.points for recipe in self.recipes for term_score in recipe.terms]
        points.extend(penalty.points for penalty in self.penalties)
        return sum(abs(point) for point in points)


@dataclass(frozen=True, slots=True)
class PlanGap:
    """How far a plan fell short of the best one, on the scale the eval's "within 15%" gate reads (spec 6.6).

    `gap` is the points between them and `scale` is what was at stake in the best plan: the sum of its terms'
    magnitudes, penalties included, floored at one. §6.6 asks for "within 15%" without naming a base, and dividing
    by a plan's total cannot be it: totals cross zero, so a one-point gap against a near-zero best would read as a
    total miss, and the generator's own alternative would fail the gate on the scorer's output rather than on
    agent drift (owner decision 2026-10-25).
    """

    gap: float
    scale: float

    @property
    def fraction(self) -> float:
        """The shortfall as a fraction of what was at stake: 0.15 or less is the eval's "within 15%"."""
        return self.gap / self.scale

    @property
    def within_15_percent(self) -> bool:
        """§6.6's soft gate: the chosen plan is within 15% of the scorer's best."""
        return self.fraction <= 0.15

    @property
    def ratio(self) -> float:
        """`1 - fraction`, floored at 0: 1.0 is as good as the best, 0.85 is the gate."""
        return max(1.0 - self.fraction, 0.0)


class UnknownRecipeIds(KeyError):
    """A plan named a recipe the caller's context does not describe: the ids and the facts disagree."""


class DuplicateRecipeIds(ValueError):
    """A plan named the same recipe twice: one week cannot cook it in two slots, and its terms would double."""


def score_meal_plan(
    recipe_ids: Sequence[str],
    ctx: ScoringContext,
    weights: ScorerWeights | None = None,
) -> PlanScore:
    """Score any set of recipes, with the breakdown, so the agent can test its own substitutions.

    Unknown ids raise rather than score as zero: a plan naming a recipe the caller did not describe is a bug in
    the caller, not a weak plan.
    """
    ids = tuple(recipe_ids)
    scorer = _Scorer(ctx, weights or ScorerWeights())
    scorer.require(ids)
    return scorer.score(ids)


def distinct_main_proteins(recipe_ids: Sequence[str], ctx: ScoringContext) -> int:
    """How many different proteins the week is built around, with `none` and `unsure` left out.

    Spec 6.6's soft gate wants at least N - 1 of these for a week of N: a week is balanced by what it varies,
    and a dish with no protein or an unknown one cannot be counted as either variety or sameness.
    """
    _require_known(recipe_ids, ctx)
    proteins = {ctx.recipes[recipe_id].attributes.main_protein for recipe_id in recipe_ids}
    return len(proteins - {MainProtein.NONE, MainProtein.UNSURE})


def distinct_main_carbs(recipe_ids: Sequence[str], ctx: ScoringContext) -> int:
    """How many different carbs the week is built around, `none` and `unsure` left out (spec 6.6)."""
    _require_known(recipe_ids, ctx)
    carbs = {ctx.recipes[recipe_id].attributes.main_carb for recipe_id in recipe_ids}
    return len(carbs - {MainCarb.NONE, MainCarb.UNSURE})


def chosen_vs_best_gap(chosen: PlanScore, best: PlanScore) -> PlanGap:
    """The points between a chosen plan and the scorer's best, and the scale §6.6's "within 15%" is read on.

    "Within 15%" means `gap <= 0.15 * scale`, which is `PlanGap.within_15_percent`. Nothing is owed when the
    chosen plan scores as well as the best, so the gap floors at zero.
    """
    return PlanGap(gap=max(best.total - chosen.total, 0.0), scale=max(1.0, best.absolute_points))


def chosen_vs_best_ratio(chosen: PlanScore, best: PlanScore) -> float:
    """The same gap as a ratio, `1 - gap/scale`, floored at 0: the float the evals and the graph log."""
    return chosen_vs_best_gap(chosen, best).ratio


def create_candidate_meal_plans(
    recipe_ids: Sequence[str],
    n: int,
    ctx: ScoringContext,
    weights: ScorerWeights | None = None,
    k: int = 2,
    seed: int = 0,
) -> tuple[PlanScore, ...]:
    """Offer up to k distinct candidate weeks of n recipes, best first, each with its score breakdown.

    This is the scorer as the graph uses it: a greedy fill, then a pairwise-swap local search, with seeded
    tie-breaks so the same seed is the same pair of weeks (ADR 0014 wants variety between Generates, not inside
    one). The plans are distinct by construction: each one after the first blocks a recipe of the plan before it,
    so a week the household has just been shown cannot come back as its own alternative.

    Fewer than k plans come back when fewer exist: a pool that is exactly one week long has no second week in it.
    A pool smaller than n plans every recipe it has.
    """
    scorer = _Scorer(ctx, weights or ScorerWeights())
    pool = tuple(dict.fromkeys(recipe_ids))
    scorer.require(pool)
    if n <= 0 or k <= 0 or not pool:
        return ()
    size = min(n, len(pool))
    ranks = _tie_break_ranks(pool, seed)
    plans: list[PlanScore] = []
    seen: set[frozenset[str]] = set()
    blockers: deque[str] = deque()
    for _attempt in range(_PLANS_ATTEMPTS_PER_PLAN * k):
        blocked = blockers.popleft() if blockers else None
        candidates = tuple(recipe_id for recipe_id in pool if recipe_id != blocked)
        if len(candidates) < size:
            continue
        chosen = _local_search(scorer, _greedy_plan(scorer, candidates, size, ranks), candidates, ranks)
        recipe_set = frozenset(chosen)
        if recipe_set in seen:
            continue
        seen.add(recipe_set)
        plans.append(scorer.score(chosen))
        if len(plans) == k:
            break
        # The next plan blocks the week's weakest recipe, so the alternative differs by one swap rather than
        # by losing whatever the seed happened to rank first.
        blockers = deque(sorted(chosen, key=lambda recipe_id: (scorer.base_total(recipe_id), ranks[recipe_id])))
    # Each plan after the first is a different local optimum, so generation order is not score order: the caller
    # reads plans[0] as the scorer's best. `sorted` is stable, so equal plans keep the order they were found in.
    return tuple(sorted(plans, key=lambda plan: plan.total, reverse=True))


class _Scorer:
    """One scoring run: the per-recipe terms are plan-independent, so they are computed once and cached."""

    def __init__(self, ctx: ScoringContext, weights: ScorerWeights) -> None:
        self._ctx = ctx
        self._weights = weights
        self._healthier = HEALTHIER_CHIP in ctx.chips
        self._pantry_multiplier = (
            weights.use_up_the_fridge_multiplier if FeedbackChip.USE_UP_THE_FRIDGE.value in ctx.chips else 1.0
        )
        self._repeat_weights = (
            weights.repeat_main_protein,
            weights.repeat_main_carb,
            weights.repeat_dish_type,
            weights.repeat_cuisine,
        )
        # Every urgent item at least one candidate uses: the ones this week could have used, and so the ones it
        # can be charged for leaving out. An item a meal already in the week uses is not one of them: it is being
        # used, just not by this generation.
        self._pool_urgent_items = frozenset(
            item for items in ctx.urgent_item_uses.values() for item in items
        ) - frozenset(ctx.urgent_items_already_used)
        self._recipes: dict[str, RecipeScore] = {}
        self._totals: dict[str, float] = {}
        self._values: dict[str, tuple[str, str, str, str]] = {}

    def require(self, recipe_ids: Sequence[str]) -> None:
        """Raise `UnknownRecipeIds` naming every id the context has no facts for."""
        _require_known(recipe_ids, self._ctx)

    def score(self, recipe_ids: Sequence[str]) -> PlanScore:
        return PlanScore(
            recipes=tuple(self.recipe(recipe_id) for recipe_id in recipe_ids),
            penalties=self.penalties(recipe_ids),
        )

    def total(self, recipe_ids: Sequence[str]) -> float:
        """The same number `score().total` gives, without building the breakdown: the search calls this."""
        return sum(self.base_total(recipe_id) for recipe_id in recipe_ids) + self._penalty_points(recipe_ids)

    def base_total(self, recipe_id: str) -> float:
        """One recipe's own fit, before any plan penalty: what the recipe brings to a week on its own."""
        cached = self._totals.get(recipe_id)
        if cached is None:
            cached = self._totals[recipe_id] = self.recipe(recipe_id).total
        return cached

    def recipe(self, recipe_id: str) -> RecipeScore:
        scored = self._recipes.get(recipe_id)
        if scored is None:
            facts = self._ctx.recipes[recipe_id]
            scored = self._recipes[recipe_id] = RecipeScore(recipe_id=recipe_id, terms=self._terms(facts))
        return scored

    def _terms(self, facts: CandidateRecipe) -> tuple[TermScore, ...]:
        """One recipe's fit: every per-recipe row of the table, in table order."""
        return (
            TermScore(Term.PANTRY_FIT, self._weights.pantry_fit * self._pantry_multiplier * facts.pantry_fit),
            TermScore(
                Term.FAVOURITE, self._weights.favourite if facts.recipe_id in self._ctx.favourite_recipe_ids else 0.0
            ),
            TermScore(Term.LIKED_CUISINE, self._liked_cuisine(facts)),
            TermScore(Term.LOVED_INGREDIENT, self._loved_ingredient(facts)),
            TermScore(Term.AVOIDED_CUISINE, self._avoided_cuisine(facts)),
            TermScore(Term.FEEDBACK_CHIP, self._feedback_chips(facts)),
            TermScore(Term.RECENCY, self._recency(facts)),
            TermScore(Term.RATING, self._rating(facts)),
            TermScore(Term.WHOLE_FOOD, self._whole_food(facts)),
        )

    def _loved_ingredient(self, facts: CandidateRecipe) -> float:
        # The row is "+1 liked cuisine or loved ingredient": a match is a point, so a dish that matched three
        # loved ingredients still scores one and cannot out-vote the week's balance.
        return self._weights.loved_ingredient if facts.loved_ingredients else 0.0

    def _liked_cuisine(self, facts: CandidateRecipe) -> float:
        return self._weights.liked_cuisine if facts.attributes.cuisine in self._ctx.liked_cuisines else 0.0

    def _avoided_cuisine(self, facts: CandidateRecipe) -> float:
        return self._weights.avoided_cuisine if facts.attributes.cuisine in self._ctx.avoided_cuisines else 0.0

    def _feedback_chips(self, facts: CandidateRecipe) -> float:
        return self._weights.feedback_chip * sum(1 for chip in self._ctx.chips if self._satisfies(chip, facts))

    def _satisfies(self, chip: str, facts: CandidateRecipe) -> bool:
        """Whether one recipe satisfies one chip: two chips read its history, the rest a predicate."""
        if chip == FeedbackChip.SOMETHING_NEW:
            return facts.days_since_cooked is None and not facts.cooked_last_week
        if chip == FeedbackChip.SAME_AS_LAST_WEEK:
            return facts.cooked_last_week
        predicate = self._ctx.chip_predicates.get(chip)
        return predicate is not None and predicate.matches(facts.attributes)

    def _recency(self, facts: CandidateRecipe) -> float:
        days = facts.days_since_cooked
        if days is None:
            return 0.0
        if days <= SIX_WEEKS_DAYS:
            # The floor normally excludes these; only a relaxed floor offers one, and only then is it penalised.
            return self._weights.recency_relaxed if facts.offered_after_floor_relaxed else 0.0
        if days <= NINE_WEEKS_DAYS:
            return self._weights.recency_weeks_7_to_9
        if days <= TWELVE_WEEKS_DAYS:
            return self._weights.recency_weeks_10_to_12
        return 0.0

    def _rating(self, facts: CandidateRecipe) -> float:
        if facts.rating is Rating.DOWN:
            return self._weights.rating_down
        if facts.rating is Rating.UP:
            # A thumb up is worth something only once the meal is old enough to be a pleasure to repeat.
            days = facts.days_since_cooked
            return self._weights.rating_up_after_six_weeks if days is not None and days > SIX_WEEKS_DAYS else 0.0
        return 0.0

    def _whole_food(self, facts: CandidateRecipe) -> float:
        if facts.attributes.whole_food is not WholeFood.WHOLE:
            return 0.0
        return self._weights.whole_food * (self._weights.healthier_multiplier if self._healthier else 1.0)

    def penalties(self, recipe_ids: Sequence[str]) -> tuple[PlanPenalty, ...]:
        """What the plan as a whole loses: repeats, the lighter chip's calories term, and protein targets."""
        penalties = [
            PlanPenalty(term=term, points=weight * (len(ids) - 1), recipe_ids=tuple(ids[1:]), detail=value)
            for term, weight, group in zip(
                _REPEAT_TERMS, self._repeat_weights, self._occurrences(recipe_ids), strict=True
            )
            for value, ids in group.items()
            if len(ids) > 1
        ]
        above, detail = self._lighter_offenders(recipe_ids)
        if above:
            penalties.append(
                PlanPenalty(
                    term=Term.LIGHTER, points=self._weights.lighter * len(above), recipe_ids=above, detail=detail
                )
            )
        penalties.extend(
            PlanPenalty(term=Term.UNUSED_URGENT_ITEM, points=self._weights.unused_urgent_item, detail=item)
            for item in self._unused_urgent_items(recipe_ids)
        )
        penalties.extend(
            PlanPenalty(
                term=Term.PROTEIN_TARGET,
                points=self._weights.protein_target_miss * misses,
                detail=f"{target.protein.value} x{count} against min {target.min_per_week} max {target.max_per_week}",
            )
            for target, count, misses in self._target_misses(recipe_ids)
        )
        return tuple(penalties)

    def _occurrences(self, recipe_ids: Sequence[str]) -> list[dict[str, list[str]]]:
        """One value-to-recipes map per repeat term, in plan order, so "the extra ones" are stable."""
        occurrences: list[dict[str, list[str]]] = [{}, {}, {}, {}]
        for recipe_id in recipe_ids:
            for group, value, exempt in zip(occurrences, self.repeat_values(recipe_id), _REPEAT_EXEMPT, strict=True):
                if value not in exempt:
                    group.setdefault(value, []).append(recipe_id)
        return occurrences

    def repeat_values(self, recipe_id: str) -> tuple[str, str, str, str]:
        """The four attributes repeats are counted on, as plain strings, read once per recipe.

        `as_mapping` builds a whole dict of all six attributes, which the search would pay for on every candidate
        of every trial swap; the repeat terms need four of them and never change, so they are kept here.
        """
        cached = self._values.get(recipe_id)
        if cached is None:
            attrs = self._ctx.recipes[recipe_id].attributes
            cached = self._values[recipe_id] = (
                attrs.main_protein.value,
                attrs.main_carb.value,
                attrs.dish_type.value,
                attrs.cuisine.value,
            )
        return cached

    def _lighter_offenders(self, recipe_ids: Sequence[str]) -> tuple[tuple[str, ...], str]:
        """The recipes above the fixed calorie reference, and what that reference is. Empty without the chip.

        A recipe with no stated calories counts as above the reference: an unknown figure must never let a recipe
        look lighter than one whose figure is known, or a plan could buy its way past the chip by choosing
        recipes nobody measured (V6 eval finding 2, owner decision 2026-10-25).
        """
        if LIGHTER_CHIP not in self._ctx.chips:
            return (), ""
        reference = self._weights.lighter_reference_kcal
        above = tuple(
            recipe_id
            for recipe_id in recipe_ids
            if (calories := self._ctx.recipes[recipe_id].calories_per_serving) is None or calories > reference
        )
        return above, f"above {reference:g} kcal" if above else ""

    def _unused_urgent_items(self, recipe_ids: Sequence[str]) -> tuple[str, ...]:
        """The pool's urgent items that no recipe in the week uses, in name order.

        The pool is the offered candidates, so an item nothing in the offer uses is nobody's to use and costs
        nothing (spec §6.2 step 4, #122's rule).
        """
        if not self._pool_urgent_items:
            return ()
        used = {item for recipe_id in recipe_ids for item in self._ctx.urgent_item_uses.get(recipe_id, ())}
        return tuple(sorted(self._pool_urgent_items - used))

    def _target_misses(self, recipe_ids: Sequence[str]) -> list[tuple[ProteinTarget, int, int]]:
        """Every protein target the plan misses, with the count it reached: more fish, fewer pork."""
        if not self._ctx.protein_targets:
            return []
        counts: Counter[MainProtein] = Counter(
            self._ctx.recipes[recipe_id].attributes.main_protein for recipe_id in recipe_ids
        )
        misses: list[tuple[ProteinTarget, int, int]] = []
        for target in self._ctx.protein_targets:
            count = counts[target.protein]
            short = 0
            if target.min_per_week is not None and count < target.min_per_week:
                short += target.min_per_week - count
            if target.max_per_week is not None and count > target.max_per_week:
                short += count - target.max_per_week
            if short:
                misses.append((target, count, short))
        return misses

    def _penalty_points(self, recipe_ids: Sequence[str]) -> float:
        """The same penalties `penalties` describes, as one number: the search's hot path builds no objects."""
        points = sum(
            weight * sum(len(ids) - 1 for ids in group.values() if len(ids) > 1)
            for weight, group in zip(self._repeat_weights, self._occurrences(recipe_ids), strict=True)
        )
        above, _detail = self._lighter_offenders(recipe_ids)
        points += self._weights.lighter * len(above)
        points += self._weights.protein_target_miss * sum(
            misses for _target, _count, misses in self._target_misses(recipe_ids)
        )
        points += self._weights.unused_urgent_item * len(self._unused_urgent_items(recipe_ids))
        return points


def _require_known(recipe_ids: Sequence[str], ctx: ScoringContext) -> None:
    """Refuse a plan or a metric naming a recipe twice, or one the caller did not describe."""
    ids = list(recipe_ids)
    repeated = sorted(recipe_id for recipe_id, count in Counter(ids).items() if count > 1)
    if repeated:
        raise DuplicateRecipeIds(f"a plan cannot name the same recipe twice: {repeated}")
    missing = sorted(set(ids) - ctx.recipes.keys())
    if missing:
        raise UnknownRecipeIds(missing)


def _tie_break_ranks(pool: Sequence[str], seed: int) -> dict[str, float]:
    """A total order over the pool: the seed shuffled against the ids, never against the order they arrived in.

    The ids are sorted before the shuffle, so two callers who list the same pool differently plan the same week.
    """
    order = sorted(pool)
    random.Random(seed).shuffle(order)  # noqa: S311 - seeded on purpose: one Generate seed plans one week
    return {recipe_id: float(position) for position, recipe_id in enumerate(order)}


def _greedy_plan(scorer: _Scorer, pool: Sequence[str], size: int, ranks: Mapping[str, float]) -> list[str]:
    """Fill the week one slot at a time with the recipe that makes the plan so far score best.

    The local search starts here, and the tests compare the two: greedy alone commits to the strongest single
    recipe, which is not always a plan that can reach a protein target or a balanced set of dishes.
    """
    chosen: list[str] = []
    remaining = list(pool)
    while len(chosen) < size:
        best = max(remaining, key=lambda recipe_id: (scorer.total((*chosen, recipe_id)), ranks[recipe_id]))
        chosen.append(best)
        remaining.remove(best)
    return chosen


def _local_search(
    scorer: _Scorer, chosen: Sequence[str], pool: Sequence[str], ranks: Mapping[str, float]
) -> tuple[str, ...]:
    """Swap one slot at a time while the week improves, taking the best swap in the neighbourhood each pass."""
    best = list(chosen)
    best_total = scorer.total(best)
    evaluations = 0
    for _pass in range(_MAX_LOCAL_SEARCH_PASSES):
        present = set(best)
        unused = [recipe_id for recipe_id in pool if recipe_id not in present]
        improvement: tuple[float, float, list[str]] | None = None
        for position in range(len(best)):
            for incoming in unused:
                if evaluations >= _MAX_SWAP_EVALUATIONS:
                    # The budget ran out mid-pass: keep the best swap this pass already found rather than
                    # throw away a real improvement, or the budget would change the answer, not just the time.
                    return tuple(best if improvement is None else improvement[2])
                evaluations += 1
                trial = [*best]
                trial[position] = incoming
                total = scorer.total(trial)
                if total > best_total + _SCORE_EPSILON and (
                    improvement is None or (total, ranks[incoming]) > improvement[:2]
                ):
                    improvement = (total, ranks[incoming], trial)
        if improvement is None:
            break
        best_total, _, best = improvement
    return tuple(best)


def _minutes(value: str) -> int | None:
    """The minutes a predicate value states (`30`, `30 min`), or None when it states none."""
    text = value.strip().casefold()
    for suffix in ("minutes", "minute", "mins", "min"):
        text = text.removesuffix(suffix)
    text = text.strip()
    return int(text) if text.isdigit() else None


# The chips that pay through a predicate on the recipe's attributes. An unknown attribute satisfies none of them.
CHIP_PREDICATES: Mapping[str, Predicate] = MappingProxyType(
    {
        FeedbackChip.QUICK_WEEKNIGHTS.value: Predicate(
            PredicateField.ACTIVE_TIME, PredicateOp.LTE, (str(QUICK_WEEKNIGHT_MINS),)
        ),
        FeedbackChip.COMFORT_FOOD.value: Predicate(
            PredicateField.DISH_TYPE, PredicateOp.IN, tuple(dish.value for dish in COMFORT_DISH_TYPES)
        ),
        FeedbackChip.GUESTS.value: Predicate(
            PredicateField.DISH_TYPE, PredicateOp.IN, tuple(dish.value for dish in GUEST_DISH_TYPES)
        ),
    }
)


def chip_narrows(chip: FeedbackChip, attributes: RecipeAttributes, *, total_time_mins: int | None) -> bool:
    """Whether one recipe passes a narrowing chip's rule (`NARROWING_CHIPS`).

    Quick weeknights is V5's time-cap rule at `QUICK_WEEKNIGHT_MINS`, the same rule the household's own cap uses:
    the bucket's bound, total time when no bucket is known, and an unknown time passes. Comfort food and guests
    are their dish-type predicates, so an unknown dish type never passes.
    """
    if chip == FeedbackChip.QUICK_WEEKNIGHTS:
        return attributes.fits_time_cap(QUICK_WEEKNIGHT_MINS, total_time_mins=total_time_mins)
    if chip not in NARROWING_CHIPS:
        raise ValueError(f"{chip} does not narrow the offer")
    return CHIP_PREDICATES[chip.value].matches(attributes)


@dataclass(frozen=True, slots=True)
class CorpusRecipe:
    """One corpus recipe as the corpus tools read it: what the projection's summary and attributes hold."""

    recipe_id: str
    title: str
    cuisine: str | None = None
    total_time_mins: int | None = None
    ingredient_names: tuple[str, ...] = ()
    attributes: RecipeAttributes = field(default_factory=RecipeAttributes)


# A full recipe's ingredient lines and method steps, which only `get_recipes(detail="full")` reads.
type FullRecipe = tuple[tuple[str, ...], tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class EligibilityContext:
    """The corpus and the session's hard constraints, as plain values the caller built from its store.

    `dietary_excluded_ids` is what the stored dietary decisions rule out for the household's flags: deciding it
    reads the decision store, so the caller does, and the tool applies it. `disliked_ingredients` are the
    profile's (V13b), a hard constraint beside them. `max_active_mins` is the household's time cap. `cooked` is
    the history window the six-week floor and the thumbs-down rule read. `text_search` is the corpus's full-text
    search (ids that match); without one, text matches title, cuisine and ingredient words in memory.
    `load_full` reads one recipe's ingredient lines and method for `get_recipes(detail="full")`.
    """

    recipes: Sequence[CorpusRecipe]
    slots: int
    now: datetime
    dietary_excluded_ids: frozenset[str] = frozenset()
    disliked_ingredients: tuple[str, ...] = ()
    planned_ids: frozenset[str] = frozenset()
    max_active_mins: int | None = None
    cooked: Sequence[CookedMeal] = ()
    pantry: Sequence[PantryItem] = ()
    seed: int = 0
    text_search: Callable[[str], Collection[str]] | None = None
    load_full: Callable[[str], FullRecipe | None] | None = None


@dataclass(frozen=True, slots=True)
class RecipeFilter:
    """The agent's filter (spec 6.2, "The filter's shape"). It can only narrow what the session allows.

    Fields and operators come from `PredicateField`/`PredicateOp`, so nothing outside the allowlist can be said.
    `max_active_mins` may only tighten the household's cap, and `limit` is at most `MAX_FILTER_LIMIT`: a filter
    that asks for more is refused (`FilterRejected`) rather than quietly clamped, so the agent learns it.
    """

    text: str | None = None
    include: tuple[Predicate, ...] = ()
    exclude: tuple[Predicate, ...] = ()
    max_active_mins: int | None = None
    uses_pantry: tuple[str, ...] | None = None
    exclude_ids: tuple[str, ...] = ()
    limit: int = MAX_FILTER_LIMIT


class FilterRejected(ValueError):
    """The filter tried to widen what the session allows, or asked for something outside the allowlist."""


@dataclass(frozen=True, slots=True)
class EligibleRecipe:
    """One recipe `get_eligible_recipes` returns, with everything the scorer and a proposal card need.

    `pantry_fit` is the raw urgency-weighted sum of the pantry items it uses (not yet scaled to the scorer's
    +3); `urgent_items` are those that go off within `URGENT_EXPIRY_DAYS`. `days_since_cooked` and `rating`
    come from the history window, and `offered_after_floor_relaxed` marks a recipe the six-week floor gave back.
    """

    recipe_id: str
    title: str
    cuisine: str | None
    total_time_mins: int | None
    attributes: RecipeAttributes
    pantry_fit: float = 0.0
    pantry_items: tuple[str, ...] = ()
    urgent_items: tuple[PantryItem, ...] = ()
    days_since_cooked: float | None = None
    rating: str | None = None
    offered_after_floor_relaxed: bool = False

    @property
    def recency_penalty(self) -> float:
        """The scorer's recency term for this recipe: -8 for a relaxed recipe, smaller as the cook ages."""
        return _recency_penalty(self.days_since_cooked)


@dataclass(frozen=True, slots=True)
class EligibleRecipes:
    """What one `get_eligible_recipes` call found: the ranked recipes, and how many passed before the limit."""

    recipes: tuple[EligibleRecipe, ...]
    matched: int
    floor_relaxed: bool


@dataclass(frozen=True, slots=True)
class RecipeCard:
    """One recipe as `get_recipes` describes it. `ingredients` and `method` are filled for `detail="full"` only."""

    recipe_id: str
    title: str
    cuisine: str | None
    total_time_mins: int | None
    active_time_mins: int | None
    attributes: RecipeAttributes
    key_ingredients: tuple[str, ...]
    ingredients: tuple[str, ...] = ()
    method: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RecipeDetails:
    """The cards found, and the ids the corpus does not hold."""

    recipes: tuple[RecipeCard, ...]
    unknown: tuple[str, ...] = ()


def get_eligible_recipes(recipe_filter: RecipeFilter, ctx: EligibilityContext) -> EligibleRecipes:
    """The recipes this household may be offered, narrowed by the agent's filter and ranked (spec 6.2).

    1. The hard constraints: the dietary decisions, the profile's disliked ingredients (V13b), a thumbs down (V8),
       the time cap (V5's bucket rule) and the meals already planned. Nothing later can bring one of these back.
    2. The six-week floor (V2): recently cooked recipes are left out unless that leaves fewer than three per
       slot, and then they come back last, carrying the recency penalty.
    3. The agent's filter, which can only narrow.
    4. The urgent guarantee (V4): every pantry item that goes off within three days gets the best recipe that
       uses it, ahead of the ranking and inside the limit, up to `GUARANTEE_MAX` of them.
    5. The ranking: urgency-weighted pantry fit, fresh before relaxed, seeded tie-breaks, and near-duplicates
       of a recipe already taken left out.

    Raises `FilterRejected` for a filter that would widen what the session allows.
    """
    _check_narrows(recipe_filter, ctx)
    by_id = {recipe.recipe_id: recipe for recipe in ctx.recipes}
    disliked = disliked_recipe_ids(
        ((recipe.recipe_id, recipe.ingredient_names) for recipe in ctx.recipes), ctx.disliked_ingredients
    )
    # Sorted, so the floor and the tie-breaks see the same order however the caller listed the corpus.
    hard = [
        recipe
        for recipe_id, recipe in sorted(by_id.items())
        if recipe_id not in ctx.planned_ids
        and recipe_id not in ctx.dietary_excluded_ids
        and recipe_id not in disliked
        and recipe.attributes.fits_time_cap(ctx.max_active_mins, total_time_mins=recipe.total_time_mins)
    ]
    floor = apply_recency_floor(
        [recipe.recipe_id for recipe in hard],
        titles={recipe.recipe_id: recipe.title for recipe in hard},
        cooked=ctx.cooked,
        now=ctx.now,
        slots=ctx.slots,
    )
    relaxed = set(floor.relaxed)
    searched = _text_matches(recipe_filter.text, hard, ctx)
    narrowed = [
        by_id[recipe_id]
        for recipe_id in floor.recipe_ids
        if _passes(by_id[recipe_id], recipe_filter, searched=searched, pantry=ctx.pantry)
    ]
    entries = {
        recipe.recipe_id: _eligible(
            recipe,
            ctx.pantry,
            days_since_cooked=floor.days_since_cooked.get(recipe.recipe_id),
            rating=floor.latest_rating.get(recipe.recipe_id),
            relaxed=recipe.recipe_id in relaxed,
        )
        for recipe in narrowed
    }
    ranks = _tie_break_ranks(list(entries), ctx.seed)
    ranked = sorted(
        entries.values(),
        key=lambda entry: (
            entry.offered_after_floor_relaxed,
            -entry.recency_penalty if entry.offered_after_floor_relaxed else 0.0,
            -entry.pantry_fit,
            ranks[entry.recipe_id],
        ),
    )
    taken = _urgent_guarantee(ranked, limit=min(GUARANTEE_MAX, recipe_filter.limit))
    for entry in ranked:
        if len(taken) >= recipe_filter.limit:
            break
        if entry in taken or any(
            near_duplicate_ingredients(by_id[entry.recipe_id].ingredient_names, by_id[other.recipe_id].ingredient_names)
            for other in taken
        ):
            continue
        taken.append(entry)
    return EligibleRecipes(recipes=tuple(taken), matched=len(narrowed), floor_relaxed=floor.relaxed_floor)


def get_recipes(
    recipe_ids: Sequence[str], detail: Literal["summary", "full"], ctx: EligibilityContext
) -> RecipeDetails:
    """Describe recipes: title, cuisine, times, attributes and key ingredients; `full` adds lines and method.

    A read, not a grant: describing a recipe does not make it eligible. Ids the corpus does not hold come back
    in `unknown` rather than raising, so one bad id costs the agent nothing but that id.
    """
    by_id = {recipe.recipe_id: recipe for recipe in ctx.recipes}
    cards: list[RecipeCard] = []
    unknown: list[str] = []
    for recipe_id in dict.fromkeys(recipe_ids):
        recipe = by_id.get(recipe_id)
        if recipe is None:
            unknown.append(recipe_id)
            continue
        full = ctx.load_full(recipe_id) if detail == "full" and ctx.load_full is not None else None
        ingredients, method = full if full is not None else ((), ())
        cards.append(
            RecipeCard(
                recipe_id=recipe_id,
                title=recipe.title,
                cuisine=recipe.cuisine,
                total_time_mins=recipe.total_time_mins,
                active_time_mins=recipe.attributes.active_time_mins(recipe.total_time_mins),
                attributes=recipe.attributes,
                key_ingredients=recipe.ingredient_names[:_KEY_INGREDIENTS],
                ingredients=ingredients,
                method=method,
            )
        )
    return RecipeDetails(recipes=tuple(cards), unknown=tuple(unknown))


def _check_narrows(recipe_filter: RecipeFilter, ctx: EligibilityContext) -> None:
    """Refuse a filter that would let more through than the session's own constraints do."""
    if not 1 <= recipe_filter.limit <= MAX_FILTER_LIMIT:
        raise FilterRejected(f"limit must be between 1 and {MAX_FILTER_LIMIT}, not {recipe_filter.limit}")
    cap = recipe_filter.max_active_mins
    if cap is not None:
        if cap <= 0:
            raise FilterRejected(f"max_active_mins must be a positive number of minutes, not {cap}")
        if ctx.max_active_mins is not None and cap > ctx.max_active_mins:
            raise FilterRejected(
                f"max_active_mins may only tighten the household's {ctx.max_active_mins}-minute cap, not raise it"
            )


def _text_matches(text: str | None, recipes: Sequence[CorpusRecipe], ctx: EligibilityContext) -> set[str] | None:
    """The ids `text` matches, or None when there is no text to match. One search per call."""
    if text is None or not text.strip():
        return None
    if ctx.text_search is not None:
        return set(ctx.text_search(text))
    tokens = _WORD_RE.findall(text.casefold())
    return {
        recipe.recipe_id
        for recipe in recipes
        if all(
            token in " ".join([recipe.title, recipe.cuisine or "", *recipe.ingredient_names]).casefold()
            for token in tokens
        )
    }


def _passes(
    recipe: CorpusRecipe, recipe_filter: RecipeFilter, *, searched: set[str] | None, pantry: Sequence[PantryItem]
) -> bool:
    """Whether one recipe survives the agent's filter. Every clause narrows; none can add."""
    attributes = recipe.attributes
    if searched is not None and recipe.recipe_id not in searched:
        return False
    if recipe.recipe_id in recipe_filter.exclude_ids:
        return False
    if not all(predicate.matches(attributes) for predicate in recipe_filter.include):
        return False
    if any(predicate.matches(attributes) for predicate in recipe_filter.exclude):
        return False
    if not attributes.fits_time_cap(recipe_filter.max_active_mins, total_time_mins=recipe.total_time_mins):
        return False
    return all(
        any(mentions_item(name, item) for name in recipe.ingredient_names) for item in recipe_filter.uses_pantry or ()
    )


def _eligible(
    recipe: CorpusRecipe,
    pantry: Sequence[PantryItem],
    *,
    days_since_cooked: float | None,
    rating: str | None,
    relaxed: bool,
) -> EligibleRecipe:
    """The recipe with its pantry fit: the same ingredient-line evidence a reason's "uses up" rests on."""
    used = [item for item in pantry if any(mentions_item(name, item.name) for name in recipe.ingredient_names)]
    return EligibleRecipe(
        recipe_id=recipe.recipe_id,
        title=recipe.title,
        cuisine=recipe.cuisine,
        total_time_mins=recipe.total_time_mins,
        attributes=recipe.attributes,
        pantry_fit=sum(item.weight for item in used),
        pantry_items=tuple(item.name for item in used),
        urgent_items=tuple(item for item in used if item.is_urgent),
        days_since_cooked=days_since_cooked,
        rating=rating,
        offered_after_floor_relaxed=relaxed,
    )


def _urgent_guarantee(ranked: Sequence[EligibleRecipe], *, limit: int) -> list[EligibleRecipe]:
    """One recipe per urgent item, soonest to go off first, the best-ranked recipe that uses it.

    A recipe already guaranteed covers every urgent item it uses, so one dish using the coriander and the kale
    takes one place, not two. Fresh recipes rank ahead of relaxed ones, so a relaxed recipe is guaranteed only
    for an item no fresh recipe uses.
    """
    items = sorted(
        {item for entry in ranked for item in entry.urgent_items},
        key=lambda item: (item.expires_in_days or 0, item.name.casefold()),
    )
    guaranteed: list[EligibleRecipe] = []
    covered: set[PantryItem] = set()
    for item in items:
        if len(guaranteed) >= limit:
            break
        if item in covered:
            continue
        entry = next((entry for entry in ranked if item in entry.urgent_items), None)
        if entry is not None and entry not in guaranteed:
            guaranteed.append(entry)
            covered.update(entry.urgent_items)
    return guaranteed
