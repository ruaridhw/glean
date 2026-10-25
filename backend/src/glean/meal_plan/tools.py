"""The planner's system-1 tools: score a week, and offer k balanced weeks to choose between.

Framework-free and pure (spec 6.2, "Tools"): plain typed functions over plain data, with no graph, store or
network import, so the agent graph, the evals (6.6) and the MCP server all call the same code through thin
adapters. Feasibility is decided upstream — dietary decisions, the time cap, meals already planned and the
six-week floor all happen in `get_eligible_recipes` — so everything here is a score, never a filter.

A plan's score is each recipe's fit minus the plan's penalties, one weight per row of the scorer table
(spec 6.2, "Scorer weights"). Every one of those numbers is a starting guess, so they live in `ScorerWeights`
and no term hard-codes its own. A recipe whose attributes are `unsure` earns no variety credit and no penalty,
and a term whose attribute is not in G1's set is skipped and named in the breakdown rather than silently scored
as zero: richness was dropped in G1, so there is nothing to read for the "3+ hearty" rule.
"""

from __future__ import annotations

import random
from collections import Counter, deque
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from glean.recipes.attributes import (
    UNSURE,
    ActiveTimeBucket,
    Cuisine,
    MainCarb,
    MainProtein,
    RecipeAttributes,
    WholeFood,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = [
    "HEALTHIER_CHIP",
    "LIGHTER_CHIP",
    "CandidateRecipe",
    "PlanPenalty",
    "PlanScore",
    "Predicate",
    "PredicateField",
    "PredicateOp",
    "ProteinTarget",
    "Rating",
    "RecipeScore",
    "ScorerWeights",
    "ScoringContext",
    "SkippedTerm",
    "Term",
    "TermScore",
    "UnknownRecipeIds",
    "chosen_vs_best_ratio",
    "create_candidate_meal_plans",
    "distinct_main_carbs",
    "distinct_main_proteins",
    "score_meal_plan",
]

# The chip names V9 sends on the wire. The scorer reads two of them by name; every other chip earns its +2 only
# through the predicate the caller maps it to.
HEALTHIER_CHIP = "healthier"
LIGHTER_CHIP = "lighter"

# Six, nine and twelve weeks, in days: the recency bands' boundaries.
SIX_WEEKS_DAYS = 42
NINE_WEEKS_DAYS = 63
TWELVE_WEEKS_DAYS = 84

# Two floats closer than this are the same score, so a "swap" between them is not an improvement.
_SCORE_EPSILON = 1e-9
# The local search stops after this many improving passes, and after this many plan evaluations, which is what
# bounds the tool's time: a 120-recipe pool's neighbourhood is far more than one plan needs to settle.
_MAX_LOCAL_SEARCH_PASSES = 8
_MAX_SWAP_EVALUATIONS = 2000
# Attempts per plan offered: each one blocks a recipe of the plan before it, so the plans differ by construction.
_PLANS_ATTEMPTS_PER_PLAN = 4

# Values that earn nothing when they repeat, one set per entry of `_REPEAT_TERMS`. An unknown attribute is not
# evidence of sameness, so `unsure` is exempt everywhere. A dish built around no protein cannot repeat a protein;
# a dish built around no carb is still a repeated carb choice, and the spec's carb row carries no exemption, so
# only the protein row exempts `none` (owner decision 2026-10-25, from the V6 eval's carb-gate misses).
_REPEAT_EXEMPT: tuple[frozenset[str], ...] = (
    frozenset({UNSURE, "none"}),
    frozenset({UNSURE}),
    frozenset({UNSURE}),
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
    # "Profile affinity": +1 loved ingredient, per ingredient of the profile this recipe was matched to.
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
    # "Whole food": the "healthier" chip doubles it. If V9 also maps a predicate to that chip, both apply, so
    # its predicate mapping is the place to keep it from counting twice.
    healthier_multiplier: float = 2.0
    # "'Lighter' chip": -1 per recipe above `lighter_reference_kcal`, once the chip is on.
    lighter: float = -1.0
    # That reference: the corpus median of STATED per-serving calories, 672 kcal. Derived from the 2026-10-24 prod
    # corpus export, where 362 of its 632 recipes state nutrition on their own page (the labeller's estimates for
    # the other 270 are excluded); their median is 672.5, rounded down to 672. Owner decision 2026-10-25: a fixed
    # reference, not the week's own median, so a plan can no longer make itself look light by choosing light
    # recipes, which the V6 eval saw it do.
    lighter_reference_kcal: int = 672
    # "Protein targets from the profile": -4 per miss, such as fish at least once.
    protein_target_miss: float = -4.0


@dataclass(frozen=True, slots=True)
class CandidateRecipe:
    """One candidate recipe exactly as the scorer needs it: all plain data, no lookup of its own.

    `pantry_fit` is the caller's already urgency-weighted, already scaled figure; `days_since_cooked` is None for
    a recipe the household has never cooked; `offered_after_floor_relaxed` says the six-week floor was lowered to
    offer it, which is the only case the recency row's -8 applies; `loved_ingredients` are the profile's loved
    ingredients this recipe was matched to upstream.
    """

    recipe_id: str
    attributes: RecipeAttributes = field(default_factory=RecipeAttributes)
    calories_per_serving: float | None = None
    pantry_fit: float = 0.0
    days_since_cooked: int | None = None
    rating: Rating | None = None
    offered_after_floor_relaxed: bool = False
    loved_ingredients: tuple[str, ...] = ()


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

    `recipes` holds one `CandidateRecipe` per candidate id. The rest are the optional profile inputs (spec 6.4)
    and the week's feedback chips. `chip_predicates` is empty until V9 gives each chip a predicate; a chip with no
    predicate earns nothing (and the two chips the scorer reads by name still work: `healthier` doubles the whole
    food term, `lighter` turns on the calories term).
    """

    recipes: Mapping[str, CandidateRecipe] = field(default_factory=dict)
    favourite_recipe_ids: frozenset[str] = frozenset()
    liked_cuisines: frozenset[Cuisine] = frozenset()
    avoided_cuisines: frozenset[Cuisine] = frozenset()
    protein_targets: tuple[ProteinTarget, ...] = ()
    chips: frozenset[str] = frozenset()
    chip_predicates: Mapping[str, Predicate] = field(default_factory=dict)


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
class SkippedTerm:
    """A term the scorer did not evaluate, and why: the eval reports these rather than reading a silent zero."""

    term: str
    reason: str


@dataclass(frozen=True, slots=True)
class PlanScore:
    """A whole week: every recipe's terms, the plan's penalties, and the terms that could not be evaluated."""

    recipes: tuple[RecipeScore, ...]
    penalties: tuple[PlanPenalty, ...] = ()
    skipped_terms: tuple[SkippedTerm, ...] = ()

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


class UnknownRecipeIds(KeyError):
    """A plan named a recipe the caller's context does not describe: the ids and the facts disagree."""


# The terms that cannot be scored yet, with the reason. G1 dropped richness, so nothing carries "hearty".
_SKIPPED_TERMS: tuple[SkippedTerm, ...] = (
    SkippedTerm(
        term="hearty_repeat",
        reason="no G1 attribute carries heartiness: richness was dropped until a slice needs it, "
        "so a plan of 3+ hearty dishes cannot be counted",
    ),
)


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


def chosen_vs_best_ratio(chosen: PlanScore, best: PlanScore) -> float:
    """The chosen plan's score as a fraction of the best plan's, for the eval's "within 15%" gate (spec 6.6).

    A plan that scores at least as well as the best is 1.0, and the gate is `ratio >= 0.85`. Scores are signed
    sums, so the shortfall is measured against the best plan's own magnitude rather than by dividing the two: a
    best of zero would make a plain ratio meaningless. It floors at 0: the gate only reads whether it clears 0.85.
    """
    shortfall = best.total - chosen.total
    if shortfall <= 0:
        return 1.0
    return max(1.0 - shortfall / max(abs(best.total), 1.0), 0.0)


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
        self._repeat_weights = (
            weights.repeat_main_protein,
            weights.repeat_main_carb,
            weights.repeat_dish_type,
            weights.repeat_cuisine,
        )
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
            skipped_terms=_SKIPPED_TERMS,
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
            TermScore(Term.PANTRY_FIT, self._weights.pantry_fit * facts.pantry_fit),
            TermScore(
                Term.FAVOURITE, self._weights.favourite if facts.recipe_id in self._ctx.favourite_recipe_ids else 0.0
            ),
            TermScore(Term.LIKED_CUISINE, self._liked_cuisine(facts)),
            TermScore(Term.LOVED_INGREDIENT, self._weights.loved_ingredient * len(facts.loved_ingredients)),
            TermScore(Term.AVOIDED_CUISINE, self._avoided_cuisine(facts)),
            TermScore(Term.FEEDBACK_CHIP, self._feedback_chips(facts)),
            TermScore(Term.RECENCY, self._recency(facts)),
            TermScore(Term.RATING, self._rating(facts)),
            TermScore(Term.WHOLE_FOOD, self._whole_food(facts)),
        )

    def _liked_cuisine(self, facts: CandidateRecipe) -> float:
        return self._weights.liked_cuisine if facts.attributes.cuisine in self._ctx.liked_cuisines else 0.0

    def _avoided_cuisine(self, facts: CandidateRecipe) -> float:
        return self._weights.avoided_cuisine if facts.attributes.cuisine in self._ctx.avoided_cuisines else 0.0

    def _feedback_chips(self, facts: CandidateRecipe) -> float:
        satisfied = sum(
            1
            for chip in self._ctx.chips
            if (predicate := self._ctx.chip_predicates.get(chip)) is not None and predicate.matches(facts.attributes)
        )
        return self._weights.feedback_chip * satisfied

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
        return points


def _require_known(recipe_ids: Sequence[str], ctx: ScoringContext) -> None:
    """Refuse a plan or a metric naming recipes the caller did not describe: the ids and the facts disagree."""
    missing = sorted(set(recipe_ids) - ctx.recipes.keys())
    if missing:
        raise UnknownRecipeIds(missing)


def _tie_break_ranks(pool: Sequence[str], seed: int) -> dict[str, float]:
    """One random rank per recipe, so a tie is broken by the seed rather than by the order ids arrived in."""
    rng = random.Random(seed)  # noqa: S311 - seeded on purpose: the same Generate seed must plan the same week
    return {recipe_id: rng.random() for recipe_id in pool}


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
                    return tuple(best)
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
