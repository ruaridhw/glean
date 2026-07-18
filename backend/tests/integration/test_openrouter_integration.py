"""Integration tests for OpenRouter connectivity.

These tests make real HTTP calls to the OpenRouter API and require a valid
``OPENROUTER_API_KEY`` (``sk-or-...``) in ``backend/.env``.

Run with::

    uv run pytest tests/integration/ -v

Or via Make::

    make test-integration-backend

Unit tests (``make test-backend``) exclude this directory automatically via
``--ignore=tests/integration`` in pytest config.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from langchain_core.messages import HumanMessage
from openrouter import OpenRouter

from glean.llm import create_chat_model, validate_model

if TYPE_CHECKING:
    from pydantic import SecretStr

pytestmark = pytest.mark.integration


class TestOpenRouterConnectivity:
    def test_list_models_returns_results(self, openrouter_api_key: SecretStr, openrouter_smoke_model: str) -> None:
        """OpenRouter API is reachable, returns a non-empty catalogue, and the default model is present."""
        client = OpenRouter(api_key=openrouter_api_key.get_secret_value())
        model_ids = {m.id for m in client.models.list().data}
        assert len(model_ids) > 0, "Expected at least one model in the OpenRouter catalogue"
        assert openrouter_smoke_model in model_ids, f"{openrouter_smoke_model!r} not found in catalogue"

    def test_default_model_exists_in_catalogue(
        self, openrouter_api_key: SecretStr, openrouter_smoke_model: str
    ) -> None:
        """The default model passes validate_model (raises ValueError if unknown)."""
        validate_model(openrouter_smoke_model, api_key=openrouter_api_key)


class TestOpenRouterChat:
    def test_simple_completion(self, openrouter_api_key: SecretStr, openrouter_smoke_model: str) -> None:
        """End-to-end: chat completion returns a response containing 'pong'."""
        model = create_chat_model(openrouter_smoke_model, api_key=openrouter_api_key)
        response = model.invoke([HumanMessage(content="Reply with exactly one word: pong")])
        assert isinstance(response.content, str)
        assert "pong" in response.content.lower(), f"Expected 'pong' in response, got: {response.content!r}"
