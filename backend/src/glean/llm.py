from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

import httpx
from langchain_openrouter import ChatOpenRouter

from glean.config import settings

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

_OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


class Feature(StrEnum):
    RECEIPT_SCAN = "receipt-scan"
    SUGGESTIONS = "suggestions"
    RECIPE_IMPORT = "recipe-import"


def validate_model(model_id: str) -> None:
    """Check that *model_id* exists in the OpenRouter catalogue. Raises ValueError if not."""
    resp = httpx.get(_OPENROUTER_MODELS_URL, timeout=10.0)
    resp.raise_for_status()
    known_ids = {m["id"] for m in resp.json()["data"]}
    if model_id not in known_ids:
        raise ValueError(
            f"Unknown OpenRouter model: {model_id!r}. "
            f"See https://openrouter.ai/models for available models."
        )


def create_chat_model(model: str, *, api_key: str) -> BaseChatModel:
    return ChatOpenRouter(model=model, openrouter_api_key=api_key)


def get_default_model() -> BaseChatModel:
    return create_chat_model(settings.llm_model, api_key=settings.openrouter_api_key)
