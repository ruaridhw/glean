"""`ground_truth`: products read from a retailer become a per-ingredient verdict with evidence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from urllib.parse import quote

import pytest
from grocery_fixtures import (
    ACCESS_DENIED,
    FakePageSource,
    ocado_product,
    ocado_search,
    sainsburys_product,
    sainsburys_search,
)
from scripts.grocery_ground_truth import (
    ContainsPolicy,
    Frequency,
    IngredientVerdict,
    OcadoReader,
    ProductCache,
    SainsburysReader,
    ground_truth,
    is_unsafe,
)

if TYPE_CHECKING:
    from pathlib import Path

SEARCH = "https://www.ocado.com/search?q=korma%20paste"
SB_SEARCH = "https://www.sainsburys.co.uk/gol-ui/SearchResults/korma%20paste"


def _ocado_shop(*products: tuple[str, str | None, str | None], query: str = "korma paste") -> FakePageSource:
    """An Ocado serving a search for `query` that lists the given (name, ingredients, allergy) products."""
    pages = {}
    rows = []
    for index, (name, ingredients, allergy) in enumerate(products):
        path = f"/products/item-{index}/{index}"
        rows.append((name, path))
        pages[f"https://www.ocado.com{path}"] = ocado_product(name, ingredients, allergy)
    pages[f"https://www.ocado.com/search?q={quote(query)}"] = ocado_search(*rows)
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
        ("ingredients", "https://www.ocado.com/products/item-0/0"),
        ("ingredients", "https://www.ocado.com/products/item-1/1"),
        ("ingredients", "https://www.ocado.com/products/item-2/2"),
        ("ingredients", "https://www.ocado.com/products/item-3/3"),
        ("may_contain", "https://www.ocado.com/products/item-0/0"),
    }
    quoted = {e.url: e for e in verdict.evidence if e.kind == "ingredients"}
    assert "Cashew Nuts" in quoted["https://www.ocado.com/products/item-0/0"].quote
    assert quoted["https://www.ocado.com/products/item-0/0"].allergens == ["cashew nuts"]
    assert quoted["https://www.ocado.com/products/item-3/3"].allergens == []


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


def test_search_hits_that_are_not_the_ingredient_asked_for_are_not_read() -> None:
    shop = _ocado_shop(
        ("Acme Korma Paste", "Water, Cashew Nuts", None),
        ("Acme Butter Chicken Paste", "Water, Spices", None),
    )

    verdict = ground_truth("korma paste", 5, readers=[OcadoReader(shop)])

    assert verdict.products_read == 1
    assert "https://www.ocado.com/products/item-1/1" not in shop.requested


def test_a_cached_re_run_makes_no_browser_requests(tmp_path: Path) -> None:
    shop = _ocado_shop(("Acme Korma Paste", "Water, Cashew Nuts", None))
    cache = ProductCache(tmp_path)
    first = ground_truth("korma paste", 3, readers=[OcadoReader(shop)], cache=cache)
    requests_after_first_run = len(shop.requested)

    second = ground_truth("korma paste", 3, readers=[OcadoReader(shop)], cache=ProductCache(tmp_path))

    assert requests_after_first_run > 0
    assert len(shop.requested) == requests_after_first_run
    assert second == first


def test_a_cache_entry_older_than_the_refetch_period_is_read_again(tmp_path: Path) -> None:
    shop = _ocado_shop(("Acme Korma Paste", "Water, Cashew Nuts", None))
    start = datetime(2026, 10, 16, tzinfo=UTC)
    ground_truth("korma paste", 3, readers=[OcadoReader(shop)], cache=ProductCache(tmp_path, clock=lambda: start))
    requests_after_first_run = len(shop.requested)
    later = start + timedelta(days=31)

    ground_truth(
        "korma paste",
        3,
        readers=[OcadoReader(shop)],
        cache=ProductCache(tmp_path, max_age=timedelta(days=30), clock=lambda: later),
    )

    assert len(shop.requested) == 2 * requests_after_first_run


def test_a_blocked_read_is_not_cached_so_the_next_run_tries_again(tmp_path: Path) -> None:
    blocked = FakePageSource({SEARCH: ACCESS_DENIED})
    ground_truth("korma paste", 3, readers=[OcadoReader(blocked)], cache=ProductCache(tmp_path))

    shop = _ocado_shop(("Acme Korma Paste", "Water, Cashew Nuts", None))
    verdict = ground_truth("korma paste", 3, readers=[OcadoReader(shop)], cache=ProductCache(tmp_path))

    assert verdict.status == "resolved"


def _shelf(
    *,
    tree_nut: Frequency = Frequency.RARELY,
    peanut: Frequency = Frequency.RARELY,
    may_contain: Frequency = Frequency.RARELY,
) -> IngredientVerdict:
    return IngredientVerdict(
        ingredient="x",
        status="resolved",
        retailer="ocado",
        products_read=7,
        tree_nut=tree_nut,
        peanut=peanut,
        may_contain=may_contain,
    )


def test_by_default_an_ingredient_contains_a_nut_only_when_most_products_list_it() -> None:
    assert is_unsafe(_shelf(tree_nut=Frequency.USUALLY)) is True
    assert is_unsafe(_shelf(peanut=Frequency.USUALLY)) is True
    assert is_unsafe(_shelf(tree_nut=Frequency.SOMETIMES, peanut=Frequency.SOMETIMES)) is False
    assert is_unsafe(_shelf()) is False


def test_by_default_a_may_contain_warning_never_counts() -> None:
    assert is_unsafe(_shelf(may_contain=Frequency.USUALLY)) is False


def test_the_policy_can_count_some_products_or_a_warning_as_containing_the_allergen() -> None:
    cautious = ContainsPolicy(minimum=Frequency.SOMETIMES)
    warned = ContainsPolicy(may_contain_counts=True)

    assert is_unsafe(_shelf(tree_nut=Frequency.SOMETIMES), cautious) is True
    assert is_unsafe(_shelf(may_contain=Frequency.SOMETIMES), warned) is False
    assert is_unsafe(_shelf(may_contain=Frequency.USUALLY), warned) is True


def test_an_unresolved_ingredient_is_neither_safe_nor_unsafe() -> None:
    blocked = IngredientVerdict(ingredient="korma paste", status="blocked")

    assert is_unsafe(blocked) is None


def test_a_recipe_that_names_a_brand_is_judged_by_that_brands_products_alone() -> None:
    shop = _ocado_shop(
        ("Patak's Korma Spice Paste", "Water, Spices, Coconut", None),
        ("Acme Korma Paste", "Water, Cashew Nuts", None),
        ("Bravo Korma Paste", "Water, Almonds", None),
        query="pataks korma paste",
    )

    named = ground_truth("pataks korma paste", 5, readers=[OcadoReader(shop)])

    assert (named.products_read, named.tree_nut) == (1, Frequency.RARELY)
    assert is_unsafe(named) is False


def test_a_verdict_with_no_nut_anywhere_still_cites_every_product_it_read() -> None:
    shop = _ocado_shop(
        ("Acme Korma Paste", "Water, Spices", None),
        ("Bravo Korma Paste", "Water, Desiccated Coconut", None),
        ("Corner Korma Paste", "Water, Turmeric", None),
    )

    verdict = ground_truth("korma paste", 3, readers=[OcadoReader(shop)])

    assert verdict.tree_nut == Frequency.RARELY
    assert [(e.url, e.quote) for e in verdict.evidence] == [
        ("https://www.ocado.com/products/item-0/0", "Water, Spices"),
        ("https://www.ocado.com/products/item-1/1", "Water, Desiccated Coconut"),
        ("https://www.ocado.com/products/item-2/2", "Water, Turmeric"),
    ]


def test_pages_that_could_not_be_read_stop_a_thin_sample_from_becoming_a_safe_verdict() -> None:
    shop = _ocado_shop(
        ("Acme Korma Paste", "Water, Spices", None),
        ("Bravo Korma Paste", None, None),
        ("Corner Korma Paste", None, None),
    )

    verdict = ground_truth("korma paste", 3, readers=[OcadoReader(shop)])

    assert verdict.status == "insufficient"
    assert (verdict.products_read, verdict.products_unread) == (1, 2)
    assert (verdict.tree_nut, verdict.peanut) == (None, None)
    assert is_unsafe(verdict) is None
    assert {e.kind for e in verdict.evidence} == {"ingredients", "unread"}


def test_an_unread_product_that_could_not_change_the_majority_does_not_stop_a_verdict() -> None:
    shop = _ocado_shop(
        ("Acme Korma Paste", "Water, Spices", None),
        ("Bravo Korma Paste", "Water, Turmeric", None),
        ("Corner Korma Paste", "Water, Cumin", None),
        ("Delta Korma Paste", "Water, Fennel", None),
        ("Echo Korma Paste", None, None),
    )

    verdict = ground_truth("korma paste", 5, readers=[OcadoReader(shop)])

    assert (verdict.status, verdict.products_read, verdict.products_unread) == ("resolved", 4, 1)


def test_an_unread_product_that_could_flip_the_majority_makes_the_verdict_insufficient() -> None:
    shop = _ocado_shop(
        ("Acme Korma Paste", "Water, Cashew Nuts", None),
        ("Bravo Korma Paste", "Water, Spices", None),
        ("Corner Korma Paste", "Water, Spices", None),
        ("Delta Korma Paste", None, None),
        ("Echo Korma Paste", None, None),
    )

    assert ground_truth("korma paste", 5, readers=[OcadoReader(shop)]).status == "insufficient"


def test_a_shelf_with_only_a_few_matching_products_still_resolves_when_all_are_read() -> None:
    shop = _ocado_shop(("Acme Korma Paste", "Water, Spices", None), ("Bravo Korma Paste", "Water, Cumin", None))

    assert ground_truth("korma paste", 5, readers=[OcadoReader(shop)]).status == "resolved"


def test_a_partial_read_is_not_cached_so_the_next_run_reads_again(tmp_path: Path) -> None:
    partial = _ocado_shop(("Acme Korma Paste", "Water, Spices", None), ("Bravo Korma Paste", None, None))
    ground_truth("korma paste", 3, readers=[OcadoReader(partial)], cache=ProductCache(tmp_path))
    whole = _ocado_shop(("Acme Korma Paste", "Water, Spices", None), ("Bravo Korma Paste", "Water, Cumin", None))

    verdict = ground_truth("korma paste", 3, readers=[OcadoReader(whole)], cache=ProductCache(tmp_path))

    assert (verdict.status, verdict.products_read) == ("resolved", 2)
    assert whole.requested


@pytest.mark.parametrize(
    ("query", "hit"),
    [
        ("curry paste", "Acme Almond Butter"),
        ("korma paste", "Acme Korma Ready Meal"),
        ("korma paste", "Acme Korma Pie"),
        ("tomato paste", "Acme Tomato Sauce"),
        ("curry paste", "Acme Tomato Paste"),
    ],
)
def test_a_search_hit_of_another_kind_of_product_is_not_read(query: str, hit: str) -> None:
    shop = _ocado_shop((hit, "Cashew Nuts, Almonds", None), query=query)

    verdict = ground_truth(query, 3, readers=[OcadoReader(shop)])

    assert verdict.status == "not_found"
    assert not any("/products/" in url for url in shop.requested)


def test_only_whole_words_of_the_right_kind_match() -> None:
    shop = _ocado_shop(
        ("Acme Madras Curry Paste", "Water, Spices", None),
        ("Bravo Korma Spice Paste", "Water, Spices", None),
        ("Corner Curry Pastes Multipack", "Water, Spices", None),
        ("Delta Curryleaf Paste", "Water, Spices", None),
        query="curry paste",
    )

    verdict = ground_truth("curry paste", 5, readers=[OcadoReader(shop)])

    assert [e.url for e in verdict.evidence] == [
        "https://www.ocado.com/products/item-0/0",
        "https://www.ocado.com/products/item-2/2",
    ]


def test_a_cached_fallback_result_makes_no_browser_requests_not_even_to_the_first_retailer(tmp_path: Path) -> None:
    def shops() -> tuple[FakePageSource, FakePageSource]:
        return FakePageSource({SEARCH: ACCESS_DENIED}), _sainsburys_shop()

    ocado, sainsburys = shops()
    first = ground_truth(
        "korma paste", 3, readers=[OcadoReader(ocado), SainsburysReader(sainsburys)], cache=ProductCache(tmp_path)
    )
    ocado_again, sainsburys_again = shops()

    second = ground_truth(
        "korma paste",
        3,
        readers=[OcadoReader(ocado_again), SainsburysReader(sainsburys_again)],
        cache=ProductCache(tmp_path),
    )

    assert first.retailer == "sainsburys"
    assert second == first
    assert ocado_again.requested == []
    assert sainsburys_again.requested == []


@pytest.mark.parametrize(
    ("query", "hit"),
    [
        ("tomato paste", "Acme Double Concentrate Tomato Pur\u00e9e"),
        ("tomato paste", "Acme Italian Tomato Puree"),
        ("vegetable stock paste", "Acme Vegetable Stock Pot"),
        ("tandoori paste", "Acme Tandoori Spice Marinade"),
    ],
)
def test_a_product_that_is_the_same_kind_of_thing_under_another_name_is_read(query: str, hit: str) -> None:
    shop = _ocado_shop((hit, "Water, Spices", None), query=query)

    assert ground_truth(query, 3, readers=[OcadoReader(shop)]).products_read == 1
