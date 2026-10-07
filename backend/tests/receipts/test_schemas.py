# backend/tests/receipts/test_schemas.py
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from glean.meal_plan.schemas import CompressedPantryItem
from glean.receipts.schemas import INGREDIENT_CATEGORY_FOOD_GROUPS, IngredientCategory, ParsedIngredient

# Frozen wire examples, consumed by Flutter through its real decoder and
# seeded SQLite repositories. Neither side parses the other side's source.
WIRE_ITEMS = json.loads((Path(__file__).parents[1] / "fixtures/receipt_taxonomy.json").read_text())["items"]
EXPECTED_CLIENT_TAXONOMY: dict[str, str] = {
    item["category"]: item["food_group"] for item in WIRE_ITEMS if item["category"] is not None
}


def _make_ingredient(**overrides: object) -> ParsedIngredient:
    defaults: dict[str, object] = {
        "name": "chicken breast",
        "quantity": 500,
        "unit": "g",
        "unit_price": None,
        "confidence": 0.9,
    }
    defaults.update(overrides)
    return ParsedIngredient(**defaults)


def test_taxonomy_matches_the_mobile_client_exactly() -> None:
    assert INGREDIENT_CATEGORY_FOOD_GROUPS == EXPECTED_CLIENT_TAXONOMY
    for wire in WIRE_ITEMS:
        # food_group is emitted, not accepted as an independent model input.
        parsed = ParsedIngredient.model_validate({key: value for key, value in wire.items() if key != "food_group"})
        assert parsed.model_dump(mode="json") == wire


def test_taxonomy_matches_ingredient_category_literal() -> None:
    """IngredientCategory is hand-written (ty can't check a dynamically-built Literal), so
    this guards it against drifting away from INGREDIENT_CATEGORY_FOOD_GROUPS."""
    assert set(get_args(IngredientCategory)) == set(INGREDIENT_CATEGORY_FOOD_GROUPS)


@pytest.mark.parametrize(("category", "expected_food_group"), EXPECTED_CLIENT_TAXONOMY.items())
def test_food_group_is_derived_deterministically_from_category(category: str, expected_food_group: str) -> None:
    ingredient = _make_ingredient(category=category)
    assert ingredient.food_group == expected_food_group


def test_null_category_yields_other_food_group() -> None:
    """Receipt proposals always emit a deterministic UI bucket, even with no category.
    Meal-plan inputs separately allow null food_group (#95)."""
    ingredient = _make_ingredient(category=None)
    assert ingredient.category is None
    assert ingredient.food_group == "other"


def test_category_defaults_to_null_and_food_group_defaults_to_other_when_omitted() -> None:
    ingredient = _make_ingredient()
    assert ingredient.category is None
    assert ingredient.food_group == "other"


def test_food_group_cannot_be_supplied_directly() -> None:
    """food_group is a computed field: the LLM cannot set it independently of category."""
    with pytest.raises(ValidationError):
        ParsedIngredient(
            name="chicken breast",
            quantity=500,
            unit="g",
            unit_price=None,
            confidence=0.9,
            category="red_meat",
            food_group="dairy",  # deliberately inconsistent with category
        )


def test_out_of_taxonomy_category_falls_back_to_null_category_and_other_food_group(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="glean"):
        ingredient = _make_ingredient(category="artisanal-cheese-boutique")

    assert ingredient.category is None
    assert ingredient.food_group == "other"


def test_out_of_taxonomy_category_fallback_is_observable(caplog: pytest.LogCaptureFixture) -> None:
    """The fallback must be logged so it can't silently become the common case."""
    with caplog.at_level(logging.WARNING, logger="glean"):
        _make_ingredient(category="artisanal-cheese-boutique")

    assert any("out-of-taxonomy" in record.message for record in caplog.records)


def test_in_taxonomy_category_does_not_trigger_fallback_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="glean"):
        _make_ingredient(category="red_meat")

    assert not any("out-of-taxonomy" in record.message for record in caplog.records)


def test_categorised_ingredient_satisfies_meal_plan_food_group_validation() -> None:
    """A derived receipt bucket remains valid for nullable meal-plan inputs."""
    ingredient = _make_ingredient(category="poultry")

    pantry_item = CompressedPantryItem(
        id=1,
        name=ingredient.name,
        quantity=ingredient.quantity,
        unit=ingredient.unit,
        food_group=ingredient.food_group,
        urgency_score=10.0,
    )

    assert pantry_item.food_group == "protein"


def test_uncategorised_ingredient_also_satisfies_meal_plan_food_group_validation() -> None:
    """The receipt fallback remains accepted by nullable meal-plan inputs."""
    ingredient = _make_ingredient(category=None)

    pantry_item = CompressedPantryItem(
        id=1,
        name=ingredient.name,
        quantity=ingredient.quantity,
        unit=ingredient.unit,
        food_group=ingredient.food_group,
        urgency_score=10.0,
    )

    assert pantry_item.food_group == "other"
