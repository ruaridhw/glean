"""The retailer adapters: hand-made pages in, products out. A block page is reported, never read as 'no nuts'."""

from __future__ import annotations

import pytest
from grocery_fixtures import (
    ACCESS_DENIED,
    CAPTCHA,
    FakePageSource,
    ocado_product,
    ocado_search,
)
from scripts.grocery_ground_truth import OcadoReader, ProductRef, ProductUnreadable, RetailerBlocked

SEARCH = "https://www.ocado.com/search?q=korma%20paste"


def test_ocado_search_lists_the_matching_products_in_order_without_tracking_parameters() -> None:
    source = FakePageSource(
        {
            SEARCH: ocado_search(
                ("Acme Korma Paste", "/products/acme-korma-paste/111"),
                ("Other Korma Sauce", "/products/other-korma-sauce/222"),
            )
        }
    )

    refs = OcadoReader(source).search("korma paste")

    assert refs == [
        ProductRef(
            retailer="ocado", name="Acme Korma Paste", url="https://www.ocado.com/products/acme-korma-paste/111"
        ),
        ProductRef(
            retailer="ocado", name="Other Korma Sauce", url="https://www.ocado.com/products/other-korma-sauce/222"
        ),
    ]


def test_ocado_read_returns_the_ingredients_and_the_allergy_advice_as_printed() -> None:
    ref = ProductRef(
        retailer="ocado", name="Acme Korma Paste", url="https://www.ocado.com/products/acme-korma-paste/111"
    )
    source = FakePageSource(
        {
            ref.url: ocado_product(
                "Acme Korma Paste",
                "Water, Ground Spices (12%), Desiccated Coconut (3%)",
                "Free From Gluten, May Contain Nuts <br> May contain Mustard and Nuts.",
            )
        }
    )

    product = OcadoReader(source).read(ref)

    assert product.name == "Acme Korma Paste"
    assert product.url == ref.url
    assert product.ingredients_text == "Water, Ground Spices (12%), Desiccated Coconut (3%)"
    assert product.allergy_text == "Free From Gluten, May Contain Nuts\nMay contain Mustard and Nuts."


def test_an_access_denied_search_is_reported_as_blocked_not_as_no_results() -> None:
    source = FakePageSource({SEARCH: ACCESS_DENIED})

    with pytest.raises(RetailerBlocked):
        OcadoReader(source).search("korma paste")


def test_a_captcha_page_in_place_of_a_product_is_reported_as_blocked_not_as_nut_free() -> None:
    ref = ProductRef(
        retailer="ocado", name="Acme Korma Paste", url="https://www.ocado.com/products/acme-korma-paste/111"
    )
    source = FakePageSource({ref.url: CAPTCHA})

    with pytest.raises(RetailerBlocked):
        OcadoReader(source).read(ref)


def test_a_product_page_without_an_ingredients_list_is_unreadable_not_an_empty_product() -> None:
    ref = ProductRef(retailer="ocado", name="Fresh Basil", url="https://www.ocado.com/products/fresh-basil/333")
    source = FakePageSource({ref.url: ocado_product("Fresh Basil", None)})

    with pytest.raises(ProductUnreadable):
        OcadoReader(source).read(ref)
