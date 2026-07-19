from __future__ import annotations

import json
import socket
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from glean.llm import Feature
from glean.recipes.providers import (
    SchemaOrgThenLlmParser,
    fetch_public_https,
    import_url_to_canonical,
)
from glean.recipes.stored import RecipeImportError, RecipeLlmResponse


def test_schema_org_then_llm_parser_returns_stored_recipe_without_calling_llm() -> None:
    html = _schema_org_html(
        {
            "@context": "https://schema.org",
            "@graph": [
                {"@type": "WebPage", "name": "Not the recipe"},
                {
                    "@type": "Recipe",
                    "name": "Miso Noodles",
                    "totalTime": "PT25M",
                    "prepTime": "PT10M",
                    "recipeYield": "2 servings",
                    "recipeIngredient": ["150g noodles", "2 tbsp miso paste"],
                    "recipeInstructions": [
                        {"@type": "HowToStep", "text": "Cook the noodles."},
                        {"@type": "HowToStep", "text": "Toss with miso sauce."},
                    ],
                },
            ],
        }
    )
    llm_router = MagicMock()

    result = SchemaOrgThenLlmParser().parse(
        html,
        source_url="https://recipes.example.test/miso-noodles",
        llm_router=llm_router,
    )

    assert result.recipe is not None
    assert result.parser == "schema.org"
    assert result.source_url == "https://recipes.example.test/miso-noodles"
    assert result.fetched_url == "https://recipes.example.test/miso-noodles"
    assert result.recipe.title == "Miso Noodles"
    assert result.recipe.total_time_mins == 25
    assert [
        (ingredient.canonical_name, ingredient.quantity, ingredient.unit) for ingredient in result.recipe.ingredients
    ] == [
        ("Noodles", 150, "g"),
        ("Miso paste", 2, "tbsp"),
    ]
    llm_router.invoke.assert_not_called()


def test_schema_org_parser_reads_embedded_nutrition_mapping() -> None:
    html = _schema_org_html(
        {
            "@context": "https://schema.org",
            "@type": "Recipe",
            "name": "Green Lentil Bowl",
            "totalTime": "PT30M",
            "recipeYield": "4",
            "nutrition": {
                "calories": "334 kcal",
                "proteinContent": "32g",
                "carbohydrateContent": "29g",
                "fatContent": "10g",
                "fiberContent": "2g",
                "sodiumContent": "0.6g",
            },
            "recipeIngredient": ["300g cooked lentils", "60g pesto"],
            "recipeInstructions": [
                {"@type": "HowToStep", "text": "Warm the lentils."},
                {"@type": "HowToStep", "text": "Fold through the pesto."},
            ],
        }
    )
    llm_router = MagicMock()

    result = SchemaOrgThenLlmParser().parse(
        html,
        source_url="https://recipes.example.test/green-lentil-bowl",
        llm_router=llm_router,
    )

    assert result.recipe is not None
    assert result.recipe.nutrition is not None
    assert result.recipe.nutrition.calories == pytest.approx(334)
    assert result.recipe.nutrition.protein_g == pytest.approx(32)
    assert result.recipe.nutrition.carbohydrates_g == pytest.approx(29)
    assert result.recipe.nutrition.fat_g == pytest.approx(10)
    assert result.recipe.nutrition.fibre_g == pytest.approx(2)
    assert result.recipe.nutrition.sodium_mg == pytest.approx(600)
    llm_router.invoke.assert_not_called()


def test_schema_org_then_llm_parser_fallback_calls_llm_and_validates_returned_recipe() -> None:
    llm_recipe = RecipeLlmResponse(
        title="Black Bean Tacos",
        source_url="https://recipes.example.test/tacos",
        total_time="PT20M",
        prep_time="PT5M",
        yield_="3 servings",
        ingredients=["6 tortillas", "400g black beans", "1 lime"],
        instructions=["Warm the tortillas.", "Fill with beans and lime."],
        dietary_flags=["vegetarian"],
        not_suitable_for=[],
    )
    llm_router = MagicMock()
    llm_router.invoke.return_value = llm_recipe

    result = SchemaOrgThenLlmParser().parse(
        "<html><body><h1>Tacos</h1></body></html>",
        source_url="https://recipes.example.test/tacos",
        llm_router=llm_router,
    )

    assert result.recipe is not None
    assert result.parser == "llm"
    assert result.recipe.title == "Black Bean Tacos"
    assert result.recipe.yield_count == 3
    assert [instruction.text for instruction in result.recipe.instructions] == [
        "Warm the tortillas.",
        "Fill with beans and lime.",
    ]
    args, _ = llm_router.invoke.call_args
    assert args[0] == Feature.RECIPE_IMPORT
    assert args[1] is RecipeLlmResponse


def test_redirect_target_validation_rejects_private_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeClient(
        [
            httpx.Response(
                302,
                headers={"location": "https://internal.example.test/recipe"},
                request=httpx.Request("GET", "https://recipes.example.test/recipe"),
            )
        ]
    )
    monkeypatch.setattr("glean.recipes.providers.httpx.Client", lambda **_: client)
    monkeypatch.setattr(
        "glean.recipes.providers.socket.getaddrinfo",
        _fake_getaddrinfo(
            {
                "recipes.example.test": "93.184.216.34",
                "internal.example.test": "192.168.1.10",
            }
        ),
    )

    with pytest.raises(RecipeImportError) as exc_info:
        fetch_public_https("https://recipes.example.test/recipe")

    assert exc_info.value.category == "unsafe_url"
    assert client.requested_urls == ["https://recipes.example.test/recipe"]


def test_oversized_response_raises_response_too_large(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeClient(
        [
            httpx.Response(
                200,
                content=b"abcdef",
                request=httpx.Request("GET", "https://recipes.example.test/recipe"),
            )
        ]
    )
    monkeypatch.setattr("glean.recipes.providers.httpx.Client", lambda **_: client)
    monkeypatch.setattr(
        "glean.recipes.providers.socket.getaddrinfo",
        _fake_getaddrinfo({"recipes.example.test": "93.184.216.34"}),
    )

    with pytest.raises(RecipeImportError) as exc_info:
        fetch_public_https("https://recipes.example.test/recipe", max_bytes=5)

    assert exc_info.value.category == "response_too_large"


def test_default_fetch_limit_allows_large_recipe_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    body = b"a" * 5_100_000
    client = _FakeClient(
        [
            httpx.Response(
                200,
                content=body,
                request=httpx.Request("GET", "https://recipes.example.test/recipes/noodle-soup"),
            )
        ]
    )
    monkeypatch.setattr("glean.recipes.providers.httpx.Client", lambda **_: client)
    monkeypatch.setattr(
        "glean.recipes.providers.socket.getaddrinfo",
        _fake_getaddrinfo({"recipes.example.test": "93.184.216.34"}),
    )

    page = fetch_public_https("https://recipes.example.test/recipes/noodle-soup")

    assert len(page.text) == 5_100_000


def test_streaming_response_aborts_as_soon_as_max_bytes_exceeded(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = _ChunkStream([b"abc", b"def", b"ghi"])
    request = httpx.Request("GET", "https://recipes.example.test/recipe")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=stream, request=request)

    transport = httpx.MockTransport(handler)
    httpx_client = httpx.Client
    monkeypatch.setattr(
        "glean.recipes.providers.httpx.Client", lambda **kwargs: httpx_client(transport=transport, **kwargs)
    )
    monkeypatch.setattr(
        "glean.recipes.providers.socket.getaddrinfo",
        _fake_getaddrinfo({"recipes.example.test": "93.184.216.34"}),
    )

    with pytest.raises(RecipeImportError) as exc_info:
        fetch_public_https("https://recipes.example.test/recipe", max_bytes=5)

    assert exc_info.value.category == "response_too_large"
    assert stream.chunks_yielded == 2


def test_fetch_public_https_retries_browser_challenge_once(monkeypatch: pytest.MonkeyPatch) -> None:
    challenge_html = (
        "<html><head><title>Simple Page</title></head><body>Enable JavaScript and cookies to continue</body></html>"
    )
    recipe_html = _schema_org_html(
        {
            "@type": "Recipe",
            "name": "Chicken Enchiladas",
            "recipeIngredient": ["12 tortillas", "3 chicken breasts"],
            "recipeInstructions": ["Fill the tortillas.", "Bake until bubbling."],
        }
    )
    client = _FakeClient(
        [
            httpx.Response(
                403,
                content=challenge_html.encode(),
                request=httpx.Request("GET", "https://recipes.example.test/recipe/chicken-enchiladas/"),
            ),
            httpx.Response(
                200,
                content=recipe_html.encode(),
                request=httpx.Request("GET", "https://recipes.example.test/recipe/chicken-enchiladas/"),
            ),
        ]
    )
    monkeypatch.setattr("glean.recipes.providers.httpx.Client", lambda **_: client)
    monkeypatch.setattr(
        "glean.recipes.providers.socket.getaddrinfo",
        _fake_getaddrinfo({"recipes.example.test": "93.184.216.34"}),
    )

    page = fetch_public_https("https://recipes.example.test/recipe/chicken-enchiladas/")

    assert page.text == recipe_html
    assert client.requested_urls == [
        "https://recipes.example.test/recipe/chicken-enchiladas/",
        "https://recipes.example.test/recipe/chicken-enchiladas/",
    ]


def test_import_url_to_canonical_uses_direct_url_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    html = _schema_org_html(
        {
            "@type": "Recipe",
            "name": "Lemon Pasta",
            "recipeIngredient": ["200g spaghetti", "1 lemon"],
            "recipeInstructions": ["Boil pasta.", "Toss with lemon."],
        }
    )
    client = _FakeClient(
        [
            httpx.Response(
                200,
                content=html.encode(),
                request=httpx.Request("GET", "https://recipes.example.test/lemon-pasta"),
            )
        ]
    )
    monkeypatch.setattr("glean.recipes.providers.httpx.Client", lambda **_: client)
    monkeypatch.setattr(
        "glean.recipes.providers.socket.getaddrinfo",
        _fake_getaddrinfo({"recipes.example.test": "93.184.216.34"}),
    )

    result = import_url_to_canonical("https://recipes.example.test/lemon-pasta", llm_router=MagicMock())

    assert result.recipe is not None
    assert result.parser == "schema.org"
    assert result.recipe.title == "Lemon Pasta"


def _schema_org_html(data: dict[str, Any]) -> str:
    return f"""
    <html><head>
      <script type="application/ld+json">{json.dumps(data)}</script>
    </head><body></body></html>
    """


class _FakeClient:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = responses
        self.requested_urls: list[str] = []

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def stream(self, method: str, url: str) -> _ResponseContext:
        assert method == "GET"
        self.requested_urls.append(url)
        response = self._responses.pop(0)
        return _ResponseContext(response)


class _ResponseContext:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response

    def __enter__(self) -> httpx.Response:
        return self.response

    def __exit__(self, *_: object) -> None:
        self.response.close()


class _ChunkStream(httpx.SyncByteStream):
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.chunks_yielded = 0

    def __iter__(self):
        for chunk in self.chunks:
            self.chunks_yielded += 1
            yield chunk


def _fake_getaddrinfo(mapping: dict[str, str]):
    def getaddrinfo(host: str, port: int, *args: object, **kwargs: object) -> list[tuple[Any, ...]]:
        del args, kwargs
        ip = mapping[host]
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]

    return getaddrinfo
