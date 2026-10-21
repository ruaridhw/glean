"""The gzipped S3 projection that planning reads in dynamo mode.

Reading every recipe's summary out of DynamoDB would cost 45-90 read units per Generate, which is
9-18 seconds of throttling at the table's 5 RCU (spec 6.1, "Recipe store"). So the store rebuilds one
small document in the recipe-cache bucket after every change: each recipe's summary, its current
decision answers, and room for the attributes F2/V5 fill in. Lambdas cache it for five minutes.

The document is deterministic — sorted by recipe id, no build timestamp, gzip with `mtime=0` — so an
unchanged rebuild produces identical bytes and the writer can skip the S3 put.
"""

from __future__ import annotations

import gzip
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel, Field, ValidationError

from glean.observability import logger
from glean.recipes.answers import RecipeAnswer, content_fingerprint
from glean.recipes.corpus import recipe_blob_key
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
    """One recipe as planning needs it: its summary, its current answers, and its future attributes."""

    summary: RecipeSummary
    answers: list[RecipeAnswer] = Field(default_factory=list)
    # F2/V5 fill these (`main_protein`, `cuisine`, `active_time_mins`, ...) without a schema change here.
    attributes: dict[str, Any] = Field(default_factory=dict)


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


class ProjectionStore(Protocol):
    """Where the projection document lives: one opaque byte string, or None before the first build."""

    def read(self) -> bytes | None: ...
    def write(self, data: bytes) -> None: ...


class S3ProjectionStore:
    def __init__(self, bucket: str, *, region: str, key: str = PROJECTION_KEY) -> None:
        import boto3  # noqa: PLC0415 - match the inline-boto3 pattern used elsewhere in the codebase

        self._bucket = bucket
        self._key = key
        self._client = boto3.client("s3", region_name=region)

    def read(self) -> bytes | None:
        from botocore.exceptions import ClientError  # noqa: PLC0415

        try:
            return self._client.get_object(Bucket=self._bucket, Key=self._key)["Body"].read()
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code not in {"NoSuchKey", "404", "NoSuchBucket"}:
                logger.warning("recipe projection read failed", extra={"key": self._key, "code": code})
            return None

    def write(self, data: bytes) -> None:
        self._client.put_object(
            Bucket=self._bucket, Key=self._key, Body=data, ContentType="application/json", ContentEncoding="gzip"
        )


class FilesystemProjectionStore:
    def __init__(self, root: Path, *, key: str = PROJECTION_KEY) -> None:
        self._path = root / key

    def read(self) -> bytes | None:
        try:
            return self._path.read_bytes()
        except OSError:
            return None

    def write(self, data: bytes) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_bytes(data)


class InMemoryProjectionStore:
    def __init__(self, data: bytes | None = None) -> None:
        self.data = data
        self.writes = 0

    def read(self) -> bytes | None:
        return self.data

    def write(self, data: bytes) -> None:
        self.data = data
        self.writes += 1


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
        projected.append(
            ProjectedRecipe(
                summary=RecipeSummary.from_recipe(recipe, key=key),
                answers=[
                    answer
                    for answer in answers_by_recipe.get(recipe.external_id, [])
                    if answer.content_hash == fingerprint
                ],
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
