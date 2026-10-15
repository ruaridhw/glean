from __future__ import annotations

from collections import Counter
from functools import cache

import pytest

from glean.catalogue.groups import GROUPS, Form, GroupId, Kind, StockUnit, TrackingMode
from glean.catalogue.models import CatalogueItem, Source, name_key
from glean.catalogue.seed import SeedData, load_seed

TEN_STAPLES = {
    "olive oil": GroupId.OILS_AND_FATS,
    "salt": GroupId.SPICES,
    "black pepper": GroupId.SPICES,
    "garlic": GroupId.ONIONS_AND_GARLIC,
    "onion": GroupId.ONIONS_AND_GARLIC,
    "butter": GroupId.DAIRY,
    "eggs": GroupId.EGGS,
    "plain flour": GroupId.BAKING,
    "sugar": GroupId.BAKING,
    "tomato paste": GroupId.SAUCES_AND_CONDIMENTS,
}


@cache
def seed() -> SeedData:
    return load_seed()


def by_name(name: str) -> CatalogueItem:
    matches = [item for item in seed().items if name_key(item.name) == name_key(name)]
    assert len(matches) == 1, name
    return matches[0]


def test_the_seed_is_versioned_and_every_item_is_a_seed_item() -> None:
    assert seed().version == 1
    assert {item.source for item in seed().items} == {Source.SEED}


def test_the_seed_has_a_few_hundred_ingredients_and_about_fifty_household_items() -> None:
    kinds = Counter(item.kind for item in seed().items)
    assert 300 <= kinds[Kind.INGREDIENT] <= 500
    assert 40 <= kinds[Kind.HOUSEHOLD] <= 70


def test_no_name_or_alias_is_used_twice_across_the_seed() -> None:
    keys = Counter(name_key(spelling) for item in seed().items for spelling in (item.name, *item.aliases))
    assert [key for key, count in keys.items() if count > 1] == []


def test_item_ids_are_unique_and_stable_slugs() -> None:
    ids = [item.id for item in seed().items]
    assert len(ids) == len(set(ids))
    assert by_name("ground cumin").id == "ground-cumin"


def test_every_group_except_other_has_seed_items() -> None:
    covered = {item.group for item in seed().items}
    assert set(GROUPS) - covered == {GroupId.OTHER}


def test_household_items_sit_only_in_household_groups() -> None:
    for item in seed().items:
        assert (item.kind is Kind.HOUSEHOLD) == (
            item.group in {GroupId.HOUSEHOLD, GroupId.HEALTH_AND_BEAUTY, GroupId.BABY, GroupId.PET}
        )


def test_cumin_and_paprika_are_presence_tracked() -> None:
    assert by_name("ground cumin").tracking_mode is TrackingMode.PRESENCE
    assert by_name("smoked paprika").tracking_mode is TrackingMode.PRESENCE


@pytest.mark.parametrize("name", ["ginger", "double cream", "coriander"])
def test_ginger_cream_and_coriander_are_perishable(name: str) -> None:
    assert by_name(name).tracking_mode is TrackingMode.PERISHABLE


@pytest.mark.parametrize("name", ["pasta", "basmati rice"])
def test_pasta_and_rice_are_counted(name: str) -> None:
    item = by_name(name)
    assert item.tracking_mode is TrackingMode.COUNTED
    assert item.stock_unit is StockUnit.GRAMS


def test_curry_paste_keeps_28_days_once_opened() -> None:
    assert by_name("curry paste").once_opened_shelf_life_days == 28


def test_the_ten_staples_are_in_the_seed_in_their_groups() -> None:
    for name, group in TEN_STAPLES.items():
        assert by_name(name).group is group, name


def test_chickpeas_come_in_separate_tinned_and_dried_items() -> None:
    tinned, dried = by_name("tinned chickpeas"), by_name("dried chickpeas")
    assert tinned.group is dried.group is GroupId.BEANS_AND_PULSES
    assert tinned.form != dried.form


def test_dried_and_grain_items_keep_at_least_90_days_once_opened() -> None:
    dry = [
        item
        for item in seed().items
        if item.form is Form.DRIED or item.group in {GroupId.GRAINS, GroupId.PASTA_AND_RICE, GroupId.BAKING}
    ]
    assert dry
    short = [item.name for item in dry if (item.once_opened_shelf_life_days or 0) < 90]
    assert short == []
    assert (by_name("dried urad dal").once_opened_shelf_life_days or 0) >= 180


def test_frozen_items_keep_at_least_30_days_once_opened() -> None:
    frozen = [item for item in seed().items if item.form is Form.FROZEN]
    assert frozen
    assert [item.name for item in frozen if (item.once_opened_shelf_life_days or 0) < 30] == []
    assert by_name("frozen broad beans").once_opened_shelf_life_days == 90


def test_hard_cheese_keeps_much_longer_than_milk() -> None:
    milk, cheddar = by_name("milk"), by_name("cheddar cheese")
    assert 60 <= cheddar.unopened_shelf_life_days <= 90
    assert 21 <= (cheddar.once_opened_shelf_life_days or 0) <= 28
    assert cheddar.unopened_shelf_life_days > 4 * milk.unopened_shelf_life_days
    assert (cheddar.once_opened_shelf_life_days or 0) > 4 * (milk.once_opened_shelf_life_days or 0)


def test_hard_semi_soft_and_blue_cheeses_have_their_own_shelf_lives() -> None:
    for name in ("emmental", "parmesan", "gruyere", "double gloucester", "red leicester"):
        assert 21 <= (by_name(name).once_opened_shelf_life_days or 0) <= 28, name
    for name in ("blue cheese", "brie", "camembert", "halloumi", "feta cheese"):
        assert 14 <= (by_name(name).once_opened_shelf_life_days or 0) <= 21, name
    for name in ("ricotta", "mozzarella", "cream cheese"):
        assert (by_name(name).once_opened_shelf_life_days or 0) <= 5, name


def test_nuts_and_seeds_are_in_their_own_group_not_snacks() -> None:
    for name in ("almonds", "walnuts", "cashew nuts", "pine nuts", "sunflower seeds", "salted peanuts"):
        assert by_name(name).group is GroupId.NUTS_AND_SEEDS, name
    assert by_name("almonds").section.value == "Food Cupboard"
    assert by_name("walnuts").tracking_mode is TrackingMode.COUNTED


def test_apples_pears_grapes_melon_and_kiwi_are_all_fruit() -> None:
    for name in ("apple", "pear", "grapes", "melon", "kiwi", "banana", "lemon", "strawberries", "peach", "mango"):
        assert by_name(name).group is GroupId.FRUIT, name
        assert by_name(name).section.value == "Fruit & Veg"


def test_every_fruit_item_keeps_its_own_shelf_life() -> None:
    fresh_days = {
        "strawberries": 4,
        "raspberries": 4,
        "blackberries": 4,
        "blueberries": 7,
        "lemon": 14,
        "lime": 14,
        "orange": 14,
        "grapefruit": 14,
        "peach": 5,
        "plum": 5,
        "cherry": 5,
        "apple": 30,
        "pear": 7,
        "grapes": 7,
        "mango": 7,
    }
    for name, days in fresh_days.items():
        assert by_name(name).unopened_shelf_life_days == days, name


def test_no_fruit_item_has_a_shorter_shelf_life_than_it_had_as_a_subgroup() -> None:
    old_fresh_minimum = {"strawberries": 4, "peach": 5, "lemon": 14, "mango": 7, "banana": 7, "avocado": 7}
    for name, days in old_fresh_minimum.items():
        assert by_name(name).unopened_shelf_life_days >= days, name
