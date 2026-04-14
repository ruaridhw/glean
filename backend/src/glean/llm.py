from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from langchain_openrouter import ChatOpenRouter
from openrouter import OpenRouter

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


class Feature(StrEnum):
    RECEIPT_SCAN = "receipt-scan"
    SUGGESTIONS = "suggestions"
    RECIPE_IMPORT = "recipe-import"


def validate_model(model_id: str, *, api_key: str) -> None:
    """Check that *model_id* exists in the OpenRouter catalogue. Raises ValueError if not."""
    client = OpenRouter(api_key=api_key)
    resp = client.models.list()
    known_ids = {m.id for m in resp.data}
    if model_id not in known_ids:
        raise ValueError(
            f"Unknown OpenRouter model: {model_id!r}. See https://openrouter.ai/models for available models."
        )


def create_chat_model(model: str, *, api_key: str, **kwargs: object) -> BaseChatModel:
    # Default max_retries=0: the OpenAI SDK respects Retry-After headers, so the default
    # of 2 retries can cause indefinite hangs when OpenRouter returns a long Retry-After
    # (e.g. free-models-per-day exhausted). Callers can override if retries are needed.
    kwargs.setdefault("max_retries", 0)
    return ChatOpenRouter(model=model, openrouter_api_key=api_key, **kwargs)


def get_default_model(*, model: str, api_key: str) -> BaseChatModel:
    return create_chat_model(model, api_key=api_key)
