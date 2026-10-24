"""Per-user limit on the paid-model routes, observed through the HTTP API.

The real routes and domain code run. Only the external boundaries are stubbed: the LLM router,
the decisions endpoint, AWS (S3, Textract), outbound HTTP and DNS, and the recipe and shopping-parse
stores (local filesystem trees).
"""

from __future__ import annotations

import json
import socket
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi import Request  # noqa: TC002 - FastAPI resolves this annotation at runtime.
from fastapi.testclient import TestClient
from limits import parse
from pydantic import SecretStr

from glean.catalogue.router import get_catalogue_store
from glean.catalogue.seed import load_seed
from glean.catalogue.store import InMemoryCatalogueStore
from glean.config import Settings, get_settings
from glean.decisions import DecisionClient
from glean.dependencies import get_decision_client, get_llm_router, verify_cognito_token
from glean.main import app
from glean.meal_plan.schemas import MealPlanResponse
from glean.receipts.schemas import ScanResponse
from glean.recipe_api.blob_store import FilesystemBlobStore, get_shopping_parse_store
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.stored import RecipeProvenance, StoredIngredient, StoredInstruction, StoredRecipe
from glean.shopping.schemas import ShoppingParseResponse

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from contextlib import AbstractContextManager

RECEIPT_FIXTURES = Path(__file__).parent / "receipts" / "fixtures"
RECIPE_FIXTURES = Path(__file__).parent / "recipes" / "fixtures"

HOURLY_LIMIT = 2


class FakeLLMRouter:
    """Answers every structured request with an empty, valid response of the requested schema."""

    _EMPTY_RESPONSES: dict[type, Any] = {  # noqa: RUF012
        ScanResponse: ScanResponse(items=[]),
        ShoppingParseResponse: ShoppingParseResponse(items=[], clarifying_questions=[]),
        MealPlanResponse: MealPlanResponse(suggestions=[]),
    }

    def invoke(self, feature: object, schema: type, *_: object, **__: object) -> Any:
        return self._EMPTY_RESPONSES[schema]

    def model_id_for(self, feature: object, **_: object) -> str:
        return "fake/model"


class _StaticPage:
    """Stands in for the outbound HTTP client: every GET returns the same recipe page."""

    def __init__(self, html: str) -> None:
        self._html = html

    def __enter__(self) -> _StaticPage:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def get(self, url: str) -> httpx.Response:
        return httpx.Response(200, content=self._html.encode(), request=httpx.Request("GET", url))


def _public_dns(hostname: str, *_: object, **__: object) -> list[tuple[Any, ...]]:
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


def _stored_recipe(external_id: str) -> StoredRecipe:
    return StoredRecipe(
        external_id=external_id,
        title="Spaghetti Carbonara",
        difficulty="Easy",
        total_time_mins=30,
        ingredients=[
            StoredIngredient(
                api_ingredient_id=f"{external_id}:ingredient:1", canonical_name="spaghetti", quantity=200, unit="g"
            )
        ],
        instructions=[StoredInstruction(step_number=1, phase="main", text="Boil the spaghetti.")],
        provenance=RecipeProvenance(source_url="", parser="test"),
    )


@contextmanager
def _recipe_store(tmp_path: Path, *recipes: StoredRecipe) -> Iterator[None]:
    store = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    for recipe in recipes:
        store.save(recipe)
    with patch("glean.recipes.service.RecipeCorpusStore", return_value=store):
        yield


@contextmanager
def _no_external_boundaries(tmp_path: Path) -> Iterator[None]:
    yield


@contextmanager
def _aws_receipt_boundaries(tmp_path: Path) -> Iterator[None]:
    textract = MagicMock()
    textract.analyze_expense.return_value = json.loads((RECEIPT_FIXTURES / "receipt_textract.json").read_text())

    def aws_client(service_name: str, **_: object) -> MagicMock:
        return MagicMock() if service_name == "s3" else textract

    with patch("boto3.client", side_effect=aws_client):
        yield


@contextmanager
def _recipe_page_boundaries(tmp_path: Path) -> Iterator[None]:
    page = json.loads((RECIPE_FIXTURES / "recipe_detail.json").read_text())
    html = f'<html><head><script type="application/ld+json">{json.dumps(page)}</script></head></html>'
    with (
        _recipe_store(tmp_path),
        patch("glean.recipes.providers.socket.getaddrinfo", _public_dns),
        patch("glean.recipes.providers.httpx.Client", lambda **_: _StaticPage(html)),
    ):
        yield


@contextmanager
def _no_recipes(tmp_path: Path) -> Iterator[None]:
    """An empty corpus: the session answers `no_eligible_recipes` without spending a model call."""
    with patch("glean.recipes.corpus.get_recipe_corpus_store", lambda: FilesystemBlobStore(tmp_path)):
        yield


@contextmanager
def _catalogue_boundaries(tmp_path: Path) -> Iterator[None]:
    """The DynamoDB table is the boundary: the seed in memory stands in for it. A known name needs no model call."""
    catalogue = InMemoryCatalogueStore(load_seed().items)
    app.dependency_overrides[get_catalogue_store] = lambda: catalogue
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_catalogue_store, None)


@dataclass(frozen=True)
class AiRoute:
    name: str
    path: str
    boundaries: Callable[[Path], AbstractContextManager[None]] = _no_external_boundaries
    request_kwargs: dict[str, Any] = field(default_factory=dict)
    # A session is accepted (202), not answered (200): it runs out of process.
    success_status: int = 200


AI_ROUTES = [
    AiRoute(
        name="meal plan",
        path="/meal-plan",
        request_kwargs={
            "json": {
                "pantry": [],
                "recipe_history": [],
                "food_group_coverage": {},
                "purchase_tolerance": 0.3,
                "meals_per_week": 5,
                "dietary_flags": [],
                "max_active_time_mins": None,
            }
        },
    ),
    AiRoute(
        name="meal plan session",
        path="/meal-plan/sessions",
        boundaries=_no_recipes,
        request_kwargs={
            "json": {
                "source": "corpus",
                "pantry": [],
                "purchase_tolerance": 0.3,
                "meals_per_week": 5,
                "dietary_flags": [],
                "max_active_time_mins": None,
            }
        },
        success_status=202,
    ),
    AiRoute(
        name="receipt scan",
        path="/receipts/scan",
        boundaries=_aws_receipt_boundaries,
        request_kwargs={"files": {"file": ("receipt.jpg", b"fake-image-bytes", "image/jpeg")}},
    ),
    AiRoute(
        name="receipt describe",
        path="/receipts/describe",
        request_kwargs={"json": {"text": "a kilo of chicken and 2 litres of milk"}},
    ),
    AiRoute(
        name="shopping parse description",
        path="/shopping/parse-description",
        request_kwargs={"json": {"text": "stuff for tacos"}},
    ),
    AiRoute(
        name="recipe import url",
        path="/recipes/import-url",
        boundaries=_recipe_page_boundaries,
        request_kwargs={"json": {"url": "https://example.com/carbonara"}},
    ),
    AiRoute(
        name="catalogue normalise",
        path="/catalogue/normalise",
        boundaries=_catalogue_boundaries,
        request_kwargs={"json": {"names": ["toilet roll"]}},
    ),
]


def _sign_in_as_header_user(request: Request) -> str:
    return request.headers.get("x-test-user", "user-a")


def _canned_decisions(request: httpx.Request) -> httpx.Response:
    """The decisions endpoint, answering every asked question with a low probability."""
    names = json.loads(request.content)["questions"]
    return httpx.Response(
        200,
        json={
            "id": "gen-dec-rate-limit",
            "model": "typesafe/jev-1.14-20261014",
            "provider": "TypeSafe",
            "answers": {name: {"type": "noul", "noul": 0.1} for name in names},
            "usage": {"input_tokens": 1, "output_tokens": 1, "cost": 0.0},
        },
    )


def _client(settings: Settings, *, signed_in: bool = True) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_llm_router] = FakeLLMRouter
    decisions = DecisionClient(api_key=SecretStr("test"), transport=httpx.MockTransport(_canned_decisions))
    app.dependency_overrides[get_decision_client] = lambda: decisions
    parse_cache = FilesystemBlobStore(Path(tempfile.mkdtemp(prefix="rate-limit-parse-cache-")))
    app.dependency_overrides[get_shopping_parse_store] = lambda: parse_cache
    if signed_in:
        app.dependency_overrides[verify_cognito_token] = _sign_in_as_header_user
    return TestClient(app)


@pytest.fixture
def limited_client(test_settings: Settings) -> Iterator[TestClient]:
    """A client whose Cognito sub comes from `x-test-user` and whose limit is HOURLY_LIMIT an hour."""
    yield _client(test_settings.model_copy(update={"rate_limit_per_hour": HOURLY_LIMIT}))
    app.dependency_overrides.clear()


def _post(client: TestClient, route: AiRoute, user: str = "user-a") -> httpx.Response:
    return client.post(route.path, headers={"x-test-user": user}, **route.request_kwargs)


def _route_named(name: str) -> AiRoute:
    return next(route for route in AI_ROUTES if route.name == name)


@pytest.mark.parametrize("name", ["meal plan session", "meal plan"])
def test_a_refused_request_says_how_many_seconds_until_it_can_try_again(
    limited_client: TestClient, name: str, tmp_path: Path
) -> None:
    """The app turns this into "Try again in N minutes", so it has to be a real wait, not zero."""
    route = _route_named(name)

    with route.boundaries(tmp_path):
        allowed = [_post(limited_client, route) for _ in range(HOURLY_LIMIT)]
        refused = _post(limited_client, route)

    assert refused.status_code == 429
    retry_after = int(refused.headers["Retry-After"])
    assert 1 <= retry_after <= 3600  # an hourly window resets within the hour
    # Additive: the body the app already reads is unchanged.
    assert "limit" in refused.json()["detail"].lower()
    assert [response.headers.get("Retry-After") for response in allowed] == [None, None]


def test_the_retry_after_is_whole_seconds_until_the_window_resets(test_settings: Settings) -> None:
    from glean.rate_limit import _seconds_until_a_slot_frees, limiter  # noqa: PLC0415 - the helper under test

    item = parse("1/hour")
    limiter.limiter.hit(item, "the-user")

    seconds = _seconds_until_a_slot_frees(item, "the-user")

    assert isinstance(seconds, int)
    assert seconds > 0


@pytest.mark.parametrize("route", AI_ROUTES, ids=lambda route: route.name)
def test_request_over_the_hourly_limit_is_rejected(limited_client: TestClient, route: AiRoute, tmp_path: Path) -> None:
    with route.boundaries(tmp_path):
        statuses = [_post(limited_client, route).status_code for _ in range(HOURLY_LIMIT + 1)]
        over_limit = _post(limited_client, route)

    assert statuses[:HOURLY_LIMIT] == [route.success_status] * HOURLY_LIMIT
    assert statuses[HOURLY_LIMIT] == 429
    assert "limit" in over_limit.json()["detail"].lower()


@pytest.mark.parametrize("route", AI_ROUTES, ids=lambda route: route.name)
def test_one_user_hitting_the_limit_does_not_block_another_user(
    limited_client: TestClient, route: AiRoute, tmp_path: Path
) -> None:
    with route.boundaries(tmp_path):
        for _ in range(HOURLY_LIMIT):
            assert _post(limited_client, route, "user-a").status_code == route.success_status
        user_a = _post(limited_client, route, "user-a")
        user_b = _post(limited_client, route, "user-b")

    assert user_a.status_code == 429
    assert user_b.status_code == route.success_status


def test_the_hourly_limit_is_the_configured_setting(test_settings: Settings) -> None:
    route = AI_ROUTES[0]
    client = _client(test_settings.model_copy(update={"rate_limit_per_hour": 4}))

    statuses = [_post(client, route).status_code for _ in range(5)]
    app.dependency_overrides.clear()

    assert statuses == [200, 200, 200, 200, 429]


def test_requests_without_a_token_get_401_and_do_not_use_up_the_limit(test_settings: Settings) -> None:
    route = AI_ROUTES[0]
    client = _client(test_settings.model_copy(update={"rate_limit_per_hour": 1}), signed_in=False)

    anonymous = [client.post(route.path, **route.request_kwargs).status_code for _ in range(3)]
    app.dependency_overrides[verify_cognito_token] = _sign_in_as_header_user
    signed_in = [_post(client, route).status_code for _ in range(2)]
    app.dependency_overrides.clear()

    assert anonymous == [401, 401, 401]
    assert signed_in == [200, 429]


def test_routes_that_call_no_paid_model_are_not_limited(test_settings: Settings, tmp_path: Path) -> None:
    client = _client(test_settings.model_copy(update={"rate_limit_per_hour": 1}))

    with _recipe_store(tmp_path, _stored_recipe("rec_carbonara")):
        health = [client.get("/health").status_code for _ in range(3)]
        search = [client.get("/recipes/search", params={"q": "carbonara"}).status_code for _ in range(3)]
        detail = [client.get("/recipes/rec_carbonara").status_code for _ in range(3)]
    app.dependency_overrides.clear()

    assert health == [200] * 3
    assert search == [200] * 3
    assert detail == [200] * 3
