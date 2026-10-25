"""What `prepare` feeds the scorer, and the weeks it makes of it (V6, spec §6.2).

Seams: `balance.facts_from` (the offer as the scorer reads it), `balance.scored_weeks` (the two weeks the model
picks between) and `balance.drift` (how far the pick fell short). Synthetic offers only: no corpus, no model.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from glean.meal_plan.balance import (
    PANTRY_FIT_TOP,
    RecipeFacts,
    drift,
    facts_from,
    scored_weeks,
    scoring_context,
    stated_calories,
)
from glean.meal_plan.candidates import OfferedRecipe
from glean.meal_plan.eligibility import RecipeHistory
from glean.meal_plan.tools import (
    LIGHTER_CHIP,
    Rating,
    ScoringContext,
    distinct_main_proteins,
)
from glean.recipes.attributes import Cuisine, DishType, MainCarb, MainProtein, RecipeAttributes, WholeFood
from glean.recipes.search_index import RecipeSummary
from glean.recipes.stored import StoredNutrition, StoredRecipe

NOW = datetime(2026, 4, 7, 12, tzinfo=UTC)


def offered(recipe_id: str, *, pantry_fit: float = 0.0, cooked_days_ago: float | None = None) -> OfferedRecipe:
    return OfferedRecipe(
        summary=RecipeSummary(external_id=recipe_id, key=recipe_id, title=f"Dish {recipe_id}"),
        cooked_days_ago=cooked_days_ago,
        pantry_fit=pantry_fit,
    )


def attributes(protein: MainProtein = MainProtein.UNSURE, carb: MainCarb = MainCarb.UNSURE) -> RecipeAttributes:
    return RecipeAttributes(main_protein=protein, main_carb=carb)


def facts(
    *proteins: MainProtein,
    fit: list[float] | None = None,
    calories: list[float | None] | None = None,
) -> list[RecipeFacts]:
    """One fact per protein, distinct carbs and dish types, so only the protein can repeat."""
    carbs = [MainCarb.RICE, MainCarb.PASTA, MainCarb.POTATO, MainCarb.NONE, MainCarb.NOODLES]
    dish_types = [entry for entry in DishType if entry is not DishType.UNSURE]
    cuisines = [entry for entry in Cuisine if entry is not Cuisine.UNSURE]
    ids = [f"rec_{index}" for index in range(len(proteins))]
    return [
        RecipeFacts(
            recipe_id=recipe_id,
            attributes=RecipeAttributes(
                main_protein=protein,
                main_carb=carbs[index % len(carbs)],
                dish_type=dish_types[index % len(dish_types)],
                cuisine=cuisines[index % len(cuisines)],
                whole_food=WholeFood.MIXED,
            ).as_mapping(),
            calories_per_serving=(calories[index] if calories else None),
            pantry_fit=(fit[index] if fit else 0.0),
        )
        for index, (recipe_id, protein) in enumerate(zip(ids, proteins, strict=True))
    ]


# --- the offer as the scorer reads it ---------------------------------------------------------------------


def test_the_pantry_fit_is_scaled_so_the_best_recipe_is_about_three() -> None:
    # The row reads "the urgency-weighted sum ... scaled so the top recipe is about +3". The sampler's raw
    # figure is a sum of urgency scores, which is far from +3.
    offer = [offered("rec_a", pantry_fit=11.0), offered("rec_b", pantry_fit=5.5), offered("rec_c", pantry_fit=0.0)]

    built = facts_from(offer, attributes={}, calories={}, history=RecipeHistory(days_since_cooked={}, latest_rating={}))

    assert [entry.pantry_fit for entry in built] == [PANTRY_FIT_TOP, PANTRY_FIT_TOP / 2, 0.0]


def test_an_offer_with_no_pantry_match_scores_no_fit_rather_than_dividing_by_zero() -> None:
    built = facts_from(
        [offered("rec_a"), offered("rec_b")],
        attributes={},
        calories={},
        history=RecipeHistory(days_since_cooked={}, latest_rating={}),
    )

    assert [entry.pantry_fit for entry in built] == [0.0, 0.0]


def test_a_fact_carries_the_attributes_calories_age_thumb_and_floor_verdict() -> None:
    offer = [offered("rec_a", pantry_fit=2.0), offered("rec_b", cooked_days_ago=9.0)]
    history = RecipeHistory(days_since_cooked={"rec_a": 60.0, "rec_b": 9.0}, latest_rating={"rec_a": "up"})

    built = facts_from(
        offer,
        attributes={"rec_a": attributes(MainProtein.FISH, MainCarb.RICE)},
        calories={"rec_a": 640.0},
        history=history,
    )

    first, second = built
    assert first.attributes["main_protein"] == "fish"
    assert first.attributes["main_carb"] == "rice"
    assert first.calories_per_serving == 640.0
    assert first.days_since_cooked == 60.0
    assert first.rating == Rating.UP
    assert first.offered_after_floor_relaxed is False
    # Nothing measured: the attributes read as unsure, and the floor relaxed this one back in.
    assert second.attributes["main_protein"] == "unsure"
    assert second.calories_per_serving is None
    assert second.offered_after_floor_relaxed is True


def test_a_stated_calorie_figure_is_read_off_the_recipe_and_nothing_else_is() -> None:
    stated = StoredRecipe(external_id="rec_a", title="Dish", nutrition=StoredNutrition(calories=612, protein_g=30))
    no_calories = StoredRecipe(external_id="rec_b", title="Dish", nutrition=StoredNutrition(protein_g=30))
    no_nutrition = StoredRecipe(external_id="rec_c", title="Dish")

    assert stated_calories(stated) == 612
    # A nutrition block with no calorie figure states nothing: zero would read as the lightest dinner.
    assert stated_calories(no_calories) is None
    assert stated_calories(no_nutrition) is None
    assert stated_calories(None) is None


def test_the_facts_survive_the_checkpoints_json_round_trip() -> None:
    # The prepared plan is checkpointed, so the scorer's inputs have to read back as the same numbers.
    built = facts_from(
        [offered("rec_a", pantry_fit=3.0), offered("rec_b", cooked_days_ago=9.0)],
        attributes={
            "rec_a": attributes(MainProtein.FISH, MainCarb.RICE),
            "rec_b": attributes(MainProtein.BEEF, MainCarb.PASTA),
        },
        calories={"rec_a": 640.0},
        history=RecipeHistory(days_since_cooked={"rec_b": 9.0}, latest_rating={"rec_b": "up"}),
    )

    reread = [RecipeFacts.model_validate(json.loads(entry.model_dump_json())) for entry in built]

    assert reread == built
    assert scoring_context(reread).recipes["rec_b"].rating is not None


# --- the two weeks ---------------------------------------------------------------------------------------


def test_two_weeks_come_back_best_first_with_the_rows_that_made_them() -> None:
    built = facts(
        MainProtein.CHICKEN,
        MainProtein.CHICKEN,
        MainProtein.FISH,
        MainProtein.BEEF,
        fit=[3.0, 2.9, 2.0, 1.9],
    )
    weeks = scored_weeks(scoring_context(built), [entry.recipe_id for entry in built], 2, seed=0)

    assert len(weeks) == 2
    best, alternative = weeks
    assert best.total >= alternative.total
    assert len(best.recipe_ids) == 2
    assert set(best.recipe_ids) != set(alternative.recipe_ids)
    assert best.terms.get("pantry_fit", 0) > 0
    assert isinstance(best.terms, dict)


def test_a_penalty_reaches_the_week_as_a_named_row() -> None:
    built = facts(MainProtein.CHICKEN, MainProtein.CHICKEN, fit=[3.0, 2.9])
    (week,) = scored_weeks(scoring_context(built), [entry.recipe_id for entry in built], 2, seed=0)

    assert [penalty.term for penalty in week.penalties] == ["repeat_main_protein"]
    assert week.penalties[0].points == -5.0
    assert "chicken" in week.penalties[0].detail


def test_the_week_carries_the_lighter_term_only_when_the_chip_is_on() -> None:
    built = facts(MainProtein.CHICKEN, MainProtein.CHICKEN, calories=[900.0, 900.0])
    ids = [entry.recipe_id for entry in built]
    off = scored_weeks(scoring_context(built), ids, 2, seed=0)[0]
    on = scored_weeks(
        ScoringContext(recipes=scoring_context(built).recipes, chips=frozenset({LIGHTER_CHIP})), ids, 2, seed=0
    )[0]

    assert "lighter" not in off.terms
    assert on.terms["lighter"] == -2.0


def test_the_scorer_varies_proteins_the_offer_led_with() -> None:
    # The sampler hands over recipes ranked by pantry fit, and the eval found its pools about 63% chicken.
    # The old fallback took the first slots of that list; the scorer's week does not.
    built = facts(
        MainProtein.CHICKEN,
        MainProtein.CHICKEN,
        MainProtein.CHICKEN,
        MainProtein.FISH,
        MainProtein.BEEF,
        fit=[3.0, 2.9, 2.8, 2.7, 2.6],
    )
    context = scoring_context(built)
    ids = [entry.recipe_id for entry in built]

    week = scored_weeks(context, ids, 3, seed=0)[0]

    assert distinct_main_proteins(week.recipe_ids, context) > distinct_main_proteins(ids[:3], context)


# --- how far a pick fell short ----------------------------------------------------------------------------


def test_the_drift_is_the_gap_between_the_pick_and_the_best_week() -> None:
    built = facts(MainProtein.CHICKEN, MainProtein.FISH, MainProtein.BEEF, fit=[3.0, 1.0, 2.5])
    context = scoring_context(built)
    best = scored_weeks(context, [entry.recipe_id for entry in built], 2, seed=0)[0]

    shortfall = drift([best.recipe_ids[1]], best.recipe_ids, context)

    assert shortfall.gap > 0
    assert shortfall.within_15_percent is False
    assert drift(best.recipe_ids, best.recipe_ids, context).gap == 0.0


def test_a_repeated_pick_is_scored_once_when_the_drift_is_measured() -> None:
    built = facts(MainProtein.CHICKEN, MainProtein.FISH, fit=[3.0, 2.0])
    context = scoring_context(built)
    ids = [entry.recipe_id for entry in built]

    assert drift(["rec_0", "rec_0"], ids, context).gap == drift(["rec_0"], ids, context).gap
