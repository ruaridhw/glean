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
    data = {"data": [], "meta": {"total": 0, "page": 1, "per_page": 20, "total_capped": False}}
    with patch("glean.recipe_api.client.CACHE_DIR", tmp_path):
        _cache_write("test_key", data)
        result = _cache_read("test_key", SEARCH_TTL_SECS)
    assert result == data


def test_cache_read_returns_none_when_expired(tmp_path: Path) -> None:
    data = {"data": [], "meta": {"total": 0, "page": 1, "per_page": 20, "total_capped": False}}
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
        "data": [
            {
                "id": "abc-123",
                "name": "Spaghetti Carbonara",
                "cuisine": "Italian",
                "difficulty": "Easy",
                "tags": [],
                "meta": {"total_time": "PT20M"},
                "dietary": {"flags": [], "not_suitable_for": []},
                "nutrition_summary": {},
            }
        ],
        "meta": {"total": 1, "page": 1, "per_page": 20, "total_capped": False},
    }
    cache_key = _cache_key_search({"q": "carbonara", "page": 1, "per_page": 20})
    client = RecipeApiClient.__new__(RecipeApiClient)
    with patch("glean.recipe_api.client.CACHE_DIR", tmp_path):
        _cache_write(cache_key, search_data)
        response = client.search(q="carbonara")
    assert response.meta.total == 1
    assert response.meta.total_capped is False
    assert response.data[0].id == "abc-123"


def test_client_search_hits_api_when_cache_miss(tmp_path: Path) -> None:
    search_data = {"data": [], "meta": {"total": 0, "page": 1, "per_page": 20, "total_capped": False}}
    mock_resp = MagicMock()
    mock_resp.json.return_value = search_data

    client = RecipeApiClient.__new__(RecipeApiClient)
    client._client = MagicMock()
    client._client.get.return_value = mock_resp

    with patch("glean.recipe_api.client.CACHE_DIR", tmp_path):
        response = client.search(q="sushi")

    assert response.meta.total == 0
    assert response.data == []
    client._client.get.assert_called_once()


def test_client_search_accepts_recipe_api_data_meta_response(tmp_path: Path) -> None:
    search_data = {
        "data": [
            {
                "id": "117e87ca-4825-48c0-8236-e80107e71d3a",
                "name": "Quick Tomato Yogurt Chicken Curry",
                "description": "A vibrant and warming single-serving chicken curry.",
                "category": "Dinner",
                "cuisine": "Indian",
                "difficulty": "Easy",
                "tags": ["Chicken Breast", "Curry Powder", "Dinner"],
                "meta": {
                    "active_time": "PT10M",
                    "passive_time": "PT5M",
                    "total_time": "PT15M",
                    "overnight_required": False,
                    "yields": "1 serving",
                    "yield_count": 1,
                    "serving_size_g": 350,
                },
                "dietary": {"flags": ["Gluten-Free", "Nut-Free"], "not_suitable_for": []},
                "nutrition_summary": {
                    "calories": 487.22,
                    "protein_g": 35.75,
                    "carbohydrates_g": 15.33,
                    "fat_g": 31.79,
                },
            }
        ],
        "meta": {"total": 15, "page": 1, "per_page": 20, "total_capped": False},
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = search_data

    client = RecipeApiClient.__new__(RecipeApiClient)
    client._client = MagicMock()
    client._client.get.return_value = mock_resp

    with patch("glean.recipe_api.client.CACHE_DIR", tmp_path):
        response = client.search(q="miso")

    assert response.meta.total == 15
    assert response.meta.page == 1
    assert response.meta.per_page == 20
    assert response.meta.total_capped is False
    assert response.data[0].id == "117e87ca-4825-48c0-8236-e80107e71d3a"
    assert response.data[0].name == "Quick Tomato Yogurt Chicken Curry"
    assert response.data[0].meta.total_time == "PT15M"
    assert response.data[0].dietary.flags == ["Gluten-Free", "Nut-Free"]
    assert response.data[0].nutrition_summary.calories == 487.22
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
    detail_response = {
        "data": {
            "id": "117e87ca-4825-48c0-8236-e80107e71d3a",
            "name": "Quick Tomato Yogurt Chicken Curry",
            "description": "A vibrant and warming single-serving chicken curry.",
            "category": "Dinner",
            "cuisine": "Indian",
            "difficulty": "Easy",
            "tags": ["Chicken Breast", "Curry Powder", "Dinner"],
            "meta": {
                "active_time": "PT10M",
                "passive_time": "PT5M",
                "total_time": "PT15M",
                "overnight_required": False,
                "yields": "1 serving",
                "yield_count": 1,
                "serving_size_g": 350,
            },
            "dietary": {"flags": ["Gluten-Free", "Nut-Free"], "not_suitable_for": []},
            "nutrition": {
                "per_serving": {
                    "calories": 487.22,
                    "protein_g": 35.75,
                    "carbohydrates_g": 15.33,
                    "fat_g": 31.79,
                },
                "sources": [],
            },
            "ingredients": [
                {
                    "group_name": "Curry",
                    "items": [
                        {
                            "ingredient_id": "ghee",
                            "name": "ghee",
                            "quantity": 15,
                            "unit": "g",
                            "preparation": None,
                            "substitutions": [],
                        }
                    ],
                }
            ],
            "instructions": [
                {
                    "step_number": 1,
                    "phase": "main",
                    "text": "Warm the ghee.",
                    "structured": {"action": "warm"},
                    "tips": [],
                }
            ],
        },
        "usage": {"daily_limit": 100, "daily_remaining": 99, "monthly_limit": 1000, "monthly_remaining": 999},
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = detail_response

    client = RecipeApiClient.__new__(RecipeApiClient)
    client._client = MagicMock()
    client._client.get.return_value = mock_resp

    with patch("glean.recipe_api.client.CACHE_DIR", tmp_path):
        response = client.get_recipe("117e87ca-4825-48c0-8236-e80107e71d3a")

    assert response.id == "117e87ca-4825-48c0-8236-e80107e71d3a"
    assert response.name == "Quick Tomato Yogurt Chicken Curry"
    assert response.meta.total_time == "PT15M"
    assert response.dietary.flags == ["Gluten-Free", "Nut-Free"]
    assert response.nutrition.per_serving.calories == 487.22
    assert response.ingredients[0].items[0].name == "ghee"
    assert response.instructions[0].text == "Warm the ghee."
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
