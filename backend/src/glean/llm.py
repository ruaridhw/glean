from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from langchain_anthropic import ChatAnthropic

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    ChatGoogleGenerativeAI = None  # type: ignore[assignment,misc]


class Feature(StrEnum):
    RECEIPT_SCAN = "receipt-scan"
    SUGGESTIONS = "suggestions"
    RECIPE_IMPORT = "recipe-import"


def create_chat_model(provider: str, model: str, *, api_key: str) -> BaseChatModel:
    match provider:
        case "anthropic":
            return ChatAnthropic(model=model, api_key=api_key)
        case "google":
            if ChatGoogleGenerativeAI is None:
                raise ImportError("langchain-google-genai is required for the google provider")
            return ChatGoogleGenerativeAI(model=model, api_key=api_key)
        case _:
            raise ValueError(f"Unknown LLM provider: {provider}")
