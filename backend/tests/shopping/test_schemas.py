from __future__ import annotations

import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ValidationError

from glean.receipts.schemas import INGREDIENT_CATEGORY_FOOD_GROUPS
from glean.shopping.schemas import ShoppingParseResponse, ShoppingProposalItem, ShoppingUnit


def _item(**overrides: object) -> dict[str, object]:
    return {"name": "milk", "quantity": 1, "unit": "bottle", "category": "dairy", "confidence": 0.9, **overrides}


@pytest.mark.parametrize("unit", ["g", "kg", "ml", "l", "units", "pack", "bottle", "bag", "box"])
def test_shopping_item_accepts_every_practical_shopping_unit(unit: str) -> None:
    assert ShoppingProposalItem.model_validate(_item(unit=unit)).unit == unit


@pytest.mark.parametrize("unit", ["tbsp", "cups", "bunch", "", "Bottle "])
def test_shopping_item_rejects_units_outside_the_vocabulary(unit: str) -> None:
    with pytest.raises(ValidationError):
        ShoppingProposalItem.model_validate(_item(unit=unit))


def test_shopping_item_serialises_unit_as_its_plain_string() -> None:
    assert ShoppingProposalItem.model_validate(_item(unit="pack")).model_dump(mode="json")["unit"] == "pack"


def test_model_is_constrained_to_the_unit_vocabulary_by_the_schema_it_receives() -> None:
    schema = convert_to_openai_tool(ShoppingParseResponse)["function"]["parameters"]
    item_properties = schema["properties"]["items"]["items"]["properties"]

    assert item_properties["unit"]["enum"] == [unit.value for unit in ShoppingUnit]


def test_unit_price_defaults_to_null_for_shopping_items() -> None:
    assert ShoppingProposalItem.model_validate(_item()).unit_price is None


def test_a_price_the_model_supplies_is_dropped_not_trusted() -> None:
    item = ShoppingProposalItem.model_validate(_item(unit_price=2.49))

    assert item.unit_price is None
    assert item.model_dump()["unit_price"] is None


def test_category_and_confidence_constraints_travel_in_the_schema_the_model_receives() -> None:
    schema = convert_to_openai_tool(ShoppingParseResponse)["function"]["parameters"]
    item_properties = schema["properties"]["items"]["items"]["properties"]

    category_options = item_properties["category"]["anyOf"][0]["enum"]
    assert category_options == list(INGREDIENT_CATEGORY_FOOD_GROUPS)
    assert (item_properties["confidence"]["minimum"], item_properties["confidence"]["maximum"]) == (0.0, 1.0)
