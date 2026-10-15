from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from glean.catalogue.groups import GROUPS, Form, GroupId
from glean.catalogue.models import CatalogueItem, Source
from glean.catalogue.router import get_catalogue_store
from glean.catalogue.seed import load_seed
from glean.catalogue.store import InMemoryCatalogueStore
from glean.config import Settings, get_settings
from glean.main import app


@pytest.fixture
def store() -> InMemoryCatalogueStore:
    return InMemoryCatalogueStore(load_seed().items)


@pytest.fixture
def wired(client: TestClient, store: InMemoryCatalogueStore) -> TestClient:
    app.dependency_overrides[get_catalogue_store] = lambda: store
    return client


def test_catalogue_sync_requires_a_token(test_settings: Settings) -> None:
    app.dependency_overrides[get_settings] = lambda: test_settings
    try:
        response = TestClient(app).get("/catalogue", params={"since": 0})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


def test_since_zero_is_the_full_catalogue(wired: TestClient, auth_headers: dict[str, str]) -> None:
    response = wired.get("/catalogue", params={"since": 0}, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert {item["id"] for item in body["items"]} == {item.id for item in load_seed().items}
    assert body["version"] == len(load_seed().items)
    assert {group["id"] for group in body["groups"]} == {group.value for group in GroupId}


def test_an_item_is_sent_with_its_group_form_and_own_overrides_but_not_its_aliases(
    wired: TestClient, auth_headers: dict[str, str]
) -> None:
    items = {item["id"]: item for item in wired.get("/catalogue", headers=auth_headers).json()["items"]}

    onion = items["onion"]
    assert (onion["name"], onion["group"], onion["form"], onion["source"]) == (
        "onion",
        "onions_and_garlic",
        "fresh",
        "seed",
    )
    assert set(onion["overrides"]) == {
        "tracking_mode",
        "stock_unit",
        "unopened_shelf_life_days",
        "once_opened_shelf_life_days",
    }
    assert "aliases" not in onion


def test_every_name_of_an_item_is_sent_as_an_alias_keyed_for_lookup(
    wired: TestClient, auth_headers: dict[str, str]
) -> None:
    aliases = wired.get("/catalogue", params={"since": 0}, headers=auth_headers).json()["aliases"]

    onion = [alias for alias in aliases if alias["item_id"] == "onion"]
    assert {alias["key"] for alias in onion} >= {"onion", "brown onion", "yellow onion", "cooking onion"}
    assert {"onion", "brown onion"} <= {alias["name"] for alias in onion}


def test_a_group_is_sent_with_the_defaults_its_items_take(wired: TestClient, auth_headers: dict[str, str]) -> None:
    groups = {group["id"]: group for group in wired.get("/catalogue", headers=auth_headers).json()["groups"]}

    spices = groups["spices"]
    rules = GROUPS[GroupId.SPICES]
    assert spices["name"] == "Spices"
    assert spices["tracking_mode"] == rules.tracking_mode.value
    assert spices["allowed_forms"] == ["not_applicable"]
    assert spices["unopened_shelf_life_days"] == {"not_applicable": 365}
    herbs = groups["leafy_greens"]
    assert herbs["once_opened_shelf_life_days"]["fresh"] == 3
    assert herbs["stock_unit"] is None


def test_a_group_with_no_shelf_life_is_sent_as_null_not_zero_and_an_edible_baby_item_keeps_its_own(
    wired: TestClient, auth_headers: dict[str, str]
) -> None:
    body = wired.get("/catalogue", headers=auth_headers).json()
    groups = {group["id"]: group for group in body["groups"]}
    items = {item["id"]: item for item in body["items"]}

    assert groups["household"]["unopened_shelf_life_days"] == {"not_applicable": None}
    assert groups["household"]["once_opened_shelf_life_days"] == {"not_applicable": None}
    assert groups["baby"]["unopened_shelf_life_days"] == {"not_applicable": None}
    assert items["baby-formula-milk-powder"]["overrides"]["unopened_shelf_life_days"] == 730
    assert items["toilet-roll"]["overrides"]["unopened_shelf_life_days"] is None


def test_a_second_sync_with_no_changes_transfers_no_items(wired: TestClient, auth_headers: dict[str, str]) -> None:
    first = wired.get("/catalogue", params={"since": 0}, headers=auth_headers).json()

    second = wired.get("/catalogue", params={"since": first["version"]}, headers=auth_headers).json()

    assert second["items"] == []
    assert second["aliases"] == []
    assert second["version"] == first["version"]


def test_a_provisional_item_created_after_a_sync_arrives_with_the_next_one(
    wired: TestClient, auth_headers: dict[str, str], store: InMemoryCatalogueStore
) -> None:
    held = wired.get("/catalogue", params={"since": 0}, headers=auth_headers).json()["version"]
    store.create_provisional("Dragon Fruit", GroupId.FRUIT, Form.FRESH, aliases=("pitaya",))

    body = wired.get("/catalogue", params={"since": held}, headers=auth_headers).json()

    assert [(item["id"], item["source"]) for item in body["items"]] == [("dragon-fruit", "llm")]
    assert {(alias["key"], alias["item_id"]) for alias in body["aliases"]} == {
        ("dragon fruit", "dragon-fruit"),
        ("pitaya", "dragon-fruit"),
    }
    assert body["version"] == held + 1


def test_a_learned_alias_reaches_the_next_sync(
    wired: TestClient, auth_headers: dict[str, str], store: InMemoryCatalogueStore
) -> None:
    held = wired.get("/catalogue", params={"since": 0}, headers=auth_headers).json()["version"]
    store.upsert_alias("coriander", "Tesco Fresh Cut Coriander 30g")

    body = wired.get("/catalogue", params={"since": held}, headers=auth_headers).json()

    assert [item["id"] for item in body["items"]] == ["coriander"]
    assert "tesco fresh cut coriander 30g" in {alias["key"] for alias in body["aliases"]}


def test_since_defaults_to_the_full_catalogue(wired: TestClient, auth_headers: dict[str, str]) -> None:
    body = wired.get("/catalogue", headers=auth_headers).json()

    assert len(body["items"]) == len(load_seed().items)


@pytest.mark.parametrize("since", ["-1", "abc"])
def test_a_since_that_is_not_a_version_is_rejected(wired: TestClient, auth_headers: dict[str, str], since: str) -> None:
    assert wired.get("/catalogue", params={"since": since}, headers=auth_headers).status_code == 422


def test_an_unconfigured_catalogue_is_a_clear_503(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/catalogue", headers=auth_headers)

    assert response.status_code == 503
    assert "catalogue" in response.json()["detail"].lower()


def test_the_groups_sent_are_the_ones_the_app_seeds_offline(wired: TestClient, auth_headers: dict[str, str]) -> None:
    app_seed = json.loads(Path("../app/test/data/fixtures/catalogue_groups.json").read_text(encoding="utf-8"))

    assert wired.get("/catalogue", headers=auth_headers).json()["groups"] == app_seed, (
        "The app's seeded groups drifted from the backend's. Regenerate app/test/data/fixtures/catalogue_groups.json "
        "from GET /catalogue and update app/lib/data/seed/ingredient_groups.dart to match."
    )


def test_an_item_is_sent_with_the_store_section_its_group_and_form_give_it(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    items = [
        CatalogueItem(id="onion", name="onion", group=GroupId.ONIONS_AND_GARLIC, form=Form.FRESH, source=Source.SEED),
        CatalogueItem(id="peas", name="peas", group=GroupId.BEANS_AND_PULSES, form=Form.FROZEN, source=Source.SEED),
        CatalogueItem(id="cumin", name="cumin", group=GroupId.SPICES, form=Form.NOT_APPLICABLE, source=Source.SEED),
    ]
    app.dependency_overrides[get_catalogue_store] = lambda: InMemoryCatalogueStore(items)

    sent = {item["id"]: item["section"] for item in client.get("/catalogue", headers=auth_headers).json()["items"]}

    assert sent == {"onion": "Fruit & Veg", "peas": "Frozen", "cumin": "Food Cupboard"}


def test_an_item_is_sent_with_the_ids_merged_into_it(client: TestClient, auth_headers: dict[str, str]) -> None:
    merged = CatalogueItem(
        id="coriander",
        name="coriander",
        group=GroupId.FRESH_HERBS,
        form=Form.NOT_APPLICABLE,
        source=Source.SEED,
        former_ids=("cilantro",),
    )
    plain = CatalogueItem(
        id="parsley", name="parsley", group=GroupId.FRESH_HERBS, form=Form.NOT_APPLICABLE, source=Source.SEED
    )
    app.dependency_overrides[get_catalogue_store] = lambda: InMemoryCatalogueStore([merged, plain])

    sent = {item["id"]: item["former_ids"] for item in client.get("/catalogue", headers=auth_headers).json()["items"]}

    assert sent == {"coriander": ["cilantro"], "parsley": []}
