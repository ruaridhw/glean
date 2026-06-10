"""Live backend smoke tests for the production AI workflows.

These tests intentionally call real providers. They require ``backend/.env`` with
``OPENROUTER_API_KEY=sk-or-...`` and skip optional receipt/recipe cases unless
their input env vars are provided.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from glean.config import get_settings
from glean.dependencies import verify_cognito_token
from glean.main import app

if TYPE_CHECKING:
    from glean.config import Settings

pytestmark = pytest.mark.integration

AUTH_HEADERS = {"Authorization": "Bearer integration-test-token"}

MEAL_PLAN_REQUEST = {
    "pantry": [
        {
            "id": 1,
            "name": "chicken breast",
            "quantity": 500,
            "unit": "g",
            "food_group": "protein",
            "urgency_score": 90.0,
        },
        {
            "id": 2,
            "name": "spinach",
            "quantity": 150,
            "unit": "g",
            "food_group": "veg",
            "urgency_score": 70.0,
        },
    ],
    "recipe_history": [
        {
            "recipe_id": 101,
            "title": "Chicken and Spinach Pasta",
            "last_cooked_at": None,
            "food_groups": ["protein", "veg", "carb"],
        },
        {
            "recipe_id": 102,
            "title": "Lentil Soup",
            "last_cooked_at": "2026-06-01T18:00:00Z",
            "food_groups": ["protein", "veg"],
        },
    ],
    "food_group_coverage": {"protein": 1, "veg": 1, "carb": 0},
    "purchase_tolerance": 0.4,
    "meals_per_week": 2,
    "dietary_flags": [],
    "max_active_time_mins": 45,
}


@pytest.fixture
def live_client(test_settings: Settings) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[verify_cognito_token] = lambda: "integration-test-user"
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def vision_live_client(test_settings: Settings) -> TestClient:
    vision_settings = test_settings.model_copy(update={"receipt_ocr_mode": "vision"})
    app.dependency_overrides[get_settings] = lambda: vision_settings
    app.dependency_overrides[verify_cognito_token] = lambda: "integration-test-user"
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_describe_purchase_live_http_returns_pantry_items(live_client: TestClient) -> None:
    response = live_client.post(
        "/receipts/describe",
        headers=AUTH_HEADERS,
        json={"text": "I bought 1kg chicken breast, two litres of whole milk, and a dozen eggs."},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    names = {item["name"] for item in items}
    assert len(items) == 3
    assert {"chicken breast", "whole milk", "eggs"} <= names
    assert all(item["quantity"] > 0 for item in items)
    assert all(0.0 <= item["confidence"] <= 1.0 for item in items)


def test_generate_meal_plan_live_http_returns_bounded_candidates(live_client: TestClient) -> None:
    response = live_client.post("/suggestions", headers=AUTH_HEADERS, json=MEAL_PLAN_REQUEST)

    assert response.status_code == 200
    suggestions = response.json()["suggestions"]
    known_recipe_ids = {recipe["recipe_id"] for recipe in MEAL_PLAN_REQUEST["recipe_history"]}
    assert 1 <= len(suggestions) <= MEAL_PLAN_REQUEST["meals_per_week"]
    for suggestion in suggestions:
        assert suggestion["recipe_id"] in known_recipe_ids
        assert len(suggestion["title"]) > 0
        assert len(suggestion["reason"]) >= 10
        assert isinstance(suggestion["missing_ingredients"], list)


def test_parse_shopping_description_live_http_returns_proposals(live_client: TestClient) -> None:
    response = live_client.post(
        "/shopping/parse-description",
        headers=AUTH_HEADERS,
        json={"text": "Need taco shells, whole milk, limes, and something crunchy for lunchboxes."},
    )

    assert response.status_code == 200
    body = response.json()
    names = {item["name"] for item in body["items"]}
    assert len(body["items"]) >= 4
    assert {"taco shells", "whole milk", "limes"} <= names
    assert isinstance(body["clarifying_questions"], list)
    assert all(item["quantity"] > 0 for item in body["items"])


def test_receipt_scan_vision_live_http_returns_items(vision_live_client: TestClient) -> None:
    image_path_raw = os.environ.get("GLEAN_VISION_RECEIPT_IMAGE")
    if not image_path_raw:
        pytest.skip("Set GLEAN_VISION_RECEIPT_IMAGE to a local receipt image for the vision smoke test")

    image_path = Path(image_path_raw)
    image_bytes = image_path.read_bytes()
    content_type = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
    response = vision_live_client.post(
        "/receipts/scan",
        headers=AUTH_HEADERS,
        files={"file": (image_path.name, image_bytes, content_type)},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) > 0
    assert all(item["quantity"] > 0 for item in items)
    assert all(item["unit"] in {"g", "ml", "units"} for item in items)
    assert all(0.0 <= item["confidence"] <= 1.0 for item in items)


def test_recipe_search_live_http_returns_results(live_client: TestClient, test_settings: Settings) -> None:
    if test_settings.recipe_api_key.get_secret_value().startswith("test-"):
        pytest.skip("Set a real RECIPE_API_KEY in backend/.env for recipe search smoke")

    response = live_client.get("/recipes/search", headers=AUTH_HEADERS, params={"q": "carbonara", "per_page": 5})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= len(body["results"])
    assert len(body["results"]) > 0
    assert all(len(recipe["title"]) > 0 for recipe in body["results"])


def test_recipe_import_url_live_http_returns_recipe(live_client: TestClient) -> None:
    recipe_url = os.environ.get("GLEAN_LIVE_RECIPE_URL")
    if not recipe_url:
        pytest.skip("Set GLEAN_LIVE_RECIPE_URL to a known recipe page for URL import smoke")

    response = live_client.post("/recipes/import-url", headers=AUTH_HEADERS, json={"url": recipe_url})

    assert response.status_code == 200
    recipe = response.json()
    assert len(recipe["title"]) > 0
    assert recipe["source_url"] == recipe_url
    assert len(recipe["ingredients"]) > 0
    assert len(recipe["instructions"]) >= 2
