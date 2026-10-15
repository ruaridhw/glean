"""DynamoCatalogueStore against moto, using the table exactly as template.yaml defines it."""

from __future__ import annotations

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
        created = list(
            pool.map(lambda s: s.create_provisional("Dragon Fruit", GroupId.TROPICAL_FRUIT, Form.FRESH), stores)
        )
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
    created = dynamo_store.create_provisional("Dragon Fruit", GroupId.TROPICAL_FRUIT, Form.FRESH)
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
    DynamoCatalogueStore(TABLE_NAME, region=REGION).create_provisional(
        "Dragon Fruit", GroupId.TROPICAL_FRUIT, Form.FRESH
    )
    assert [item.id for item in dynamo_store.shortlist("dragon fruit")] == ["dragon-fruit"]


def test_a_refused_creation_writes_no_alias_rows(table: Any, dynamo_store: DynamoCatalogueStore) -> None:
    rows_before = table.scan()["Items"]
    with pytest.raises(AliasConflictError):
        dynamo_store.create_provisional("fresh thing", GroupId.SPICES, Form.NOT_APPLICABLE, aliases=("cilantro",))
    assert table.scan()["Items"] == rows_before
