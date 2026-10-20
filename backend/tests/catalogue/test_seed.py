from __future__ import annotations

import json
from collections import Counter
from functools import cache
from pathlib import Path

import pytest

from glean.catalogue.groups import GROUPS, Form, GroupId, Kind, StockUnit, TrackingMode
from glean.catalogue.models import CatalogueItem, Source, name_key
from glean.catalogue.seed import SeedData, load_seed
from glean.catalogue.store import InMemoryCatalogueStore

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
    assert seed().version == 2
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


NON_FOOD_GROUPS = {GroupId.HOUSEHOLD, GroupId.HEALTH_AND_BEAUTY}
EDIBLE_PET_AND_BABY = {
    "baby formula milk powder",
    "baby rice",
    "baby fruit puree pouch",
    "baby pasta stars",
    "baby teething biscuits",
    "baby vegetable meal jar",
    "baby corn puffs",
    "dog food pouches",
    "cat food tins",
    "dry dog food",
    "dry cat food",
    "dog treats",
    "cat treats",
    "wild bird seed",
}


def test_household_and_health_and_beauty_items_never_expire() -> None:
    items = [item for item in seed().items if item.group in NON_FOOD_GROUPS]
    assert items
    for item in items:
        assert item.unopened_shelf_life_days is None, item.name
        assert item.once_opened_shelf_life_days is None, item.name


def test_non_edible_baby_and_pet_items_never_expire_and_edible_ones_keep_shelf_lives() -> None:
    baby_and_pet = [item for item in seed().items if item.group in {GroupId.BABY, GroupId.PET}]
    edible = {item.name for item in baby_and_pet if item.unopened_shelf_life_days is not None}
    assert edible == EDIBLE_PET_AND_BABY
    assert by_name("cat litter").unopened_shelf_life_days is None
    for name in EDIBLE_PET_AND_BABY:
        assert by_name(name).once_opened_shelf_life_days is not None, name


def test_every_food_item_has_an_unopened_shelf_life() -> None:
    assert [
        item.name
        for item in seed().items
        if item.group not in NON_FOOD_GROUPS
        and item.group not in {GroupId.BABY, GroupId.PET}
        and not item.unopened_shelf_life_days
    ] == []


def test_every_perishable_food_item_opens_into_a_once_opened_shelf_life_except_loose_herbs() -> None:
    perishable = [item for item in seed().items if item.tracking_mode is TrackingMode.PERISHABLE]
    assert perishable
    no_once_opened = {item.name for item in perishable if item.once_opened_shelf_life_days is None}
    assert {by_name(name).group for name in no_once_opened} <= {GroupId.FRESH_HERBS}
    assert {item.name for item in perishable if item.group is GroupId.BREAD} >= {"white loaf", "pitta bread"}
    assert by_name("white loaf").once_opened_shelf_life_days == 4


def test_every_milk_is_perishable() -> None:
    milks = ["milk", "whole milk", "semi-skimmed milk", "skimmed milk", "buttermilk", "kefir"]
    for name in milks:
        assert by_name(name).tracking_mode is TrackingMode.PERISHABLE, name
        assert by_name(name).stock_unit is None, name


def test_chilled_dairy_is_perishable_with_a_use_by_except_tinned_and_whole_pack_items() -> None:
    counted = {
        item.name
        for item in seed().items
        if item.group is GroupId.DAIRY and item.tracking_mode is not TrackingMode.PERISHABLE
    }
    assert counted == {"evaporated milk", "halloumi", "mozzarella", "ghee"}
    assert by_name("ghee").tracking_mode is TrackingMode.PRESENCE
    assert by_name("butter").tracking_mode is TrackingMode.PERISHABLE
    assert by_name("cheddar cheese").tracking_mode is TrackingMode.PERISHABLE


def test_coconut_milk_is_counted_in_millilitres_like_the_400_ml_tin_it_comes_in() -> None:
    coconut = by_name("coconut milk")
    assert coconut.tracking_mode is TrackingMode.COUNTED
    assert coconut.stock_unit is StockUnit.MILLILITRES


def test_tins_are_counted_in_grams_except_the_small_use_jars() -> None:
    tinned = [item for item in seed().items if item.form is Form.TINNED_JARRED]
    not_counted = {item.name for item in tinned if item.tracking_mode is not TrackingMode.COUNTED}
    assert not_counted == {"garlic puree", "sun-dried tomato", "roasted red pepper"}
    for name in ("tinned chopped tomatoes", "tinned chickpeas", "tinned kidney beans", "tinned tuna chunks"):
        assert by_name(name).tracking_mode is TrackingMode.COUNTED, name
        assert by_name(name).stock_unit is StockUnit.GRAMS, name
    assert by_name("tomato paste").tracking_mode is TrackingMode.PRESENCE
    assert "tomato puree" in by_name("tomato paste").aliases


def test_condiment_jars_keep_and_are_presence_while_short_life_pastes_are_perishable() -> None:
    sauces = {item.name: item.tracking_mode for item in seed().items if item.group is GroupId.SAUCES_AND_CONDIMENTS}
    perishable = {name for name, mode in sauces.items() if mode is TrackingMode.PERISHABLE}
    counted = {name for name, mode in sauces.items() if mode is TrackingMode.COUNTED}
    assert perishable == {"curry paste", "pesto", "chipotle paste", "harissa paste", "anchovy paste"}
    assert counted == {"coconut milk"}
    for name in ("soy sauce", "fish sauce", "malt vinegar", "ketchup", "preserved lemons", "shrimp paste"):
        assert by_name(name).tracking_mode is TrackingMode.PRESENCE, name
    for name in perishable - {"curry paste"}:
        assert (by_name(name).once_opened_shelf_life_days or 0) <= 28, name


# Every canonical name and alias the v1 seed knew, mapped to its v1 canonical name.
V1_SPELLINGS: dict[str, str] = json.loads(
    (Path(__file__).parent / "fixtures" / "seed_v1_spellings.json").read_text(encoding="utf-8")
)

# Spellings v2 deliberately dropped because they named a different product, or were typos.
DELIBERATELY_REMOVED = {
    "dog meat",  # not a product we stock
    "plum plum",  # typo
    "italin hard cheese",  # typo; parmigiano reggiano covers the real name
    "fruit",  # far too generic for mango
    "honey roasted parsnip",  # a different product from parsnip
    "sweet baby peppers",  # not orange pepper
    "rolled lamb leg",  # lamb leg, not lamb shoulder
    "yam",  # a different vegetable from sweet potato
    "fire lighters",  # not matches
}

# Spellings that still resolve, but now to a different item than in v1 (duplicates merged or a spelling moved).
MOVED_TO = {
    "tomato puree": "tomato paste",
    "tinned butter beans in water": "tinned butter beans",
    "large white beans": "tinned butter beans",
    "semi skimmed milk": "semi-skimmed milk",
    "descaler": "limescale remover",  # a limescale descaler, not toilet cleaner
}


@cache
def v2_store() -> InMemoryCatalogueStore:
    return InMemoryCatalogueStore(seed().items)


@pytest.mark.parametrize(
    ("spelling", "canonical"),
    [
        ("tinned butter beans in water", "tinned butter beans"),
        ("semi skimmed milk", "semi-skimmed milk"),
        ("desiccated coconut", "dried coconut flakes"),
        ("dessicated coconut", "dried coconut flakes"),  # historical alias still resolves
    ],
)
def test_the_spellings_a_merge_or_move_could_lose_still_resolve(spelling: str, canonical: str) -> None:
    found = v2_store().get_by_name(spelling)
    assert found is not None
    assert found.name == canonical


def test_every_v1_name_and_alias_still_resolves_unless_deliberately_removed() -> None:
    lost = [
        spelling
        for spelling in V1_SPELLINGS
        if spelling not in DELIBERATELY_REMOVED and v2_store().get_by_name(spelling) is None
    ]
    assert lost == []


def test_removed_spellings_are_really_gone_and_moved_ones_land_on_the_right_item() -> None:
    assert [s for s in DELIBERATELY_REMOVED if v2_store().get_by_name(s) is not None] == []
    for spelling, canonical in V1_SPELLINGS.items():
        if spelling in DELIBERATELY_REMOVED:
            continue
        found = v2_store().get_by_name(spelling)
        assert found is not None
        assert found.name == MOVED_TO.get(spelling, canonical), spelling
