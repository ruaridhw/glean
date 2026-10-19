from __future__ import annotations

from glean.catalogue.groups import GROUPS, GroupId
from glean.catalogue.legacy_categories import LEGACY_CATEGORY_GROUPS, legacy_category_for
from glean.receipts.schemas import INGREDIENT_CATEGORY_FOOD_GROUPS

# The 23 categories the app shipped with, each with the food group it always had. Written out here, not read from
# the module under test, so the derivation can't agree with itself by construction.
SHIPPED_CATEGORY_FOOD_GROUPS = {
    "leafy_greens": "vegetables",
    "brassicas": "vegetables",
    "alliums": "vegetables",
    "root_vegetables": "vegetables",
    "nightshades": "vegetables",
    "legumes": "protein",
    "citrus": "fruit",
    "tropical_fruit": "fruit",
    "stone_fruit": "fruit",
    "berries": "fruit",
    "red_meat": "protein",
    "poultry": "protein",
    "seafood": "protein",
    "eggs": "protein",
    "dairy": "dairy",
    "grains": "carbohydrates",
    "pasta_rice": "carbohydrates",
    "bread": "carbohydrates",
    "oils_fats": "fats",
    "herbs_fresh": "condiments",
    "herbs_dried": "condiments",
    "spices": "condiments",
    "condiments": "condiments",
}


def test_every_shipped_category_maps_to_a_group_with_the_same_food_group() -> None:
    assert set(LEGACY_CATEGORY_GROUPS) == set(SHIPPED_CATEGORY_FOOD_GROUPS)
    for category, group in LEGACY_CATEGORY_GROUPS.items():
        assert GROUPS[group].food_group.value == SHIPPED_CATEGORY_FOOD_GROUPS[category], category


def test_the_renamed_groups_follow_the_decision_record() -> None:
    assert LEGACY_CATEGORY_GROUPS["nightshades"] is GroupId.TOMATOES_PEPPERS_AND_AUBERGINES
    assert LEGACY_CATEGORY_GROUPS["alliums"] is GroupId.ONIONS_AND_GARLIC
    assert LEGACY_CATEGORY_GROUPS["brassicas"] is GroupId.CABBAGE_AND_BROCCOLI
    assert LEGACY_CATEGORY_GROUPS["oils_fats"] is GroupId.OILS_AND_FATS


def test_the_four_fruit_categories_merge_into_one_fruit_group() -> None:
    fruit = {"citrus", "tropical_fruit", "stone_fruit", "berries"}
    assert {LEGACY_CATEGORY_GROUPS[c] for c in fruit} == {GroupId.FRUIT}


def test_the_category_food_groups_are_derived_from_the_catalogue_not_copied() -> None:
    assert INGREDIENT_CATEGORY_FOOD_GROUPS == SHIPPED_CATEGORY_FOOD_GROUPS


def test_a_group_with_a_legacy_category_names_one_and_the_rest_name_none() -> None:
    assert legacy_category_for(GroupId.TOMATOES_PEPPERS_AND_AUBERGINES) == "nightshades"
    assert legacy_category_for(GroupId.FRUIT) == "tropical_fruit"
    assert legacy_category_for(GroupId.HOUSEHOLD) is None
    assert legacy_category_for(GroupId.BAKING) is None
