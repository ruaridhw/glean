# backend/src/glean/receipts/schemas.py
from pydantic import BaseModel, ConfigDict, Field


class ParsedIngredient(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str  # Claude-normalised canonical name
    quantity: float
    unit: str  # Normalised unit: "g", "ml", "units"
    unit_price: float | None = None  # Price per normalised unit (e.g. £/g)
    confidence: float = Field(ge=0.0, le=1.0)  # < 0.7 flagged for user review


class ScanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ParsedIngredient]


class DescribeRequest(BaseModel):
    text: str
