# backend/src/glean/receipts/schemas.py
from pydantic import BaseModel, ConfigDict, Field


class ParsedIngredient(BaseModel):
    """A parsed grocery ingredient with normalised quantity details."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="LLM-normalised concise grocery item name suitable for a shopping list.")
    quantity: float = Field(description="Numeric quantity requested or inferred for the item.")
    unit: str = Field(description='Practical shopping unit such as "g", "ml", "units", "pack", or "bottle".')
    unit_price: float | None = Field(
        default=None,
        description="Price per requested unit when the user provided enough pricing detail.",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence from 0.0 to 1.0 that the item matches the request.",
    )


class ScanResponse(BaseModel):
    """Receipt scan or purchase-description parse result containing parsed ingredients."""

    model_config = ConfigDict(extra="forbid")

    items: list[ParsedIngredient] = Field(description="Parsed grocery ingredients extracted from the user input.")


class DescribeRequest(BaseModel):
    text: str
