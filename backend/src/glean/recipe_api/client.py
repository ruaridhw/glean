from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

import httpx

from glean.observability import tracer
from glean.recipe_api.schemas import RecipeApiDetailResponse, RecipeApiRecipe, RecipeApiSearchResponse

CACHE_DIR = Path(".cache/glean_recipe_cache")
SEARCH_TTL_SECS = 86_400  # 24h
DETAIL_TTL_SECS = float("inf")


def _iso_to_mins(iso: str | None) -> int | None:
    if not iso:
        return None
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", iso)
    if not match:
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    return hours * 60 + minutes


def _cache_key_search(params: dict) -> str:
    raw = json.dumps(params, sort_keys=True)
    return "search_" + hashlib.sha256(raw.encode()).hexdigest()


def _cache_read(key: str, ttl: float) -> dict | None:
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if time.time() - data["cached_at"] > ttl:
            return None
        return data["data"]
    except Exception:
        return None


def _cache_write(key: str, data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{key}.json"
    path.write_text(json.dumps({"data": data, "cached_at": time.time()}))


class RecipeApiClient:
    def __init__(self, *, base_url: str, api_key: str) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            headers={"X-API-Key": api_key},
            timeout=10.0,
        )

    @tracer.capture_method
    def search(
        self,
        q: str | None = None,
        cuisine: str | None = None,
        dietary: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> RecipeApiSearchResponse:
        params = {
            k: v
            for k, v in {"q": q, "cuisine": cuisine, "dietary": dietary, "page": page, "per_page": per_page}.items()
            if v is not None
        }
        cache_key = _cache_key_search(params)
        if cached := _cache_read(cache_key, SEARCH_TTL_SECS):
            return RecipeApiSearchResponse(**cached)
        resp = self._client.get("/recipes", params=params)
        resp.raise_for_status()
        result = resp.json()
        parsed = RecipeApiSearchResponse(**result)
        _cache_write(cache_key, parsed.model_dump())
        return parsed

    @tracer.capture_method
    def get_recipe(self, recipe_id: str) -> RecipeApiRecipe:
        cache_key = f"detail_{recipe_id}"
        if cached := _cache_read(cache_key, DETAIL_TTL_SECS):
            return RecipeApiRecipe(**cached)
        resp = self._client.get(f"/recipes/{recipe_id}")
        resp.raise_for_status()
        result = resp.json()
        parsed = RecipeApiDetailResponse(**result)
        _cache_write(cache_key, parsed.data.model_dump())
        return parsed.data

    def active_time_mins(self, recipe: RecipeApiRecipe) -> int | None:
        return _iso_to_mins(recipe.meta.active_time)

    def total_time_mins(self, recipe: RecipeApiRecipe) -> int | None:
        return _iso_to_mins(recipe.meta.total_time)
