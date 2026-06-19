from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, computed_field

from glean.receipts.schemas import ParsedIngredient


class ShoppingParseRequest(BaseModel):
    """Natural-language shopping-list description to parse."""

    text: str = Field(min_length=1, max_length=2_000)


class ShoppingProposalItem(ParsedIngredient):
    """A grocery item proposal extracted from a shopping-list description."""

    model_config = ConfigDict(extra="forbid")

    category: str | None = Field(default=None, description="Broad grocery category when obvious.")

    @computed_field(
        return_type=str | None,
        description="Trusted ingredient catalogue ID; null until backend resolution is available.",
    )
    @property
    def api_ingredient_id(self) -> str | None:
        return None


class ShoppingParseResponse(BaseModel):
    """Structured shopping-list parse result for the Glean app."""

    model_config = ConfigDict(extra="forbid")

    items: list[ShoppingProposalItem] = Field(description="Shopping item proposals parsed from the user description.")
    clarifying_questions: list[str] = Field(
        default_factory=list,
        description="Questions to ask when the request is too ambiguous to propose confidently.",
    )
