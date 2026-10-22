"""The recipe corpus in DynamoDB (F1/#162), plus the S3 projection planning reads.

Table `glean-recipes-<env>`, provisioned at 5/5 with no GSIs (ADR 0001). Three item shapes, all keyed by
`pk` + `sk` strings:

- `pk=RECIPE#<id>`, `sk=RECIPE` — the recipe body as JSON, at most 10 KB.
- `pk=RECIPE#<id>`, `sk=ANSWER#<question>#<criteria_hash>` — one decision answer (probabilities, model,
  the recipe content hash it answered). Dietary decisions are answers under `dietary:<flag>`; F2's
  enrichers add their own question names beside them.
- `pk=SOURCE#<sha256 of the source url>`, `sk=RECIPE` — the recipe id that URL imported to. Written in the
  same transaction as the body, so import dedupe is one read.

Reading 632 summaries from this table would cost 45-90 read units per Generate (9-18 s of throttling at
5 RCU), so search, summaries and planning's dietary decisions read the gzipped S3 projection instead
(`recipes/projection.py`), cached for `PROJECTION_TTL_SECONDS`. `get` reads the table directly.

Every write here is compare-before-write, so a re-run of the migration writes nothing, and every call is
retried with backoff on throttling: 5 WCU means roughly five small writes a second.

The projection is one S3 object, so publishing it is a read-modify-write against the object version
(ETag `If-Match`, `If-None-Match: *` on create). A writer re-reads and re-applies its change when the
object moved on, instead of dropping the entry another Lambda just published. If publication still fails
after the bounded retries, `ProjectionPublishError` is raised and logged with the rebuild command: the
table has the change, and `rebuild_projection()` / `scripts/build_recipe_index.py --table` repairs it.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from weakref import WeakKeyDictionary

import boto3
from botocore.exceptions import ClientError

from glean.observability import logger
from glean.recipes.answers import RecipeAnswer, content_fingerprint, latest_per_question
from glean.recipes.corpus import recipe_blob_key, recipe_payload
from glean.recipes.projection import (
    PROJECTION_TTL_SECONDS,
    ProjectedRecipe,
    ProjectionSnapshot,
    RecipeProjection,
    build_projection,
    dumps,
    loads,
)
from glean.recipes.search_index import RecipeSearchIndex, RecipeSummary
from glean.recipes.stored import StoredRecipe

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

    from glean.recipes.projection import ProjectionStore

__all__ = [
    "MAX_RECIPE_BYTES",
    "DynamoCorpusBackend",
    "ProjectionPublishError",
    "ProjectionWrite",
    "RecipeTooLargeError",
    "answer_item",
    "answer_sk",
    "answer_write_units",
    "item_write_units",
    "recipe_item",
    "recipe_pk",
    "recipe_write_units",
    "retry_throttled",
    "source_item",
    "source_pk",
]

RECIPE_SK = "RECIPE"
ANSWER_PREFIX = "ANSWER#"
# The design's per-recipe budget: well inside a DynamoDB item's 400 KB, and small enough that a full
# projection of the corpus stays about 1.6 MB uncompressed.
MAX_RECIPE_BYTES = 10_000

_RETRYABLE = {
    "ProvisionedThroughputExceededException",
    "ThrottlingException",
    "RequestLimitExceeded",
    "TransactionConflictException",
    "InternalServerError",
    "ServiceUnavailable",
}
# A transaction reports its own throttling as cancellation reasons, one per item, not as the top-level code.
_RETRYABLE_CANCELLATION_REASONS = {
    "ProvisionedThroughputExceeded",
    "ThrottlingError",
    "TransactionConflict",
    "RequestLimitExceeded",
    "InternalServerError",
    "ServiceUnavailable",
}
_MAX_ATTEMPTS = 6
# Publishing the whole projection is a read-modify-write: bound the re-read/re-apply loop, then say so.
_MAX_PUBLISH_ATTEMPTS = 4
# A full rebuild re-scans the table after every lost race (correctness over speed: conflicts are rare), so it
# gets fewer attempts than an incremental merge that only re-reads one small object.
_MAX_REBUILD_ATTEMPTS = 3
_REBUILD_COMMAND = "uv run python scripts/build_recipe_index.py --table <table> --bucket <recipe-cache-bucket>"


class RecipeTooLargeError(Exception):
    """A recipe body is over the corpus's 10 KB budget, so it can't be stored as one item."""


class ProjectionPublishError(Exception):
    """The table has a change the projection could not publish, so planning would not see it."""


@dataclass(frozen=True)
class ProjectionWrite:
    recipes: int
    written: bool


@dataclass
class _LoadedProjection:
    """The projection as last read or written, with the search index built from it."""

    raw: bytes | None
    projection: RecipeProjection
    index: RecipeSearchIndex | None


# Per projection store: (monotonic load time, document). Keyed weakly so a backend built for one script
# or test doesn't pin its projection, and shared between backends over the same bucket.
_projection_cache: WeakKeyDictionary[Any, tuple[float, _LoadedProjection]] = WeakKeyDictionary()


def recipe_pk(recipe_id: str) -> str:
    return f"RECIPE#{recipe_id}"


def answer_sk(question: str, criteria_hash: str) -> str:
    return f"{ANSWER_PREFIX}{question}#{criteria_hash}"


def source_pk(source_url: str) -> str:
    return f"SOURCE#{hashlib.sha256(source_url.encode('utf-8')).hexdigest()}"


def retry_throttled[T](
    operation: Callable[[], T], *, attempts: int = _MAX_ATTEMPTS, sleep: Callable[[float], None] = time.sleep
) -> T:
    """Run `operation`, retrying with exponential backoff while DynamoDB is throttling it."""
    for attempt in range(attempts):
        try:
            return operation()
        except ClientError as error:
            if not _is_throttle(error) or attempt == attempts - 1:
                raise
            sleep(random.uniform(0.05, min(0.05 * 2**attempt, 2.0)))  # noqa: S311 - backoff jitter
    raise AssertionError("unreachable: the last attempt returns or raises")


class DynamoCorpusBackend:
    """The corpus in one DynamoDB table, with the S3 projection kept in step."""

    index_ttl_seconds = PROJECTION_TTL_SECONDS

    def __init__(
        self,
        table_name: str,
        *,
        projection: ProjectionStore,
        region: str = "eu-west-2",
        session: boto3.Session | None = None,
    ) -> None:
        self._table = table_name
        self._projections = projection
        self._client = (session or boto3.Session()).resource("dynamodb", region_name=region).meta.client

    # -- the CorpusBackend interface ----------------------------------------------------------------

    def save(self, recipe: StoredRecipe) -> None:
        self.upsert(recipe)

    def get(self, recipe_id: str) -> StoredRecipe | None:
        row = self._get(recipe_pk(recipe_id), RECIPE_SK)
        return _stored_recipe(row) if row else None

    def get_by_source_url(self, source_url: str) -> StoredRecipe | None:
        if not source_url:
            return None  # a recipe imported without a URL has no pointer to find it by
        pointer = self._get(source_pk(source_url), RECIPE_SK)
        return self.get(str(pointer["recipe_id"])) if pointer else None

    def index(self) -> RecipeSearchIndex | None:
        return self._load_projection().index

    def all_recipes(self) -> Iterator[StoredRecipe]:
        for summary in self._load_projection().projection.summaries():
            recipe = self.get(summary.external_id)
            if recipe is None:
                logger.warning(
                    "recipe in the projection is missing from the table", extra={"recipe_id": summary.external_id}
                )
                continue
            yield recipe

    def rebuild_index(self) -> int:
        return self.rebuild_projection().recipes

    def answers(self) -> list[RecipeAnswer]:
        return sorted(self._load_projection().projection.answers(), key=lambda a: (a.recipe_id, a.question))

    def save_answers(self, answers: Sequence[RecipeAnswer], *, rebuild_projection: bool = True) -> int:
        """Store the answers that changed, returning how many items were written.

        `rebuild_projection=False` is the bulk path (the migration): the caller writes the projection once
        at the end from the data it migrated, instead of once per recipe.
        """
        snapshot, current = self._fresh_projection()
        known = {_answer_key(answer): answer for answer in current.answers()}
        changed = [answer for answer in answers if known.get(_answer_key(answer)) != answer]
        for answer in changed:
            self._put(answer_item(answer))
        if changed and rebuild_projection:
            self._publish(
                lambda projection, _refresh: self._project_answers(projection, changed),
                what=f"{len(changed)} answers",
            )
        elif changed:
            self._remember(snapshot, current)
        return len(changed)

    # -- the migration and F2's runner ---------------------------------------------------------------

    def upsert(self, recipe: StoredRecipe) -> bool:
        """Write the recipe and its SOURCE pointer, and make sure the projection carries it.

        Returns whether anything durable was written: a recipe already in the table whose projection entry
        is also current writes nothing, which is what makes the migration re-runnable. The projection step
        always runs, so a retry after a failed publish repairs it without touching the table.
        """
        body = _recipe_body(recipe)
        # Only a URL-imported recipe has a pointer; one without a URL would otherwise share a single
        # `SOURCE#` row with every other such recipe.
        pointer = source_item(recipe)
        stored = self._get(recipe_pk(recipe.external_id), RECIPE_SK)
        wrote_table = not (
            stored is not None and stored.get("body") == body and (pointer is None or self._source_is_current(pointer))
        )
        if wrote_table:
            ops: list[dict[str, Any]] = [{"Put": {"TableName": self._table, "Item": recipe_item(recipe)}}]
            if pointer is not None:
                ops.append({"Put": {"TableName": self._table, "Item": pointer}})
            self._transact(ops)
        published = self.publish(recipe)  # always: this is also the repair after an earlier failed publish
        return wrote_table or published

    def publish(self, recipe: StoredRecipe) -> bool:
        """Make an already-stored recipe visible to search and planning. True when the projection changed.

        Idempotent, and the repair path for a publish that failed earlier: a retried import deduped on its
        source URL calls this instead of paying for another parse, and a retried `upsert` converges here too.
        """
        return self._publish(
            lambda projection, _refresh: projection.with_recipe(self._projected(recipe, projection)),
            what=f"recipe {recipe.external_id}",
        )

    def rebuild_projection(self) -> ProjectionWrite:
        """Rebuild the whole projection from the table. Owner-run, or F2's runner after a bulk change.

        A consistent scan: 632 recipe bodies is a few hundred read units, slow at 5 RCU but exact. Prefer
        `save_answers` for an incremental change. A lost race re-scans and recomputes, because republishing
        a document computed before the race would overwrite whatever the other writer just added.
        """
        document: RecipeProjection | None = None

        def build(_current: RecipeProjection, refresh: bool) -> RecipeProjection:
            nonlocal document
            if document is None or refresh:
                document = self._projection_from_table()
            return document

        written = self._publish(build, what="a full rebuild", attempts=_MAX_REBUILD_ATTEMPTS)
        return ProjectionWrite(recipes=len(document.recipes) if document else 0, written=written)

    def projection(self) -> RecipeProjection:
        """The cached projection document, as planning sees it."""
        return self._load_projection().projection

    def write_projection(self, projection: RecipeProjection) -> bool:
        """Publish a projection built from data written outside the table (the migration). True when written.

        The document comes from the source corpus, so a lost race re-derives from the table instead of
        republishing the snapshot: a recipe imported while the migration ran stays in the projection.
        """
        document = {"current": projection}

        def build(_current: RecipeProjection, refresh: bool) -> RecipeProjection:
            if refresh:
                document["current"] = self._projection_from_table()
            return document["current"]

        return self._publish(build, what="the migration", attempts=_MAX_REBUILD_ATTEMPTS)

    def _projection_from_table(self) -> RecipeProjection:
        """The whole projection, scanned back out of the table."""
        rows = self._scan()
        # SOURCE pointers share `sk=RECIPE`; only a recipe row carries a body.
        recipes = [_stored_recipe(row) for row in rows if row["sk"] == RECIPE_SK and "body" in row]
        answers = [_answer_from_row(row) for row in rows if str(row["sk"]).startswith(ANSWER_PREFIX)]
        return build_projection([recipe for recipe in recipes if recipe is not None], answers)

    # -- projection cache ---------------------------------------------------------------------------

    def _load_projection(self) -> _LoadedProjection:
        cached = _projection_cache.get(self._projections)
        now = time.monotonic()
        if cached is not None and now - cached[0] < self.index_ttl_seconds:
            return cached[1]
        raw = self._projections.read()
        if raw is None:
            logger.error("recipe projection missing", extra={"table": self._table})
            loaded = _LoadedProjection(raw=None, projection=RecipeProjection(), index=None)
        else:
            projection = loads(raw)
            loaded = _LoadedProjection(raw=raw, projection=projection, index=RecipeSearchIndex(projection.summaries()))
        _projection_cache[self._projections] = (now, loaded)
        return loaded

    def _fresh_projection(self) -> tuple[ProjectionSnapshot, RecipeProjection]:
        """The projection as the object has it now, never from this process's cache: writers merge into it."""
        snapshot = self._projections.load()
        if snapshot.data is None:
            return snapshot, RecipeProjection()
        return snapshot, loads(snapshot.data)

    def _publish(
        self,
        build: Callable[[RecipeProjection, bool], RecipeProjection],
        *,
        what: str,
        attempts: int = _MAX_PUBLISH_ATTEMPTS,
    ) -> bool:
        """Publish the document `build` returns for the object's current state, or lose the race and retry.

        `build(current, refresh)` is called on every attempt: `refresh` is False on the first try and True
        after a lost race, so a merge re-applies itself to the fresh document, and a full rebuild recomputes
        from the table instead of republishing a snapshot taken before the other writer's change.
        Returns False when the object already says what `build` would write.
        """
        last_error: Exception | None = None
        for attempt in range(attempts):
            snapshot, current = self._fresh_projection()
            document = build(current, attempt > 0)
            data = dumps(document)
            if data == snapshot.data:
                self._remember(snapshot, document)
                return False
            try:
                if self._projections.store(data, etag=snapshot.etag):
                    self._remember(ProjectionSnapshot(data=data, etag=None), document)
                    return True
            except ClientError as error:
                if not _is_publish_retryable(error):
                    last_error = error
                    break
                last_error = error
            if attempt < attempts - 1:
                time.sleep(random.uniform(0.02, min(0.02 * 2**attempt, 0.5)))  # noqa: S311 - backoff jitter
        logger.error(
            "recipe projection publish failed; the table has the change and planning will not see it until the"
            f" projection is rebuilt ({what}): {_REBUILD_COMMAND}",
            extra={"table": self._table, "change": what, "error": repr(last_error)},
        )
        raise ProjectionPublishError(
            f"could not publish the recipe projection ({what}) after {attempts} attempts. "
            f"The table holds the change; rebuild the projection with: {_REBUILD_COMMAND}"
        ) from last_error

    def _remember(self, snapshot: ProjectionSnapshot, projection: RecipeProjection) -> None:
        """Keep this process's read cache in step with the document it just read or wrote."""
        index = RecipeSearchIndex(projection.summaries()) if snapshot.data is not None else None
        _projection_cache[self._projections] = (
            time.monotonic(),
            _LoadedProjection(raw=snapshot.data, projection=projection, index=index),
        )

    def _projected(self, recipe: StoredRecipe, projection: RecipeProjection) -> ProjectedRecipe:
        """The projection entry for a recipe just written: its summary and the answers that still apply."""
        fingerprint = _fingerprint(recipe)
        known = projection.by_id(recipe.external_id)
        key = known.summary.key if known is not None else recipe_blob_key(recipe.external_id)
        answers = latest_per_question(
            answer for answer in self._answers_for(recipe.external_id) if answer.content_hash == fingerprint
        )
        return ProjectedRecipe(
            summary=RecipeSummary.from_recipe(recipe, key=key),
            answers=answers,
            attributes=known.attributes if known is not None else {},
        )

    def _project_answers(self, projection: RecipeProjection, changed: Sequence[RecipeAnswer]) -> RecipeProjection:
        """The projection with the stored answers folded in, dropping answers for superseded content."""
        by_recipe: dict[str, list[RecipeAnswer]] = {}
        for answer in changed:
            by_recipe.setdefault(answer.recipe_id, []).append(answer)
        for recipe_id, answers in by_recipe.items():
            entry = projection.by_id(recipe_id)
            recipe = self.get(recipe_id)
            if entry is None or recipe is None:
                logger.warning("answer stored for a recipe missing from the projection", extra={"recipe_id": recipe_id})
                continue
            # Only an answer about the recipe's current state belongs in the projection.
            fingerprint = _fingerprint(recipe)
            incoming = {_answer_key(answer): answer for answer in answers if answer.content_hash == fingerprint}
            kept = [
                answer
                for answer in entry.answers
                if answer.content_hash == fingerprint and _answer_key(answer) not in incoming
            ]
            answers_for_entry = latest_per_question([*kept, *incoming.values()])
            projection = projection.with_recipe(entry.model_copy(update={"answers": answers_for_entry}))
        return projection

    # -- table access -------------------------------------------------------------------------------

    def _source_is_current(self, pointer: dict[str, Any]) -> bool:
        stored = self._get(str(pointer["pk"]), RECIPE_SK)
        return stored is not None and stored.get("recipe_id") == pointer["recipe_id"]

    def _answers_for(self, recipe_id: str) -> list[RecipeAnswer]:
        rows = self._retry(
            lambda: self._client.query(
                TableName=self._table,
                KeyConditionExpression="pk = :pk AND begins_with(sk, :answers)",
                ExpressionAttributeValues={":pk": recipe_pk(recipe_id), ":answers": ANSWER_PREFIX},
                ConsistentRead=True,
            )
        )["Items"]
        return [_answer_from_row(row) for row in rows]

    def _get(self, pk: str, sk: str) -> dict[str, Any] | None:
        response = self._retry(
            lambda: self._client.get_item(TableName=self._table, Key={"pk": pk, "sk": sk}, ConsistentRead=True)
        )
        return response.get("Item")

    def _put(self, item: dict[str, Any]) -> None:
        self._retry(lambda: self._client.put_item(TableName=self._table, Item=item))

    def _transact(self, ops: list[dict[str, Any]]) -> None:
        self._retry(lambda: self._client.transact_write_items(TransactItems=ops))

    def _scan(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        kwargs: dict[str, Any] = {"TableName": self._table, "ConsistentRead": True}
        while True:
            page = self._retry(lambda: self._client.scan(**kwargs))
            rows.extend(page["Items"])
            if "LastEvaluatedKey" not in page:
                return rows
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    def _retry[T](self, operation: Callable[[], T]) -> T:
        return retry_throttled(operation)


def recipe_item(recipe: StoredRecipe) -> dict[str, Any]:
    """The RECIPE item for a recipe: the body with the fields the table indexes or compares on."""
    return {"pk": recipe_pk(recipe.external_id), "sk": RECIPE_SK, "body": _recipe_body(recipe)}


def source_item(recipe: StoredRecipe) -> dict[str, Any] | None:
    """The SOURCE pointer for a URL-imported recipe, or None when there is no URL to dedupe on."""
    if not recipe.source_url:
        return None
    return {
        "pk": source_pk(recipe.source_url),
        "sk": RECIPE_SK,
        "recipe_id": recipe.external_id,
        "source_url": recipe.source_url,
    }


def answer_item(answer: RecipeAnswer) -> dict[str, Any]:
    """The ANSWER item: one per (recipe, question, criteria hash)."""
    # DynamoDB takes no floats: the probability is a Decimal on the wire and a float in the model.
    return {
        "pk": recipe_pk(answer.recipe_id),
        "sk": answer_sk(answer.question, answer.criteria_hash),
        "recipe_id": answer.recipe_id,
        "question": answer.question,
        "probability": Decimal(str(answer.probability)),
        "model": answer.model,
        "content_hash": answer.content_hash,
        "criteria_hash": answer.criteria_hash,
        "computed_at": answer.computed_at.isoformat(),
    }


def item_write_units(item: dict[str, Any]) -> int:
    """What DynamoDB charges to write one item: 1 unit per KiB of attribute names and values, rounded up.

    Sized the way DynamoDB sizes an item, not the way JSON encodes it: a string attribute costs its UTF-8
    bytes (no quotes or escapes), a number its significant digits, a set its elements, and a list or map a
    small container overhead. Counted from the item the write will send, so a caller pacing writes charges
    what the write costs rather than a guess from the recipe body.
    """
    return max(1, math.ceil(_item_size_bytes(item) / 1024))


def recipe_write_units(recipe: StoredRecipe) -> int:
    """Write units for one recipe: its body and SOURCE pointer in one transaction, which bills double."""
    items = [recipe_item(recipe), source_item(recipe)]
    return 2 * sum(item_write_units(item) for item in items if item is not None)


def answer_write_units(answer: RecipeAnswer) -> int:
    return item_write_units(answer_item(answer))


def _item_size_bytes(item: dict[str, Any]) -> int:
    return sum(len(str(name).encode("utf-8")) + _value_size_bytes(value) for name, value in item.items())


def _value_size_bytes(value: Any) -> int:
    """The bytes DynamoDB stores for one attribute value."""
    if isinstance(value, str):
        return len(value.encode("utf-8"))
    if isinstance(value, bool):
        return 1
    if isinstance(value, (int, float, Decimal)):
        return len(str(value).encode("utf-8"))  # DynamoDB charges a number by its significant digits
    if isinstance(value, bytes | bytearray):
        return len(value)
    if isinstance(value, list | tuple):
        return 3 + sum(_value_size_bytes(element) for element in value)
    if isinstance(value, dict):
        return 3 + sum(len(str(key).encode("utf-8")) + _value_size_bytes(element) for key, element in value.items())
    return len(str(value).encode("utf-8"))


def _recipe_body(recipe: StoredRecipe) -> str:
    body = json.dumps(recipe_payload(recipe), sort_keys=True, separators=(",", ":"))
    size = len(body.encode("utf-8"))
    if size > MAX_RECIPE_BYTES:
        raise RecipeTooLargeError(
            f"recipe {recipe.external_id!r} is {size} bytes, over the corpus's {MAX_RECIPE_BYTES} byte budget"
        )
    return body


_TRANSIENT_S3_CODES = {"SlowDown", "RequestTimeout", "InternalError", "ServiceUnavailable", "RequestLimitExceeded"}


def _is_publish_retryable(error: ClientError) -> bool:
    """Whether a publication error is worth backing off and retrying: Dynamo throttling or an S3 blip."""
    return _is_throttle(error) or error.response.get("Error", {}).get("Code") in _TRANSIENT_S3_CODES


def _is_throttle(error: ClientError) -> bool:
    """Whether DynamoDB asked us to back off, including the cancellation reasons a transaction reports."""
    code = error.response["Error"]["Code"]
    if code in _RETRYABLE:
        return True
    if code != "TransactionCanceledException":
        return False
    reasons = [reason.get("Code", "None") for reason in error.response.get("CancellationReasons") or []]
    # `None` is a healthy item; a conditional failure is a real refusal, never something to retry.
    retryable = [reason for reason in reasons if reason != "None"]
    return bool(retryable) and all(reason in _RETRYABLE_CANCELLATION_REASONS for reason in retryable)


def _stored_recipe(row: dict[str, Any]) -> StoredRecipe | None:
    try:
        return StoredRecipe.model_validate_json(row["body"])
    except (KeyError, TypeError, ValueError):
        logger.warning("stored recipe body is unreadable", extra={"pk": row.get("pk")})
        return None


def _answer_from_row(row: dict[str, Any]) -> RecipeAnswer:
    return RecipeAnswer(
        recipe_id=str(row["recipe_id"]),
        question=str(row["question"]),
        probability=float(row["probability"]),
        model=str(row["model"]),
        content_hash=str(row["content_hash"]),
        criteria_hash=str(row["criteria_hash"]),
        computed_at=row["computed_at"],
    )


def _answer_key(answer: RecipeAnswer) -> tuple[str, str, str]:
    return (answer.recipe_id, answer.question, answer.criteria_hash)


def _fingerprint(recipe: StoredRecipe) -> str:
    return content_fingerprint(recipe.title, [ingredient.canonical_name for ingredient in recipe.ingredients])
