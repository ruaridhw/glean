from __future__ import annotations

from typing import TYPE_CHECKING, Any

import boto3
import pytest
from moto import mock_aws
from scripts import seed_catalogue
from tests.infra.cfn import catalogue_table_properties

from glean.catalogue.dynamo_store import DynamoCatalogueStore
from glean.catalogue.seed import load_seed

if TYPE_CHECKING:
    from collections.abc import Iterator

_CFN_ONLY = {"TableName", "TableClass", "PointInTimeRecoverySpecification"}


@pytest.fixture
def table() -> Iterator[Any]:
    with mock_aws():
        props = {k: v for k, v in catalogue_table_properties().items() if k not in _CFN_ONLY}
        yield boto3.resource("dynamodb", region_name="eu-west-2").create_table(TableName="seed-test", **props)


def _rows(table: Any) -> list[dict[str, Any]]:
    return sorted(table.scan()["Items"], key=lambda row: row["pk"])


def test_seeding_twice_writes_nothing_the_second_time(table: Any) -> None:
    store = DynamoCatalogueStore("seed-test")
    items = load_seed().items
    assert seed_catalogue.seed_catalogue(store) == len(items)
    for item in items:  # including per-form once-opened shelf life and overrides, as the model resolves them
        found = store.get_by_name(item.name)
        assert found == item
        assert found.once_opened_shelf_life_days == item.once_opened_shelf_life_days
        assert found.unopened_shelf_life_days == item.unopened_shelf_life_days
    rows_after_first = _rows(table)
    version_after_first = store.catalogue_version()

    assert seed_catalogue.seed_catalogue(store) == 0
    assert _rows(table) == rows_after_first
    assert store.catalogue_version() == version_after_first


def test_seeding_after_one_item_changed_rewrites_only_that_item(table: Any) -> None:
    store = DynamoCatalogueStore("seed-test")
    seed_catalogue.seed_catalogue(store)
    first = load_seed().items[0]
    store.seed([first.model_copy(update={"density_g_per_ml": 9.99})])

    assert seed_catalogue.seed_catalogue(store) == 1
    assert store.get_by_name(first.name) == first
