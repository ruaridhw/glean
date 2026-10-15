from __future__ import annotations

from enum import StrEnum

from glean.catalogue.groups import GROUPS, Form, GroupId


class Section(StrEnum):
    """Store sections: the level shared by every UK supermarket, plus an Other fallback."""

    FRUIT_AND_VEG = "Fruit & Veg"
    MEAT_AND_FISH = "Meat & Fish"
    DAIRY_EGGS_CHILLED = "Dairy, Eggs & Chilled"
    BAKERY = "Bakery"
    FROZEN = "Frozen"
    PASTA_RICE_GRAINS = "Pasta, Rice & Grains"
    FOOD_CUPBOARD = "Food Cupboard"
    BAKING = "Baking"
    SNACKS_AND_TREATS = "Snacks & Treats"
    DRINKS = "Drinks"
    HOUSEHOLD = "Household"
    HEALTH_AND_BEAUTY = "Health & Beauty"
    BABY_AND_TODDLER = "Baby & Toddler"
    PET = "Pet"
    OTHER = "Other"


_FRESH_PRODUCE = {
    GroupId.LEAFY_GREENS,
    GroupId.CABBAGE_AND_BROCCOLI,
    GroupId.ONIONS_AND_GARLIC,
    GroupId.ROOT_VEG,
    GroupId.TOMATOES_PEPPERS_AND_AUBERGINES,
    GroupId.BEANS_AND_PULSES,
    GroupId.CITRUS,
    GroupId.TROPICAL_FRUIT,
    GroupId.STONE_FRUIT,
    GroupId.BERRIES,
}

# Groups without forms: one section each.
_PLAIN_SECTION = {
    GroupId.EGGS: Section.DAIRY_EGGS_CHILLED,
    GroupId.DAIRY: Section.DAIRY_EGGS_CHILLED,
    GroupId.GRAINS: Section.PASTA_RICE_GRAINS,
    GroupId.PASTA_AND_RICE: Section.PASTA_RICE_GRAINS,
    GroupId.BREAD: Section.BAKERY,
    GroupId.OILS_AND_FATS: Section.FOOD_CUPBOARD,
    GroupId.FRESH_HERBS: Section.FRUIT_AND_VEG,
    GroupId.DRIED_HERBS: Section.FOOD_CUPBOARD,
    GroupId.SPICES: Section.FOOD_CUPBOARD,
    GroupId.SAUCES_AND_CONDIMENTS: Section.FOOD_CUPBOARD,
    GroupId.BAKING: Section.BAKING,
    GroupId.NUTS_AND_SEEDS: Section.FOOD_CUPBOARD,
    GroupId.DRINKS: Section.DRINKS,
    GroupId.SNACKS_AND_TREATS: Section.SNACKS_AND_TREATS,
    GroupId.HOUSEHOLD: Section.HOUSEHOLD,
    GroupId.HEALTH_AND_BEAUTY: Section.HEALTH_AND_BEAUTY,
    GroupId.BABY: Section.BABY_AND_TODDLER,
    GroupId.PET: Section.PET,
    GroupId.OTHER: Section.OTHER,
}


def section_for(group: GroupId, form: Form) -> Section:
    """The store section for an ingredient group in a given form."""
    if form not in GROUPS[group].allowed_forms:
        raise ValueError(f"{group.value} does not allow form {form.value}")
    if form is Form.FROZEN:
        return Section.FROZEN
    if form is Form.TINNED_JARRED:
        return Section.FOOD_CUPBOARD
    if group in _FRESH_PRODUCE:
        if form is Form.FRESH:
            return Section.FRUIT_AND_VEG
        # Dried pulses sit with the pasta and rice; other dried produce (fruit, mushrooms) in the cupboard.
        return Section.PASTA_RICE_GRAINS if group is GroupId.BEANS_AND_PULSES else Section.FOOD_CUPBOARD
    if group in _PLAIN_SECTION:
        return _PLAIN_SECTION[group]
    # Meat, poultry and fish: fresh in Meat & Fish, dried (jerky, salt fish) in the cupboard.
    return Section.MEAT_AND_FISH if form is Form.FRESH else Section.FOOD_CUPBOARD
