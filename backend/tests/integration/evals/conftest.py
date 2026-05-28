from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

from glean.llm import create_chat_model

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> list[dict[str, Any]]:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(scope="session")
def eval_model(openrouter_api_key: str, llm_model: str) -> BaseChatModel:
    """LLM for eval runs. Key + model flow from tests/integration/conftest.py."""
    model_id = os.environ.get("GLEAN_LLM_MODEL", llm_model)
    return create_chat_model(model_id, api_key=openrouter_api_key)


@pytest.fixture(scope="session")
def judge_model(openrouter_api_key: str, llm_model: str) -> BaseChatModel:
    """LLM for judge scoring. Same credentials as eval_model."""
    model_id = os.environ.get("GLEAN_LLM_MODEL", llm_model)
    return create_chat_model(model_id, api_key=openrouter_api_key)


@pytest.fixture(scope="session")
def receipt_scan_dataset() -> list[dict[str, Any]]:
    return _load_fixture("receipt_scan.json")


@pytest.fixture(scope="session")
def suggestions_dataset() -> list[dict[str, Any]]:
    return _load_fixture("suggestions.json")


@pytest.fixture(scope="session")
def recipe_import_dataset() -> list[dict[str, Any]]:
    return _load_fixture("recipe_import.json")
