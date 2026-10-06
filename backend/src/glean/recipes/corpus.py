from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING
from urllib.parse import quote
from weakref import WeakKeyDictionary

from pydantic import ValidationError

from glean.observability import logger
from glean.recipe_api.blob_store import get_recipe_corpus_store
from glean.recipes.search_index import INDEX_KEY, RecipeSearchIndex, RecipeSummary, dumps_summaries, loads_summaries
from glean.recipes.stored import StoredRecipe

if TYPE_CHECKING:
    from collections.abc import Iterable

    from glean.recipe_api.blob_store import BlobStore

# How long a loaded index is trusted before re-reading it, so recipes saved by
# another Lambda container become searchable here within this window.
_INDEX_TTL_SECONDS = 60.0

# Per blob store: (monotonic load time, index or None if the index was missing).
# Keyed weakly so short-lived stores (tests, scripts) don't pin their indexes.
_index_cache: WeakKeyDictionary[BlobStore, tuple[float, RecipeSearchIndex | None]] = WeakKeyDictionary()


class RecipeCorpusStore:
    def __init__(self, store: BlobStore | None = None) -> None:
        self.store = store if store is not None else get_recipe_corpus_store()

    def save(self, recipe: StoredRecipe) -> StoredRecipe:
        data = recipe.model_dump(mode="json")
        for ingredient in data.get("ingredients", []):
            if isinstance(ingredient, dict) and ingredient.get("api_ingredient_id") is None:
                ingredient.pop("api_ingredient_id", None)
        content = json.dumps(data, indent=2, sort_keys=True) + "\n"
        key = self._key_for(recipe.external_id)
        self.store.write(key, content)
        self._upsert_summary(RecipeSummary.from_recipe(recipe, key=key))
        return recipe

    def get(self, recipe_id: str) -> StoredRecipe | None:
        index = self._index()
        summary = index.by_id(recipe_id) if index is not None else None
        return self._load(summary.key if summary is not None else self._key_for(recipe_id))

    def get_by_source_url(self, source_url: str) -> StoredRecipe | None:
        index = self._index()
        summary = index.by_source_url(source_url) if index is not None else None
        return self._load(summary.key) if summary is not None else None

    def search(
        self,
        q: str | None = None,
        cuisine: str | None = None,
        dietary: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[RecipeSummary], int]:
        index = self._index()
        if index is None:
            return [], 0
        return index.search(q=q, cuisine=cuisine, dietary=dietary, page=page, per_page=per_page)

    def rebuild_index(self) -> int:
        """Rebuild the search index by reading every recipe blob. Returns the recipe count."""
        summaries: dict[str, RecipeSummary] = {}
        for key in self.store.list_keys():
            if (recipe := self._load(key)) is not None:
                summaries[recipe.external_id] = RecipeSummary.from_recipe(recipe, key=key)
        self._write_index(summaries.values())
        return len(summaries)

    def _index(self) -> RecipeSearchIndex | None:
        cached = _index_cache.get(self.store)
        now = time.monotonic()
        if cached is not None and now - cached[0] < _INDEX_TTL_SECONDS:
            return cached[1]
        raw = self.store.read(INDEX_KEY)
        if raw is None:
            logger.error("recipe search index missing", extra={"key": INDEX_KEY})
            index = None
        else:
            index = RecipeSearchIndex(loads_summaries(raw))
        _index_cache[self.store] = (now, index)
        return index

    def _upsert_summary(self, summary: RecipeSummary) -> None:
        # Read fresh rather than from cache so a save never drops another container's recent writes.
        raw = self.store.read(INDEX_KEY)
        if raw is None:
            # No index yet (fresh local corpus): build it from the blobs, which include this recipe.
            self.rebuild_index()
            return
        summaries = {existing.external_id: existing for existing in loads_summaries(raw)}
        summaries[summary.external_id] = summary
        self._write_index(summaries.values())

    def _write_index(self, summaries: Iterable[RecipeSummary]) -> None:
        summaries = list(summaries)
        self.store.write(INDEX_KEY, dumps_summaries(summaries))
        _index_cache[self.store] = (time.monotonic(), RecipeSearchIndex(summaries))

    def _load(self, key: str) -> StoredRecipe | None:
        raw = self.store.read(key)
        if raw is None:
            return None
        try:
            return StoredRecipe.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
            return None

    @staticmethod
    def _key_for(recipe_id: str) -> str:
        namespace, separator, namespaced_recipe_id = recipe_id.partition(":")
        if not separator:
            namespace = "_unknown"
            namespaced_recipe_id = recipe_id
        return f"{quote(namespace, safe='')}/{quote(namespaced_recipe_id, safe='')}.json"
