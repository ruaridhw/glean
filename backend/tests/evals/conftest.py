from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models import BaseChatModel

from glean.llm import create_chat_model

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> list[dict[str, Any]]:
    return json.loads((FIXTURES / name).read_text())


def _make_model() -> BaseChatModel:
    provider = os.environ.get("GLEAN_LLM_PROVIDER", "google")
    model = os.environ.get("GLEAN_LLM_MODEL", "gemma-3")
    api_key = os.environ.get("GOOGLE_API_KEY", "") or os.environ.get("ANTHROPIC_API_KEY", "")
    return create_chat_model(provider, model, api_key=api_key)


@pytest.fixture(scope="session")
def eval_model() -> BaseChatModel:
    """Create the LLM used for eval runs. Defaults to google/gemma-3."""
    return _make_model()


@pytest.fixture(scope="session")
def judge_model() -> BaseChatModel:
    """Create the LLM used for LLM-as-judge scoring. Defaults to google/gemma-3."""
    return _make_model()


@pytest.fixture(scope="session")
def receipt_scan_dataset() -> list[dict[str, Any]]:
    return _load_fixture("receipt_scan.json")


@pytest.fixture(scope="session")
def suggestions_dataset() -> list[dict[str, Any]]:
    return _load_fixture("suggestions.json")


@pytest.fixture(scope="session")
def recipe_import_dataset() -> list[dict[str, Any]]:
    return _load_fixture("recipe_import.json")
