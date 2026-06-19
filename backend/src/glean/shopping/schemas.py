from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from glean.receipts.schemas import ParsedIngredient


class ShoppingParseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2_000)


class ShoppingProposalItem(ParsedIngredient):
    model_config = ConfigDict(extra="forbid")

    api_ingredient_id: str | None = None
    category: str | None = None  # noqa: F841,RUF100


class ShoppingParseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ShoppingProposalItem]
    clarifying_questions: list[str] = Field(default_factory=list)
