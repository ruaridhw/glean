"""Live end-to-end normalisation: the real decisions endpoint and the real naming LLM, against an in-memory catalogue.

Needs a real OPENROUTER_API_KEY in backend/.env. Run with:
    uv run pytest tests/integration/test_normalise_live_smoke.py -v --no-cov
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest

from glean.catalogue.groups import GroupId
from glean.catalogue.normalise import ItemKind, Status, normalise
from glean.catalogue.seed import load_seed
from glean.catalogue.store import InMemoryCatalogueStore
from glean.decisions import DecisionClient
from glean.llm import LLMRouter

if TYPE_CHECKING:
    from pydantic import SecretStr

pytestmark = pytest.mark.integration


@pytest.fixture
def services(openrouter_api_key: SecretStr) -> tuple[InMemoryCatalogueStore, DecisionClient, LLMRouter]:
    return (
        InMemoryCatalogueStore(load_seed().items),
        DecisionClient(api_key=openrouter_api_key, timeout_s=15.0),
        LLMRouter(api_key=openrouter_api_key),
    )


def test_real_names_match_create_and_stay_unmatched_then_repeat_from_the_catalogue(
    services: tuple[InMemoryCatalogueStore, DecisionClient, LLMRouter],
) -> None:
    store, decisions, llm_router = services
    names = ["Tesco Fresh Cut Coriander 30g", "Birthday Candles", "Dragon Fruit Each", "asdkjh"]

    coriander, candles, dragon_fruit, nonsense = normalise(
        names, store=store, decisions=decisions, llm_router=llm_router
    )

    assert (coriander.status, coriander.catalogue_item_id) == (Status.MATCHED, "coriander")
    assert coriander.ingredient_group is GroupId.FRESH_HERBS
    assert coriander.perishable is True
    assert (candles.status, candles.kind, candles.ingredient_group) == (
        Status.CREATED,
        ItemKind.HOUSEHOLD_ITEM,
        GroupId.HOUSEHOLD,
    )
    assert (dragon_fruit.status, dragon_fruit.kind, dragon_fruit.ingredient_group) == (
        Status.CREATED,
        ItemKind.INGREDIENT,
        GroupId.FRUIT,
    )
    assert (nonsense.status, nonsense.input) == (Status.UNMATCHED, "asdkjh")

    again = normalise(names, store=store, decisions=decisions, llm_router=llm_router)
    assert [r.source for r in again] == ["cache"] * 4


def test_twenty_new_names_finish_well_inside_the_request_limit(
    services: tuple[InMemoryCatalogueStore, DecisionClient, LLMRouter],
) -> None:
    store, decisions, llm_router = services
    names = [
        f"{brand} {thing}"
        for brand, thing in zip(
            ["Tesco Finest"] * 20,
            [
                "Yuzu Juice 100ml",
                "Kohlrabi Each",
                "Romanesco Each",
                "Fresh Turmeric Root 50g",
                "Galangal 40g",
                "Kaffir Lime Leaves 10g",
                "Curry Leaves 15g",
                "Tamarind Paste 200g",
                "Miso Paste 300g",
                "Nori Sheets 10 Pack",
                "Gochujang 500g",
                "Jackfruit Tin 400g",
                "Tempeh 250g",
                "Seitan 200g",
                "Bok Choy Baby 200g",
                "Salsify 300g",
                "Celeriac Each",
                "Fennel Bulb Each",
                "Radicchio Each",
                "Endive 2 Pack",
            ],
            strict=True,
        )
    ]

    started = time.monotonic()
    results = normalise(names, store=store, decisions=decisions, llm_router=llm_router)
    elapsed = time.monotonic() - started

    assert elapsed < 20
    assert all(r.status in {Status.MATCHED, Status.CREATED} for r in results)
