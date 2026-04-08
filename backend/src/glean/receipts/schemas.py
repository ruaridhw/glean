# backend/src/glean/receipts/schemas.py
from pydantic import BaseModel


class ParsedIngredient(BaseModel):
    name: str  # Claude-normalised canonical name
    quantity: float
    unit: str  # Normalised unit: "g", "ml", "units"
    unit_price: float | None = None  # Price per normalised unit (e.g. £/g)
    confidence: float  # 0.0-1.0; < 0.7 flagged for user review


class ScanResponse(BaseModel):
    items: list[ParsedIngredient]


class DescribeRequest(BaseModel):
    text: str
