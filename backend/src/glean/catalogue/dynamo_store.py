from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from glean.catalogue.models import CatalogueItem, name_key

if TYPE_CHECKING:
    from collections.abc import Iterable

_GSI_PK = "CATALOGUE"
_META = "META"


def _item_pk(item_id: str) -> str:
    return f"ITEM#{item_id}"


def _alias_pk(name: str) -> str:
    return f"ALIAS#{name_key(name)}"


class DynamoCatalogueStore:
    """The catalogue in a single DynamoDB table (ADR 0001).

    Rows by `pk`: `ITEM#<id>` (the item as JSON, stamped with its `version`), `ALIAS#<name key>` (points at an
    item id; the canonical name has one too), `UNMATCHED#<name key>` and `META` (the catalogue version counter).
    """

    def __init__(self, table_name: str, region: str = "eu-west-2") -> None:
        self._table_name = table_name
        self._client = boto3.resource("dynamodb", region_name=region).meta.client

    def catalogue_version(self) -> int:
        """How many content writes the catalogue has had. Every item row carries the version it was last written at."""
        row = self._client.get_item(TableName=self._table_name, Key={"pk": _META}, ConsistentRead=True).get("Item")
        return int(row["version"]) if row else 0

    def get_by_name(self, name: str) -> CatalogueItem | None:
        alias = self._get(_alias_pk(name))
        if alias is None:
            return None
        row = self._get(_item_pk(alias["item_id"]))
        return _to_item(row) if row else None

    def seed(self, items: Iterable[CatalogueItem]) -> int:
        """Write the items that are missing or changed. Returns how many were written."""
        written = 0
        for item in items:
            row = self._get(_item_pk(item.id))
            if row is not None and _to_item(row) == item:
                continue
            self._write_item(item)
            written += 1
        return written

    def _write_item(self, item: CatalogueItem) -> None:
        version = self.catalogue_version() + 1
        keys = {name_key(item.name), *(name_key(alias) for alias in item.aliases)}
        ops: list[dict[str, Any]] = [
            self._bump_meta(version - 1, version),
            {"Put": {"TableName": self._table_name, "Item": _item_row(item, version)}},
            *(
                {"Put": {"TableName": self._table_name, "Item": {"pk": f"ALIAS#{key}", "item_id": item.id}}}
                for key in keys
            ),
        ]
        self._client.transact_write_items(TransactItems=ops)

    def _bump_meta(self, seen: int, new: int) -> dict[str, Any]:
        return {
            "Update": {
                "TableName": self._table_name,
                "Key": {"pk": _META},
                "UpdateExpression": "SET version = :new",
                "ConditionExpression": "version = :seen" if seen else "attribute_not_exists(version)",
                "ExpressionAttributeValues": {":new": new, **({":seen": seen} if seen else {})},
            }
        }

    def _get(self, pk: str) -> dict[str, Any] | None:
        return self._client.get_item(TableName=self._table_name, Key={"pk": pk}, ConsistentRead=True).get("Item")


def _item_row(item: CatalogueItem, version: int) -> dict[str, Any]:
    return {"pk": _item_pk(item.id), "gsi_pk": _GSI_PK, "version": version, "item": item.model_dump_json()}


def _to_item(row: dict[str, Any]) -> CatalogueItem:
    return CatalogueItem.model_validate_json(row["item"])
