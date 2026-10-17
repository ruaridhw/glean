"""DynamoCatalogueStore against moto, using the table exactly as template.yaml defines it."""

from __future__ import annotations

import copy
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

import boto3
import pytest
from boto3.dynamodb.conditions import Key
from moto import mock_aws
from moto.dynamodb.models import DynamoDBBackend

from glean.catalogue.dynamo_store import DynamoCatalogueStore
from glean.catalogue.groups import Form, GroupId
from glean.catalogue.seed import load_seed
from glean.catalogue.store import AliasConflictError
from tests.catalogue.test_store_contract import CatalogueStoreContract, seed_items
from tests.infra.cfn import catalogue_table_properties

if TYPE_CHECKING:
    from collections.abc import Iterator

    from glean.catalogue.store import CatalogueStore

TABLE_NAME = "glean-catalogue-test"
REGION = "eu-west-2"
# CloudFormation-only properties that create_table does not take.
_CFN_ONLY = {"TableName", "TableClass", "PointInTimeRecoverySpecification"}


@pytest.fixture
def atomic_transactions(monkeypatch: pytest.MonkeyPatch) -> None:
    """moto runs transactions without a lock (and rolls back from a snapshot), so racing threads corrupt it.
    Real DynamoDB transactions are atomic; give the fake the same property."""
    lock = threading.Lock()
    original = DynamoDBBackend.transact_write_items

    def locked(self: DynamoDBBackend, *args: Any, **kwargs: Any) -> Any:
        with lock:
            return original(self, *args, **kwargs)

    monkeypatch.setattr(DynamoDBBackend, "transact_write_items", locked)


@pytest.fixture
def table(atomic_transactions: None) -> Iterator[Any]:
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        props = {k: v for k, v in catalogue_table_properties().items() if k not in _CFN_ONLY}
        yield dynamodb.create_table(TableName=TABLE_NAME, **props)


@pytest.fixture
def dynamo_store(table: Any) -> DynamoCatalogueStore:
    store = DynamoCatalogueStore(TABLE_NAME, region=REGION)
    store.seed(seed_items())
    return store


class TestDynamoCatalogueStore(CatalogueStoreContract):
    @pytest.fixture
    def store(self, dynamo_store: DynamoCatalogueStore) -> CatalogueStore:
        return dynamo_store


def _item_rows(table: Any) -> list[dict[str, Any]]:
    rows = table.scan()["Items"]
    return [row for row in rows if row["pk"].startswith("ITEM#")]


def test_concurrent_creates_of_one_name_make_one_row(table: Any, dynamo_store: DynamoCatalogueStore) -> None:
    stores = [DynamoCatalogueStore(TABLE_NAME, region=REGION) for _ in range(6)]
    before = len(_item_rows(table))
    with ThreadPoolExecutor(max_workers=6) as pool:
        created = list(pool.map(lambda s: s.create_provisional("Dragon Fruit", GroupId.FRUIT, Form.FRESH), stores))
    assert {item.id for item in created} == {"dragon-fruit"}
    assert len(_item_rows(table)) == before + 1


def test_concurrent_creates_of_different_names_all_land_with_distinct_versions(
    table: Any, dynamo_store: DynamoCatalogueStore
) -> None:
    stores = [DynamoCatalogueStore(TABLE_NAME, region=REGION) for _ in range(5)]
    start = dynamo_store.catalogue_version()
    names = [f"novel thing {n}" for n in range(5)]
    with ThreadPoolExecutor(max_workers=5) as pool:
        list(
            pool.map(
                lambda pair: pair[0].create_provisional(pair[1], GroupId.SPICES, Form.NOT_APPLICABLE),
                zip(stores, names, strict=True),
            )
        )
    assert dynamo_store.catalogue_version() == start + 5
    versions = [int(row["version"]) for row in _item_rows(table) if row["pk"].startswith("ITEM#novel-thing")]
    assert sorted(versions) == list(range(start + 1, start + 6))


def test_every_write_bumps_the_catalogue_version_and_stamps_the_item(
    table: Any, dynamo_store: DynamoCatalogueStore
) -> None:
    start = dynamo_store.catalogue_version()
    dynamo_store.upsert_alias("coriander", "green coriander")
    assert dynamo_store.catalogue_version() == start + 1
    created = dynamo_store.create_provisional("Dragon Fruit", GroupId.FRUIT, Form.FRESH)
    assert dynamo_store.catalogue_version() == start + 2
    by_version = table.query(
        IndexName="by_version", KeyConditionExpression=Key("gsi_pk").eq("CATALOGUE"), ScanIndexForward=False
    )["Items"]
    assert [(row["pk"], int(row["version"])) for row in by_version[:2]] == [
        (f"ITEM#{created.id}", start + 2),
        ("ITEM#coriander", start + 1),
    ]


def test_reads_and_unmatched_names_do_not_change_the_catalogue_version(dynamo_store: DynamoCatalogueStore) -> None:
    start = dynamo_store.catalogue_version()
    dynamo_store.get_by_name("coriander")
    dynamo_store.upsert_alias("coriander", "cilantro")
    dynamo_store.record_unmatched("zzqx")
    assert dynamo_store.catalogue_version() == start


def test_shortlist_reflects_a_write_made_through_another_store(dynamo_store: DynamoCatalogueStore) -> None:
    assert dynamo_store.shortlist("dragon fruit") == []
    DynamoCatalogueStore(TABLE_NAME, region=REGION).create_provisional("Dragon Fruit", GroupId.FRUIT, Form.FRESH)
    assert [item.id for item in dynamo_store.shortlist("dragon fruit")] == ["dragon-fruit"]


def test_a_refused_creation_writes_no_alias_rows(table: Any, dynamo_store: DynamoCatalogueStore) -> None:
    rows_before = table.scan()["Items"]
    with pytest.raises(AliasConflictError):
        dynamo_store.create_provisional("fresh thing", GroupId.SPICES, Form.NOT_APPLICABLE, aliases=("cilantro",))
    assert table.scan()["Items"] == rows_before


class _IndexView:
    """Makes the by_version index lag: drops chosen item rows from Query responses while `lagging` is set."""

    def __init__(self) -> None:
        self.lagging = False
        self.hidden: set[str] = set()
        self.stale: set[str] = set()  # rows served as the revision last seen while the index was healthy
        self._last_seen: dict[str, Any] = {}

    def __call__(self, parsed: dict[str, Any], **_: Any) -> None:
        if "Items" not in parsed:
            return
        if not self.lagging:
            self._last_seen.update({_plain(row["pk"]): copy.deepcopy(row) for row in parsed["Items"]})
            return
        parsed["Items"] = [
            self._last_seen[_plain(row["pk"])] if _plain(row["pk"]) in self.stale else row
            for row in parsed["Items"]
            if _plain(row["pk"]) not in self.hidden
        ]


def _plain(value: Any) -> str:
    return value["S"] if isinstance(value, dict) else value


def test_a_shortlist_built_from_a_lagging_index_is_not_kept_once_the_index_recovers(table: Any) -> None:
    view = _IndexView()
    session = boto3.Session(region_name=REGION)
    session.events.register("after-call.dynamodb.Query", view)
    store = DynamoCatalogueStore(TABLE_NAME, region=REGION, session=session)
    store.create_provisional("Dragon Fruit", GroupId.FRUIT, Form.FRESH)
    store.create_provisional("Birthday Candles", GroupId.HOUSEHOLD, Form.NOT_APPLICABLE)

    view.lagging, view.hidden = True, {"ITEM#dragon-fruit"}
    assert store.shortlist("dragon fruit") == []  # the index really is behind; a direct lookup is not
    assert store.get_by_name("dragon fruit") is not None

    view.lagging = False
    assert [item.id for item in store.shortlist("dragon fruit")] == ["dragon-fruit"]


def test_reseeding_keeps_aliases_learned_since_the_seed(dynamo_store: DynamoCatalogueStore) -> None:
    dynamo_store.upsert_alias("coriander", "green herb bunch")

    assert dynamo_store.seed(seed_items()) == 0

    found = dynamo_store.get_by_name("green herb bunch")
    assert found is not None
    assert "green herb bunch" in found.aliases
    assert [item.id for item in dynamo_store.shortlist("green herb bunch")] == ["coriander"]


def test_reseeding_a_changed_item_keeps_its_learned_aliases_and_applies_the_change(
    dynamo_store: DynamoCatalogueStore,
) -> None:
    dynamo_store.upsert_alias("coriander", "green herb bunch")
    changed = [
        item.model_copy(update={"density_g_per_ml": 0.4}) if item.id == "coriander" else item for item in seed_items()
    ]

    assert dynamo_store.seed(changed) == 1

    found = dynamo_store.get_by_name("cilantro")
    assert found is not None
    assert found.density_g_per_ml == 0.4
    assert {"green herb bunch", "cilantro", "fresh coriander"} <= set(found.aliases)
    assert dynamo_store.get_by_name("green herb bunch") == found


def test_reseeding_with_a_new_seed_alias_makes_it_resolve_and_keeps_item_and_lookup_in_agreement(
    dynamo_store: DynamoCatalogueStore,
) -> None:
    grown = [
        item.model_copy(update={"aliases": (*item.aliases, "coriander leaf")}) if item.id == "coriander" else item
        for item in seed_items()
    ]

    assert dynamo_store.seed(grown) == 1

    found = dynamo_store.get_by_name("coriander leaf")
    assert found is not None
    assert "coriander leaf" in found.aliases
    assert [item.id for item in dynamo_store.shortlist("coriander leaf")][:1] == ["coriander"]


def test_a_snapshot_with_a_stale_revision_is_not_kept_even_when_the_count_and_newest_version_match(table: Any) -> None:
    view = _IndexView()
    session = boto3.Session(region_name=REGION)
    session.events.register("after-call.dynamodb.Query", view)
    store = DynamoCatalogueStore(TABLE_NAME, region=REGION, session=session)
    store.create_provisional("Dragon Fruit", GroupId.FRUIT, Form.FRESH)
    store.shortlist("dragon fruit")  # the healthy index shows the first revision
    store.upsert_alias("dragon-fruit", "pitaya")
    store.create_provisional("Birthday Candles", GroupId.HOUSEHOLD, Form.NOT_APPLICABLE)

    view.lagging, view.stale = True, {"ITEM#dragon-fruit"}
    assert store.shortlist("pitaya") == []  # the index serves the old revision of the older item

    view.lagging = False
    assert [item.id for item in store.shortlist("pitaya")] == ["dragon-fruit"]


def test_reseeding_a_renamed_item_keeps_its_old_name_as_an_alias(dynamo_store: DynamoCatalogueStore) -> None:
    renamed = [
        item.model_copy(update={"name": "jeera", "aliases": ()}) if item.id == "ground-cumin" else item
        for item in seed_items()
    ]

    assert dynamo_store.seed(renamed) == 1

    for name in ("ground cumin", "jeera"):
        found = dynamo_store.get_by_name(name)
        assert found is not None
        assert found.id == "ground-cumin"
        assert {"ground cumin", "jeera"} <= {found.name, *found.aliases}
        assert [item.id for item in dynamo_store.shortlist(name)][:1] == ["ground-cumin"]
    assert dynamo_store.seed(renamed) == 0


def _stored_shelf_lives(store: DynamoCatalogueStore, name: str) -> tuple[int | None, int | None]:
    item = store.get_by_name(name)
    assert item is not None, name
    return item.unopened_shelf_life_days, item.once_opened_shelf_life_days


def test_an_item_with_no_shelf_life_still_has_none_after_a_round_trip(dynamo_store: DynamoCatalogueStore) -> None:
    assert _stored_shelf_lives(dynamo_store, "toilet roll") == (None, None)


def test_a_provisional_non_food_item_never_expires_rather_than_expiring_at_zero(
    dynamo_store: DynamoCatalogueStore,
) -> None:
    dynamo_store.create_provisional("birthday candles", GroupId.HOUSEHOLD, Form.NOT_APPLICABLE)
    assert _stored_shelf_lives(dynamo_store, "birthday candles") == (None, None)


def test_the_whole_seed_round_trips_every_shelf_life_through_the_table(table: Any) -> None:
    store = DynamoCatalogueStore(TABLE_NAME, region=REGION)
    items = load_seed().items
    store.seed(items)
    for item in items:
        stored = store.get_by_name(item.name)
        assert stored is not None, item.name
        assert stored.unopened_shelf_life_days == item.unopened_shelf_life_days, item.name
        assert stored.once_opened_shelf_life_days == item.once_opened_shelf_life_days, item.name
    assert _stored_shelf_lives(store, "baby formula milk powder")[0] is not None
    assert _stored_shelf_lives(store, "dog food pouches")[0] is not None
    assert any(item.unopened_shelf_life_days is None for item in items)
