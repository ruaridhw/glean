from __future__ import annotations

import random
import time
from typing import TYPE_CHECKING, Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from glean.catalogue.models import CatalogueItem, Source, name_key, slugify
from glean.catalogue.store import (
    AliasConflictError,
    DuplicateIdError,
    InMemoryCatalogueStore,
    UnknownItemError,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from glean.catalogue.groups import Form, GroupId

_CATALOGUE_GSI_PK = "CATALOGUE"
_UNMATCHED_GSI_PK = "UNMATCHED"
_META = "META"
_INDEX = "by_version"
_MAX_ATTEMPTS = 25
_RETRYABLE = {"ThrottlingException", "ProvisionedThroughputExceededException", "TransactionConflictException"}

type _Op = dict[str, Any]


def _item_pk(item_id: str) -> str:
    return f"ITEM#{item_id}"


def _alias_pk(key: str) -> str:
    return f"ALIAS#{key}"


class DynamoCatalogueStore:
    """The catalogue in a single DynamoDB table (ADR 0001).

    Rows by `pk`: `ITEM#<id>` (the item as JSON, stamped with the `version` it was written at), `ALIAS#<name key>`
    (points at an item id; the canonical name has one too), `UNMATCHED#<name as written>` and `META` (the catalogue
    version counter).

    Every content write is one transaction that moves `META.version` from the value the writer read to the next one,
    and stamps the written item with that value. A writer that lost the race re-reads and tries again, so two
    writers never share a version and a lost race never leaves a half-written change.
    """

    def __init__(self, table_name: str, region: str = "eu-west-2", session: boto3.Session | None = None) -> None:
        self._table_name = table_name
        self._client = (session or boto3.Session()).resource("dynamodb", region_name=region).meta.client
        self._snapshot: tuple[int, InMemoryCatalogueStore] | None = None

    def catalogue_version(self) -> int:
        """How many content writes the catalogue has had; the newest item row carries this version."""
        return self._meta()[0]

    def _meta(self) -> tuple[int, int]:
        """The version counter and how many items the catalogue holds."""
        row = self._get(_META)
        return (int(row["version"]), int(row.get("item_count", 0))) if row else (0, 0)

    def get_by_name(self, name: str) -> CatalogueItem | None:
        alias = self._get(_alias_pk(name_key(name)))
        if alias is None:
            return None
        row = self._get(_item_pk(alias["item_id"]))
        return _to_item(row) if row else None

    def shortlist(self, name: str, limit: int = 8) -> list[CatalogueItem]:
        return self._catalogue().shortlist(name, limit)

    def upsert_alias(self, item_id: str, alias: str) -> CatalogueItem:
        def plan(version: int) -> tuple[CatalogueItem, list[_Op], int]:
            row = self._get(_item_pk(item_id))
            if row is None:
                raise UnknownItemError(item_id)
            item = _to_item(row)
            owner = self._alias_owner(alias)
            if owner == item_id:
                return item, [], 0
            if owner is not None:
                raise AliasConflictError(f"{alias!r} already names {owner}")
            updated = item.model_copy(update={"aliases": (*item.aliases, alias.strip())})
            return updated, [self._put_item(updated, version), self._put_alias(name_key(alias), item_id)], 0

        return self._commit(plan)

    def create_provisional(self, name: str, group: GroupId, form: Form, aliases: tuple[str, ...] = ()) -> CatalogueItem:
        def plan(version: int) -> tuple[CatalogueItem, list[_Op], int]:
            existing = self.get_by_name(name)
            if existing is not None:
                return existing, [], 0
            item = CatalogueItem(
                id=self._free_id(name), name=name.strip(), aliases=aliases, group=group, form=form, source=Source.LLM
            )
            keys = _name_keys(item)
            for key in keys:
                owner = self._alias_owner(key)
                if owner is not None:
                    raise AliasConflictError(f"{key!r} already names {owner}")
            ops = [self._put_item(item, version, must_be_new=True), *(self._put_alias(k, item.id) for k in keys)]
            return item, ops, 1

        return self._commit(plan)

    def record_unmatched(self, name: str) -> None:
        # Not a catalogue change, so it neither bumps the version nor appears in delta sync.
        row = {"pk": f"UNMATCHED#{name}", "gsi_pk": _UNMATCHED_GSI_PK, "version": 0, "name": name}
        self._client.put_item(TableName=self._table_name, Item=row)

    def is_unmatched(self, name: str) -> bool:
        return self._get(f"UNMATCHED#{name}") is not None

    def unmatched_names(self) -> list[str]:
        rows = self._query(_UNMATCHED_GSI_PK)
        return [row["name"] for row in rows]

    def seed(self, items: Iterable[CatalogueItem]) -> int:
        """Write the items that are missing or changed. Returns how many were written."""
        written = 0
        for item in items:
            row = self._get(_item_pk(item.id))
            if row is not None and _to_item(row) == item:
                continue

            def plan(version: int, item: CatalogueItem = item) -> tuple[None, list[_Op], int]:
                keys = _name_keys(item)
                for key in keys:
                    owner = self._alias_owner(key)
                    if owner is not None and owner != item.id:
                        raise AliasConflictError(f"{key!r} already names {owner}")
                is_new = self._get(_item_pk(item.id)) is None
                return None, [self._put_item(item, version), *(self._put_alias(k, item.id) for k in keys)], int(is_new)

            self._commit(plan)
            written += 1
        return written

    def _catalogue(self) -> InMemoryCatalogueStore:
        """Every item, reused only while it is provably complete and current.

        The index is eventually consistent, so a read can miss items that META already counts. Such a partial read is
        used for this call but never kept: the next call reads the index again.
        """
        version, count = self._meta()
        if self._snapshot is not None and self._snapshot[0] == version:
            return self._snapshot[1]
        rows = self._query(_CATALOGUE_GSI_PK)
        catalogue = InMemoryCatalogueStore(_to_item(row) for row in rows)
        self._snapshot = (version, catalogue) if len(rows) == count else None
        return catalogue

    def _commit[T](self, plan: Callable[[int], tuple[T, list[_Op], int]]) -> T:
        """Run *plan* against the current version; its writes land together with the version bump, or not at all."""
        for attempt in range(_MAX_ATTEMPTS):
            seen = self.catalogue_version()
            try:
                result, ops, new_items = plan(seen + 1)
            except (AliasConflictError, UnknownItemError):
                if self.catalogue_version() == seen:
                    raise
                continue  # a refusal judged against a catalogue that has since moved: look again
            if not ops:
                return result
            try:
                self._client.transact_write_items(TransactItems=[self._bump_meta(seen, new_items), *ops])
            except ClientError as error:
                if not _is_contention(error):
                    raise
                if _meta_was_current(error):
                    raise DuplicateIdError("an item with this id already exists") from error
                time.sleep(random.uniform(0, min(0.02 * 2**attempt, 1.0)))  # noqa: S311 - backoff jitter
                continue
            return result
        raise RuntimeError("catalogue write kept losing the version race")

    def _bump_meta(self, seen: int, new_items: int) -> _Op:
        return {
            "Update": {
                "TableName": self._table_name,
                "Key": {"pk": _META},
                "UpdateExpression": "SET version = :new ADD item_count :added",
                "ConditionExpression": "version = :seen" if seen else "attribute_not_exists(version)",
                "ExpressionAttributeValues": {
                    ":new": seen + 1,
                    ":added": new_items,
                    **({":seen": seen} if seen else {}),
                },
            }
        }

    def _put_item(self, item: CatalogueItem, version: int, *, must_be_new: bool = False) -> _Op:
        row = {"pk": _item_pk(item.id), "gsi_pk": _CATALOGUE_GSI_PK, "version": version, "item": item.model_dump_json()}
        put: _Op = {"TableName": self._table_name, "Item": row}
        if must_be_new:
            put["ConditionExpression"] = "attribute_not_exists(pk)"
        return {"Put": put}

    def _put_alias(self, key: str, item_id: str) -> _Op:
        return {
            "Put": {
                "TableName": self._table_name,
                "Item": {"pk": _alias_pk(key), "item_id": item_id},
                "ConditionExpression": "attribute_not_exists(pk) OR item_id = :id",
                "ExpressionAttributeValues": {":id": item_id},
            }
        }

    def _alias_owner(self, name: str) -> str | None:
        row = self._get(_alias_pk(name_key(name)))
        return row["item_id"] if row else None

    def _free_id(self, name: str) -> str:
        # Slugs are lossy ("a-b" and "a b" collide), so number the id until it is unclaimed.
        base = slugify(name)
        candidate, number = base, 1
        while self._get(_item_pk(candidate)) is not None:
            number += 1
            candidate = f"{base}-{number}"
        return candidate

    def _get(self, pk: str) -> dict[str, Any] | None:
        return self._client.get_item(TableName=self._table_name, Key={"pk": pk}, ConsistentRead=True).get("Item")

    def _query(self, gsi_pk: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        kwargs: dict[str, Any] = {
            "TableName": self._table_name,
            "IndexName": _INDEX,
            "KeyConditionExpression": Key("gsi_pk").eq(gsi_pk),
        }
        while True:
            page = self._client.query(**kwargs)
            rows.extend(page["Items"])
            if "LastEvaluatedKey" not in page:
                return rows
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def _name_keys(item: CatalogueItem) -> list[str]:
    return sorted({name_key(item.name), *(name_key(alias) for alias in item.aliases)})


def _to_item(row: dict[str, Any]) -> CatalogueItem:
    return CatalogueItem.model_validate_json(row["item"])


def _reasons(error: ClientError) -> list[str]:
    return [reason.get("Code", "None") for reason in error.response.get("CancellationReasons", [])]


def _is_contention(error: ClientError) -> bool:
    code = error.response["Error"]["Code"]
    return code in _RETRYABLE or code == "TransactionCanceledException"


def _meta_was_current(error: ClientError) -> bool:
    """The version check passed but another condition failed: a real conflict, not a lost race."""
    reasons = _reasons(error)
    return bool(reasons) and reasons[0] == "None" and "ConditionalCheckFailed" in reasons[1:]
