from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from langchain_openrouter import ChatOpenRouter
from openrouter import OpenRouter

if TYPE_CHECKING:
    from collections.abc import Mapping

    from langchain_core.language_models import BaseChatModel
    from pydantic import SecretStr


class Feature(StrEnum):
    RECEIPT_SCAN = "receipt-scan"
    PANTRY_PURCHASE_DESCRIPTION = "pantry-purchase-description"
    MEAL_PLAN_GENERATION = "meal-plan-generation"
    RECIPE_IMPORT = "recipe-import"
    SHOPPING_LIST_DESCRIPTION = "shopping-list-description"


class ModelPurpose(StrEnum):
    PRODUCTION = "production"
    EVAL = "eval"


@dataclass(frozen=True, slots=True)
class LLMModelPolicy:
    production_model: str
    eval_model: str


DEFAULT_LLM_MODEL_POLICY: dict[Feature, LLMModelPolicy] = {
    Feature.SHOPPING_LIST_DESCRIPTION: LLMModelPolicy(
        production_model="google/gemini-2.5-flash-lite",
        eval_model="google/gemini-3.1-flash-lite",
    ),
    Feature.PANTRY_PURCHASE_DESCRIPTION: LLMModelPolicy(
        production_model="google/gemini-2.5-flash-lite",
        eval_model="google/gemini-3.1-flash-lite",
    ),
    Feature.RECEIPT_SCAN: LLMModelPolicy(
        production_model="google/gemini-3.1-flash-lite",
        eval_model="google/gemini-3.5-flash",
    ),
    Feature.RECIPE_IMPORT: LLMModelPolicy(
        production_model="qwen/qwen3.7-plus",
        eval_model="z-ai/glm-5.2",
    ),
    Feature.MEAL_PLAN_GENERATION: LLMModelPolicy(
        production_model="qwen/qwen3.7-plus",
        eval_model="z-ai/glm-5.2",
    ),
}


class LLMRouter:
    def __init__(
        self,
        *,
        api_key: SecretStr,
        policy_overrides: Mapping[Feature, LLMModelPolicy] | None = None,
    ) -> None:
        self.api_key = api_key
        self.policy = dict(DEFAULT_LLM_MODEL_POLICY)
        if policy_overrides:
            self.policy.update(policy_overrides)

    @classmethod
    def from_settings(cls, settings: Any) -> LLMRouter:
        return cls(api_key=settings.openrouter_api_key, policy_overrides=settings.llm_model_policy_overrides)

    def model_id_for(self, feature: Feature, *, purpose: ModelPurpose = ModelPurpose.PRODUCTION) -> str:
        feature_policy = self.policy[feature]
        if purpose == ModelPurpose.EVAL:
            return feature_policy.eval_model
        return feature_policy.production_model

    def chat_model(
        self,
        feature: Feature,
        *,
        purpose: ModelPurpose = ModelPurpose.PRODUCTION,
        **kwargs: Any,
    ) -> BaseChatModel:
        return create_chat_model(self.model_id_for(feature, purpose=purpose), api_key=self.api_key, **kwargs)


def validate_model(model_id: str, *, api_key: SecretStr) -> None:
    """Check that *model_id* exists in the OpenRouter catalogue. Raises ValueError if not."""
    client = OpenRouter(api_key=api_key.get_secret_value())
    resp = client.models.list()
    known_ids = {m.id for m in resp.data}
    if model_id not in known_ids:
        raise ValueError(
            f"Unknown OpenRouter model: {model_id!r}. See https://openrouter.ai/models for available models."
        )


def message_content_as_text(content: object) -> str:
    if not isinstance(content, str):
        raise TypeError(f"Expected text content from LLM response, got {type(content).__name__}")
    return content


def create_chat_model(model: str, *, api_key: SecretStr, **kwargs: Any) -> BaseChatModel:
    # Default max_retries=0: the OpenAI SDK respects Retry-After headers, so the default
    # of 2 retries can cause indefinite hangs when OpenRouter returns a long Retry-After
    # (e.g. free-models-per-day exhausted). Callers can override if retries are needed.
    kwargs.setdefault("max_retries", 0)
    return ChatOpenRouter(model=model, openrouter_api_key=api_key, **kwargs)
