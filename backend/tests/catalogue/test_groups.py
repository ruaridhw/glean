from __future__ import annotations

from glean.catalogue.groups import GROUPS, FoodGroup, Form, Kind

EXPECTED_GROUP_IDS = {
    # the 23 current categories, with the four renames
    "leafy_greens",
    "cabbage_and_broccoli",
    "onions_and_garlic",
    "root_veg",
    "tomatoes_peppers_and_aubergines",
    "beans_and_pulses",
    "citrus",
    "tropical_fruit",
    "stone_fruit",
    "berries",
    "red_meat",
    "poultry",
    "fish_and_seafood",
    "eggs",
    "dairy",
    "grains",
    "pasta_and_rice",
    "bread",
    "oils_and_fats",
    "fresh_herbs",
    "dried_herbs",
    "spices",
    "sauces_and_condiments",
    # the eight new groups
    "baking",
    "drinks",
    "snacks_and_treats",
    "household",
    "health_and_beauty",
    "baby",
    "pet",
    "other",
}

FORM_GROUP_IDS = {
    "leafy_greens",
    "cabbage_and_broccoli",
    "onions_and_garlic",
    "root_veg",
    "tomatoes_peppers_and_aubergines",
    "beans_and_pulses",
    "citrus",
    "tropical_fruit",
    "stone_fruit",
    "berries",
    "red_meat",
    "poultry",
    "fish_and_seafood",
}


def test_there_are_31_ingredient_groups() -> None:
    assert {group_id.value for group_id in GROUPS} == EXPECTED_GROUP_IDS
    assert len(GROUPS) == 31


def test_only_household_groups_are_household_kind() -> None:
    household = {group_id.value for group_id, rules in GROUPS.items() if rules.kind is Kind.HOUSEHOLD}
    assert household == {"household", "health_and_beauty", "baby", "pet"}


def test_forms_are_allowed_only_for_veg_fruit_pulses_meat_and_fish() -> None:
    with_forms = {group_id.value for group_id, rules in GROUPS.items() if rules.has_forms}
    assert with_forms == FORM_GROUP_IDS


def test_form_groups_allow_the_four_real_forms_and_others_only_not_applicable() -> None:
    real_forms = {Form.FRESH, Form.FROZEN, Form.TINNED_JARRED, Form.DRIED}
    for group_id, rules in GROUPS.items():
        expected = real_forms if group_id.value in FORM_GROUP_IDS else {Form.NOT_APPLICABLE}
        assert set(rules.allowed_forms) == expected, group_id


def test_each_group_maps_to_its_food_group() -> None:
    food_group = {group_id.value: rules.food_group for group_id, rules in GROUPS.items()}
    assert food_group["spices"] is FoodGroup.CONDIMENTS
    assert food_group["eggs"] is FoodGroup.PROTEIN
    assert food_group["beans_and_pulses"] is FoodGroup.PROTEIN
    assert food_group["root_veg"] is FoodGroup.VEGETABLES
    assert food_group["berries"] is FoodGroup.FRUIT
    assert food_group["dairy"] is FoodGroup.DAIRY
    assert food_group["pasta_and_rice"] is FoodGroup.CARBOHYDRATES
    assert food_group["oils_and_fats"] is FoodGroup.FATS


def test_nightshades_jargon_is_gone() -> None:
    assert not {"nightshades", "alliums", "brassicas", "oils_fats"} & {g.value for g in GROUPS}
