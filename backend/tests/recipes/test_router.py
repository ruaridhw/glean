from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from glean.config import Settings, get_settings
from glean.dependencies import verify_cognito_token
from glean.main import app
from glean.recipe_api.schemas import RecipeApiRecipe, RecipeApiSearchResponse

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def client(test_settings: Settings) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[verify_cognito_token] = lambda: "test-user"
    yield TestClient(app)
    app.dependency_overrides.clear()


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


# ---------------------------------------------------------------------------
# Test 1: search returns results
# ---------------------------------------------------------------------------


def test_search_recipes_returns_results(client: TestClient) -> None:
    fixture = _load_fixture("recipe_search.json")
    mock_response = RecipeApiSearchResponse(**fixture)

    with patch("glean.recipes.service.RecipeApiClient") as MockClient:
        MockClient.return_value.search.return_value = mock_response
        resp = client.get("/recipes/search?q=carbonara")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["results"]) == 2
    assert data["results"][0]["external_id"] == "abc-123"
    assert data["results"][0]["title"] == "Spaghetti Carbonara"
    assert data["results"][1]["dietary_flags"] == ["Gluten-Free"]


# ---------------------------------------------------------------------------
# Test 2: get recipe detail
# ---------------------------------------------------------------------------


def test_get_recipe_returns_detail(client: TestClient) -> None:
    api_recipe = RecipeApiRecipe(
        id="abc-123",
        name="Spaghetti Carbonara",
        cuisine="Italian",
        difficulty="Easy",
        dietary={"flags": ["Gluten-Free"], "not_suitable_for": ["Vegan diets"]},
        nutrition={"per_serving": {"calories": 487.22, "protein_g": 35.75}},
        ingredients=[
            {
                "group_name": "Pasta",
                "items": [
                    {
                        "ingredient_id": "spaghetti",
                        "name": "spaghetti",
                        "quantity": 200,
                        "unit": "g",
                    }
                ],
            }
        ],
        source_url="https://example.com/carbonara",
    )

    with patch("glean.recipes.service.RecipeApiClient") as MockClient:
        MockClient.return_value.get_recipe.return_value = api_recipe
        resp = client.get("/recipes/abc-123")

    assert resp.status_code == 200
    data = resp.json()
    assert data["external_id"] == "abc-123"
    assert data["title"] == "Spaghetti Carbonara"
    assert data["cuisine"] == "Italian"
    assert data["dietary_flags"] == ["Gluten-Free"]
    assert data["not_suitable_for"] == ["Vegan diets"]
    assert data["nutrition"]["calories"] == pytest.approx(487.22)
    assert data["nutrition"]["protein_g"] == pytest.approx(35.75)
    assert data["ingredients"][0]["canonical_name"] == "spaghetti"
    assert data["ingredients"][0]["quantity"] == pytest.approx(200)
    assert data["source_url"] == "https://example.com/carbonara"


# ---------------------------------------------------------------------------
# Test 3: search requires auth (no dependency override)
# ---------------------------------------------------------------------------


def test_search_requires_auth(test_settings: Settings) -> None:
    # No override — real auth dependency will reject missing token
    app.dependency_overrides.clear()
    app.dependency_overrides[get_settings] = lambda: test_settings
    plain_client = TestClient(app)
    resp = plain_client.get("/recipes/search?q=test")
    assert resp.status_code in (401, 403)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test 4: import-url rejects http:// URLs
# ---------------------------------------------------------------------------


def test_import_url_rejects_http(client: TestClient) -> None:
    resp = client.post("/recipes/import-url", json={"url": "http://example.com/recipe"})
    assert resp.status_code == 422
    assert "HTTPS" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Test 5: import-url rejects private IP addresses
# ---------------------------------------------------------------------------


def test_import_url_rejects_private_ip(client: TestClient) -> None:
    with patch("glean.recipes.service.socket.gethostbyname", return_value="192.168.1.1"):
        resp = client.post("/recipes/import-url", json={"url": "https://internal.example.com/recipe"})
    assert resp.status_code == 422
    assert "192.168.1.1" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Test 6: import-url uses schema.org when available
# ---------------------------------------------------------------------------


def test_import_url_uses_schema_org(client: TestClient) -> None:
    fixture = _load_fixture("recipe_detail.json")
    html = f"""
    <html><head>
    <script type="application/ld+json">{json.dumps(fixture)}</script>
    </head><body></body></html>
    """

    mock_response = MagicMock()
    mock_response.text = html

    with (
        patch("glean.recipes.service.socket.gethostbyname", return_value="93.184.216.34"),
        patch("glean.recipes.service.httpx.get", return_value=mock_response),
    ):
        resp = client.post("/recipes/import-url", json={"url": "https://example.com/carbonara"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Spaghetti Carbonara"
    assert len(data["ingredients"]) == 2
    assert len(data["instructions"]) == 2
    assert data["total_time_mins"] == 20


# ---------------------------------------------------------------------------
# Test 7: import-url falls back to Claude/LangChain when no schema.org
# ---------------------------------------------------------------------------


def test_import_url_falls_back_to_claude(client: TestClient) -> None:
    html = "<html><body><p>A recipe page with no structured data</p></body></html>"

    mock_http_response = MagicMock()
    mock_http_response.text = html

    llm_json = json.dumps(
        {
            "title": "Pasta Primavera",
            "source_url": "https://example.com/pasta",
            "cuisine": "Italian",
            "difficulty": None,
            "total_time": "PT30M",
            "prep_time": "PT10M",
            "yield": "4 servings",
            "ingredients": ["200g pasta", "1 courgette", "2 tbsp olive oil"],
            "instructions": ["Boil pasta.", "Sauté vegetables.", "Combine and serve."],
            "dietary_flags": ["Vegan"],
            "not_suitable_for": [],
        }
    )

    mock_llm_response = MagicMock()
    mock_llm_response.content = llm_json

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_llm_response

    with (
        patch("glean.recipes.service.socket.gethostbyname", return_value="93.184.216.34"),
        patch("glean.recipes.service.httpx.get", return_value=mock_http_response),
        patch("glean.recipes.router.create_chat_model", return_value=mock_llm),
    ):
        resp = client.post("/recipes/import-url", json={"url": "https://example.com/pasta"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Pasta Primavera"
    assert data["total_time_mins"] == 30
    assert len(data["ingredients"]) == 3
    assert len(data["instructions"]) == 3
    assert data["dietary_flags"] == ["Vegan"]
