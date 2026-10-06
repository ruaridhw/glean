"""Searchable summary index over the recipe corpus.

Searching the corpus by reading every recipe blob costs one S3 GET per recipe
per request. Instead, the corpus keeps one small JSONL file of per-recipe
summaries (`INDEX_KEY`), and search runs against an in-memory SQLite FTS5 table
built from it. Summaries carry each recipe's blob key, so lookups by id or
source URL resolve to a single read whatever layout the blob was stored under.
"""

from __future__ import annotations

import re
import sqlite3
import threading
import weakref
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, ValidationError

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from glean.recipes.stored import StoredRecipe

# Not `.json`-suffixed, so `BlobStore.list_keys` never mistakes it for a recipe.
INDEX_KEY = "_index/recipes.jsonl"

_TOKEN_RE = re.compile(r"\w+")
# bm25 column weights, in table column order: external_id (unindexed), title,
# ingredients, cuisine. Title hits outrank ingredient hits.
_RANK = "bm25(recipe_fts, 0.0, 10.0, 1.0, 2.0)"


class RecipeSummary(BaseModel):
    """The fields search results and lookups need, without the full recipe."""

    external_id: str
    key: str
    title: str
    source_url: str | None = None
    cuisine: str | None = None
    difficulty: str | None = None
    total_time_mins: int | None = None
    dietary_flags: list[str] = Field(default_factory=list)
    ingredient_names: list[str] = Field(default_factory=list)

    @classmethod
    def from_recipe(cls, recipe: StoredRecipe, *, key: str) -> RecipeSummary:
        return cls(
            external_id=recipe.external_id,
            key=key,
            title=recipe.title,
            source_url=recipe.source_url,
            cuisine=recipe.cuisine,
            difficulty=recipe.difficulty,
            total_time_mins=recipe.total_time_mins,
            dietary_flags=recipe.dietary_flags,
            ingredient_names=[ingredient.canonical_name for ingredient in recipe.ingredients],
        )


def dumps_summaries(summaries: Iterable[RecipeSummary]) -> str:
    ordered = sorted(summaries, key=lambda summary: summary.external_id)
    return "".join(summary.model_dump_json() + "\n" for summary in ordered)


def loads_summaries(text: str) -> list[RecipeSummary]:
    summaries = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            summaries.append(RecipeSummary.model_validate_json(line))
        except ValidationError:
            continue
    return sorted(summaries, key=lambda summary: summary.external_id)


class RecipeSearchIndex:
    def __init__(self, summaries: Iterable[RecipeSummary]) -> None:
        self._by_id = {summary.external_id: summary for summary in summaries}
        self._by_source_url = {summary.source_url: summary for summary in self._by_id.values() if summary.source_url}
        self._lock = threading.Lock()
        # FastAPI runs sync endpoints on a worker thread pool; the lock serialises access.
        self._db = sqlite3.connect(":memory:", check_same_thread=False)
        # Indexes are replaced on every reload; close each connection when its index is collected.
        weakref.finalize(self, self._db.close)
        self._db.execute(
            "CREATE VIRTUAL TABLE recipe_fts USING fts5("
            "external_id UNINDEXED, title, ingredients, cuisine, tokenize='unicode61 remove_diacritics 2')"
        )
        self._db.executemany(
            "INSERT INTO recipe_fts VALUES (?, ?, ?, ?)",
            [
                (summary.external_id, summary.title, " ".join(summary.ingredient_names), summary.cuisine or "")
                for summary in self._by_id.values()
            ],
        )

    def by_id(self, external_id: str) -> RecipeSummary | None:
        return self._by_id.get(external_id)

    def by_source_url(self, source_url: str) -> RecipeSummary | None:
        return self._by_source_url.get(source_url)

    def search(
        self,
        q: str | None = None,
        cuisine: str | None = None,
        dietary: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[RecipeSummary], int]:
        cuisine_filter = (cuisine or "").strip().casefold()
        dietary_filters = [flag.strip().casefold() for flag in (dietary or "").split(",") if flag.strip()]

        matches = [
            summary
            for summary in self._ranked_matches((q or "").strip())
            if _matches_cuisine(summary, cuisine_filter) and _matches_dietary(summary, dietary_filters)
        ]

        total = len(matches)
        start = (max(page, 1) - 1) * max(per_page, 1)
        return matches[start : start + max(per_page, 1)], total

    def _ranked_matches(self, query: str) -> list[RecipeSummary]:
        if not query:
            return sorted(self._by_id.values(), key=lambda summary: (summary.title.casefold(), summary.external_id))
        tokens = _TOKEN_RE.findall(query.casefold())
        if not tokens:
            return []
        # Quote every token so user input can never be read as FTS5 syntax; `*` makes each a prefix match.
        match_expression = " ".join(f'"{token}"*' for token in tokens)
        with self._lock:
            rows = self._db.execute(
                f"SELECT external_id FROM recipe_fts WHERE recipe_fts MATCH ? ORDER BY {_RANK}, title, external_id",  # noqa: S608 - _RANK is a constant
                (match_expression,),
            ).fetchall()
        return [self._by_id[external_id] for (external_id,) in rows]


def _matches_cuisine(summary: RecipeSummary, cuisine_filter: str) -> bool:
    return not cuisine_filter or (summary.cuisine or "").casefold() == cuisine_filter


def _matches_dietary(summary: RecipeSummary, dietary_filters: Sequence[str]) -> bool:
    recipe_flags = {flag.casefold() for flag in summary.dietary_flags}
    return all(flag in recipe_flags for flag in dietary_filters)
