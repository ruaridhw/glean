"""The planner's system-1 tools: `score_meal_plan` and `create_candidate_meal_plans` (spec 6.2, "Tools").

Seams: the two tools are what the agent graph (V7), the evals (6.6) and the MCP server (T1) call, so these tests
pin each row of the scorer-weights table, the exemptions it names, and the guarantees of plan generation. They run
on synthetic attributes only: no corpus, no store, no model.
"""

from __future__ import annotations

import random
import time

import pytest

import glean.meal_plan.tools as tools_module
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
    _greedy_plan,
    _Scorer,
    chosen_vs_best_ratio,
    create_candidate_meal_plans,
    distinct_main_carbs,
    distinct_main_proteins,
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
    assert weights.repeat_main_protein == -5.0
    assert weights.repeat_main_carb == -2.0
    assert weights.repeat_dish_type == -2.0
    assert weights.repeat_cuisine == -1.0
    assert weights.whole_food == 0.5
    assert weights.healthier_multiplier == 2.0
    assert weights.lighter == -1.0
    assert weights.lighter_reference_kcal == 672
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


def test_whole_food_earns_its_half_point_only_when_the_recipe_is_whole() -> None:
    ctx = context(
        candidate("whole", whole_food=WholeFood.WHOLE),
        candidate("mixed", whole_food=WholeFood.MIXED),
        candidate("processed", whole_food=WholeFood.PROCESSED),
        candidate("unknown"),
    )
    assert score(["whole"], ctx).points(Term.WHOLE_FOOD) == 0.5
    assert score(["mixed"], ctx).points(Term.WHOLE_FOOD) == 0.0
    assert score(["processed"], ctx).points(Term.WHOLE_FOOD) == 0.0
    assert score(["unknown"], ctx).points(Term.WHOLE_FOOD) == 0.0


def test_the_healthier_chip_doubles_whole_food() -> None:
    ctx = context(candidate("a", whole_food=WholeFood.WHOLE), chips=frozenset({"healthier"}))
    assert score(["a"], ctx).points(Term.WHOLE_FOOD) == 1.0
    assert score(["a"], context(candidate("a", whole_food=WholeFood.WHOLE))).points(Term.WHOLE_FOOD) == 0.5


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


def test_repeated_main_proteins_cost_five_for_every_extra() -> None:
    ctx = context(
        candidate("one", main_protein=MainProtein.CHICKEN),
        candidate("two", main_protein=MainProtein.CHICKEN),
        candidate("three", main_protein=MainProtein.CHICKEN),
    )
    plan = score(["one", "two", "three"], ctx)
    assert plan.points(Term.REPEAT_MAIN_PROTEIN) == -10.0
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


def test_repeated_unknown_attributes_are_exempt() -> None:
    ctx = context(
        candidate("a"),
        candidate("b"),
    )
    plan = score(["a", "b"], ctx)
    assert plan.points(Term.REPEAT_MAIN_CARB) == 0.0
    assert plan.points(Term.REPEAT_DISH_TYPE) == 0.0
    assert plan.points(Term.REPEAT_CUISINE) == 0.0


def test_a_repeated_none_carb_still_costs_its_row() -> None:
    # The spec's carb row carries no exemption: a dish with no carb is still a repeated carb choice, and a
    # gluten-free week of four `none`-carb dinners is exactly the week the carb gate exists to catch.
    ctx = context(candidate("a", main_carb=MainCarb.NONE), candidate("b", main_carb=MainCarb.NONE))
    plan = score(["a", "b"], ctx)
    assert plan.points(Term.REPEAT_MAIN_CARB) == -2.0
    (penalty,) = [penalty for penalty in plan.penalties if penalty.term is Term.REPEAT_MAIN_CARB]
    assert penalty.detail == "none"


# --- plan penalties: the lighter chip and protein targets -------------------------------------------------


def test_the_lighter_chip_costs_a_point_per_recipe_above_the_fixed_reference() -> None:
    ctx = context(
        candidate("light", calories=400, main_protein=MainProtein.NONE),
        candidate("at-the-line", calories=672, main_protein=MainProtein.NONE),
        candidate("heavy", calories=900, main_protein=MainProtein.NONE),
        chips=frozenset({LIGHTER_CHIP}),
    )
    plan = score(["light", "at-the-line", "heavy"], ctx)
    assert plan.points(Term.LIGHTER) == -1.0
    (penalty,) = [penalty for penalty in plan.penalties if penalty.term is Term.LIGHTER]
    assert penalty.recipe_ids == ("heavy",)
    assert "672" in penalty.detail


def test_a_light_week_is_not_measured_against_its_own_median() -> None:
    # The reference does not move with the week. Under a week-median rule the heaviest of these three would be
    # penalised, which is how a plan made itself look light by choosing only light recipes.
    ctx = context(
        candidate("light", calories=400, main_protein=MainProtein.NONE),
        candidate("middle", calories=500, main_protein=MainProtein.NONE),
        candidate("heavier", calories=600, main_protein=MainProtein.NONE),
        chips=frozenset({LIGHTER_CHIP}),
    )
    assert score(["light", "middle", "heavier"], ctx).points(Term.LIGHTER) == 0.0


def test_a_recipe_with_unknown_calories_is_never_under_the_lighter_reference() -> None:
    # An unknown figure must not make a recipe look lighter than one whose figure is known, or a plan can buy
    # its way past the chip by picking recipes nobody measured.
    ctx = context(
        candidate("light", calories=400, main_protein=MainProtein.NONE),
        candidate("unmeasured", main_protein=MainProtein.NONE),
        chips=frozenset({LIGHTER_CHIP}),
    )
    plan = score(["light", "unmeasured"], ctx)
    (penalty,) = [penalty for penalty in plan.penalties if penalty.term is Term.LIGHTER]
    assert penalty.recipe_ids == ("unmeasured",)
    assert plan.points(Term.LIGHTER) == -1.0


def test_a_week_with_no_stated_calories_counts_every_recipe_as_above() -> None:
    ctx = context(
        candidate("unmeasured", main_protein=MainProtein.NONE),
        candidate("also-unmeasured", main_protein=MainProtein.NONE),
        chips=frozenset({LIGHTER_CHIP}),
    )
    plan = score(["unmeasured", "also-unmeasured"], ctx)
    assert plan.points(Term.LIGHTER) == -2.0


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
    assert plan.total == -3.5
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


# --- create_candidate_meal_plans: k distinct balanced weeks -----------------------------------------------


def week(*, n: int = 3, pool: int = 6):
    """A pool wide enough for a balanced week: cycling proteins, carbs, cuisines and dish types."""
    proteins = [MainProtein.CHICKEN, MainProtein.FISH, MainProtein.BEEF, MainProtein.BEANS_AND_PULSES]
    carbs = [MainCarb.RICE, MainCarb.PASTA, MainCarb.POTATO, MainCarb.NONE]
    cuisines = [Cuisine.ITALIAN, Cuisine.INDIAN, Cuisine.THAI, Cuisine.MEXICAN]
    dish_types = [DishType.CURRY, DishType.SALAD_OR_BOWL, DishType.PAN_OR_GRILL, DishType.SOUP_OR_STEW]
    return context(
        *(
            candidate(
                f"recipe-{index}",
                main_protein=proteins[index % len(proteins)],
                main_carb=carbs[index % len(carbs)],
                cuisine=cuisines[index % len(cuisines)],
                dish_type=dish_types[index % len(dish_types)],
                pantry_fit=float(pool - index),
            )
            for index in range(pool)
        )
    )


def test_two_distinct_plans_of_n_recipes() -> None:
    plans = create_candidate_meal_plans(
        ["recipe-0", "recipe-1", "recipe-2", "recipe-3", "recipe-4", "recipe-5"], 3, week()
    )
    assert len(plans) == 2
    for plan in plans:
        assert len(plan.recipes) == 3
        assert len(set(plan.recipe_ids)) == 3
    assert set(plans[0].recipe_ids) != set(plans[1].recipe_ids)


def test_the_plans_are_ordered_best_first() -> None:
    ids = [f"recipe-{index}" for index in range(6)]
    plans = create_candidate_meal_plans(ids, 3, week())
    assert plans[0].total >= plans[1].total


def test_a_plan_scores_exactly_what_scoring_its_ids_scores() -> None:
    ctx = week()
    plans = create_candidate_meal_plans([f"recipe-{index}" for index in range(6)], 3, ctx)
    for plan in plans:
        assert plan.total == score_meal_plan(plan.recipe_ids, ctx).total


def test_the_same_seed_gives_the_same_plans() -> None:
    ids = [f"recipe-{index}" for index in range(6)]
    first = create_candidate_meal_plans(ids, 3, week(), seed=7)
    again = create_candidate_meal_plans(ids, 3, week(), seed=7)
    assert [plan.recipe_ids for plan in first] == [plan.recipe_ids for plan in again]


def test_a_different_seed_breaks_the_ties_differently() -> None:
    # Every candidate scores the same, so the seed's tie-break is the only thing choosing between them.
    ctx = context(*(candidate(f"recipe-{index}") for index in range(6)))
    ids = [f"recipe-{index}" for index in range(6)]
    assert (
        create_candidate_meal_plans(ids, 3, ctx, seed=0)[0].recipe_ids
        != create_candidate_meal_plans(ids, 3, ctx, seed=1)[0].recipe_ids
    )


def test_a_balanced_week_does_not_put_two_chickens_in_it() -> None:
    ctx = context(
        candidate("chicken-one", main_protein=MainProtein.CHICKEN, main_carb=MainCarb.RICE, pantry_fit=3.0),
        candidate("chicken-two", main_protein=MainProtein.CHICKEN, main_carb=MainCarb.PASTA, pantry_fit=2.9),
        candidate("fish", main_protein=MainProtein.FISH, main_carb=MainCarb.POTATO, pantry_fit=2.0),
        candidate("lamb", main_protein=MainProtein.LAMB, main_carb=MainCarb.NONE, pantry_fit=1.9),
    )
    (best,) = create_candidate_meal_plans(["chicken-one", "chicken-two", "fish", "lamb"], 2, ctx, k=1)
    proteins = [ctx.recipes[recipe_id].attributes.main_protein for recipe_id in best.recipe_ids]
    assert proteins.count(MainProtein.CHICKEN) == 1


def test_local_search_improves_on_the_greedy_fill() -> None:
    # Greedy's third slot takes a second fish, which makes its second slot the wrong partner: the rice repeat it
    # brought is still there, and swapping it for the stronger beef-and-pasta week only pays once the second fish
    # is already in. Greedy never looks back, so the local search's one swap is what earns the extra 1.3.
    ctx = context(
        candidate(
            "curry",
            main_protein=MainProtein.FISH,
            main_carb=MainCarb.PASTA,
            dish_type=DishType.CURRY,
            cuisine=Cuisine.THAI,
            pantry_fit=3.5,
        ),
        candidate(
            "thai-beef",
            main_protein=MainProtein.BEEF,
            main_carb=MainCarb.RICE,
            dish_type=DishType.SALAD_OR_BOWL,
            cuisine=Cuisine.THAI,
            pantry_fit=5.6,
        ),
        candidate(
            "thai-fish",
            main_protein=MainProtein.FISH,
            main_carb=MainCarb.RICE,
            dish_type=DishType.SALAD_OR_BOWL,
            cuisine=Cuisine.THAI,
            pantry_fit=7.1,
        ),
        candidate(
            "italian-fish",
            main_protein=MainProtein.FISH,
            main_carb=MainCarb.PASTA,
            dish_type=DishType.CURRY,
            cuisine=Cuisine.ITALIAN,
            pantry_fit=10.0,
        ),
        candidate(
            "italian-beef",
            main_protein=MainProtein.BEEF,
            main_carb=MainCarb.PASTA,
            dish_type=DishType.SALAD_OR_BOWL,
            cuisine=Cuisine.ITALIAN,
            pantry_fit=6.9,
        ),
    )
    ids = ["curry", "thai-beef", "thai-fish", "italian-fish", "italian-beef"]
    greedy = _greedy_plan(_Scorer(ctx, ScorerWeights()), ids, 3, dict.fromkeys(ids, 0.0))
    assert greedy == ["italian-fish", "thai-beef", "thai-fish"]
    (best,) = create_candidate_meal_plans(ids, 3, ctx, k=1)
    assert set(best.recipe_ids) == {"italian-fish", "italian-beef", "thai-fish"}
    assert best.total > score_meal_plan(greedy, ctx).total


def test_a_pool_the_size_of_the_week_can_only_yield_one_plan() -> None:
    ctx = week(pool=3)
    plans = create_candidate_meal_plans(["recipe-0", "recipe-1", "recipe-2"], 3, ctx)
    assert len(plans) == 1


def test_a_pool_smaller_than_the_week_plans_every_recipe() -> None:
    ctx = week(pool=4)
    (plan,) = create_candidate_meal_plans(["recipe-0", "recipe-1", "recipe-2", "recipe-3"], 7, ctx, k=1)
    assert sorted(plan.recipe_ids) == ["recipe-0", "recipe-1", "recipe-2", "recipe-3"]


@pytest.mark.parametrize(("ids", "n", "k"), [([], 3, 2), (["recipe-0"], 0, 2), (["recipe-0"], 3, 0)])
def test_a_week_that_cannot_be_planned_yields_no_plans(ids, n, k) -> None:
    ctx = week(pool=4)
    assert create_candidate_meal_plans(ids, n, ctx, k=k) == ()


def test_generation_rejects_an_id_the_context_does_not_describe() -> None:
    with pytest.raises(UnknownRecipeIds, match="ghost"):
        create_candidate_meal_plans(["recipe-0", "ghost"], 2, week())


def test_the_swap_search_stops_at_its_evaluation_budget(monkeypatch) -> None:
    # The budget is what bounds the tool's time on a pool with a neighbourhood far larger than a week needs.
    monkeypatch.setattr(tools_module, "_MAX_SWAP_EVALUATIONS", 0)
    ctx = week(pool=6)
    plans = create_candidate_meal_plans([f"recipe-{index}" for index in range(6)], 3, ctx)
    assert len(plans) == 2
    assert all(len(plan.recipes) == 3 for plan in plans)


def test_generating_two_weeks_of_seven_is_well_under_a_hundred_milliseconds() -> None:
    pool = [f"recipe-{index}" for index in range(120)]
    ctx = context(
        *(
            candidate(
                recipe_id,
                main_protein=list(MainProtein)[index % len(MainProtein)],
                main_carb=list(MainCarb)[index % len(MainCarb)],
                dish_type=list(DishType)[index % len(DishType)],
                cuisine=list(Cuisine)[index % len(Cuisine)],
                pantry_fit=float(120 - index) / 40,
            )
            for index, recipe_id in enumerate(pool)
        )
    )
    create_candidate_meal_plans(pool, 7, ctx, seed=0)  # warm the caches the way the graph will have them warm
    started = time.perf_counter()
    plans = create_candidate_meal_plans(pool, 7, ctx, seed=0)
    elapsed = time.perf_counter() - started
    assert len(plans) == 2
    assert elapsed < 0.1, f"two weeks of seven from 120 candidates took {elapsed * 1000:.1f} ms"


def test_the_searchs_penalty_total_is_the_breakdowns_penalty_total() -> None:
    # The search adds the penalties up arithmetically so it can afford to try thousands of swaps; this pins that
    # the number it optimises is the number the breakdown reports.
    ctx = context(
        candidate("a", main_protein=MainProtein.CHICKEN, cuisine=Cuisine.THAI, calories=400),
        candidate("b", main_protein=MainProtein.CHICKEN, cuisine=Cuisine.THAI, calories=900),
        candidate("c", main_protein=MainProtein.FISH, cuisine=Cuisine.THAI, calories=None),
        chips=frozenset({LIGHTER_CHIP, "healthier"}),
        protein_targets=(ProteinTarget(MainProtein.FISH, min_per_week=2),),
    )
    scorer = _Scorer(ctx, ScorerWeights())
    plan = scorer.score(["a", "b", "c"])
    assert scorer._penalty_points(["a", "b", "c"]) == sum(penalty.points for penalty in plan.penalties)
    assert plan.points(Term.LIGHTER) < 0
    assert plan.points(Term.PROTEIN_TARGET) < 0


def random_context(rng: random.Random, *, pool_size: int) -> tuple[list[str], ScoringContext]:
    """A pool drawn the way the eval's households draw one: every G1 value, thin nutrition, some history."""
    ids = [f"r{index}" for index in range(pool_size)]
    recipes = {
        recipe_id: candidate(
            recipe_id,
            main_protein=rng.choice(list(MainProtein)),
            main_carb=rng.choice(list(MainCarb)),
            dish_type=rng.choice(list(DishType)),
            cuisine=rng.choice(list(Cuisine)),
            whole_food=rng.choice(list(WholeFood)),
            calories=rng.choice([None, 300.0, 500.0, 700.0, 900.0]),
            pantry_fit=rng.uniform(0.0, 3.0),
            days_since_cooked=rng.choice([None, 50, 70]),
        )
        for recipe_id in ids
    }
    chips = frozenset({LIGHTER_CHIP}) if rng.random() < 0.5 else frozenset()
    ctx = ScoringContext(
        recipes=recipes, chips=chips, protein_targets=(ProteinTarget(MainProtein.FISH, min_per_week=2),)
    )
    return ids, ctx


def test_the_plans_come_back_best_first_on_any_pool() -> None:
    # Each plan after the first is a different local optimum (its pool blocks one recipe), so generation order is
    # not score order: the caller reads plans[0] as the scorer's best, and the eval's drift gate depends on it.
    rng = random.Random(20261024)
    for trial in range(60):
        ids, ctx = random_context(rng, pool_size=rng.choice([8, 10, 12]))
        for k in (2, 3):
            plans = create_candidate_meal_plans(ids, rng.choice([4, 5]), ctx, k=k, seed=trial)
            totals = [plan.total for plan in plans]
            assert totals == sorted(totals, reverse=True), f"trial {trial} k={k}: {totals}"


# --- variety metrics for the eval (spec 6.6) --------------------------------------------------------------


def test_distinct_main_proteins_exclude_none_and_unsure() -> None:
    ctx = context(
        candidate("chicken", main_protein=MainProtein.CHICKEN),
        candidate("chicken-again", main_protein=MainProtein.CHICKEN),
        candidate("fish", main_protein=MainProtein.FISH),
        candidate("vegetable", main_protein=MainProtein.NONE),
        candidate("unknown", main_protein=MainProtein.UNSURE),
    )
    assert distinct_main_proteins(["chicken", "chicken-again", "fish", "vegetable", "unknown"], ctx) == 2


def test_distinct_main_carbs_exclude_none_and_unsure() -> None:
    ctx = context(
        candidate("rice", main_carb=MainCarb.RICE),
        candidate("pasta", main_carb=MainCarb.PASTA),
        candidate("pasta-again", main_carb=MainCarb.PASTA),
        candidate("no-carb", main_carb=MainCarb.NONE),
        candidate("unknown"),
    )
    assert distinct_main_carbs(["rice", "pasta", "pasta-again", "no-carb", "unknown"], ctx) == 2


def test_variety_metrics_reject_an_id_the_context_does_not_describe() -> None:
    with pytest.raises(UnknownRecipeIds, match="ghost"):
        distinct_main_proteins(["ghost"], context(candidate("a")))


def test_the_chosen_plan_is_compared_with_the_best_as_a_ratio() -> None:
    ctx = context(candidate("a", pantry_fit=10.0), candidate("b", pantry_fit=6.0))
    best = score(["a", "b"], ctx)
    assert chosen_vs_best_ratio(score(["a", "b"], ctx), best) == 1.0
    assert chosen_vs_best_ratio(score(["a", "b"], ctx), best) > 0.85
    assert chosen_vs_best_ratio(score(["b"], ctx), best) == pytest.approx(0.375)
    assert chosen_vs_best_ratio(score(["b"], ctx), best) < 0.85


def test_the_ratio_holds_up_when_the_scores_are_negative() -> None:
    ctx = context(candidate("a", rating=Rating.DOWN), candidate("b", rating=Rating.DOWN))
    best = score(["a"], ctx)
    assert chosen_vs_best_ratio(score(["a"], ctx), best) == 1.0
    assert chosen_vs_best_ratio(score(["b"], ctx), best) == 1.0
    far_worse = score(["a", "b"], ctx)
    assert chosen_vs_best_ratio(far_worse, best) >= 0.0
    assert chosen_vs_best_ratio(far_worse, best) < 0.85


def test_a_minutes_predicate_takes_exactly_one_number() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        Predicate(PredicateField.ACTIVE_TIME, PredicateOp.LTE, ("30", "45"))
    with pytest.raises(ValueError, match="exactly one"):
        Predicate(PredicateField.ACTIVE_TIME, PredicateOp.GTE, ("quick",))


def test_the_alternative_week_keeps_the_strongest_recipe_and_differs_by_one_swap() -> None:
    # The alternative exists to be swapped in, so it must not give up the week's best recipe: an alternative the
    # scorer itself rates well short of the best would trip the eval's drift gate on the scorer's own output.
    ctx = context(
        candidate(
            "dominant",
            main_protein=MainProtein.CHICKEN,
            main_carb=MainCarb.RICE,
            dish_type=DishType.CURRY,
            cuisine=Cuisine.ITALIAN,
            pantry_fit=9.0,
        ),
        candidate(
            "fish",
            main_protein=MainProtein.FISH,
            main_carb=MainCarb.POTATO,
            dish_type=DishType.SALAD_OR_BOWL,
            cuisine=Cuisine.THAI,
            pantry_fit=2.0,
        ),
        candidate(
            "beef",
            main_protein=MainProtein.BEEF,
            main_carb=MainCarb.NONE,
            dish_type=DishType.PAN_OR_GRILL,
            cuisine=Cuisine.MEXICAN,
            pantry_fit=1.9,
        ),
        candidate(
            "lamb",
            main_protein=MainProtein.LAMB,
            main_carb=MainCarb.PASTA,
            dish_type=DishType.SOUP_OR_STEW,
            cuisine=Cuisine.INDIAN,
            pantry_fit=1.8,
        ),
    )
    ids = ["dominant", "fish", "beef", "lamb"]
    best, alternative = create_candidate_meal_plans(ids, 2, ctx)
    assert "dominant" in best.recipe_ids
    assert "dominant" in alternative.recipe_ids
    assert len(set(best.recipe_ids) ^ set(alternative.recipe_ids)) == 2
    assert chosen_vs_best_ratio(alternative, best) > 0.85
