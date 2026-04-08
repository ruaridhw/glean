from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from pathlib import Path

from glean.recipe_api.client import (
    SEARCH_TTL_SECS,
    RecipeApiClient,
    _cache_key_search,
    _cache_read,
    _cache_write,
    _iso_to_mins,
)
from glean.recipe_api.schemas import RecipeApiRecipe

# ---------------------------------------------------------------------------
# _iso_to_mins
# ---------------------------------------------------------------------------


def test_iso_to_mins_hours_and_minutes() -> None:
    assert _iso_to_mins("PT1H30M") == 90


def test_iso_to_mins_minutes_only() -> None:
    assert _iso_to_mins("PT45M") == 45


def test_iso_to_mins_none_returns_none() -> None:
    assert _iso_to_mins(None) is None


def test_iso_to_mins_invalid_returns_none() -> None:
    assert _iso_to_mins("not-a-duration") is None


def test_iso_to_mins_hours_only() -> None:
    assert _iso_to_mins("PT2H") == 120


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def test_cache_key_search_is_deterministic() -> None:
    params = {"q": "pasta", "cuisine": "Italian"}
    key1 = _cache_key_search(params)
    key2 = _cache_key_search(params)
    assert key1 == key2
    assert key1.startswith("search_")


def test_cache_key_search_differs_for_different_params() -> None:
    key1 = _cache_key_search({"q": "pasta"})
    key2 = _cache_key_search({"q": "soup"})
    assert key1 != key2


def test_cache_read_returns_none_when_file_missing(tmp_path: Path) -> None:
    with patch("glean.recipe_api.client.CACHE_DIR", tmp_path):
        result = _cache_read("nonexistent_key", SEARCH_TTL_SECS)
    assert result is None


def test_cache_write_and_read_roundtrip(tmp_path: Path) -> None:
    data = {"results": [], "total": 0}
    with patch("glean.recipe_api.client.CACHE_DIR", tmp_path):
        _cache_write("test_key", data)
        result = _cache_read("test_key", SEARCH_TTL_SECS)
    assert result == data


def test_cache_read_returns_none_when_expired(tmp_path: Path) -> None:
    data = {"results": [], "total": 0}
    with patch("glean.recipe_api.client.CACHE_DIR", tmp_path):
        _cache_write("test_key", data)
        cache_file = tmp_path / "test_key.json"
        raw = json.loads(cache_file.read_text())
        raw["cached_at"] = time.time() - SEARCH_TTL_SECS - 1
        cache_file.write_text(json.dumps(raw))
        result = _cache_read("test_key", SEARCH_TTL_SECS)
    assert result is None


def test_cache_read_returns_none_on_corrupt_file(tmp_path: Path) -> None:
    (tmp_path / "bad_key.json").write_text("not json at all {{{")
    with patch("glean.recipe_api.client.CACHE_DIR", tmp_path):
        result = _cache_read("bad_key", SEARCH_TTL_SECS)
    assert result is None


# ---------------------------------------------------------------------------
# RecipeApiClient.search
# ---------------------------------------------------------------------------


def test_client_search_uses_cache_on_hit(tmp_path: Path) -> None:
    search_data = {
        "results": [
            {
                "id": "abc-123",
                "name": "Spaghetti Carbonara",
                "cuisine": "Italian",
                "difficulty": "Easy",
                "total_time": "PT20M",
                "flags": [],
            }
        ],
        "total": 1,
    }
    cache_key = _cache_key_search({"q": "carbonara", "page": 1, "per_page": 20})
    client = RecipeApiClient.__new__(RecipeApiClient)
    with patch("glean.recipe_api.client.CACHE_DIR", tmp_path):
        _cache_write(cache_key, search_data)
        response = client.search(q="carbonara")
    assert response.total == 1
    assert response.results[0].id == "abc-123"


def test_client_search_hits_api_when_cache_miss(tmp_path: Path) -> None:
    search_data = {"results": [], "total": 0}
    mock_resp = MagicMock()
    mock_resp.json.return_value = search_data

    client = RecipeApiClient.__new__(RecipeApiClient)
    client._client = MagicMock()
    client._client.get.return_value = mock_resp

    with patch("glean.recipe_api.client.CACHE_DIR", tmp_path):
        response = client.search(q="sushi")

    assert response.total == 0
    client._client.get.assert_called_once()


def test_client_get_recipe_uses_cache_on_hit(tmp_path: Path) -> None:
    detail_data = {
        "id": "abc-123",
        "name": "Spaghetti Carbonara",
        "flags": [],
        "not_suitable_for": [],
        "meta": {},
        "ingredients": [],
        "instructions": [],
        "nutrition": {},
    }
    client = RecipeApiClient.__new__(RecipeApiClient)
    with patch("glean.recipe_api.client.CACHE_DIR", tmp_path):
        _cache_write("detail_abc-123", detail_data)
        response = client.get_recipe("abc-123")
    assert response.id == "abc-123"
    assert response.name == "Spaghetti Carbonara"


def test_client_get_recipe_hits_api_when_cache_miss(tmp_path: Path) -> None:
    detail_data = {
        "id": "xyz-789",
        "name": "Risotto",
        "flags": [],
        "not_suitable_for": [],
        "meta": {},
        "ingredients": [],
        "instructions": [],
        "nutrition": {},
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = detail_data

    client = RecipeApiClient.__new__(RecipeApiClient)
    client._client = MagicMock()
    client._client.get.return_value = mock_resp

    with patch("glean.recipe_api.client.CACHE_DIR", tmp_path):
        response = client.get_recipe("xyz-789")

    assert response.id == "xyz-789"
    client._client.get.assert_called_once()


# ---------------------------------------------------------------------------
# RecipeApiClient time helpers
# ---------------------------------------------------------------------------


def test_client_active_time_mins() -> None:
    recipe = RecipeApiRecipe(id="x", name="Test")
    recipe.meta.active_time = "PT15M"
    client = RecipeApiClient.__new__(RecipeApiClient)
    assert client.active_time_mins(recipe) == 15


def test_client_total_time_mins() -> None:
    recipe = RecipeApiRecipe(id="x", name="Test")
    recipe.meta.total_time = "PT1H"
    client = RecipeApiClient.__new__(RecipeApiClient)
    assert client.total_time_mins(recipe) == 60
