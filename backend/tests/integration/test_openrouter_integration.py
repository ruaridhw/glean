"""Integration tests for OpenRouter connectivity.

These tests make real HTTP calls to the OpenRouter API and require a valid
``OPENROUTER_API_KEY`` (``sk-or-...``) in ``backend/.env``.

Run with::

    uv run pytest tests/test_openrouter_integration.py -v

Or via Make::

    make test-integration-backend

Unit tests (``make test-backend``) exclude this file automatically via the
``-m "not integration"`` flag so CI never hits the network unintentionally.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from dotenv import dotenv_values
from langchain_core.messages import HumanMessage
from openrouter import OpenRouter

from glean.llm import create_chat_model, validate_model

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ENV_FILE = Path(__file__).parent.parent / ".env"
_ENV = dotenv_values(_ENV_FILE)


@pytest.fixture(scope="module")
def openrouter_api_key() -> str:
    """Read directly from backend/.env, bypassing os.environ.

    conftest.py plants ``OPENROUTER_API_KEY=test-key`` via setdefault so that
    unit tests never need real credentials.  Integration tests must bypass
    os.environ entirely and read the file directly.
    """
    key = _ENV.get("OPENROUTER_API_KEY")
    if not key or not key.startswith("sk-or-"):
        pytest.skip("No real OPENROUTER_API_KEY found in backend/.env (expected sk-or-... prefix)")
    return key


@pytest.fixture(scope="module")
def default_model() -> str:
    return _ENV.get("LLM_MODEL") or "google/gemma-3-4b-it:free"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestOpenRouterConnectivity:
    def test_list_models_returns_results(self, openrouter_api_key: str, default_model: str) -> None:
        """OpenRouter API is reachable, returns a non-empty catalogue, and the default model is present."""
        client = OpenRouter(api_key=openrouter_api_key)
        model_ids = {m.id for m in client.models.list().data}
        assert len(model_ids) > 0, "Expected at least one model in the OpenRouter catalogue"
        assert default_model in model_ids, f"{default_model!r} not found in catalogue"

    def test_default_model_exists_in_catalogue(self, openrouter_api_key: str, default_model: str) -> None:
        """The default model passes validate_model (raises ValueError if unknown)."""
        validate_model(default_model, api_key=openrouter_api_key)


class TestOpenRouterChat:
    def test_simple_completion(self, openrouter_api_key: str, default_model: str) -> None:
        """End-to-end: chat completion returns a response containing 'pong'."""
        model = create_chat_model(default_model, api_key=openrouter_api_key)
        response = model.invoke([HumanMessage(content="Reply with exactly one word: pong")])
        assert isinstance(response.content, str)
        assert "pong" in response.content.lower(), f"Expected 'pong' in response, got: {response.content!r}"
