"""`ground_truth`: products read from a retailer become a per-ingredient verdict with evidence."""

from __future__ import annotations

from grocery_fixtures import (
    ACCESS_DENIED,
    FakePageSource,
    ocado_product,
    ocado_search,
    sainsburys_product,
    sainsburys_search,
)
from scripts.grocery_ground_truth import Frequency, OcadoReader, SainsburysReader, ground_truth

SEARCH = "https://www.ocado.com/search?q=korma%20paste"
SB_SEARCH = "https://www.sainsburys.co.uk/gol-ui/SearchResults/korma%20paste"


def _ocado_shop(*products: tuple[str, str | None, str | None]) -> FakePageSource:
    """An Ocado serving a search for 'korma paste' that lists the given (name, ingredients, allergy) products."""
    pages = {}
    rows = []
    for index, (name, ingredients, allergy) in enumerate(products):
        path = f"/products/item-{index}/{index}"
        rows.append((name, path))
        pages[f"https://www.ocado.com{path}"] = ocado_product(name, ingredients, allergy)
    pages[SEARCH] = ocado_search(*rows)
    return FakePageSource(pages)


def test_the_verdict_counts_products_and_says_usually_sometimes_or_rarely_with_the_evidence() -> None:
    shop = _ocado_shop(
        ("Acme Korma Paste", "Water, Cashew Nuts, Spices", "May contain Peanuts"),
        ("Bravo Korma Paste", "Water, Almonds, Spices", None),
        ("Corner Korma Paste", "Water, Desiccated Coconut", None),
        ("Delta Korma Paste", "Water, Spices", "May contain Mustard"),
    )

    verdict = ground_truth("korma paste", 4, readers=[OcadoReader(shop)])

    assert verdict.status == "resolved"
    assert verdict.retailer == "ocado"
    assert verdict.products_read == 4
    assert (verdict.tree_nut_products, verdict.tree_nut) == (2, Frequency.SOMETIMES)
    assert (verdict.peanut_products, verdict.peanut) == (0, Frequency.RARELY)
    assert (verdict.may_contain_products, verdict.may_contain) == (1, Frequency.SOMETIMES)
    assert {(e.kind, e.url) for e in verdict.evidence} == {
        ("ingredient", "https://www.ocado.com/products/item-0/0"),
        ("ingredient", "https://www.ocado.com/products/item-1/1"),
        ("may_contain", "https://www.ocado.com/products/item-0/0"),
    }
    assert "Cashew Nuts" in next(e.quote for e in verdict.evidence if e.url.endswith("/0") and e.kind == "ingredient")


def _sainsburys_shop() -> FakePageSource:
    url = "https://www.sainsburys.co.uk/gol-ui/product/sb-korma"
    return FakePageSource(
        {
            SB_SEARCH: sainsburys_search(("Sainsbury's Korma Paste", "sb-korma")),
            url: sainsburys_product("Sainsbury's Korma Paste", "Water, Spices, Cashew Nuts"),
        }
    )


def test_a_blocked_retailer_falls_back_to_the_next_one() -> None:
    ocado = FakePageSource({SEARCH: ACCESS_DENIED})

    verdict = ground_truth("korma paste", 3, readers=[OcadoReader(ocado), SainsburysReader(_sainsburys_shop())])

    assert (verdict.status, verdict.retailer) == ("resolved", "sainsburys")
    assert verdict.tree_nut == Frequency.USUALLY


def test_when_every_retailer_blocks_the_verdict_is_blocked_and_says_nothing_about_nuts() -> None:
    verdict = ground_truth(
        "korma paste",
        3,
        readers=[
            OcadoReader(FakePageSource({SEARCH: ACCESS_DENIED})),
            SainsburysReader(FakePageSource({SB_SEARCH: ACCESS_DENIED})),
        ],
    )

    assert verdict.status == "blocked"
    assert (verdict.tree_nut, verdict.peanut, verdict.may_contain) == (None, None, None)


def test_an_ingredient_no_retailer_stocks_is_not_found_rather_than_nut_free() -> None:
    verdict = ground_truth(
        "korma paste",
        3,
        readers=[OcadoReader(_ocado_shop()), SainsburysReader(FakePageSource({SB_SEARCH: sainsburys_search()}))],
    )

    assert verdict.status == "not_found"
    assert verdict.tree_nut is None
