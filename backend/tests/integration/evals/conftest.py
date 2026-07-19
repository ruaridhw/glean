from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel
    from pydantic import SecretStr

from glean.llm import (
    Feature,
    LLMRouter,
    ModelPurpose,
    create_chat_model,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> list[dict[str, Any]]:
    return json.loads((FIXTURES / name).read_text())


def _eval_feature_for_request(request: pytest.FixtureRequest) -> Feature:
    """Resolve the Feature under test from the module's own declaration.

    Each eval test module declares a module-level `FEATURE: Feature` constant.
    Reading that (instead of keying a lookup table on the test file's name)
    means renaming a test module can never again break model selection —
    see the two "Fix eval feature lookup for renamed meal-plan module" fixes
    in git history, both caused by a stale filename key.
    """
    module = request.module
    feature = getattr(module, "FEATURE", None)
    if not isinstance(feature, Feature):
        raise RuntimeError(
            f"{module.__name__} must define a module-level `FEATURE: Feature` constant "
            "identifying which feature it evaluates."
        )
    return feature


def _eval_model_id_for(feature: Feature, router: LLMRouter) -> str:
    return os.environ.get("GLEAN_EVAL_MODEL") or router.model_id_for(feature)


def _judge_model_id_for(feature: Feature, router: LLMRouter) -> str:
    return os.environ.get("GLEAN_JUDGE_MODEL") or router.model_id_for(feature, purpose=ModelPurpose.EVAL)


@pytest.fixture(scope="module")
def eval_model(request: pytest.FixtureRequest, openrouter_api_key: SecretStr) -> BaseChatModel:
    """Feature-specific LLM for eval runs."""
    feature = _eval_feature_for_request(request)
    model_id = _eval_model_id_for(feature, LLMRouter(api_key=openrouter_api_key))
    return create_chat_model(model_id, api_key=openrouter_api_key)


@pytest.fixture(scope="module")
def judge_model(request: pytest.FixtureRequest, openrouter_api_key: SecretStr) -> BaseChatModel:
    """Feature-specific LLM for judge scoring."""
    feature = _eval_feature_for_request(request)
    model_id = _judge_model_id_for(feature, LLMRouter(api_key=openrouter_api_key))
    return create_chat_model(model_id, api_key=openrouter_api_key)


@pytest.fixture(scope="session")
def receipt_scan_dataset() -> list[dict[str, Any]]:
    return _load_fixture("receipt_scan.json")


@pytest.fixture(scope="session")
def purchase_description_dataset() -> list[dict[str, Any]]:
    return _load_fixture("purchase_description.json")


@pytest.fixture(scope="session")
def meal_plan_generation_dataset() -> list[dict[str, Any]]:
    return _load_fixture("meal_plan_generation.json")


@pytest.fixture(scope="session")
def shopping_list_description_dataset() -> list[dict[str, Any]]:
    return _load_fixture("shopping_list_description.json")


@pytest.fixture(scope="session")
def recipe_import_dataset() -> list[dict[str, Any]]:
    return _load_fixture("recipe_import.json")
