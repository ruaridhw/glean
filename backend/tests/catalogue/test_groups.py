from __future__ import annotations

from glean.catalogue.groups import GROUPS, FoodGroup, Form, GroupId, Kind, StockUnit, TrackingMode

EXPECTED_GROUP_IDS = {
    # the 23 current categories, with the four renames
    "leafy_greens",
    "cabbage_and_broccoli",
    "onions_and_garlic",
    "root_veg",
    "tomatoes_peppers_and_aubergines",
    "beans_and_pulses",
    "fruit",
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
    # the nine new groups
    "baking",
    "nuts_and_seeds",
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
    "fruit",
    "red_meat",
    "poultry",
    "fish_and_seafood",
}


def test_there_are_29_ingredient_groups() -> None:
    assert {group_id.value for group_id in GROUPS} == EXPECTED_GROUP_IDS
    assert len(GROUPS) == 29


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
    assert food_group["fruit"] is FoodGroup.FRUIT
    assert food_group["dairy"] is FoodGroup.DAIRY
    assert food_group["pasta_and_rice"] is FoodGroup.CARBOHYDRATES
    assert food_group["oils_and_fats"] is FoodGroup.FATS


def test_nightshades_jargon_is_gone() -> None:
    assert not {"nightshades", "alliums", "brassicas", "oils_fats"} & {g.value for g in GROUPS}


def test_only_the_other_food_group_does_not_count_towards_week_balance() -> None:
    not_counted = {food_group for food_group in FoodGroup if not food_group.counts_towards_balance}
    assert not_counted == {FoodGroup.OTHER}


def test_drinks_snacks_and_non_food_groups_do_not_count_towards_balance() -> None:
    uncounted = {group_id.value for group_id, rules in GROUPS.items() if not rules.food_group.counts_towards_balance}
    assert uncounted == {"drinks", "snacks_and_treats", "household", "health_and_beauty", "baby", "pet", "other"}


def test_once_opened_shelf_life_depends_on_form_where_a_group_has_forms() -> None:
    pulses = GROUPS[GroupId.BEANS_AND_PULSES]
    assert pulses.once_opened_shelf_life_days[Form.TINNED_JARRED] == 3
    assert pulses.once_opened_shelf_life_days[Form.DRIED] == 365
    assert pulses.once_opened_shelf_life_days[Form.FROZEN] == 90
    assert pulses.once_opened_shelf_life_days[Form.FRESH] == 3


def test_once_opened_shelf_life_has_one_value_per_allowed_form() -> None:
    for group_id, rules in GROUPS.items():
        assert set(rules.once_opened_shelf_life_days) == set(rules.allowed_forms), group_id
        assert set(rules.unopened_shelf_life_days) == set(rules.allowed_forms), group_id


def test_grains_pasta_and_rice_keep_a_long_time_once_opened() -> None:
    assert GROUPS[GroupId.PASTA_AND_RICE].once_opened_shelf_life_days[Form.NOT_APPLICABLE] == 365
    assert GROUPS[GroupId.GRAINS].once_opened_shelf_life_days[Form.NOT_APPLICABLE] == 180


def test_nuts_and_seeds_are_a_protein_counted_in_grams_with_no_forms() -> None:
    rules = GROUPS[GroupId.NUTS_AND_SEEDS]
    assert rules.name == "Nuts & seeds"
    assert rules.kind is Kind.INGREDIENT
    assert rules.food_group is FoodGroup.PROTEIN
    assert rules.tracking_mode is TrackingMode.COUNTED
    assert rules.stock_unit is StockUnit.GRAMS
    assert not rules.has_forms
    assert rules.unopened_shelf_life_days[Form.NOT_APPLICABLE] == 180
    assert rules.once_opened_shelf_life_days[Form.NOT_APPLICABLE] == 90


def test_fruit_is_one_group_with_a_generic_fresh_default_of_a_week() -> None:
    assert not {"citrus", "tropical_fruit", "stone_fruit", "berries"} & {g.value for g in GROUPS}
    fruit = GROUPS[GroupId.FRUIT]
    assert fruit.name == "Fruit"
    assert fruit.unopened_shelf_life_days[Form.FRESH] == 7
    assert fruit.has_forms


NON_FOOD_GROUPS = (GroupId.HOUSEHOLD, GroupId.HEALTH_AND_BEAUTY, GroupId.BABY, GroupId.PET)


def test_non_food_groups_have_no_shelf_life_at_all() -> None:
    for group_id in NON_FOOD_GROUPS:
        rules = GROUPS[group_id]
        assert rules.unopened_shelf_life_days == {Form.NOT_APPLICABLE: None}, group_id
        assert rules.once_opened_shelf_life_days == {Form.NOT_APPLICABLE: None}, group_id


def test_every_other_group_gives_an_unopened_shelf_life_for_each_form() -> None:
    for group_id, rules in GROUPS.items():
        if group_id in NON_FOOD_GROUPS:
            continue
        assert all(days is not None and days > 0 for days in rules.unopened_shelf_life_days.values()), group_id


def test_dairy_defaults_to_perishable() -> None:
    assert GROUPS[GroupId.DAIRY].tracking_mode is TrackingMode.PERISHABLE
    assert GROUPS[GroupId.DAIRY].stock_unit is None
