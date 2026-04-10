from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from langchain_openrouter import ChatOpenRouter

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


class Feature(StrEnum):
    RECEIPT_SCAN = "receipt-scan"
    SUGGESTIONS = "suggestions"
    RECIPE_IMPORT = "recipe-import"


def create_chat_model(model: str, *, api_key: str) -> BaseChatModel:
    return ChatOpenRouter(model=model, openrouter_api_key=api_key)


def get_default_model() -> BaseChatModel:
    from glean.config import settings  # noqa: PLC0415 - local import avoids circular dependency

    return create_chat_model(settings.llm_model, api_key=settings.openrouter_api_key)
