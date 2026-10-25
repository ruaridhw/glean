"""The attribute contract (spec 6.1, G1): the values, the model every recipe carries, and the time rule.

Seams: the enums and `RecipeAttributes` that the enrichers, the projection, the filter and the check-sample
tooling all share, and the projection entry's typed accessor over its `attributes` slot.
"""

from __future__ import annotations

import pytest

from glean.recipes.attributes import (
    ACTIVE_TIME_QUESTION,
    ATTRIBUTE_QUESTIONS,
    ActiveTimeBucket,
    Cuisine,
    DishType,
    MainCarb,
    MainProtein,
    RecipeAttributes,
    WholeFood,
    normalise_cuisine,
)
from glean.recipes.projection import ProjectedRecipe
from glean.recipes.search_index import RecipeSummary

CHOICES = [MainProtein, MainCarb, DishType, Cuisine, WholeFood, ActiveTimeBucket]


@pytest.mark.parametrize("enum", CHOICES)
def test_every_attribute_can_be_unsure(enum) -> None:
    assert enum("unsure") is enum.UNSURE


def test_the_choice_values_are_the_ones_settled_in_g1() -> None:
    assert {value.value for value in MainProtein} == {
        "unsure",
        "chicken",
        "turkey_or_duck",
        "beef",
        "pork",
        "lamb",
        "fish",
        "seafood",
        "beans_and_pulses",
        "tofu_or_plant_protein",
        "vegetarian_other",
        "mixed",
        "none",
    }
    assert {value.value for value in MainCarb} == {
        "unsure",
        "rice",
        "pasta",
        "noodles",
        "potato",
        "bread_or_wraps",
        "other_grains",
        "none",
    }
    assert {value.value for value in DishType} == {
        "unsure",
        "curry",
        "stir_fry",
        "pasta_dish",
        "soup_or_stew",
        "roast_or_traybake",
        "salad_or_bowl",
        "handheld",
        "pie_or_bake",
        "rice_dish",
        "pan_or_grill",
        "other",
    }
    assert {value.value for value in WholeFood} == {"unsure", "whole", "mixed", "processed"}


def test_cuisine_is_the_settled_regional_list_with_no_fusion_value() -> None:
    assert len(Cuisine) == 20  # `unsure` plus the 19 G1 regions, "Southeast Asian (other)" and "Other" included
    assert {value.value for value in Cuisine} == {
        "unsure",
        "british",
        "italian",
        "french",
        "spanish",
        "greek",
        "middle_eastern",
        "north_african",
        "indian",
        "thai",
        "vietnamese",
        "chinese",
        "japanese",
        "korean",
        "southeast_asian",
        "mexican",
        "caribbean",
        "american",
        "latin_american",
        "other",
    }


def test_the_time_buckets_are_the_five_the_owner_labels_use() -> None:
    assert {value.value for value in ActiveTimeBucket} == {"unsure", "<=15", "15-30", "30-45", "45-60", "60+"}


@pytest.mark.parametrize(
    ("bucket", "bound"),
    [
        (ActiveTimeBucket.UP_TO_15, 15),
        (ActiveTimeBucket.FROM_15_TO_30, 30),
        (ActiveTimeBucket.FROM_30_TO_45, 45),
        (ActiveTimeBucket.FROM_45_TO_60, 60),
        (ActiveTimeBucket.OVER_60, None),
        (ActiveTimeBucket.UNSURE, None),
    ],
)
def test_each_bucket_states_its_upper_bound(bucket, bound) -> None:
    assert bucket.upper_bound_mins == bound


@pytest.mark.parametrize(
    ("label", "bucket"),
    [
        ("<=15", ActiveTimeBucket.UP_TO_15),
        ("<15", ActiveTimeBucket.UP_TO_15),
        ("15-30", ActiveTimeBucket.FROM_15_TO_30),
        ("15\u201330", ActiveTimeBucket.FROM_15_TO_30),  # the en dash a labeller's table writes
        ("30-45", ActiveTimeBucket.FROM_30_TO_45),
        ("45\u201360 min", ActiveTimeBucket.FROM_45_TO_60),
        ("60+", ActiveTimeBucket.OVER_60),
        ("60 mins+", ActiveTimeBucket.OVER_60),
        ("unsure", ActiveTimeBucket.UNSURE),
        ("about half an hour", ActiveTimeBucket.UNSURE),
        (None, ActiveTimeBucket.UNSURE),
    ],
)
def test_a_written_bucket_reads_as_its_bucket(label, bucket) -> None:
    assert ActiveTimeBucket.from_text(label) is bucket


@pytest.mark.parametrize(
    ("raw", "cuisine"),
    [
        ("Italian", Cuisine.ITALIAN),
        ("thai", Cuisine.THAI),
        ("Thai-Inspired", Cuisine.THAI),
        ("Thai, Thai-Inspired", Cuisine.THAI),
        ("Indian & British", Cuisine.INDIAN),
        ("Middle Eastern", Cuisine.MIDDLE_EASTERN),
        ("middle-eastern", Cuisine.MIDDLE_EASTERN),
        ("South-East Asian", Cuisine.SOUTHEAST_ASIAN),
        ("Mexican-Inspired", Cuisine.MEXICAN),
        ("British", Cuisine.BRITISH),
        ("Southeast Asian (other)", Cuisine.SOUTHEAST_ASIAN),  # the G1 table's own spelling
        ("South East Asian", Cuisine.SOUTHEAST_ASIAN),
        ("Other", Cuisine.OTHER),
        ("Fusion", None),  # there is no fusion value
        ("Grandma's best", None),
        ("", None),
        (None, None),
    ],
)
def test_one_place_normalises_cuisine_spellings(raw, cuisine) -> None:
    assert normalise_cuisine(raw) is cuisine


@pytest.mark.parametrize("cuisine", [value for value in Cuisine if value is not Cuisine.UNSURE])
def test_every_g1_cuisine_value_normalises_to_itself(cuisine) -> None:
    assert normalise_cuisine(cuisine.value) is cuisine


G1_SPELLINGS = {
    "British": Cuisine.BRITISH,
    "Italian": Cuisine.ITALIAN,
    "French": Cuisine.FRENCH,
    "Spanish": Cuisine.SPANISH,
    "Greek": Cuisine.GREEK,
    "Middle Eastern": Cuisine.MIDDLE_EASTERN,
    "North African": Cuisine.NORTH_AFRICAN,
    "Indian": Cuisine.INDIAN,
    "Thai": Cuisine.THAI,
    "Vietnamese": Cuisine.VIETNAMESE,
    "Chinese": Cuisine.CHINESE,
    "Japanese": Cuisine.JAPANESE,
    "Korean": Cuisine.KOREAN,
    "Southeast Asian (other)": Cuisine.SOUTHEAST_ASIAN,
    "Mexican": Cuisine.MEXICAN,
    "Caribbean": Cuisine.CARIBBEAN,
    "American": Cuisine.AMERICAN,
    "Latin American": Cuisine.LATIN_AMERICAN,
    "Other": Cuisine.OTHER,
}


@pytest.mark.parametrize(("written", "cuisine"), sorted(G1_SPELLINGS.items()))
def test_every_cuisine_as_the_g1_table_writes_it_normalises_to_itself(written, cuisine) -> None:
    """The G1 table writes "Southeast Asian (other)" with a parenthetical; that must not read as unknown."""
    assert normalise_cuisine(written) is cuisine


def test_a_recipe_with_no_answers_is_unsure_everywhere_rather_than_missing_attributes() -> None:
    attributes = RecipeAttributes()

    assert attributes == RecipeAttributes.from_mapping({})
    assert set(attributes.as_mapping().values()) == {"unsure"}
    assert set(attributes.as_mapping()) == {
        "main_protein",
        "main_carb",
        "dish_type",
        "cuisine",
        "whole_food",
        "active_time",
    }


def test_the_mapping_round_trips_every_settled_value() -> None:
    attributes = RecipeAttributes(
        main_protein=MainProtein.BEANS_AND_PULSES,
        main_carb=MainCarb.BREAD_OR_WRAPS,
        dish_type=DishType.HANDHELD,
        cuisine=Cuisine.MIDDLE_EASTERN,
        whole_food=WholeFood.MIXED,
        active_time=ActiveTimeBucket.FROM_15_TO_30,
    )

    assert RecipeAttributes.from_mapping(attributes.as_mapping()) == attributes


def test_reading_a_mapping_tolerates_what_a_label_or_an_older_projection_writes() -> None:
    read = RecipeAttributes.from_mapping(
        {
            "main_protein": "stir fry",  # a wrong attribute for it: still unsure, never a crash
            "main_carb": "Bread or wraps",
            "dish_type": "Stir-Fry",
            "cuisine": "Thai-Inspired",
            "whole_food": "processed",
            "active_time": "15\u201330",
            "something_else": "ignored",
        }
    )

    assert read.main_protein is MainProtein.UNSURE
    assert read.main_carb is MainCarb.BREAD_OR_WRAPS
    assert read.dish_type is DishType.STIR_FRY
    assert read.cuisine is Cuisine.THAI
    assert read.whole_food is WholeFood.PROCESSED
    assert read.active_time is ActiveTimeBucket.FROM_15_TO_30


def test_attributes_are_frozen() -> None:
    attributes = RecipeAttributes()

    with pytest.raises(ValueError, match="frozen"):
        attributes.main_protein = MainProtein.CHICKEN  # type: ignore[misc]


def test_each_attribute_names_the_question_its_answer_is_stored_under() -> None:
    assert ATTRIBUTE_QUESTIONS == {
        "main_protein": "attribute:main_protein",
        "main_carb": "attribute:main_carb",
        "dish_type": "attribute:dish_type",
        "cuisine": "attribute:cuisine",
        "whole_food": "attribute:whole_food",
        "active_time": ACTIVE_TIME_QUESTION,
    }
    assert ACTIVE_TIME_QUESTION == "active_time:bucket"


@pytest.mark.parametrize(
    ("attributes", "total", "cap", "fits"),
    [
        # The bucket's upper bound is what the cap is compared against, not its lower bound.
        ({"active_time": "15-30"}, 40, 30, True),
        ({"active_time": "15-30"}, 40, 29, False),
        ({"active_time": "<=15"}, 60, 15, True),
        # 60+ has no upper bound; a cap under an hour rejects it outright, above that the total time decides.
        ({"active_time": "60+"}, 70, 120, True),
        ({"active_time": "60+"}, 200, 45, False),
        ({"active_time": "60+"}, None, 120, True),  # nothing known but "at least an hour", and the cap is above it
        # No bucket yet: fall back to total time, as the filter did before V5.
        ({}, 40, 45, True),
        ({}, 40, 35, False),
        ({}, None, 20, True),  # unknown total time passes, as it always has
        ({"active_time": "unsure"}, 40, 45, True),
        # No cap at all admits everything, whatever the bucket says.
        ({"active_time": "60+"}, 200, None, True),
    ],
)
def test_the_time_cap_compares_against_the_buckets_upper_bound(attributes, total, cap, fits) -> None:
    assert RecipeAttributes.from_mapping(attributes).fits_time_cap(cap, total_time_mins=total) is fits


def test_a_projection_entry_exposes_its_attributes_typed() -> None:
    summary = RecipeSummary(external_id="rec_x", key="x/rec_x.json", title="Synthetic", total_time_mins=25)
    entry = ProjectedRecipe(summary=summary, attributes={"main_protein": "chicken", "cuisine": "korean"})

    attributes = entry.recipe_attributes

    assert attributes.main_protein is MainProtein.CHICKEN
    assert attributes.cuisine is Cuisine.KOREAN
    assert attributes.dish_type is DishType.UNSURE
    assert ProjectedRecipe(summary=summary).recipe_attributes == RecipeAttributes()
