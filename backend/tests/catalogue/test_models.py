from __future__ import annotations

import pytest
from pydantic import ValidationError

from glean.catalogue.groups import Form, GroupId, Kind, StockUnit, TrackingMode
from glean.catalogue.models import CatalogueItem, ItemOverrides, Source
from glean.catalogue.sections import Section


def item(name: str, group: GroupId, form: Form = Form.NOT_APPLICABLE, **kwargs: object) -> CatalogueItem:
    return CatalogueItem(id=name.replace(" ", "-"), name=name, group=group, form=form, source=Source.SEED, **kwargs)


def test_an_item_in_a_household_group_is_a_household_item() -> None:
    assert item("toilet roll", GroupId.HOUSEHOLD).kind is Kind.HOUSEHOLD
    assert item("shampoo", GroupId.HEALTH_AND_BEAUTY).kind is Kind.HOUSEHOLD
    assert item("cat food", GroupId.PET).kind is Kind.HOUSEHOLD


def test_an_item_in_a_food_group_is_an_ingredient() -> None:
    assert item("ground cumin", GroupId.SPICES).kind is Kind.INGREDIENT
    assert item("snack bar", GroupId.SNACKS_AND_TREATS).kind is Kind.INGREDIENT


def test_a_group_without_forms_requires_not_applicable() -> None:
    with pytest.raises(ValidationError, match="does not allow form"):
        item("ground cumin", GroupId.SPICES, Form.DRIED)


def test_a_group_with_forms_rejects_not_applicable() -> None:
    with pytest.raises(ValidationError, match="needs an explicit form"):
        item("chickpeas", GroupId.BEANS_AND_PULSES, Form.NOT_APPLICABLE)


def test_form_is_never_defaulted() -> None:
    with pytest.raises(ValidationError, match="form"):
        CatalogueItem(id="x", name="x", group=GroupId.SPICES, source=Source.SEED)  # ty: ignore[missing-argument]


def test_form_is_part_of_what_an_ingredient_is() -> None:
    tinned = item("tinned chickpeas", GroupId.BEANS_AND_PULSES, Form.TINNED_JARRED)
    dried = item("dried chickpeas", GroupId.BEANS_AND_PULSES, Form.DRIED)
    assert tinned.section is Section.FOOD_CUPBOARD
    assert dried.section is Section.PASTA_RICE_GRAINS
    assert tinned.unopened_shelf_life_days == 730
    assert dried.unopened_shelf_life_days == 730
    assert tinned.once_opened_shelf_life_days == 3


def test_item_takes_its_rules_from_its_group() -> None:
    cumin = item("ground cumin", GroupId.SPICES)
    assert cumin.tracking_mode is TrackingMode.PRESENCE
    assert cumin.stock_unit is None
    rice = item("basmati rice", GroupId.PASTA_AND_RICE)
    assert rice.tracking_mode is TrackingMode.COUNTED
    assert rice.stock_unit is StockUnit.GRAMS


def test_item_overrides_beat_the_group_defaults() -> None:
    ginger = item(
        "ginger", GroupId.ROOT_VEG, Form.FRESH, overrides=ItemOverrides(tracking_mode=TrackingMode.PERISHABLE)
    )
    assert ginger.tracking_mode is TrackingMode.PERISHABLE
    paste = item(
        "curry paste",
        GroupId.SAUCES_AND_CONDIMENTS,
        overrides=ItemOverrides(unopened_shelf_life_days=365, once_opened_shelf_life_days=28),
    )
    assert paste.unopened_shelf_life_days == 365
    assert paste.once_opened_shelf_life_days == 28
    evaporated = item(
        "evaporated milk",
        GroupId.DAIRY,
        overrides=ItemOverrides(tracking_mode=TrackingMode.COUNTED, stock_unit=StockUnit.GRAMS),
    )
    assert evaporated.tracking_mode is TrackingMode.COUNTED
    assert evaporated.stock_unit is StockUnit.GRAMS


def test_overriding_a_presence_item_to_counted_needs_a_stock_unit() -> None:
    with pytest.raises(ValidationError, match="stock unit"):
        item("saffron", GroupId.SPICES, overrides=ItemOverrides(tracking_mode=TrackingMode.COUNTED))
    counted = item(
        "saffron",
        GroupId.SPICES,
        overrides=ItemOverrides(tracking_mode=TrackingMode.COUNTED, stock_unit=StockUnit.GRAMS),
    )
    assert counted.stock_unit is StockUnit.GRAMS


def test_density_must_be_positive() -> None:
    assert item("olive oil", GroupId.OILS_AND_FATS, density_g_per_ml=0.91).density_g_per_ml == 0.91
    with pytest.raises(ValidationError):
        item("olive oil", GroupId.OILS_AND_FATS, density_g_per_ml=0)


def test_aliases_are_trimmed() -> None:
    assert item("coriander", GroupId.FRESH_HERBS, aliases=("  fresh coriander ",)).aliases == ("fresh coriander",)


def test_a_household_item_never_expires_unless_overridden() -> None:
    toilet_roll = item("toilet roll", GroupId.HOUSEHOLD)
    assert toilet_roll.unopened_shelf_life_days is None
    assert toilet_roll.once_opened_shelf_life_days is None
    pouch = item(
        "dog food pouches",
        GroupId.PET,
        overrides=ItemOverrides(unopened_shelf_life_days=730, once_opened_shelf_life_days=2),
    )
    assert pouch.unopened_shelf_life_days == 730
    assert pouch.once_opened_shelf_life_days == 2


def test_an_item_has_no_former_ids_unless_it_absorbed_others() -> None:
    assert item("coriander", GroupId.FRESH_HERBS).former_ids == ()
    assert item("coriander", GroupId.FRESH_HERBS, former_ids=("cilantro",)).former_ids == ("cilantro",)


def test_a_former_id_cannot_be_blank() -> None:
    with pytest.raises(ValidationError):
        item("coriander", GroupId.FRESH_HERBS, former_ids=("",))


def test_former_ids_survive_the_stored_json_round_trip() -> None:
    original = item("coriander", GroupId.FRESH_HERBS, former_ids=("cilantro", "fresh-coriander"))

    assert CatalogueItem.model_validate_json(original.model_dump_json()) == original
