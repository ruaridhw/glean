"""The 23 categories the app shipped with, mapped onto the catalogue's ingredient groups.

Only the transition needs this: responses carry both `category` and `ingredient_group` until every phone runs a build
that reads the group. Delete it with `category`.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from glean.catalogue.groups import GroupId

if TYPE_CHECKING:
    from collections.abc import Mapping

LEGACY_CATEGORY_GROUPS: Mapping[str, GroupId] = MappingProxyType(
    {
        "leafy_greens": GroupId.LEAFY_GREENS,
        "brassicas": GroupId.CABBAGE_AND_BROCCOLI,
        "alliums": GroupId.ONIONS_AND_GARLIC,
        "root_vegetables": GroupId.ROOT_VEG,
        "nightshades": GroupId.TOMATOES_PEPPERS_AND_AUBERGINES,
        "legumes": GroupId.BEANS_AND_PULSES,
        "citrus": GroupId.FRUIT,
        "tropical_fruit": GroupId.FRUIT,
        "stone_fruit": GroupId.FRUIT,
        "berries": GroupId.FRUIT,
        "red_meat": GroupId.RED_MEAT,
        "poultry": GroupId.POULTRY,
        "seafood": GroupId.FISH_AND_SEAFOOD,
        "eggs": GroupId.EGGS,
        "dairy": GroupId.DAIRY,
        "grains": GroupId.GRAINS,
        "pasta_rice": GroupId.PASTA_AND_RICE,
        "bread": GroupId.BREAD,
        "oils_fats": GroupId.OILS_AND_FATS,
        "herbs_fresh": GroupId.FRESH_HERBS,
        "herbs_dried": GroupId.DRIED_HERBS,
        "spices": GroupId.SPICES,
        "condiments": GroupId.SAUCES_AND_CONDIMENTS,
    }
)

# Fruit was four categories; tropical_fruit is the one whose shelf life (7 days) is the Fruit group's fresh life.
_FRUIT_STAND_IN = "tropical_fruit"


def legacy_category_for(group: GroupId) -> str | None:
    """The shipped category an older app build should see for `group`, or None where it had no equivalent."""
    if group is GroupId.FRUIT:
        return _FRUIT_STAND_IN
    return next((category for category, mapped in LEGACY_CATEGORY_GROUPS.items() if mapped is group), None)
