from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from glean.config import Settings, get_settings
from glean.dependencies import get_llm_router, verify_cognito_token
from glean.llm import Feature
from glean.main import app
from glean.recipe_api.schemas import RecipeApiRecipe, RecipeApiSearchResponse
from glean.recipes import service
from glean.recipes.schemas import ImportUrlRequest
from glean.recipes.stored import RecipeLlmResponse, RecipeProvenance, StoredIngredient, StoredInstruction, StoredRecipe

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

    with (
        patch("glean.recipes.service.RecipeCorpusStore", return_value=_empty_corpus_store()),
        patch("glean.recipes.service.RecipeApiClient") as MockClient,
    ):
        MockClient.return_value.search.return_value = mock_response
        resp = client.get("/recipes/search?q=carbonara")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["results"]) == 2
    assert data["results"][0]["external_id"] == "abc-123"
    assert data["results"][0]["title"] == "Spaghetti Carbonara"
    assert data["results"][1]["dietary_flags"] == ["Gluten-Free"]


def test_search_recipes_uses_corpus_as_first_port_of_call_before_recipe_api_resort() -> None:
    recipe = _stored_recipe(
        "import:carbonara",
        title="Spaghetti Carbonara",
        cuisine="Italian",
        dietary_flags=["High-Protein"],
    )
    corpus_store = MagicMock()
    corpus_store.search.return_value = ([recipe], 1)

    with (
        patch("glean.recipes.service.RecipeCorpusStore", return_value=corpus_store),
        patch("glean.recipes.service.RecipeApiClient") as MockClient,
    ):
        response = service.search_recipes(
            recipe_api_base_url="https://recipe-api.example.com",
            recipe_api_key=SecretStr("test-key"),
            q="carbonara",
            cuisine="italian",
        )

    assert response.total == 1
    assert [result.title for result in response.results] == ["Spaghetti Carbonara"]
    assert response.results[0].external_id == "import:carbonara"
    MockClient.assert_not_called()


def test_search_recipes_falls_back_to_recipe_api_when_corpus_has_no_matches() -> None:
    fixture = _load_fixture("recipe_search.json")
    mock_response = RecipeApiSearchResponse(**fixture)
    corpus_store = MagicMock()
    corpus_store.search.return_value = ([], 0)

    with (
        patch("glean.recipes.service.RecipeCorpusStore", return_value=corpus_store),
        patch("glean.recipes.service.RecipeApiClient") as MockClient,
    ):
        MockClient.return_value.search.return_value = mock_response
        response = service.search_recipes(
            recipe_api_base_url="https://recipe-api.example.com",
            recipe_api_key=SecretStr("test-key"),
            q="carbonara",
        )

    assert response.total == 2
    assert [result.title for result in response.results] == ["Spaghetti Carbonara", "Chicken Tikka Masala"]
    MockClient.return_value.search.assert_called_once_with(
        q="carbonara",
        cuisine=None,
        dietary=None,
        page=1,
        per_page=20,
    )


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

    with (
        patch("glean.recipes.service.RecipeCorpusStore", return_value=_empty_corpus_store()),
        patch("glean.recipes.service.RecipeApiClient") as MockClient,
    ):
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


def test_get_recipe_returns_corpus_detail_by_stored_id() -> None:
    recipe = _stored_recipe(
        "import:carbonara",
        title="Spaghetti Carbonara",
        source_url="https://example.com/carbonara",
    )
    corpus_store = MagicMock()
    corpus_store.get.return_value = recipe

    with (
        patch("glean.recipes.service.RecipeCorpusStore", return_value=corpus_store),
        patch("glean.recipes.service.RecipeApiClient") as MockClient,
    ):
        response = service.get_recipe(
            "import:carbonara",
            recipe_api_base_url="https://recipe-api.example.com",
            recipe_api_key=SecretStr("test-key"),
        )

    assert response.external_id == "import:carbonara"
    assert response.title == "Spaghetti Carbonara"
    assert response.source_url == "https://example.com/carbonara"
    MockClient.assert_not_called()


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
    with patch(
        "glean.recipes.providers.socket.getaddrinfo",
        _fake_getaddrinfo({"internal.example.com": "192.168.1.1"}),
    ):
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

    client_response = _FakeClient(
        [
            httpx.Response(
                200,
                content=html.encode(),
                request=httpx.Request("GET", "https://example.com/carbonara"),
            )
        ]
    )
    mock_llm = MagicMock()
    llm_router = MagicMock()
    llm_router.chat_model.return_value = mock_llm
    app.dependency_overrides[get_llm_router] = lambda: llm_router

    with (
        patch("glean.recipes.service.RecipeCorpusStore", return_value=_empty_corpus_store()),
        patch("glean.recipes.providers.socket.getaddrinfo", _fake_getaddrinfo({"example.com": "93.184.216.34"})),
        patch("glean.recipes.providers.httpx.Client", lambda **_: client_response),
    ):
        resp = client.post("/recipes/import-url", json={"url": "https://example.com/carbonara"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Spaghetti Carbonara"
    assert len(data["ingredients"]) == 2
    assert len(data["instructions"]) == 2
    assert data["total_time_mins"] == 20
    mock_llm.invoke.assert_not_called()
    llm_router.chat_model.assert_called_once_with(Feature.RECIPE_IMPORT)


def test_import_url_uses_rendered_html_when_supplied(client: TestClient) -> None:
    html = """
    <html><head>
    <script type="application/ld+json">
    {
      "@type": "Recipe",
      "name": "Chicken Enchiladas with Creamy Green Chile Sauce",
      "recipeIngredient": ["12 corn tortillas", "3 chicken breasts"],
      "recipeInstructions": [
        {"@type": "HowToStep", "text": "Fill the tortillas."},
        {"@type": "HowToStep", "text": "Bake until bubbling."}
      ]
    }
    </script>
    </head><body></body></html>
    """
    mock_llm = MagicMock()
    llm_router = MagicMock()
    llm_router.chat_model.return_value = mock_llm
    app.dependency_overrides[get_llm_router] = lambda: llm_router

    with (
        patch("glean.recipes.service.RecipeCorpusStore", return_value=_empty_corpus_store()),
        patch("glean.recipes.providers.socket.getaddrinfo", _fake_getaddrinfo({"www.allrecipes.com": "151.101.2.137"})),
        patch("glean.recipes.service.recipe_providers.import_url_to_canonical") as import_url_to_canonical,
    ):
        resp = client.post(
            "/recipes/import-url",
            json={
                "url": "https://www.allrecipes.com/recipe/125658/chicken-enchiladas-with-creamy-green-chile-sauce/",
                "rendered_html": html,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Chicken Enchiladas with Creamy Green Chile Sauce"
    assert (
        data["source_url"]
        == "https://www.allrecipes.com/recipe/125658/chicken-enchiladas-with-creamy-green-chile-sauce/"
    )
    assert len(data["ingredients"]) == 2
    assert len(data["instructions"]) == 2
    mock_llm.invoke.assert_not_called()
    import_url_to_canonical.assert_not_called()
    llm_router.chat_model.assert_called_once_with(Feature.RECIPE_IMPORT)


def test_import_url_returns_cached_recipe_for_same_source_url_without_import_pipeline() -> None:
    recipe = _stored_recipe(
        "import:pasta",
        title="Pasta Primavera",
        source_url="https://example.com/pasta",
    )
    corpus_store = MagicMock()
    corpus_store.get_by_source_url.return_value = recipe

    with (
        patch("glean.recipes.service.RecipeCorpusStore", return_value=corpus_store),
        patch("glean.recipes.providers.socket.getaddrinfo", _fake_getaddrinfo({"example.com": "93.184.216.34"})),
        patch("glean.recipes.service.recipe_providers.import_url_to_canonical") as import_url_to_canonical,
    ):
        response = service.import_recipe_from_url(
            ImportUrlRequest(url="https://example.com/pasta"),
            model=MagicMock(),
        )

    assert response.external_id == "import:pasta"
    assert response.title == "Pasta Primavera"
    assert response.source_url == "https://example.com/pasta"
    import_url_to_canonical.assert_not_called()


def test_import_url_rejects_http_before_matching_cached_recipe() -> None:
    recipe = _stored_recipe(
        "import:pasta",
        title="Pasta Primavera",
        source_url="http://example.com/pasta",
    )
    corpus_store = MagicMock()
    corpus_store.get_by_source_url.return_value = recipe

    with (
        patch("glean.recipes.service.RecipeCorpusStore", return_value=corpus_store) as CorpusStore,
        patch("glean.recipes.service.recipe_providers.import_url_to_canonical") as import_url_to_canonical,
        pytest.raises(ValueError, match="HTTPS"),
    ):
        service.import_recipe_from_url(
            ImportUrlRequest(url="http://example.com/pasta"),
            model=MagicMock(),
        )

    CorpusStore.assert_not_called()
    import_url_to_canonical.assert_not_called()


def test_import_url_rejects_private_host_before_matching_cached_recipe() -> None:
    recipe = _stored_recipe(
        "import:pasta",
        title="Pasta Primavera",
        source_url="https://internal.example.com/pasta",
    )
    corpus_store = MagicMock()
    corpus_store.get_by_source_url.return_value = recipe

    with (
        patch("glean.recipes.service.RecipeCorpusStore", return_value=corpus_store) as CorpusStore,
        patch("glean.recipes.providers.socket.getaddrinfo", _fake_getaddrinfo({"internal.example.com": "192.168.1.1"})),
        patch("glean.recipes.service.recipe_providers.import_url_to_canonical") as import_url_to_canonical,
        pytest.raises(ValueError, match="192\\.168\\.1\\.1"),
    ):
        service.import_recipe_from_url(
            ImportUrlRequest(url="https://internal.example.com/pasta"),
            model=MagicMock(),
        )

    CorpusStore.assert_not_called()
    import_url_to_canonical.assert_not_called()


# ---------------------------------------------------------------------------
# Test 7: import-url falls back to Claude/LangChain when no schema.org
# ---------------------------------------------------------------------------


def test_import_url_falls_back_to_claude(client: TestClient) -> None:
    html = "<html><body><p>A recipe page with no structured data</p></body></html>"

    client_response = _FakeClient(
        [
            httpx.Response(
                200,
                content=html.encode(),
                request=httpx.Request("GET", "https://example.com/pasta"),
            )
        ]
    )

    llm_recipe = RecipeLlmResponse(
        title="Pasta Primavera",
        source_url="https://example.com/pasta",
        cuisine="Italian",
        difficulty=None,
        total_time="PT30M",
        prep_time="PT10M",
        yield_="4 servings",
        ingredients=["200g pasta", "1 courgette", "2 tbsp olive oil"],
        instructions=["Boil pasta.", "Sauté vegetables.", "Combine and serve."],
        dietary_flags=["Vegan"],
        not_suitable_for=[],
    )

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = AssertionError("raw LLM JSON should not be used")
    mock_llm.with_structured_output.return_value.invoke.return_value = llm_recipe
    llm_router = MagicMock()
    llm_router.chat_model.return_value = mock_llm
    app.dependency_overrides[get_llm_router] = lambda: llm_router

    with (
        patch("glean.recipes.service.RecipeCorpusStore", return_value=_empty_corpus_store()),
        patch("glean.recipes.providers.socket.getaddrinfo", _fake_getaddrinfo({"example.com": "93.184.216.34"})),
        patch("glean.recipes.providers.httpx.Client", lambda **_: client_response),
    ):
        resp = client.post("/recipes/import-url", json={"url": "https://example.com/pasta"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Pasta Primavera"
    assert data["total_time_mins"] == 30
    assert len(data["ingredients"]) == 3
    assert len(data["instructions"]) == 3
    assert data["dietary_flags"] == ["Vegan"]
    mock_llm.invoke.assert_not_called()
    mock_llm.with_structured_output.assert_called_once_with(RecipeLlmResponse, method="json_schema")
    llm_router.chat_model.assert_called_once_with(Feature.RECIPE_IMPORT)


class _FakeClient:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = responses

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def get(self, url: str) -> httpx.Response:
        return self._responses.pop(0)


def _fake_getaddrinfo(host_map: dict[str, str]) -> Any:
    def getaddrinfo(hostname: str, *_: object, **__: object) -> list[tuple[int, int, int, str, tuple[str, int]]]:
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                (host_map[hostname], 443),
            )
        ]

    return getaddrinfo


def _empty_corpus_store() -> MagicMock:
    corpus_store = MagicMock()
    corpus_store.search.return_value = ([], 0)
    corpus_store.get.return_value = None
    corpus_store.get_by_source_url.return_value = None
    return corpus_store


def _stored_recipe(
    external_id: str,
    *,
    title: str,
    source_url: str | None = None,
    cuisine: str | None = None,
    dietary_flags: list[str] | None = None,
) -> StoredRecipe:
    return StoredRecipe(
        external_id=external_id,
        title=title,
        source_url=source_url,
        cuisine=cuisine,
        difficulty="Easy",
        total_time_mins=30,
        dietary_flags=dietary_flags or [],
        ingredients=[
            StoredIngredient(
                api_ingredient_id=f"{external_id}:ingredient:1",
                canonical_name="ingredient",
                quantity=1,
                unit="each",
            )
        ],
        instructions=[
            StoredInstruction(step_number=1, phase="main", text="Prepare ingredients."),
            StoredInstruction(step_number=2, phase="main", text="Cook and serve."),
        ],
        provenance=RecipeProvenance(
            source_url=source_url or "",
            parser="test",
        ),
    )
