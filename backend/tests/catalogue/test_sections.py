from __future__ import annotations

import pytest

from glean.catalogue.groups import GROUPS, Form, GroupId
from glean.catalogue.sections import Section, section_for

N_A = Form.NOT_APPLICABLE


@pytest.mark.parametrize(
    ("group", "form", "expected"),
    [
        (GroupId.CABBAGE_AND_BROCCOLI, Form.FROZEN, Section.FROZEN),
        (GroupId.BEANS_AND_PULSES, Form.FROZEN, Section.FROZEN),
        (GroupId.TOMATOES_PEPPERS_AND_AUBERGINES, Form.TINNED_JARRED, Section.FOOD_CUPBOARD),
        (GroupId.FISH_AND_SEAFOOD, Form.TINNED_JARRED, Section.FOOD_CUPBOARD),
        (GroupId.BEANS_AND_PULSES, Form.DRIED, Section.PASTA_RICE_GRAINS),
        (GroupId.BEANS_AND_PULSES, Form.FRESH, Section.FRUIT_AND_VEG),
        (GroupId.BERRIES, Form.FRESH, Section.FRUIT_AND_VEG),
        (GroupId.CITRUS, Form.DRIED, Section.FOOD_CUPBOARD),
        (GroupId.RED_MEAT, Form.FRESH, Section.MEAT_AND_FISH),
        (GroupId.FISH_AND_SEAFOOD, Form.FROZEN, Section.FROZEN),
        (GroupId.SPICES, N_A, Section.FOOD_CUPBOARD),
        (GroupId.OILS_AND_FATS, N_A, Section.FOOD_CUPBOARD),
        (GroupId.SAUCES_AND_CONDIMENTS, N_A, Section.FOOD_CUPBOARD),
        (GroupId.DRIED_HERBS, N_A, Section.FOOD_CUPBOARD),
        (GroupId.FRESH_HERBS, N_A, Section.FRUIT_AND_VEG),
        (GroupId.BAKING, N_A, Section.BAKING),
        (GroupId.NUTS_AND_SEEDS, N_A, Section.FOOD_CUPBOARD),
        (GroupId.PASTA_AND_RICE, N_A, Section.PASTA_RICE_GRAINS),
        (GroupId.GRAINS, N_A, Section.PASTA_RICE_GRAINS),
        (GroupId.BREAD, N_A, Section.BAKERY),
        (GroupId.EGGS, N_A, Section.DAIRY_EGGS_CHILLED),
        (GroupId.DAIRY, N_A, Section.DAIRY_EGGS_CHILLED),
        (GroupId.DRINKS, N_A, Section.DRINKS),
        (GroupId.SNACKS_AND_TREATS, N_A, Section.SNACKS_AND_TREATS),
        (GroupId.HOUSEHOLD, N_A, Section.HOUSEHOLD),
        (GroupId.HEALTH_AND_BEAUTY, N_A, Section.HEALTH_AND_BEAUTY),
        (GroupId.BABY, N_A, Section.BABY_AND_TODDLER),
        (GroupId.PET, N_A, Section.PET),
        (GroupId.OTHER, N_A, Section.OTHER),
    ],
)
def test_section_for_group_and_form(group: GroupId, form: Form, expected: Section) -> None:
    assert section_for(group, form) is expected


def test_there_are_14_sections_plus_other() -> None:
    assert len(Section) == 15
    assert Section.OTHER.value == "Other"


def test_every_group_and_allowed_form_has_a_section() -> None:
    for group_id, rules in GROUPS.items():
        for form in rules.allowed_forms:
            assert isinstance(section_for(group_id, form), Section)


def test_a_form_the_group_does_not_allow_is_rejected() -> None:
    with pytest.raises(ValueError, match="does not allow form"):
        section_for(GroupId.SPICES, Form.FROZEN)
    with pytest.raises(ValueError, match="does not allow form"):
        section_for(GroupId.RED_MEAT, Form.NOT_APPLICABLE)
