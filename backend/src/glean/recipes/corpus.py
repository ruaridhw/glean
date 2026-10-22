"""The recipe corpus: bodies, summaries and stored decision answers.

The corpus has two adapters behind one small interface — the seam is the *backend*, not a branch in
every caller:

- `BlobCorpusBackend` — the deployed S3 `corpus/` prefix (or the `.cache/...` tree): one JSON blob per
  recipe, one JSONL search index, one JSONL of dietary answers.
- `DynamoCorpusBackend` (`recipes/dynamo_corpus.py`) — the `glean-recipes` table (F1/#162): a recipe
  body item, one item per decision answer, a SOURCE pointer for import dedupe, and a gzipped S3
  projection that search and planning read.

`RecipeCorpusStore` is what callers use: it resolves the adapter from `RECIPE_STORE` and runs search over
whichever index the adapter offers. Its interface does not change with the adapter, so the API, the meal
planner and the scripts never know which store they are on. `RECIPE_STORE` defaults to `blobs`.
"""

from __future__ import annotations

import json
import time
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Protocol, cast, runtime_checkable
from urllib.parse import quote
from weakref import WeakKeyDictionary

from pydantic import ValidationError

from glean.observability import logger
from glean.recipe_api.blob_store import get_recipe_corpus_store
from glean.recipes.answers import DIETARY_DECISIONS_KEY, RecipeAnswer
from glean.recipes.search_index import INDEX_KEY, RecipeSearchIndex, RecipeSummary, dumps_summaries, loads_summaries
from glean.recipes.stored import StoredRecipe

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence
    from pathlib import Path

    from glean.recipe_api.blob_store import BlobStore
    from glean.recipes.projection import ProjectionStore

__all__ = [
    "DIETARY_DECISIONS_KEY",
    "BlobCorpusBackend",
    "CorpusBackend",
    "CorpusStoreError",
    "RecipeCorpusStore",
    "get_corpus_backend",
    "open_corpus",
    "projection_store_for",
    "recipe_blob_key",
    "recipe_payload",
]

# How long a loaded blob index is trusted before re-reading it, so recipes saved by
# another Lambda container become searchable here within this window.
_INDEX_TTL_SECONDS = 60.0

# Per blob store: (monotonic load time, index or None if the index was missing).
# Keyed weakly so short-lived stores (tests, scripts) don't pin their indexes.
_index_cache: WeakKeyDictionary[BlobStore, tuple[float, RecipeSearchIndex | None]] = WeakKeyDictionary()


class CorpusStoreError(Exception):
    """The configured corpus store can't be opened, so the corpus would silently read as empty."""


@runtime_checkable
class CorpusBackend(Protocol):
    """Where corpus bodies, summaries and decision answers live. Both adapters implement exactly this."""

    def save(self, recipe: StoredRecipe) -> None:
        """Write the recipe and keep the summaries current."""
        ...

    def publish(self, recipe: StoredRecipe) -> bool:
        """Make an already-stored recipe visible to search and planning, without rewriting it.

        Idempotent, and the repair path for a summary/projection publish that failed earlier. Returns
        whether anything changed.
        """
        ...

    def get(self, recipe_id: str) -> StoredRecipe | None: ...

    def get_by_source_url(self, source_url: str) -> StoredRecipe | None: ...

    def index(self) -> RecipeSearchIndex | None:
        """The cached search index over every recipe summary, or None when there is none yet."""
        ...

    def all_recipes(self) -> Iterator[StoredRecipe]: ...

    def rebuild_index(self) -> int:
        """Rebuild the search index from every stored recipe, returning the recipe count."""
        ...

    def answers(self) -> list[RecipeAnswer]:
        """Every stored decision answer (dietary now, F2's enrichers later)."""
        ...

    def save_answers(self, answers: Sequence[RecipeAnswer]) -> int:
        """Store the answers that changed, returning how many were written."""
        ...


def recipe_blob_key(recipe_id: str) -> str:
    """The blob key a recipe is stored under: its id namespace as a directory, then the id."""
    namespace, separator, namespaced_recipe_id = recipe_id.partition(":")
    if not separator:
        namespace = "_unknown"
        namespaced_recipe_id = recipe_id
    return f"{quote(namespace, safe='')}/{quote(namespaced_recipe_id, safe='')}.json"


def recipe_payload(recipe: StoredRecipe) -> dict[str, Any]:
    """The recipe as stored: JSON-safe, without the empty ingredient ids an imported recipe carries."""
    data = recipe.model_dump(mode="json")
    for ingredient in data.get("ingredients", []):
        if isinstance(ingredient, dict) and ingredient.get("api_ingredient_id") is None:
            ingredient.pop("api_ingredient_id", None)
    return data


class BlobCorpusBackend:
    """The corpus as JSON blobs: one recipe per key, plus the JSONL index and the answers JSONL."""

    def __init__(self, blobs: BlobStore) -> None:
        self.blobs = blobs

    def save(self, recipe: StoredRecipe) -> None:
        content = json.dumps(recipe_payload(recipe), indent=2, sort_keys=True) + "\n"
        key = recipe_blob_key(recipe.external_id)
        self.blobs.write(key, content)
        self._upsert_summary(RecipeSummary.from_recipe(recipe, key=key))

    def publish(self, recipe: StoredRecipe) -> bool:
        summary = RecipeSummary.from_recipe(recipe, key=recipe_blob_key(recipe.external_id))
        index = self.index()
        if index is not None and index.by_id(recipe.external_id) == summary:
            return False
        self._upsert_summary(summary)
        return True

    def get(self, recipe_id: str) -> StoredRecipe | None:
        index = self.index()
        summary = index.by_id(recipe_id) if index is not None else None
        return self._load(summary.key if summary is not None else recipe_blob_key(recipe_id))

    def get_by_source_url(self, source_url: str) -> StoredRecipe | None:
        index = self.index()
        summary = index.by_source_url(source_url) if index is not None else None
        return self._load(summary.key) if summary is not None else None

    def index(self) -> RecipeSearchIndex | None:
        cached = _index_cache.get(self.blobs)
        now = time.monotonic()
        if cached is not None and now - cached[0] < _INDEX_TTL_SECONDS:
            return cached[1]
        raw = self.blobs.read(INDEX_KEY)
        if raw is None:
            logger.error("recipe search index missing", extra={"key": INDEX_KEY})
            index = None
        else:
            index = RecipeSearchIndex(loads_summaries(raw))
        _index_cache[self.blobs] = (now, index)
        return index

    def all_recipes(self) -> Iterator[StoredRecipe]:
        """Yield every recipe blob in the corpus (the index and answers blobs are skipped)."""
        for key in self.blobs.list_keys():
            if (recipe := self._load(key)) is not None:
                yield recipe

    def rebuild_index(self) -> int:
        """Rebuild the search index by reading every recipe blob. Returns the recipe count."""
        summaries: dict[str, RecipeSummary] = {}
        for key in self.blobs.list_keys():
            if (recipe := self._load(key)) is not None:
                summaries[recipe.external_id] = RecipeSummary.from_recipe(recipe, key=key)
        self._write_index(summaries.values())
        return len(summaries)

    def answers(self) -> list[RecipeAnswer]:
        raw = self.blobs.read(DIETARY_DECISIONS_KEY)
        if raw is None:
            return []
        answers = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            try:
                answers.append(RecipeAnswer.model_validate_json(line))
            except ValidationError:
                continue
        return sorted(answers, key=_answer_order)

    def save_answers(self, answers: Sequence[RecipeAnswer]) -> int:
        ordered = sorted(answers, key=_answer_order)
        self.blobs.write(DIETARY_DECISIONS_KEY, "".join(answer.model_dump_json() + "\n" for answer in ordered))
        return len(ordered)

    # The blob store itself, for the pieces that still work on blobs (and the tests that seed corrupt ones).
    def read(self, key: str) -> str | None:
        return self.blobs.read(key)

    def write(self, key: str, content: str) -> None:
        self.blobs.write(key, content)

    def list_keys(self, prefix: str = "") -> list[str]:
        return self.blobs.list_keys(prefix)

    def _upsert_summary(self, summary: RecipeSummary) -> None:
        # Read fresh rather than from cache so a save never drops another container's recent writes.
        raw = self.blobs.read(INDEX_KEY)
        if raw is None:
            # No index yet (fresh local corpus): build it from the blobs, which include this recipe.
            self.rebuild_index()
            return
        summaries = {existing.external_id: existing for existing in loads_summaries(raw)}
        summaries[summary.external_id] = summary
        self._write_index(summaries.values())

    def _write_index(self, summaries: Iterable[RecipeSummary]) -> None:
        summaries = list(summaries)
        self.blobs.write(INDEX_KEY, dumps_summaries(summaries))
        _index_cache[self.blobs] = (time.monotonic(), RecipeSearchIndex(summaries))

    def _load(self, key: str) -> StoredRecipe | None:
        raw = self.blobs.read(key)
        if raw is None:
            return None
        try:
            return StoredRecipe.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
            return None


class RecipeCorpusStore:
    """The corpus as callers see it: one interface over whichever backend is configured."""

    def __init__(self, store: BlobStore | CorpusBackend | None = None) -> None:
        # `store` is the backend seam; `None` opens the one `RECIPE_STORE` selects.
        self.store: CorpusBackend = get_corpus_backend() if store is None else _as_backend(store)

    def save(self, recipe: StoredRecipe) -> StoredRecipe:
        self.store.save(recipe)
        return recipe

    def publish(self, recipe: StoredRecipe) -> bool:
        return self.store.publish(recipe)

    def get(self, recipe_id: str) -> StoredRecipe | None:
        return self.store.get(recipe_id)

    def get_by_source_url(self, source_url: str) -> StoredRecipe | None:
        return self.store.get_by_source_url(source_url)

    def search(
        self,
        q: str | None = None,
        cuisine: str | None = None,
        dietary: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[RecipeSummary], int]:
        index = self.store.index()
        if index is None:
            return [], 0
        return index.search(q=q, cuisine=cuisine, dietary=dietary, page=page, per_page=per_page)

    def all_recipes(self) -> Iterator[StoredRecipe]:
        return self.store.all_recipes()

    def rebuild_index(self) -> int:
        return self.store.rebuild_index()

    def answers(self) -> list[RecipeAnswer]:
        return self.store.answers()

    def save_answers(self, answers: Sequence[RecipeAnswer]) -> int:
        return self.store.save_answers(answers)


@lru_cache(maxsize=1)
def _dynamo_corpus_backend() -> CorpusBackend:
    """The DynamoDB backend, opened once per process so its projection cache is shared across requests."""
    from glean.config import get_settings  # noqa: PLC0415 - avoid a circular import at module load
    from glean.recipes.dynamo_corpus import DynamoCorpusBackend  # noqa: PLC0415 - boto3 only when used
    from glean.recipes.projection import get_projection_store  # noqa: PLC0415

    settings = get_settings()
    if not settings.recipes_table:
        raise CorpusStoreError("RECIPE_STORE=dynamo needs RECIPES_TABLE; refusing to read the corpus as empty")
    return DynamoCorpusBackend(settings.recipes_table, projection=get_projection_store(), region=settings.aws_region)


def get_corpus_backend() -> CorpusBackend:
    """The backend `RECIPE_STORE` selects. The blob path is default, so an unconfigured corpus stays blob-backed."""
    if _recipe_store() == "dynamo":
        return _dynamo_corpus_backend()
    return BlobCorpusBackend(get_recipe_corpus_store())


def _recipe_store() -> str:
    """`RECIPE_STORE` as configured, or `blobs` when this process has no deployment configuration at all.

    A script or test with no settings to read is on the blob path already, so it must not start failing
    because the choice of store is read through `Settings`.
    """
    from glean.config import get_settings  # noqa: PLC0415 - avoid a circular import at module load

    try:
        return get_settings().recipe_store
    except ValidationError:
        return "blobs"


def _as_backend(store: BlobStore | CorpusBackend) -> CorpusBackend:
    """The corpus backend for `store`: a bare BlobStore (every existing caller passes one) is the blob adapter.

    Discriminated on the corpus methods rather than `isinstance`, which would reject a backend that does not
    yet implement a newly added seam method.
    """
    if hasattr(store, "answers") or hasattr(store, "index"):
        return cast("CorpusBackend", store)
    return BlobCorpusBackend(store)


def _answer_order(answer: RecipeAnswer) -> tuple[str, str]:
    return (answer.recipe_id, answer.question)


def projection_store_for(
    *, bucket: str | None = None, cache_dir: Path | None = None, region: str = "eu-west-2"
) -> ProjectionStore:
    """Where the projection document lives: the recipe-cache bucket, or a local cache root."""
    from glean.recipe_api.blob_store import DEFAULT_CACHE_DIR  # noqa: PLC0415
    from glean.recipes.projection import FilesystemProjectionStore, S3ProjectionStore  # noqa: PLC0415 - cycle

    if bucket:
        return S3ProjectionStore(bucket, region=region)
    return FilesystemProjectionStore(cache_dir or DEFAULT_CACHE_DIR)


def open_corpus(
    *,
    table: str | None = None,
    bucket: str | None = None,
    cache_dir: Path | None = None,
    region: str = "eu-west-2",
    corpus_dir: Path | None = None,
) -> RecipeCorpusStore:
    """The store the corpus scripts should use: `--table` selects DynamoDB, otherwise the blob corpus.

    `--bucket` / `--cache-dir` says where the data lives: the `corpus/` prefix in blob mode, the projection
    document in dynamo mode. Scripts without `--table` therefore keep working exactly as before.
    """
    if table:
        from glean.recipes.dynamo_corpus import DynamoCorpusBackend  # noqa: PLC0415 - boto3 only when used

        projection = projection_store_for(bucket=bucket, cache_dir=cache_dir, region=region)
        return RecipeCorpusStore(DynamoCorpusBackend(table, projection=projection, region=region))
    if bucket:
        from glean.recipe_api.blob_store import S3BlobStore  # noqa: PLC0415

        return RecipeCorpusStore(BlobCorpusBackend(S3BlobStore(bucket, region=region, prefix="corpus/")))
    from glean.recipe_api.blob_store import FilesystemBlobStore  # noqa: PLC0415

    return RecipeCorpusStore(
        BlobCorpusBackend(FilesystemBlobStore(corpus_dir or (cache_dir or default_cache_dir()) / "corpus"))
    )


def default_cache_dir() -> Path:
    from glean.recipe_api.blob_store import DEFAULT_CACHE_DIR  # noqa: PLC0415

    return DEFAULT_CACHE_DIR
