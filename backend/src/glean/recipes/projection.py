"""The gzipped S3 projection that planning reads in dynamo mode.

Reading every recipe's summary out of DynamoDB would cost 45-90 read units per Generate, which is
9-18 seconds of throttling at the table's 5 RCU (spec 6.1, "Recipe store"). So the store rebuilds one
small document in the recipe-cache bucket after every change: each recipe's summary, its current
decision answers, and room for the attributes F2/V5 fill in. Lambdas cache it for five minutes.

The document is deterministic — sorted by recipe id, no build timestamp, gzip with `mtime=0` — so an
unchanged rebuild produces identical bytes, and the writer can skip the put.

Every writer publishes the whole object, so publication is conditional on the object version it read
(`store(..., etag=...)`, an S3 `If-Match`): two Lambdas importing different recipes at once would
otherwise each publish their own snapshot and one of the two entries would disappear for good.
"""

from __future__ import annotations

import contextlib
import gzip
import hashlib
import os
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel, Field, ValidationError

from glean.observability import logger
from glean.recipes.answers import RecipeAnswer, content_fingerprint, latest_per_question
from glean.recipes.attributes import RecipeAttributes
from glean.recipes.corpus import recipe_blob_key
from glean.recipes.enrichment.projection_attributes import attributes_from_answers
from glean.recipes.search_index import RecipeSummary

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path

    from glean.recipes.stored import StoredRecipe

PROJECTION_KEY = "projection/recipes-v1.json.gz"
PROJECTION_VERSION = 1
# How long a Lambda trusts a loaded projection. Long enough that Generate's frequent reads are free,
# short enough that an import or enrichment run elsewhere is visible without a deploy.
PROJECTION_TTL_SECONDS = 300.0


class ProjectionError(Exception):
    """The stored projection document can't be read as one this build understands."""


class ProjectedRecipe(BaseModel):
    """One recipe as planning needs it: its summary, its current answers, and its attributes."""

    summary: RecipeSummary
    answers: list[RecipeAnswer] = Field(default_factory=list)
    # V5's attributes by their G1 names (`main_protein`, `cuisine`, `active_time`, ...), each a stored value
    # or `unsure` (recipes/attributes.py). Plain strings, so a document written by any build reads back.
    attributes: dict[str, str] = Field(default_factory=dict)

    @property
    def recipe_attributes(self) -> RecipeAttributes:
        """The attributes typed, and `unsure` where the entry carries nothing: how planning reads them."""
        return RecipeAttributes.from_mapping(self.attributes)


class RecipeProjection(BaseModel):
    version: int = PROJECTION_VERSION
    recipes: list[ProjectedRecipe] = Field(default_factory=list)

    def by_id(self, recipe_id: str) -> ProjectedRecipe | None:
        return next((recipe for recipe in self.recipes if recipe.summary.external_id == recipe_id), None)

    def summaries(self) -> list[RecipeSummary]:
        return [recipe.summary for recipe in self.recipes]

    def answers(self) -> list[RecipeAnswer]:
        return [answer for recipe in self.recipes for answer in recipe.answers]

    def with_recipe(self, recipe: ProjectedRecipe) -> RecipeProjection:
        """This projection with `recipe` replaced or inserted, still sorted by recipe id."""
        others = [existing for existing in self.recipes if existing.summary.external_id != recipe.summary.external_id]
        return self.model_copy(update={"recipes": sorted([*others, recipe], key=_by_id)})


@dataclass(frozen=True)
class ProjectionSnapshot:
    """The document as read, with the version a conditional publish must present."""

    data: bytes | None
    etag: str | None


class ProjectionStore(Protocol):
    """Where the projection document lives, with the object version a writer has to publish against."""

    def read(self) -> bytes | None:
        """The current document, for verification and scripts (never for a read-modify-write)."""
        ...

    def load(self) -> ProjectionSnapshot: ...

    def store(self, data: bytes, *, etag: str | None) -> bool:
        """Publish `data` only if the object is still at `etag` (`None`: it must not exist yet).

        Returns False when another writer got there first, so the caller re-reads and re-applies its
        change instead of dropping the other writer's entry.
        """
        ...


# S3 answers a lost conditional write in more than one way: a stale ETag, a conditional-request conflict
# between two conditional writes, or the object disappearing under an If-Match. Transient blips are the same
# answer as far as a publisher is concerned: read again and retry. Everything else is a real refusal.
_RETRYABLE_S3_CODES = {
    "PreconditionFailed",
    "412",
    "ConditionalRequestConflict",
    "409",
    "NoSuchKey",
    "404",
    "OperationAborted",
    "SlowDown",
    "RequestTimeout",
    "InternalError",
    "ServiceUnavailable",
    "RequestLimitExceeded",
}
# The subset worth re-raising to the publisher, which backs off before trying again.
_TRANSIENT_S3_CODES = {"SlowDown", "RequestTimeout", "InternalError", "ServiceUnavailable", "RequestLimitExceeded"}


class S3ProjectionStore:
    def __init__(self, bucket: str, *, region: str, key: str = PROJECTION_KEY, client: Any | None = None) -> None:
        if client is None:
            import boto3  # noqa: PLC0415 - match the inline-boto3 pattern used elsewhere in the codebase

            client = boto3.client("s3", region_name=region)
        self._bucket = bucket
        self._key = key
        self._client = client

    def read(self) -> bytes | None:
        return self.load().data

    def load(self) -> ProjectionSnapshot:
        from botocore.exceptions import ClientError  # noqa: PLC0415

        try:
            response = self._client.get_object(Bucket=self._bucket, Key=self._key)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in _TRANSIENT_S3_CODES:
                raise  # let the publisher back off rather than treat a blip as "no projection"
            if code not in {"NoSuchKey", "404", "NoSuchBucket"}:
                logger.warning("recipe projection read failed", extra={"key": self._key, "code": code})
            return ProjectionSnapshot(data=None, etag=None)
        return ProjectionSnapshot(data=response["Body"].read(), etag=response.get("ETag"))

    def store(self, data: bytes, *, etag: str | None) -> bool:
        from botocore.exceptions import ClientError  # noqa: PLC0415

        kwargs: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": self._key,
            "Body": data,
            "ContentType": "application/json",
            "ContentEncoding": "gzip",
        }
        if etag is None:
            kwargs["IfNoneMatch"] = "*"
        else:
            kwargs["IfMatch"] = etag
        try:
            self._client.put_object(**kwargs)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in _RETRYABLE_S3_CODES:
                return False  # read the object again: the ETag, the conditional race, or the object changed
            raise
        return True


class FilesystemProjectionStore:
    """A local projection file. The version is the content hash; compare-and-swap is best effort.

    Local rehearsal only: two processes can still interleave between the read and the replace, which is
    why the deployed writer is the S3 adapter with its `If-Match`.
    """

    def __init__(self, root: Path, *, key: str = PROJECTION_KEY) -> None:
        self._path = root / key

    def read(self) -> bytes | None:
        return self.load().data

    def load(self) -> ProjectionSnapshot:
        try:
            data = self._path.read_bytes()
        except OSError:
            return ProjectionSnapshot(data=None, etag=None)
        return ProjectionSnapshot(data=data, etag=_content_etag(data))

    def store(self, data: bytes, *, etag: str | None) -> bool:
        current = self.load()
        if current.etag != etag:
            return False
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp = tempfile.mkstemp(dir=self._path.parent, prefix=f".{self._path.name}.", suffix=".tmp")
        try:
            with os.fdopen(handle, "wb") as file:
                file.write(data)
            os.replace(temp, self._path)
        except OSError:
            with contextlib.suppress(OSError):
                os.unlink(temp)
            raise
        return True


@lru_cache(maxsize=1)
def get_projection_store() -> ProjectionStore:
    from glean.config import get_settings  # noqa: PLC0415 - avoid a circular import at module load
    from glean.recipe_api.blob_store import DEFAULT_CACHE_DIR  # noqa: PLC0415

    settings = get_settings()
    if settings.s3_recipe_cache_bucket:
        return S3ProjectionStore(settings.s3_recipe_cache_bucket, region=settings.aws_region)
    return FilesystemProjectionStore(DEFAULT_CACHE_DIR)


def build_projection(
    recipes: Iterable[StoredRecipe],
    answers: Iterable[RecipeAnswer],
    *,
    keys: Mapping[str, str] | None = None,
) -> RecipeProjection:
    """The projection for `recipes` and their `answers`, keeping only the answers that still apply.

    `keys` maps a recipe id to the blob key it was stored under, so a corpus migrated from S3 keeps the
    blob layout in its summaries; anything missing falls back to the key the blob store would use.
    An answer is kept only when it answered the recipe's current state: a content change voids it.
    """
    keys = keys or {}
    answers_by_recipe: dict[str, list[RecipeAnswer]] = {}
    for answer in answers:
        answers_by_recipe.setdefault(answer.recipe_id, []).append(answer)
    projected = []
    for recipe in recipes:
        fingerprint = content_fingerprint(
            recipe.title, [ingredient.canonical_name for ingredient in recipe.ingredients]
        )
        key = keys.get(recipe.external_id) or recipe_blob_key(recipe.external_id)
        # Only the answers about the recipe's current state, and for each question only the one the latest
        # wording produced: an older criteria hash must never shadow the current answer.
        current = latest_per_question(
            answer for answer in answers_by_recipe.get(recipe.external_id, []) if answer.content_hash == fingerprint
        )
        projected.append(
            ProjectedRecipe(
                summary=RecipeSummary.from_recipe(recipe, key=key),
                answers=current,
                # Every recipe has attributes; one nothing has enriched is `unsure` throughout. Derived from
                # the answers rather than stored twice: the answers are the authority, this is the cache.
                attributes=attributes_from_answers(current, content_hash=fingerprint).as_mapping(),
            )
        )
    return RecipeProjection(recipes=sorted(projected, key=_by_id))


def dumps(projection: RecipeProjection) -> bytes:
    return gzip.compress(projection.model_dump_json().encode("utf-8"), mtime=0)


def loads(raw: bytes) -> RecipeProjection:
    try:
        projection = RecipeProjection.model_validate_json(gzip.decompress(raw))
    except (OSError, ValueError, ValidationError) as exc:
        raise ProjectionError(f"recipe projection is unreadable: {exc}") from exc
    if projection.version != PROJECTION_VERSION:
        raise ProjectionError(
            f"recipe projection is version {projection.version}, this build writes {PROJECTION_VERSION}"
        )
    return projection


def _by_id(projected: ProjectedRecipe) -> str:
    return projected.summary.external_id


def _content_etag(data: bytes) -> str:
    return f'"{hashlib.sha256(data).hexdigest()}"'
