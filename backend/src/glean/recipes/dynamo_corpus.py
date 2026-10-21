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
"""

from __future__ import annotations

import hashlib
import json
import random
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from weakref import WeakKeyDictionary

import boto3
from botocore.exceptions import ClientError

from glean.observability import logger
from glean.recipes.answers import RecipeAnswer, content_fingerprint
from glean.recipes.corpus import recipe_blob_key, recipe_payload
from glean.recipes.projection import (
    PROJECTION_TTL_SECONDS,
    ProjectedRecipe,
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
    "ProjectionWrite",
    "RecipeTooLargeError",
    "answer_sk",
    "recipe_pk",
    "retry_throttled",
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
}
_MAX_ATTEMPTS = 6


class RecipeTooLargeError(Exception):
    """A recipe body is over the corpus's 10 KB budget, so it can't be stored as one item."""


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
        known = {
            (answer.recipe_id, answer.question, answer.criteria_hash): answer
            for answer in self._load_projection().projection.answers()
        }
        changed = [answer for answer in answers if known.get(_answer_key(answer)) != answer]
        for answer in changed:
            self._put(_answer_item(answer))
        if changed and rebuild_projection:
            self._store_projection(self._project_answers(changed))
        return len(changed)

    # -- the migration and F2's runner ---------------------------------------------------------------

    def upsert(self, recipe: StoredRecipe) -> bool:
        """Write the recipe and its SOURCE pointer unless both are already stored. True when written."""
        body = _recipe_body(recipe)
        pointer = self._source_item(recipe)
        stored = self._get(recipe_pk(recipe.external_id), RECIPE_SK)
        if stored is not None and stored.get("body") == body and self._source_is_current(pointer):
            return False
        self._transact(
            [
                {"Put": {"TableName": self._table, "Item": _recipe_item(recipe, body)}},
                {"Put": {"TableName": self._table, "Item": pointer}},
            ]
        )
        self._store_projection(self._load_projection().projection.with_recipe(self._projected(recipe)))
        return True

    def rebuild_projection(self) -> ProjectionWrite:
        """Rebuild the whole projection from the table. Owner-run, or F2's runner after a bulk change.

        A consistent scan: 632 recipe bodies is a few hundred read units, slow at 5 RCU but exact. Prefer
        `save_answers` for an incremental change.
        """
        rows = self._scan()
        # SOURCE pointers share `sk=RECIPE`; only a recipe row carries a body.
        recipes = [_stored_recipe(row) for row in rows if row["sk"] == RECIPE_SK and "body" in row]
        answers = [_answer_from_row(row) for row in rows if str(row["sk"]).startswith(ANSWER_PREFIX)]
        projection = build_projection([recipe for recipe in recipes if recipe is not None], answers)
        return ProjectionWrite(recipes=len(projection.recipes), written=self._store_projection(projection))

    def projection(self) -> RecipeProjection:
        """The cached projection document, as planning sees it."""
        return self._load_projection().projection

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

    def _store_projection(self, projection: RecipeProjection) -> bool:
        """Write the projection unless it is byte-identical to what is stored. True when written."""
        data = dumps(projection)
        cached = _projection_cache.get(self._projections)
        if cached is not None and cached[1].raw == data and cached[1].index is not None:
            return False
        if cached is None or cached[1].raw != data:
            self._projections.write(data)
        _projection_cache[self._projections] = (
            time.monotonic(),
            _LoadedProjection(raw=data, projection=projection, index=RecipeSearchIndex(projection.summaries())),
        )
        return cached is None or cached[1].raw != data

    def _projected(self, recipe: StoredRecipe) -> ProjectedRecipe:
        """The projection entry for a recipe just written: its summary and the answers that still apply."""
        fingerprint = _fingerprint(recipe)
        known = self._load_projection().projection.by_id(recipe.external_id)
        key = known.summary.key if known is not None else recipe_blob_key(recipe.external_id)
        answers = [answer for answer in self._answers_for(recipe.external_id) if answer.content_hash == fingerprint]
        return ProjectedRecipe(
            summary=RecipeSummary.from_recipe(recipe, key=key),
            answers=sorted(answers, key=_answer_sort_key),
            attributes=known.attributes if known is not None else {},
        )

    def _project_answers(self, changed: Sequence[RecipeAnswer]) -> RecipeProjection:
        """The projection with the stored answers folded in, dropping answers for superseded content."""
        projection = self._load_projection().projection
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
            answers_for_entry = sorted([*kept, *incoming.values()], key=_answer_sort_key)
            projection = projection.with_recipe(entry.model_copy(update={"answers": answers_for_entry}))
        return projection

    # -- table access -------------------------------------------------------------------------------

    def _source_item(self, recipe: StoredRecipe) -> dict[str, Any]:
        item: dict[str, Any] = {
            "pk": source_pk(recipe.source_url or ""),
            "sk": RECIPE_SK,
            "recipe_id": recipe.external_id,
        }
        if recipe.source_url:
            item["source_url"] = recipe.source_url
        return item

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


def _recipe_body(recipe: StoredRecipe) -> str:
    body = json.dumps(recipe_payload(recipe), sort_keys=True, separators=(",", ":"))
    size = len(body.encode("utf-8"))
    if size > MAX_RECIPE_BYTES:
        raise RecipeTooLargeError(
            f"recipe {recipe.external_id!r} is {size} bytes, over the corpus's {MAX_RECIPE_BYTES} byte budget"
        )
    return body


def _recipe_item(recipe: StoredRecipe, body: str) -> dict[str, Any]:
    return {"pk": recipe_pk(recipe.external_id), "sk": RECIPE_SK, "body": body}


def _stored_recipe(row: dict[str, Any]) -> StoredRecipe | None:
    try:
        return StoredRecipe.model_validate_json(row["body"])
    except (KeyError, TypeError, ValueError):
        logger.warning("stored recipe body is unreadable", extra={"pk": row.get("pk")})
        return None


def _answer_item(answer: RecipeAnswer) -> dict[str, Any]:
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


def _answer_sort_key(answer: RecipeAnswer) -> tuple[str, str]:
    return (answer.question, answer.criteria_hash)


def _fingerprint(recipe: StoredRecipe) -> str:
    return content_fingerprint(recipe.title, [ingredient.canonical_name for ingredient in recipe.ingredients])


def _is_throttle(error: ClientError) -> bool:
    return error.response["Error"]["Code"] in _RETRYABLE
