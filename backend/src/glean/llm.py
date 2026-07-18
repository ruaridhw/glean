from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from langchain_openrouter import ChatOpenRouter
from openrouter import OpenRouter
from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Mapping

    from langchain_core.language_models import BaseChatModel, LanguageModelInput
    from langchain_core.runnables import RunnableConfig
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


def invoke_structured[StructuredResponseT: BaseModel](
    model: BaseChatModel,
    schema: type[StructuredResponseT],
    messages: LanguageModelInput,
    *,
    config: RunnableConfig | None = None,
) -> StructuredResponseT:
    """Invoke an LLM through LangChain structured output and validate the result."""
    # method="json_schema" (OpenRouter response_format), NOT LangChain's default
    # function-calling path. The default binds the schema as a tool and forces it with
    # tool_choice=required; reasoning/"thinking" models reject that at the provider —
    # qwen/qwen3.7-plus returns "<400> InvalidParameter: The tool_choice parameter does
    # not support being set to required or object in thinking mode". json_schema asks for
    # the object via response_format instead of a forced tool call, so it sends no
    # tool_choice and works for every model in DEFAULT_LLM_MODEL_POLICY (verified against
    # qwen3.7-plus, z-ai/glm-5.2 and the gemini models). Without this, POST /meal-plan and
    # /recipes/import-url — both routed to qwen3.7-plus — fail in production.
    structured_model = model.with_structured_output(schema, method="json_schema")
    result = structured_model.invoke(messages, config=config)
    if isinstance(result, schema):
        return result
    return schema.model_validate(result)


def create_chat_model(model: str, *, api_key: SecretStr, **kwargs: Any) -> BaseChatModel:
    # Default max_retries=0: the OpenAI SDK respects Retry-After headers, so the default
    # of 2 retries can cause indefinite hangs when OpenRouter returns a long Retry-After
    # (e.g. free-models-per-day exhausted). Callers can override if retries are needed.
    kwargs.setdefault("max_retries", 0)
    # Bound stalled calls: without a timeout a single request blocks until OpenRouter's
    # ~600s server cap. Value is milliseconds (ChatOpenRouter.request_timeout -> SDK
    # timeout_ms). Caller-overridable for slower reasoning models.
    kwargs.setdefault("request_timeout", 10_000)
    return ChatOpenRouter(model=model, openrouter_api_key=api_key, **kwargs)
