from __future__ import annotations

import base64
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage, SystemMessage  # noqa: TID251 - this module owns LangChain
from langchain_core.messages.content import create_image_block, create_text_block  # noqa: TID251
from langchain_openrouter import ChatOpenRouter  # noqa: TID251 - this module owns LangChain
from openrouter import OpenRouter  # noqa: TID251 - this module owns the SDK
from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from langchain_core.language_models import BaseChatModel, LanguageModelInput  # noqa: TID251
    from langchain_core.messages import BaseMessage  # noqa: TID251
    from langchain_core.messages.content import ContentBlock  # noqa: TID251
    from langchain_core.runnables import RunnableConfig  # noqa: TID251
    from pydantic import SecretStr


@dataclass(frozen=True, slots=True)
class LLMModelPolicy:
    production_model: str
    eval_model: str


class ModelPurpose(StrEnum):
    PRODUCTION = "production"
    EVAL = "eval"


class Feature(StrEnum):
    """Every LLM-backed feature, with its LLMModelPolicy attached to the member.

    This is the single place to add a feature: one line below with its slug
    and policy. Python enforces total coverage for free — a member defined
    without a policy (or with something that isn't an LLMModelPolicy) raises
    an error while this module is imported, so there is no way to ship a
    Feature that later raises a latent KeyError in LLMRouter.model_id_for.
    """

    policy: LLMModelPolicy

    def __new__(cls, value: str, policy: LLMModelPolicy) -> Feature:
        if not isinstance(policy, LLMModelPolicy):
            raise TypeError(f"Feature {value!r} must be given an LLMModelPolicy, got {policy!r}")
        member = str.__new__(cls, value)
        member._value_ = value
        member.policy = policy
        return member

    RECEIPT_SCAN = (
        "receipt-scan",
        LLMModelPolicy(
            production_model="google/gemini-3.1-flash-lite",
            eval_model="google/gemini-3.5-flash",
        ),
    )
    PANTRY_PURCHASE_DESCRIPTION = (
        "pantry-purchase-description",
        LLMModelPolicy(
            production_model="google/gemini-2.5-flash-lite",
            eval_model="google/gemini-3.1-flash-lite",
        ),
    )
    MEAL_PLAN_GENERATION = (
        "meal-plan-generation",
        LLMModelPolicy(
            # qwen/qwen3.7-plus took 27-33s per plan, past the 30s Lambda/API Gateway cap;
            # this model returned the same plan in ~1.5s.
            production_model="google/gemini-3.1-flash-lite",
            eval_model="z-ai/glm-5.2",
        ),
    )
    RECIPE_IMPORT = (
        "recipe-import",
        LLMModelPolicy(
            # qwen/qwen3.7-plus took 19-61s per page (past the 30s Lambda cap); this model
            # extracted the same recipes in 1.4-2.3s.
            production_model="google/gemini-3.1-flash-lite",
            eval_model="z-ai/glm-5.2",
        ),
    )
    SHOPPING_LIST_DESCRIPTION = (
        "shopping-list-description",
        LLMModelPolicy(
            production_model="google/gemini-2.5-flash-lite",
            eval_model="google/gemini-3.1-flash-lite",
        ),
    )
    INGREDIENT_NORMALISATION = (
        "ingredient-normalisation",
        LLMModelPolicy(
            production_model="google/gemini-2.5-flash-lite",
            eval_model="google/gemini-3.1-flash-lite",
        ),
    )


# Derived, not authored: kept for callers that want a plain mapping (e.g. the
# LLMRouter default policy below). Building it by iterating Feature means it can
# never drift from the per-member policies declared above.
DEFAULT_LLM_MODEL_POLICY: dict[Feature, LLMModelPolicy] = {feature: feature.policy for feature in Feature}


@dataclass(frozen=True, slots=True)
class ImagePart:
    """An image in the user message, such as a receipt photo for a vision model."""

    data: bytes
    mime_type: str


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

    def invoke[StructuredResponseT: BaseModel](
        self,
        feature: Feature,
        schema: type[StructuredResponseT],
        *,
        system: str,
        user: str | Sequence[str | ImagePart],
        purpose: ModelPurpose = ModelPurpose.PRODUCTION,
        timeout_ms: int | None = None,
    ) -> StructuredResponseT:
        """Ask *feature*'s model one question: a *system* prompt and a *user* message, which is text or a
        sequence of text and image parts. Returns the reply validated as *schema*.

        The chat model, messages, structured-output policy and LangSmith metadata (`{"feature": feature}`) all stay
        in this module, so callers never import LangChain. *timeout_ms* bounds the call; without it the call gets
        create_chat_model's default.
        """
        options: dict[str, Any] = {} if timeout_ms is None else {"request_timeout": timeout_ms}
        model = create_chat_model(self.model_id_for(feature, purpose=purpose), api_key=self.api_key, **options)
        return invoke_structured(model, schema, _messages(system, user), config={"metadata": {"feature": feature}})


def _messages(system: str, user: str | Sequence[str | ImagePart]) -> list[BaseMessage]:
    if isinstance(user, str):
        return [SystemMessage(content=system), HumanMessage(content=user)]
    return [SystemMessage(content=system), HumanMessage(content_blocks=[_content_block(part) for part in user])]


def _content_block(part: str | ImagePart) -> ContentBlock:
    if isinstance(part, str):
        return create_text_block(part)
    return create_image_block(base64=base64.b64encode(part.data).decode(), mime_type=part.mime_type)


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
    # qwen3.7-plus, z-ai/glm-5.2 and the gemini models). Without this, reasoning models such
    # as z-ai/glm-5.2 (the eval judge) fail outright.
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
