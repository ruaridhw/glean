from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from glean.config import Settings, get_settings
from glean.dependencies import get_llm_router
from glean.llm import Feature
from glean.main import app
from glean.shopping.schemas import ShoppingParseResponse


@pytest.fixture
def unauth_client(test_settings: Settings) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: test_settings
    return TestClient(app)


def test_parse_shopping_description_returns_items(client: TestClient, auth_headers: dict[str, str]) -> None:
    structured_response = ShoppingParseResponse(
        items=[
            {
                "name": "taco shells",
                "quantity": 1,
                "unit": "pack",
                "unit_price": None,
                "api_ingredient_id": "taco-shells",
                "category": "bakery",
                "confidence": 0.82,
            }
        ],
        clarifying_questions=["What kind of salsa do you want?"],
    )

    llm_router = MagicMock()
    llm_router.chat_model.return_value.invoke.side_effect = AssertionError("raw LLM JSON should not be used")
    llm_router.chat_model.return_value.with_structured_output.return_value.invoke.return_value = structured_response
    app.dependency_overrides[get_llm_router] = lambda: llm_router
    response = client.post(
        "/shopping/parse-description",
        headers=auth_headers,
        json={"text": "stuff for tacos"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == [
        {
            "name": "taco shells",
            "quantity": 1.0,
            "unit": "pack",
            "unit_price": None,
            "confidence": 0.82,
            "api_ingredient_id": "taco-shells",
            "category": "bakery",
        }
    ]
    assert body["clarifying_questions"] == ["What kind of salsa do you want?"]
    llm_router.chat_model.assert_called_once_with(Feature.SHOPPING_LIST_DESCRIPTION)


def test_parse_shopping_description_requires_auth(test_settings: Settings) -> None:
    app.dependency_overrides[get_settings] = lambda: test_settings
    unauthenticated = TestClient(app)

    response = unauthenticated.post(
        "/shopping/parse-description",
        json={"text": "milk and bananas"},
    )

    assert response.status_code == 401
    app.dependency_overrides.clear()


def test_parse_shopping_description_rejects_empty_text(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/shopping/parse-description",
        headers=auth_headers,
        json={"text": ""},
    )

    assert response.status_code == 422
