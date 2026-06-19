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
    DEFAULT_LLM_MODEL_POLICY,
    Feature,
    LLMModelPolicy,
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
    "test_suggestions": Feature.MEAL_PLAN_GENERATION,
}


def _load_fixture(name: str) -> list[dict[str, Any]]:
    return json.loads((FIXTURES / name).read_text())


def _eval_feature_for_request(request: pytest.FixtureRequest) -> Feature:
    module_name = request.module.__name__.rsplit(".", maxsplit=1)[-1]
    return _EVAL_FEATURES_BY_MODULE[module_name]


def _model_override_for(feature: Feature, *, purpose: ModelPurpose) -> str | None:
    specific_env = f"GLEAN_{feature.name}_{purpose.value.upper()}_MODEL"
    return os.environ.get(specific_env) or os.environ.get(f"GLEAN_{purpose.value.upper()}_MODEL")


def _router_for_eval(openrouter_api_key: SecretStr) -> LLMRouter:
    policy_overrides: dict[Feature, LLMModelPolicy] = {}
    for feature in Feature:
        production_model = _model_override_for(feature, purpose=ModelPurpose.PRODUCTION)
        eval_model = _model_override_for(feature, purpose=ModelPurpose.EVAL)
        if production_model or eval_model:
            default_policy = DEFAULT_LLM_MODEL_POLICY[feature]
            policy_overrides[feature] = LLMModelPolicy(
                production_model=production_model or default_policy.production_model,
                eval_model=eval_model or default_policy.eval_model,
            )
    return LLMRouter(api_key=openrouter_api_key, policy=DEFAULT_LLM_MODEL_POLICY | policy_overrides)


@pytest.fixture(scope="module")
def eval_model(request: pytest.FixtureRequest, openrouter_api_key: SecretStr) -> BaseChatModel:
    """Feature-specific LLM for eval runs."""
    feature = _eval_feature_for_request(request)
    if model_id := _model_override_for(feature, purpose=ModelPurpose.EVAL):
        return create_chat_model(model_id, api_key=openrouter_api_key)
    return _router_for_eval(openrouter_api_key).chat_model(feature, purpose=ModelPurpose.EVAL)


@pytest.fixture(scope="module")
def judge_model(request: pytest.FixtureRequest, openrouter_api_key: SecretStr) -> BaseChatModel:
    """Feature-specific LLM for judge scoring."""
    feature = _eval_feature_for_request(request)
    model_id = os.environ.get("GLEAN_JUDGE_MODEL") or _model_override_for(feature, purpose=ModelPurpose.EVAL)
    if model_id:
        return create_chat_model(model_id, api_key=openrouter_api_key)
    return _router_for_eval(openrouter_api_key).chat_model(feature, purpose=ModelPurpose.EVAL)


@pytest.fixture(scope="session")
def receipt_scan_dataset() -> list[dict[str, Any]]:
    return _load_fixture("receipt_scan.json")


@pytest.fixture(scope="session")
def purchase_description_dataset() -> list[dict[str, Any]]:
    return _load_fixture("purchase_description.json")


@pytest.fixture(scope="session")
def suggestions_dataset() -> list[dict[str, Any]]:
    return _load_fixture("suggestions.json")


@pytest.fixture(scope="session")
def shopping_list_description_dataset() -> list[dict[str, Any]]:
    return _load_fixture("shopping_list_description.json")


@pytest.fixture(scope="session")
def recipe_import_dataset() -> list[dict[str, Any]]:
    return _load_fixture("recipe_import.json")
