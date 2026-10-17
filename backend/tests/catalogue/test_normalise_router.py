from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from glean.catalogue.groups import Form, GroupId
from glean.catalogue.router import get_catalogue_store, get_decision_client
from glean.catalogue.seed import load_seed
from glean.catalogue.store import InMemoryCatalogueStore
from glean.config import Settings, get_settings
from glean.dependencies import get_llm_router
from glean.main import app
from tests.catalogue.normalise_fakes import FakeDecisions, FakeRouter, decision
from tests.catalogue.test_normalise import naming


@pytest.fixture
def store() -> InMemoryCatalogueStore:
    return InMemoryCatalogueStore(load_seed().items)


@pytest.fixture
def decisions() -> FakeDecisions:
    return FakeDecisions(script=lambda name, questions: decision(questions, group=GroupId.FRUIT, form=Form.FRESH))


@pytest.fixture
def router() -> FakeRouter:
    return FakeRouter(script=naming(**{"Dragon Fruit Each": "dragon fruit"}))


@pytest.fixture
def wired(
    client: TestClient, store: InMemoryCatalogueStore, decisions: FakeDecisions, router: FakeRouter
) -> TestClient:
    app.dependency_overrides[get_catalogue_store] = lambda: store
    app.dependency_overrides[get_decision_client] = lambda: decisions
    app.dependency_overrides[get_llm_router] = lambda: router
    return client


def test_normalise_requires_a_token(test_settings: Settings) -> None:
    app.dependency_overrides[get_settings] = lambda: test_settings
    try:
        response = TestClient(app).post("/catalogue/normalise", json={"names": ["coriander"]})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


def test_normalise_returns_one_result_per_name_in_order(wired: TestClient, auth_headers: dict[str, str]) -> None:
    response = wired.post(
        "/catalogue/normalise",
        headers=auth_headers,
        json={"names": ["cilantro", "Dragon Fruit Each"], "context": "receipt line"},
    )

    assert response.status_code == 200
    first, second = response.json()["results"]
    assert (first["input"], first["status"], first["source"], first["catalogue_item_id"]) == (
        "cilantro",
        "matched",
        "cache",
        "coriander",
    )
    assert (second["status"], second["source"], second["kind"], second["canonical_name"]) == (
        "created",
        "llm",
        "ingredient",
        "dragon fruit",
    )
    assert second["ingredient_group"] == "fruit"


def test_normalise_is_idempotent_and_the_repeat_makes_no_model_calls(
    wired: TestClient, auth_headers: dict[str, str], decisions: FakeDecisions, router: FakeRouter
) -> None:
    body = {"names": ["Dragon Fruit Each"]}
    first = wired.post("/catalogue/normalise", headers=auth_headers, json=body).json()["results"][0]
    calls = (len(decisions.calls), len(router.calls))

    second = wired.post("/catalogue/normalise", headers=auth_headers, json=body).json()["results"][0]

    assert second["catalogue_item_id"] == first["catalogue_item_id"]
    assert second["status"] == "matched"
    assert (len(decisions.calls), len(router.calls)) == calls


@pytest.mark.parametrize("names", [[f"item {n}" for n in range(21)], [], [""], ["   "]])
def test_normalise_rejects_more_than_twenty_or_blank_names(
    wired: TestClient, auth_headers: dict[str, str], names: list[str]
) -> None:
    response = wired.post("/catalogue/normalise", headers=auth_headers, json={"names": names})

    assert response.status_code == 422


def test_an_unconfigured_catalogue_is_a_clear_503(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post("/catalogue/normalise", headers=auth_headers, json={"names": ["coriander"]})

    assert response.status_code == 503
    assert "catalogue" in response.json()["detail"].lower()


def test_unmatched_text_comes_back_exactly_as_written(wired: TestClient, auth_headers: dict[str, str]) -> None:
    wired.app.dependency_overrides[get_llm_router] = lambda: FakeRouter(script=naming(**{"  asdkjh  ": None}))

    response = wired.post("/catalogue/normalise", headers=auth_headers, json={"names": ["  asdkjh  "]})

    [result] = response.json()["results"]
    assert (result["status"], result["input"], result["canonical_name"]) == ("unmatched", "  asdkjh  ", "  asdkjh  ")
