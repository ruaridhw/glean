"""Live smoke test: reads real Ocado product pages in a headless browser.

Skipped unless GLEAN_LIVE_RETAILER=1 (it needs the `audit` dependency group and its Chromium build, and
makes a handful of polite, read-only requests)::

    GLEAN_LIVE_RETAILER=1 uv run --group audit pytest tests/integration/test_grocery_ground_truth_live.py -v
"""

from __future__ import annotations

import os

import pytest
from scripts.grocery_ground_truth import OcadoReader, RetailerBlocked
from scripts.grocery_ground_truth.browser import PlaywrightPageSource

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("GLEAN_LIVE_RETAILER") != "1", reason="set GLEAN_LIVE_RETAILER=1 to read Ocado"),
]


def test_a_real_ocado_product_is_read_with_its_ingredients() -> None:
    pytest.importorskip("playwright")
    with PlaywrightPageSource() as source:
        reader = OcadoReader(source)
        try:
            refs = reader.search("korma paste")
            assert refs, "Ocado listed no products for 'korma paste'"
            product = reader.read(refs[0])
        except RetailerBlocked:
            pytest.skip("Ocado served a block page")

    assert product.ingredients_text
    assert product.url.startswith("https://www.ocado.com/products/")
