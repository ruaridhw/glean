from __future__ import annotations

import pytest

from glean.recipes.ingredient_parser import parse_ingredient_text


@pytest.mark.parametrize(
    ("raw", "expected_name", "expected_quantity", "expected_unit", "expected_preparation"),
    [
        ("240 grams British Beef Mince", "British Beef Mince", 240, "g", None),
        ("2 unit(s) Garlic Clove", "Garlic Clove", 2, "pcs", None),
        ("1 sachet(s) Central American Style Spice Mix", "Central American Style Spice Mix", 1, "units", "1 sachet"),
        ("3tbsp Al'Fez Harissa Paste", "Al'Fez Harissa Paste", 3, "tbsp", None),
        ("8 Boneless Skinless Chicken Thigh", "Boneless Skinless Chicken Thigh", 8, "pcs", None),
        ("1x 460g Jar Roasted Red Peppers", "Roasted Red Peppers", 460, "g", "1 jar"),
        ("2x 400g Can Chickpeas", "Chickpeas", 800, "g", "2 cans"),
        ("1x 1.4kg Whole Chicken", "Whole Chicken", 1400, "g", None),
        ("Bacon lardons (100g)", "Bacon lardons", 100, "g", None),
        ("Ground cumin (1tsp) x2", "Ground cumin", 2, "tsp", None),
        ("Garlic clove x3", "Garlic clove", 3, "pcs", None),
        ("1/2 tsp dried chilli flakes", "Dried chilli flakes", 0.5, "tsp", None),
        ("2 pouches Microwave Rice", "Microwave Rice", 2, "units", "2 pouches"),
        ("1x 250g Pouch Cooked Lentils", "Cooked Lentils", 250, "g", "1 pouch"),
        ("8Clove Garlic", "Clove Garlic", 8, "pcs", None),
        ("3Stick Celery", "Celery", 3, "pcs", None),
        ("3cm Ginger", "Ginger", 3, "cm", None),
        ("0.5Stick Cinnamon", "Cinnamon", 0.5, "pcs", None),
        ("2Pouch Microwaveable Basmati Rice", "Microwaveable Basmati Rice", 2, "units", "2 pouches"),
        ("1tabtbsp Sesame Seeds", "Sesame Seeds", 1, "tbsp", None),
        ("Tenderstem® Broccoli", "Tenderstem Broccoli", 1, "pcs", None),
        ("Tomato", "Tomato", 1, "pcs", None),
    ],
)
def test_parse_ingredient_text_extracts_quantity_unit_name_and_package(
    raw: str,
    expected_name: str,
    expected_quantity: float,
    expected_unit: str,
    expected_preparation: str | None,
) -> None:
    parsed = parse_ingredient_text(raw)

    assert parsed is not None
    assert parsed.api_ingredient_id is None
    assert parsed.canonical_name == expected_name
    assert parsed.quantity == pytest.approx(expected_quantity)
    assert parsed.unit == expected_unit
    assert parsed.preparation == expected_preparation


@pytest.mark.parametrize(
    ("raw", "expected_name", "expected_quantity", "expected_unit"),
    [
        ("8 oz cheddar", "Cheddar", 226.8, "g"),
        ("2 ounces grated parmesan", "Grated parmesan", 56.7, "g"),
        ("1 lb minced beef", "Minced beef", 453.6, "g"),
        ("8 fl oz double cream", "Double cream", 236.56, "ml"),
        ("1 pint milk", "Milk", 568, "ml"),
        ("2 pints vegetable stock", "Vegetable stock", 1136, "ml"),
    ],
)
def test_parse_ingredient_text_converts_imperial_measures_to_metric(
    raw: str, expected_name: str, expected_quantity: float, expected_unit: str
) -> None:
    parsed = parse_ingredient_text(raw)

    assert parsed is not None
    assert parsed.canonical_name == expected_name
    assert parsed.quantity == pytest.approx(expected_quantity, rel=1e-3)
    assert parsed.unit == expected_unit
    assert parsed.preparation is None


@pytest.mark.parametrize(
    ("raw", "expected_name", "expected_quantity", "expected_unit"),
    [
        ("1 stick butter", "Butter", 113, "g"),
        ("2 sticks unsalted butter", "Unsalted butter", 226, "g"),
        ("1 stick peanut butter", "Peanut butter", 1, "pcs"),
        ("2 sticks lemongrass", "Lemongrass", 2, "pcs"),
        ("1 cinnamon stick", "Cinnamon stick", 1, "pcs"),
        ("2 sticks celery, chopped", "Celery, chopped", 2, "pcs"),
    ],
)
def test_parse_ingredient_text_resolves_a_stick_of_butter_to_grams_and_other_sticks_to_pieces(
    raw: str, expected_name: str, expected_quantity: float, expected_unit: str
) -> None:
    parsed = parse_ingredient_text(raw)

    assert parsed is not None
    assert parsed.canonical_name == expected_name
    assert parsed.quantity == pytest.approx(expected_quantity)
    assert parsed.unit == expected_unit
