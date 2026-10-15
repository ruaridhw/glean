"""Per-user limit on the paid-model routes, observed through the HTTP API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Request
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
