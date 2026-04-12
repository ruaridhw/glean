from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from langchain_openrouter import ChatOpenRouter
from openrouter import OpenRouter

from glean.config import settings

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


class Feature(StrEnum):
    RECEIPT_SCAN = "receipt-scan"
    SUGGESTIONS = "suggestions"
    RECIPE_IMPORT = "recipe-import"


def validate_model(model_id: str, *, api_key: str | None = None) -> None:
    """Check that *model_id* exists in the OpenRouter catalogue. Raises ValueError if not."""
    client = OpenRouter(api_key=api_key or settings.openrouter_api_key)
    resp = client.models.list()
    known_ids = {m.id for m in resp.data}
    if model_id not in known_ids:
        raise ValueError(
            f"Unknown OpenRouter model: {model_id!r}. See https://openrouter.ai/models for available models."
        )


def create_chat_model(model: str, *, api_key: str) -> BaseChatModel:
    return ChatOpenRouter(model=model, openrouter_api_key=api_key)


def get_default_model() -> BaseChatModel:
    return create_chat_model(settings.llm_model, api_key=settings.openrouter_api_key)
