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

_EVAL_FEATURES_BY_MODULE = {
    "test_purchase_description": Feature.PANTRY_PURCHASE_DESCRIPTION,
    "test_receipt_scan": Feature.RECEIPT_SCAN,
    "test_recipe_import": Feature.RECIPE_IMPORT,
    "test_shopping_list_description": Feature.SHOPPING_LIST_DESCRIPTION,
    "test_meal_plan_generation": Feature.MEAL_PLAN_GENERATION,
}


def _load_fixture(name: str) -> list[dict[str, Any]]:
    return json.loads((FIXTURES / name).read_text())


def _eval_feature_for_request(request: pytest.FixtureRequest) -> Feature:
    module_name = request.module.__name__.rsplit(".", maxsplit=1)[-1]
    return _EVAL_FEATURES_BY_MODULE[module_name]


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
