from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING
from urllib.parse import quote

from pydantic import ValidationError

from glean.recipe_api.client import CACHE_DIR
from glean.recipes.stored import StoredRecipe

if TYPE_CHECKING:
    from collections.abc import Sequence

CORPUS_DIR = CACHE_DIR / "corpus"


class RecipeCorpusStore:
    def __init__(self, root: Path = CORPUS_DIR) -> None:
        self.root = root

    def save(self, recipe: StoredRecipe) -> StoredRecipe:
        path = self._path_for(recipe.external_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = recipe.model_dump(mode="json")
        for ingredient in data.get("ingredients", []):
            if isinstance(ingredient, dict) and ingredient.get("api_ingredient_id") is None:
                ingredient.pop("api_ingredient_id", None)
        content = json.dumps(data, indent=2, sort_keys=True) + "\n"
        temp_path: Path | None = None
        try:
            with NamedTemporaryFile(
                "w",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                temp_file.write(content)
                temp_path = Path(temp_file.name)
            temp_path.replace(path)
        except OSError:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            raise
        return recipe

    def get(self, recipe_id: str) -> StoredRecipe | None:
        return self._load_recipe(self._path_for(recipe_id))

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
        recipes = list(self._iter_recipes())
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
        if not self.root.exists():
            return []
        return [
            recipe
            for path in sorted(self.root.rglob("*.json"))
            if path.is_file() and (recipe := self._load_recipe(path)) is not None
        ]

    @staticmethod
    def _load_recipe(path: Path) -> StoredRecipe | None:
        if not path.exists() or not path.is_file():
            return None
        try:
            return StoredRecipe.model_validate(json.loads(path.read_text()))
        except (OSError, json.JSONDecodeError, ValidationError, TypeError, ValueError):
            return None

    def _path_for(self, recipe_id: str) -> Path:
        namespace, separator, namespaced_recipe_id = recipe_id.partition(":")
        if not separator:
            namespace = "_unknown"
            namespaced_recipe_id = recipe_id
        return self.root / quote(namespace, safe="") / f"{quote(namespaced_recipe_id, safe='')}.json"

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
