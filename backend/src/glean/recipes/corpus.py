from __future__ import annotations

import json
from typing import TYPE_CHECKING
from urllib.parse import quote

from pydantic import ValidationError

from glean.recipe_api.blob_store import get_recipe_corpus_store
from glean.recipes.stored import StoredRecipe

if TYPE_CHECKING:
    from collections.abc import Sequence

    from glean.recipe_api.blob_store import BlobStore


class RecipeCorpusStore:
    def __init__(self, store: BlobStore | None = None) -> None:
        self.store = store if store is not None else get_recipe_corpus_store()

    def save(self, recipe: StoredRecipe) -> StoredRecipe:
        data = recipe.model_dump(mode="json")
        for ingredient in data.get("ingredients", []):
            if isinstance(ingredient, dict) and ingredient.get("api_ingredient_id") is None:
                ingredient.pop("api_ingredient_id", None)
        content = json.dumps(data, indent=2, sort_keys=True) + "\n"
        self.store.write(self._key_for(recipe.external_id), content)
        return recipe

    def get(self, recipe_id: str) -> StoredRecipe | None:
        return self._load(self._key_for(recipe_id))

    def get_by_source_url(self, source_url: str) -> StoredRecipe | None:
        for recipe in self._iter_recipes():
            if recipe.source_url == source_url:
                return recipe
        return None

    def search(
        self,
        q: str | None = None,
        cuisine: str | None = None,
        dietary: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[StoredRecipe], int]:
        recipes = self._iter_recipes()
        query = (q or "").strip().casefold()
        cuisine_filter = (cuisine or "").strip().casefold()
        dietary_filters = [flag.strip().casefold() for flag in (dietary or "").split(",") if flag.strip()]

        filtered = [
            recipe
            for recipe in recipes
            if self._matches_query(recipe, query)
            and self._matches_cuisine(recipe, cuisine_filter)
            and self._matches_dietary(recipe, dietary_filters)
        ]
        filtered.sort(key=lambda recipe: (recipe.title.casefold(), recipe.external_id))

        total = len(filtered)
        safe_page = max(page, 1)
        safe_per_page = max(per_page, 1)
        start = (safe_page - 1) * safe_per_page
        end = start + safe_per_page
        return filtered[start:end], total

    def _iter_recipes(self) -> list[StoredRecipe]:
        return [recipe for key in self.store.list_keys() if (recipe := self._load(key)) is not None]

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

    @staticmethod
    def _matches_query(recipe: StoredRecipe, query: str) -> bool:
        return not query or query in recipe.title.casefold()

    @staticmethod
    def _matches_cuisine(recipe: StoredRecipe, cuisine_filter: str) -> bool:
        if not cuisine_filter:
            return True
        return (recipe.cuisine or "").casefold() == cuisine_filter

    @staticmethod
    def _matches_dietary(recipe: StoredRecipe, dietary_filters: Sequence[str]) -> bool:
        if not dietary_filters:
            return True
        recipe_flags = {flag.casefold() for flag in recipe.dietary_flags}
        return all(flag in recipe_flags for flag in dietary_filters)
