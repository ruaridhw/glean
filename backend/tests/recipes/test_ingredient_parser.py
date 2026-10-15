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
        ("8Clove Garlic", "Garlic", 8, "clove", None),
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


@pytest.mark.parametrize(
    ("raw", "expected_name", "expected_quantity", "expected_unit"),
    [
        ("1 knob butter", "Butter", 1, "knob"),
        ("1 pinch of salt", "Salt", 1, "pinch"),
        ("2 Dashes Worcestershire sauce", "Worcestershire sauce", 2, "dash"),
        ("1 handful coriander", "Coriander", 1, "handful"),
        ("3 sprigs thyme", "Thyme", 3, "sprig"),
        ("4 cloves garlic, crushed", "Garlic, crushed", 4, "clove"),
        ("1 bunch of spring onions", "Spring onions", 1, "bunch"),
        ("1 thumb of ginger", "Ginger", 2.5, "cm"),
        ("2 thumbs ginger", "Ginger", 5, "cm"),
        ("2 slices bread", "Bread", 2, "pcs"),
        ("4 rashers streaky bacon", "Streaky bacon", 4, "pcs"),
    ],
)
def test_parse_ingredient_text_gives_vague_measures_named_units_without_leaking_the_word(
    raw: str, expected_name: str, expected_quantity: float, expected_unit: str
) -> None:
    parsed = parse_ingredient_text(raw)

    assert parsed is not None
    assert parsed.canonical_name == expected_name
    assert parsed.quantity == pytest.approx(expected_quantity)
    assert parsed.unit == expected_unit


@pytest.mark.parametrize(
    ("raw", "expected_name", "expected_quantity", "expected_unit"),
    [
        # A US cup of butter weighs about 227 g.
        ("1/4 cup butter", "Butter", 56.75, "g"),
        ("1 cup butter, melted", "Butter, melted", 227, "g"),
        ("2 cups plain flour", "Plain flour", 280.6, "g"),
        ("1 cup milk", "Milk", 236.59, "ml"),
        ("1 cup of vegetable stock", "Vegetable stock", 236.59, "ml"),
        ("1 cup chickpeas", "Chickpeas", 1, "cup"),
        ("2 Cups peanut butter", "Peanut butter", 2, "cup"),
    ],
)
def test_parse_ingredient_text_converts_cups_by_density_then_to_ml_else_keeps_the_cup(
    raw: str, expected_name: str, expected_quantity: float, expected_unit: str
) -> None:
    parsed = parse_ingredient_text(raw)

    assert parsed is not None
    assert parsed.canonical_name == expected_name
    assert parsed.quantity == pytest.approx(expected_quantity, rel=1e-2)
    assert parsed.unit == expected_unit


@pytest.mark.parametrize(
    ("raw", "expected_name", "expected_quantity", "expected_unit", "expected_preparation"),
    [
        ("1 x 400g tin chopped tomatoes", "Chopped tomatoes", 400, "g", "1 tin"),
        ("2 x 400g tins chickpeas", "Chickpeas", 800, "g", "2 tins"),
        ("1 (4 ounce) can chopped green chiles", "Chopped green chiles", 113.4, "g", "1 can"),
        ("2 (14 ounce) cans coconut milk", "Coconut milk", 793.8, "g", "2 cans"),
    ],
)
def test_parse_ingredient_text_reads_spaced_and_us_style_sized_packages(
    raw: str,
    expected_name: str,
    expected_quantity: float,
    expected_unit: str,
    expected_preparation: str | None,
) -> None:
    parsed = parse_ingredient_text(raw)

    assert parsed is not None
    assert parsed.canonical_name == expected_name
    assert parsed.quantity == pytest.approx(expected_quantity)
    assert parsed.unit == expected_unit
    assert parsed.preparation == expected_preparation


@pytest.mark.parametrize(
    ("raw", "expected_name", "expected_quantity", "expected_unit"),
    [
        ("1 cup coconut milk", "Coconut milk", 236.59, "ml"),
        ("2 cups chicken stock", "Chicken stock", 473.18, "ml"),
        ("1 cup freshly squeezed orange juice", "Freshly squeezed orange juice", 236.59, "ml"),
        ("1/2 cup extra virgin olive oil", "Extra virgin olive oil", 118.3, "ml"),
        ("1 cup soy sauce", "Soy sauce", 236.59, "ml"),
        ("1 cup milk powder", "Milk powder", 1, "cup"),
        ("1 cup cream cheese", "Cream cheese", 1, "cup"),
        ("1 cup grated cheddar", "Grated cheddar", 1, "cup"),
        ("1 cup rolled oats", "Rolled oats", 97, "g"),
        ("1 cup honey", "Honey", 336, "g"),
    ],
)
def test_parse_ingredient_text_treats_a_cup_of_a_liquid_as_ml_and_only_unknown_solids_stay_cups(
    raw: str, expected_name: str, expected_quantity: float, expected_unit: str
) -> None:
    parsed = parse_ingredient_text(raw)

    assert parsed is not None
    assert parsed.canonical_name == expected_name
    assert parsed.quantity == pytest.approx(expected_quantity, rel=1e-2)
    assert parsed.unit == expected_unit
