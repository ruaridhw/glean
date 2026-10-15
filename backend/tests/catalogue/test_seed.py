from __future__ import annotations

from collections import Counter
from functools import cache

import pytest

from glean.catalogue.groups import GROUPS, GroupId, Kind, StockUnit, TrackingMode
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
