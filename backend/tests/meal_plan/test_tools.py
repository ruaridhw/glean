"""The planner's system-1 tools: `score_meal_plan` and `create_candidate_meal_plans` (spec 6.2, "Tools").

Seams: the two tools are what the agent graph (V7), the evals (6.6) and the MCP server (T1) call, so these tests
pin each row of the scorer-weights table, the exemptions it names, and the guarantees of plan generation. They run
on synthetic attributes only: no corpus, no store, no model.
"""

from __future__ import annotations

import pytest

from glean.meal_plan.tools import (
    LIGHTER_CHIP,
    CandidateRecipe,
    Predicate,
    PredicateField,
    PredicateOp,
    ProteinTarget,
    Rating,
    ScorerWeights,
    ScoringContext,
    Term,
    UnknownRecipeIds,
    score_meal_plan,
)
from glean.recipes.attributes import (
    ActiveTimeBucket,
    Cuisine,
    DishType,
    MainCarb,
    MainProtein,
    RecipeAttributes,
    WholeFood,
)


def attributes(
    *,
    main_protein: MainProtein = MainProtein.UNSURE,
    main_carb: MainCarb = MainCarb.UNSURE,
    dish_type: DishType = DishType.UNSURE,
    cuisine: Cuisine = Cuisine.UNSURE,
    whole_food: WholeFood = WholeFood.UNSURE,
) -> RecipeAttributes:
    return RecipeAttributes(
        main_protein=main_protein,
        main_carb=main_carb,
        dish_type=dish_type,
        cuisine=cuisine,
        whole_food=whole_food,
    )


def candidate(
    recipe_id: str,
    *,
    calories: float | None = None,
    pantry_fit: float = 0.0,
    days_since_cooked: int | None = None,
    rating: Rating | None = None,
    floor_relaxed: bool = False,
    loved_ingredients: tuple[str, ...] = (),
    **attribute_values: object,
) -> CandidateRecipe:
    return CandidateRecipe(
        recipe_id=recipe_id,
        attributes=attributes(**attribute_values),  # type: ignore[arg-type]
        calories_per_serving=calories,
        pantry_fit=pantry_fit,
        days_since_cooked=days_since_cooked,
        rating=rating,
        offered_after_floor_relaxed=floor_relaxed,
        loved_ingredients=loved_ingredients,
    )


def context(*recipes: CandidateRecipe, **inputs: object) -> ScoringContext:
    return ScoringContext(recipes={recipe.recipe_id: recipe for recipe in recipes}, **inputs)  # type: ignore[arg-type]


def score(recipe_ids: list[str], ctx=None, weights: ScorerWeights | None = None):
    return score_meal_plan(recipe_ids, ctx if ctx is not None else context(), weights)  # type: ignore[arg-type]


# --- the weights are the table's defaults, in one place ---------------------------------------------------


def test_the_weights_are_the_scorer_table_defaults() -> None:
    weights = ScorerWeights()
    assert weights.pantry_fit == 1.0
    assert weights.favourite == 2.0
    assert weights.liked_cuisine == 1.0
    assert weights.loved_ingredient == 1.0
    assert weights.avoided_cuisine == -2.0
    assert weights.feedback_chip == 2.0
    assert weights.recency_relaxed == -8.0
    assert weights.recency_weeks_7_to_9 == -3.0
    assert weights.recency_weeks_10_to_12 == -1.0
    assert weights.rating_down == -8.0
    assert weights.rating_up_after_six_weeks == 1.0
    assert weights.repeat_main_protein == -3.0
    assert weights.repeat_main_carb == -2.0
    assert weights.repeat_dish_type == -2.0
    assert weights.repeat_cuisine == -1.0
    assert weights.whole_food == 1.0
    assert weights.healthier_multiplier == 2.0
    assert weights.lighter == -1.0
    assert weights.protein_target_miss == -4.0


def test_a_scorer_weights_override_is_the_one_the_plan_is_scored_with() -> None:
    ctx = context(candidate("a", pantry_fit=2.0))
    assert score(["a"], ctx, ScorerWeights(pantry_fit=0.5)).points(Term.PANTRY_FIT) == 1.0


# --- per-recipe terms, one at a time ----------------------------------------------------------------------


def test_pantry_fit_is_the_urgency_weighted_sum_the_caller_scaled() -> None:
    ctx = context(candidate("a", pantry_fit=2.5), candidate("b"))
    plan = score(["a", "b"], ctx)
    assert plan.points(Term.PANTRY_FIT) == 2.5
    assert plan.total == 2.5


def test_a_favourite_meal_earns_two() -> None:
    ctx = context(candidate("a"), candidate("b"), favourite_recipe_ids=frozenset({"a"}))
    assert score(["a", "b"], ctx).points(Term.FAVOURITE) == 2.0
    assert score(["a", "b"], ctx).total == 2.0


def test_a_liked_cuisine_and_a_loved_ingredient_earn_one_each() -> None:
    ctx = context(
        candidate("a", cuisine=Cuisine.ITALIAN, loved_ingredients=("basil", "parmesan")),
        liked_cuisines=frozenset({Cuisine.ITALIAN}),
    )
    plan = score(["a"], ctx)
    assert plan.points(Term.LIKED_CUISINE) == 1.0
    assert plan.points(Term.LOVED_INGREDIENT) == 2.0
    assert plan.total == 3.0


def test_an_avoided_cuisine_loses_two() -> None:
    ctx = context(candidate("a", cuisine=Cuisine.THAI), avoided_cuisines=frozenset({Cuisine.THAI}))
    plan = score(["a"], ctx)
    assert plan.points(Term.AVOIDED_CUISINE) == -2.0
    assert plan.total == -2.0


def test_each_satisfied_feedback_chip_earns_two() -> None:
    fish = candidate("a", main_protein=MainProtein.FISH)
    beef = candidate("b", main_protein=MainProtein.BEEF)
    ctx = context(
        fish,
        beef,
        chips=frozenset({"something new", "lighter"}),
        chip_predicates={
            "something new": Predicate(PredicateField.MAIN_PROTEIN, PredicateOp.IN, ("fish", "seafood")),
            "lighter": Predicate(PredicateField.MAIN_PROTEIN, PredicateOp.IN, ("vegetarian_other",)),
        },
    )
    assert score(["a"], ctx).points(Term.FEEDBACK_CHIP) == 2.0  # one of the two chips is satisfied
    assert score(["b"], ctx).points(Term.FEEDBACK_CHIP) == 0.0


def test_a_chip_with_no_predicate_yet_earns_nothing() -> None:
    ctx = context(candidate("a"), chips=frozenset({"comfort food"}))
    assert score(["a"], ctx).points(Term.FEEDBACK_CHIP) == 0.0


def test_whole_food_earns_one_only_when_the_recipe_is_whole() -> None:
    ctx = context(
        candidate("whole", whole_food=WholeFood.WHOLE),
        candidate("mixed", whole_food=WholeFood.MIXED),
        candidate("processed", whole_food=WholeFood.PROCESSED),
        candidate("unknown"),
    )
    assert score(["whole"], ctx).points(Term.WHOLE_FOOD) == 1.0
    assert score(["mixed"], ctx).points(Term.WHOLE_FOOD) == 0.0
    assert score(["processed"], ctx).points(Term.WHOLE_FOOD) == 0.0
    assert score(["unknown"], ctx).points(Term.WHOLE_FOOD) == 0.0


def test_the_healthier_chip_doubles_whole_food() -> None:
    ctx = context(candidate("a", whole_food=WholeFood.WHOLE), chips=frozenset({"healthier"}))
    assert score(["a"], ctx).points(Term.WHOLE_FOOD) == 2.0
    assert score(["a"], context(candidate("a", whole_food=WholeFood.WHOLE))).points(Term.WHOLE_FOOD) == 1.0


# --- recency and ratings ----------------------------------------------------------------------------------


def test_recency_penalises_weeks_seven_to_twelve_and_nothing_older() -> None:
    ctx = context(
        candidate("week7", days_since_cooked=43),
        candidate("week9", days_since_cooked=63),
        candidate("week10", days_since_cooked=64),
        candidate("week12", days_since_cooked=84),
        candidate("older", days_since_cooked=85),
        candidate("never", days_since_cooked=None),
    )
    assert score(["week7"], ctx).points(Term.RECENCY) == -3.0
    assert score(["week9"], ctx).points(Term.RECENCY) == -3.0
    assert score(["week10"], ctx).points(Term.RECENCY) == -1.0
    assert score(["week12"], ctx).points(Term.RECENCY) == -1.0
    assert score(["older"], ctx).points(Term.RECENCY) == 0.0
    assert score(["never"], ctx).points(Term.RECENCY) == 0.0


def test_a_recipe_cooked_in_the_last_six_weeks_is_penalised_only_when_the_floor_relaxed() -> None:
    ctx = context(
        candidate("recent", days_since_cooked=10), candidate("relaxed", days_since_cooked=42, floor_relaxed=True)
    )
    assert score(["recent"], ctx).points(Term.RECENCY) == 0.0
    assert score(["relaxed"], ctx).points(Term.RECENCY) == -8.0


def test_a_thumb_down_costs_eight_whatever_its_age() -> None:
    ctx = context(
        candidate("last_night", days_since_cooked=1, rating=Rating.DOWN),
        candidate("last_year", days_since_cooked=400, rating=Rating.DOWN),
    )
    assert score(["last_night"], ctx).points(Term.RATING) == -8.0
    assert score(["last_year"], ctx).points(Term.RATING) == -8.0


def test_a_thumb_up_earns_one_only_once_it_is_past_six_weeks() -> None:
    ctx = context(
        candidate("recent", days_since_cooked=42, rating=Rating.UP),
        candidate("past", days_since_cooked=43, rating=Rating.UP),
        candidate("unaged", days_since_cooked=None, rating=Rating.UP),
    )
    assert score(["recent"], ctx).points(Term.RATING) == 0.0
    assert score(["past"], ctx).points(Term.RATING) == 1.0
    assert score(["unaged"], ctx).points(Term.RATING) == 0.0


def test_an_unrated_recipe_earns_nothing_from_ratings() -> None:
    assert score(["a"], context(candidate("a"))).points(Term.RATING) == 0.0


# --- plan penalties: repeats ------------------------------------------------------------------------------


def test_repeated_main_proteins_cost_three_for_every_extra() -> None:
    ctx = context(
        candidate("one", main_protein=MainProtein.CHICKEN),
        candidate("two", main_protein=MainProtein.CHICKEN),
        candidate("three", main_protein=MainProtein.CHICKEN),
    )
    plan = score(["one", "two", "three"], ctx)
    assert plan.points(Term.REPEAT_MAIN_PROTEIN) == -6.0
    (penalty,) = [penalty for penalty in plan.penalties if penalty.term is Term.REPEAT_MAIN_PROTEIN]
    assert penalty.recipe_ids == ("two", "three")
    assert penalty.detail == "chicken"


def test_a_repeated_protein_is_exempt_when_it_is_none_or_unsure() -> None:
    ctx = context(
        candidate("veg", main_protein=MainProtein.NONE),
        candidate("veg2", main_protein=MainProtein.NONE),
        candidate("unknown", main_protein=MainProtein.UNSURE),
        candidate("unknown2", main_protein=MainProtein.UNSURE),
    )
    assert score(["veg", "veg2", "unknown", "unknown2"], ctx).points(Term.REPEAT_MAIN_PROTEIN) == 0.0


def test_repeated_carbs_dish_types_and_cuisines_cost_their_own_row() -> None:
    ctx = context(
        candidate("a", main_carb=MainCarb.RICE, dish_type=DishType.CURRY, cuisine=Cuisine.INDIAN),
        candidate("b", main_carb=MainCarb.RICE, dish_type=DishType.CURRY, cuisine=Cuisine.INDIAN),
    )
    plan = score(["a", "b"], ctx)
    assert plan.points(Term.REPEAT_MAIN_CARB) == -2.0
    assert plan.points(Term.REPEAT_DISH_TYPE) == -2.0
    assert plan.points(Term.REPEAT_CUISINE) == -1.0
    assert plan.total == -5.0


@pytest.mark.parametrize(
    ("main_carb", "dish_type", "cuisine"),
    [(MainCarb.NONE, DishType.UNSURE, Cuisine.UNSURE), (MainCarb.UNSURE, DishType.UNSURE, Cuisine.UNSURE)],
)
def test_repeated_carbs_and_unknown_attributes_are_exempt(main_carb, dish_type, cuisine) -> None:
    ctx = context(
        candidate("a", main_carb=main_carb, dish_type=dish_type, cuisine=cuisine),
        candidate("b", main_carb=main_carb, dish_type=dish_type, cuisine=cuisine),
    )
    plan = score(["a", "b"], ctx)
    assert plan.points(Term.REPEAT_MAIN_CARB) == 0.0
    assert plan.points(Term.REPEAT_DISH_TYPE) == 0.0
    assert plan.points(Term.REPEAT_CUISINE) == 0.0


# --- plan penalties: the lighter chip and protein targets -------------------------------------------------


def test_the_lighter_chip_costs_a_point_per_recipe_above_the_weeks_median() -> None:
    ctx = context(
        candidate("light", calories=400, main_protein=MainProtein.NONE),
        candidate("middle", calories=500, main_protein=MainProtein.NONE),
        candidate("heavy", calories=600, main_protein=MainProtein.NONE),
        chips=frozenset({LIGHTER_CHIP}),
    )
    plan = score(["light", "middle", "heavy"], ctx)
    assert plan.points(Term.LIGHTER) == -1.0
    (penalty,) = [penalty for penalty in plan.penalties if penalty.term is Term.LIGHTER]
    assert penalty.recipe_ids == ("heavy",)


def test_the_lighter_chip_only_counts_where_nutrition_exists() -> None:
    ctx = context(
        candidate("known", calories=900, main_protein=MainProtein.NONE),
        candidate("unknown", main_protein=MainProtein.NONE),
        chips=frozenset({LIGHTER_CHIP}),
    )
    assert score(["known", "unknown"], ctx).points(Term.LIGHTER) == 0.0
    no_nutrition = context(
        candidate("a", main_protein=MainProtein.NONE),
        candidate("b", main_protein=MainProtein.NONE),
        chips=frozenset({LIGHTER_CHIP}),
    )
    assert score(["a", "b"], no_nutrition).points(Term.LIGHTER) == 0.0


def test_the_lighter_term_is_absent_without_the_chip() -> None:
    ctx = context(candidate("light", calories=400), candidate("heavy", calories=600))
    assert score(["light", "heavy"], ctx).points(Term.LIGHTER) == 0.0


def test_a_missing_protein_target_costs_four() -> None:
    ctx = context(
        candidate("beef", main_protein=MainProtein.BEEF),
        protein_targets=(ProteinTarget(MainProtein.FISH, min_per_week=1),),
    )
    plan = score(["beef"], ctx)
    assert plan.points(Term.PROTEIN_TARGET) == -4.0
    with_fish = context(
        candidate("fish", main_protein=MainProtein.FISH),
        protein_targets=(ProteinTarget(MainProtein.FISH, min_per_week=1),),
    )
    assert score(["fish"], with_fish).points(Term.PROTEIN_TARGET) == 0.0


def test_a_target_short_by_two_misses_twice() -> None:
    ctx = context(
        candidate("fish", main_protein=MainProtein.FISH),
        candidate("beef", main_protein=MainProtein.BEEF),
        protein_targets=(ProteinTarget(MainProtein.FISH, min_per_week=3),),
    )
    assert score(["fish", "beef"], ctx).points(Term.PROTEIN_TARGET) == -8.0


def test_a_maximum_target_is_missed_by_every_extra() -> None:
    ctx = context(
        candidate("one", main_protein=MainProtein.PORK),
        candidate("two", main_protein=MainProtein.PORK),
        protein_targets=(ProteinTarget(MainProtein.PORK, max_per_week=1),),
    )
    assert score(["one", "two"], ctx).points(Term.PROTEIN_TARGET) == -4.0


# --- the breakdown ----------------------------------------------------------------------------------------


def test_a_plans_total_is_its_recipe_terms_plus_its_penalties() -> None:
    ctx = context(
        candidate("a", main_protein=MainProtein.CHICKEN, pantry_fit=1.5),
        candidate("b", main_protein=MainProtein.CHICKEN),
    )
    plan = score(["a", "b"], ctx)
    assert sum(recipe.total for recipe in plan.recipes) == 1.5
    assert plan.total == sum(recipe.total for recipe in plan.recipes) + sum(p.points for p in plan.penalties)
    assert plan.total == -1.5
    assert plan.recipe_ids == ("a", "b")


def test_every_recipe_carries_the_terms_that_were_evaluated() -> None:
    plan = score(["a"], context(candidate("a", main_protein=MainProtein.FISH)))
    terms = {term_score.term for term_score in plan.recipes[0].terms}
    assert Term.PANTRY_FIT in terms
    assert Term.RATING in terms
    assert Term.WHOLE_FOOD in terms


def test_a_term_with_no_attribute_in_the_g1_set_is_skipped_with_a_reason() -> None:
    plan = score(["a"], context(candidate("a")))
    (skipped,) = plan.skipped_terms
    assert skipped.term == "hearty_repeat"
    assert "richness" in skipped.reason


def test_a_plan_naming_a_recipe_the_caller_did_not_describe_is_an_error() -> None:
    ctx = context(candidate("a"))
    with pytest.raises(UnknownRecipeIds, match="ghost"):
        score_meal_plan(["a", "ghost"], ctx)


# --- predicates (how a chip is satisfied) -----------------------------------------------------------------


def test_a_predicate_holds_when_the_attribute_is_one_of_its_values() -> None:
    predicate = Predicate(PredicateField.CUISINE, PredicateOp.IN, ("korean", "thai"))
    assert predicate.matches(attributes(cuisine=Cuisine.KOREAN))
    assert not predicate.matches(attributes(cuisine=Cuisine.ITALIAN))
    assert not predicate.matches(attributes())


def test_a_not_in_predicate_holds_for_everything_else() -> None:
    predicate = Predicate(PredicateField.WHOLE_FOOD, PredicateOp.NOT_IN, ("processed",))
    assert predicate.matches(attributes(whole_food=WholeFood.WHOLE))
    assert not predicate.matches(attributes(whole_food=WholeFood.PROCESSED))


def test_a_minutes_predicate_compares_the_active_time_bucket() -> None:
    quick = RecipeAttributes(active_time=ActiveTimeBucket.FROM_15_TO_30)
    slow = RecipeAttributes(active_time=ActiveTimeBucket.FROM_45_TO_60)
    unknown = RecipeAttributes()
    assert Predicate(PredicateField.ACTIVE_TIME, PredicateOp.LTE, ("30",)).matches(quick)
    assert not Predicate(PredicateField.ACTIVE_TIME, PredicateOp.LTE, ("30",)).matches(slow)
    assert not Predicate(PredicateField.ACTIVE_TIME, PredicateOp.LTE, ("30",)).matches(unknown)
    assert Predicate(PredicateField.ACTIVE_TIME, PredicateOp.GTE, ("45",)).matches(slow)


def test_a_minutes_predicate_only_applies_to_active_time() -> None:
    with pytest.raises(ValueError, match="active_time"):
        Predicate(PredicateField.CUISINE, PredicateOp.LTE, ("30",))
