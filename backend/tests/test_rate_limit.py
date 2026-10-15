"""Per-user limit on the paid-model routes, observed through the HTTP API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Request  # noqa: TC002 - FastAPI resolves this annotation at runtime.
from fastapi.testclient import TestClient

from glean.config import Settings, get_settings
from glean.dependencies import verify_cognito_token
from glean.main import app

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass(frozen=True)
class AiRoute:
    name: str
    path: str
    service_function: str
    request_kwargs: dict[str, Any] = field(default_factory=dict)


AI_ROUTES = [
    AiRoute(
        name="meal plan",
        path="/meal-plan",
        service_function="glean.meal_plan.router.service.generate_meal_plan",
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
        name="receipt scan",
        path="/receipts/scan",
        service_function="glean.receipts.router.service.scan_receipt",
        request_kwargs={"files": {"file": ("receipt.jpg", b"fake-image-bytes", "image/jpeg")}},
    ),
    AiRoute(
        name="receipt describe",
        path="/receipts/describe",
        service_function="glean.receipts.router.service.describe_purchase",
        request_kwargs={"json": {"text": "a kilo of chicken and 2 litres of milk"}},
    ),
    AiRoute(
        name="shopping parse description",
        path="/shopping/parse-description",
        service_function="glean.shopping.router.service.parse_shopping_description",
        request_kwargs={"json": {"text": "stuff for tacos"}},
    ),
    AiRoute(
        name="recipe import url",
        path="/recipes/import-url",
        service_function="glean.recipes.router.service.import_recipe_from_url",
        request_kwargs={"json": {"url": "https://example.com/carbonara"}},
    ),
]


def _sign_in_as_header_user(request: Request) -> str:
    return request.headers.get("x-test-user", "user-a")


@pytest.fixture
def limited_client(test_settings: Settings) -> Iterator[TestClient]:
    """A client whose Cognito sub comes from `x-test-user` and whose limit is 2 an hour."""
    settings = test_settings.model_copy(update={"rate_limit_per_hour": 2})
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[verify_cognito_token] = _sign_in_as_header_user
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.mark.parametrize("route", AI_ROUTES, ids=lambda route: route.name)
def test_request_over_the_hourly_limit_is_rejected_before_any_model_call(
    limited_client: TestClient, route: AiRoute
) -> None:
    with patch(route.service_function, MagicMock(side_effect=RuntimeError("model unavailable"))) as paid_call:
        responses = [limited_client.post(route.path, **route.request_kwargs) for _ in range(3)]

    assert [response.status_code for response in responses[:2]] != [429, 429]
    assert responses[2].status_code == 429
    assert "limit" in responses[2].json()["detail"].lower()
    assert paid_call.call_count == 2


@pytest.mark.parametrize("route", AI_ROUTES, ids=lambda route: route.name)
def test_one_user_hitting_the_limit_does_not_block_another_user(limited_client: TestClient, route: AiRoute) -> None:
    with patch(route.service_function, MagicMock(side_effect=RuntimeError("model unavailable"))):
        for _ in range(3):
            limited_client.post(route.path, headers={"x-test-user": "user-a"}, **route.request_kwargs)
        user_a = limited_client.post(route.path, headers={"x-test-user": "user-a"}, **route.request_kwargs)
        user_b = limited_client.post(route.path, headers={"x-test-user": "user-b"}, **route.request_kwargs)

    assert user_a.status_code == 429
    assert user_b.status_code != 429


def test_the_hourly_limit_is_the_configured_setting(test_settings: Settings) -> None:
    route = AI_ROUTES[0]
    settings = test_settings.model_copy(update={"rate_limit_per_hour": 4})
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[verify_cognito_token] = _sign_in_as_header_user
    client = TestClient(app, raise_server_exceptions=False)

    with patch(route.service_function, MagicMock(side_effect=RuntimeError("model unavailable"))) as paid_call:
        statuses = [client.post(route.path, **route.request_kwargs).status_code for _ in range(5)]
    app.dependency_overrides.clear()

    assert statuses[:4] == [500] * 4
    assert statuses[4] == 429
    assert paid_call.call_count == 4


def test_requests_without_a_token_get_401_and_do_not_use_up_the_limit(test_settings: Settings) -> None:
    route = AI_ROUTES[0]
    app.dependency_overrides[get_settings] = lambda: test_settings.model_copy(update={"rate_limit_per_hour": 1})
    client = TestClient(app, raise_server_exceptions=False)

    with patch(route.service_function, MagicMock(side_effect=RuntimeError("model unavailable"))):
        anonymous = [client.post(route.path, **route.request_kwargs).status_code for _ in range(3)]
        app.dependency_overrides[verify_cognito_token] = _sign_in_as_header_user
        first_signed_in = client.post(route.path, **route.request_kwargs)
    app.dependency_overrides.clear()

    assert anonymous == [401, 401, 401]
    assert first_signed_in.status_code != 429


def test_routes_that_call_no_paid_model_are_not_limited(test_settings: Settings) -> None:
    app.dependency_overrides[get_settings] = lambda: test_settings.model_copy(update={"rate_limit_per_hour": 1})
    app.dependency_overrides[verify_cognito_token] = _sign_in_as_header_user
    client = TestClient(app, raise_server_exceptions=False)

    health = [client.get("/health").status_code for _ in range(3)]
    with patch("glean.recipes.router.service.search_recipes", MagicMock(side_effect=RuntimeError("down"))):
        search = [client.get("/recipes/search", params={"q": "soup"}).status_code for _ in range(3)]
    app.dependency_overrides.clear()

    assert 429 not in health
    assert 429 not in search
