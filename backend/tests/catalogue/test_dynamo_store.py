"""DynamoCatalogueStore against moto, using the table exactly as template.yaml defines it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import boto3
import pytest
from moto import mock_aws

from glean.catalogue.dynamo_store import DynamoCatalogueStore
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
def table() -> Iterator[Any]:
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        props = {k: v for k, v in catalogue_table_properties().items() if k not in _CFN_ONLY}
        yield dynamodb.create_table(TableName=TABLE_NAME, **props)


@pytest.fixture
def dynamo_store(table: Any) -> DynamoCatalogueStore:  # noqa: ARG001 - the fixture creates the table
    store = DynamoCatalogueStore(TABLE_NAME, region=REGION)
    store.seed(seed_items())
    return store


class TestDynamoCatalogueStore(CatalogueStoreContract):
    @pytest.fixture
    def store(self, dynamo_store: DynamoCatalogueStore) -> CatalogueStore:
        return dynamo_store
