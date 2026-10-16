"""The deterministic allergen classifier: plain parsing of a retailer's ingredients and allergy text."""

from __future__ import annotations

from scripts.grocery_ground_truth import Product, classify


def _product(ingredients: str, allergy: str = "") -> Product:
    return Product(
        retailer="ocado",
        name="Test paste",
        url="https://example.test/products/test-paste/1",
        ingredients_text=ingredients,
        allergy_text=allergy,
    )


def test_coconut_is_not_a_tree_nut() -> None:
    facts = classify(_product("Water, Desiccated Coconut (3%), Coconut Cream, Nutmeg, Butternut Squash"))

    assert facts.tree_nut_ingredients == []
    assert facts.peanut_ingredients == []


def test_pine_nuts_count_as_a_tree_nut_ingredient() -> None:
    facts = classify(_product("Basil, Pine Nuts (8%), Parmesan, Olive Oil"))

    assert facts.tree_nut_ingredients == ["pine nuts"]


def test_peanut_and_tree_nut_ingredients_are_reported_separately() -> None:
    facts = classify(_product("Roasted Peanuts (40%), Cashew Nuts, Sugar, Groundnut Oil"))

    assert facts.peanut_ingredients == ["peanuts", "groundnut"]
    assert facts.tree_nut_ingredients == ["cashew nuts"]


def test_a_may_contain_warning_is_kept_apart_from_the_ingredients() -> None:
    facts = classify(_product("Water, Spices, Desiccated Coconut", "May contain Mustard, Peanuts and Nuts."))

    assert facts.tree_nut_ingredients == []
    assert facts.peanut_ingredients == []
    assert (facts.may_contain_tree_nut, facts.may_contain_peanut) == (True, True)
    assert facts.may_contain_quote == "May contain Mustard, Peanuts and Nuts"


def test_a_may_contain_warning_for_one_kind_does_not_flag_the_other() -> None:
    facts = classify(_product("Water, Spices", "Free From Gluten, May Contain Mustard, May Contain Peanuts"))

    assert (facts.may_contain_tree_nut, facts.may_contain_peanut) == (False, True)


def test_a_warning_that_names_no_nuts_is_not_a_nut_warning() -> None:
    facts = classify(
        _product("Water, Creamed Coconut", "May Contain Sesame. Not suitable for those with a Sesame allergy.")
    )

    assert (facts.may_contain_tree_nut, facts.may_contain_peanut, facts.may_contain_quote) == (False, False, None)


def test_a_warning_printed_inside_the_ingredients_text_does_not_count_as_an_ingredient() -> None:
    facts = classify(_product("Tomato, Basil, Salt. May contain Almonds."))

    assert facts.tree_nut_ingredients == []
    assert facts.may_contain_tree_nut is True
