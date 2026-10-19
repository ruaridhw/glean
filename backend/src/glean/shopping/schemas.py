from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from glean.receipts.schemas import ParsedIngredient


class ShoppingParseRequest(BaseModel):
    """Natural-language shopping-list description to parse."""

    text: str = Field(min_length=1, max_length=2_000)


class ShoppingUnit(StrEnum):
    """The practical units a shopping item may be proposed in.

    This deliberately duplicates the mobile-owned vocabulary (`shoppingUnits` in
    app/lib/data/util/unit_normalization.dart): the app decides which units it can add up and
    display, and until the project has a shared schema package the backend mirrors that list by
    hand. `tests/shopping/test_unit_vocabulary.py` fails when the two drift apart, so change
    both together.
    """

    G = "g"
    KG = "kg"
    ML = "ml"
    L = "l"
    UNITS = "units"
    PACK = "pack"
    BOTTLE = "bottle"
    BAG = "bag"
    BOX = "box"


class ShoppingProposalItem(ParsedIngredient):
    """A grocery item proposal extracted from a shopping-list description.

    `category` (and the `food_group` it derives) are inherited from `ParsedIngredient` —
    see that class for the taxonomy and out-of-taxonomy fallback.
    """

    model_config = ConfigDict(extra="forbid")

    unit: ShoppingUnit = Field(
        description='Practical shopping unit; use "units" for a plain count or when no amount was given.'
    )

    # Inactive for shopping parses: a model-supplied price can't be attributed to a store or date,
    # so it is always null. Re-enable (drop the validator) only when pricing attribution exists.
    unit_price: float | None = Field(default=None, description="Inactive: always null for shopping items.")

    @field_validator("unit_price", mode="after")
    @classmethod
    def _drop_unit_price(cls, _: float | None) -> None:
        return None


class ShoppingParseResponse(BaseModel):
    """Structured shopping-list parse result for the Glean app."""

    model_config = ConfigDict(extra="forbid")

    items: list[ShoppingProposalItem] = Field(description="Shopping item proposals parsed from the user description.")
    clarifying_questions: list[str] = Field(
        default_factory=list,
        description="Questions to ask when the request is too ambiguous to propose confidently.",
    )


class ShoppingUnitParse(BaseModel):
    """The parse of one numbered phrase in a batch."""

    model_config = ConfigDict(extra="forbid")

    number: int = Field(description="The number of the phrase this answers, exactly as listed in the request.")
    items: list[ShoppingProposalItem] = Field(description="Shopping item proposals for this phrase.")
    clarifying_questions: list[str] = Field(
        default_factory=list,
        description="Questions to ask when this phrase is too ambiguous to propose confidently.",
    )


class ShoppingBatchParseResponse(BaseModel):
    """Structured parse of several numbered phrases from one shopping list, answered in a single call."""

    model_config = ConfigDict(extra="forbid")

    units: list[ShoppingUnitParse] = Field(description="One entry for every numbered phrase, in any order.")
