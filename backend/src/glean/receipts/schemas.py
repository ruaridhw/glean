# backend/src/glean/receipts/schemas.py
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from glean.observability import logger

# The 23-category taxonomy the Flutter client already uses
# (app/lib/data/seed/taxonomy.dart) and expects `food_group` to be derived
# from. Keep this mapping in sync with that file — it is the single source
# `food_group` is derived from, so the client never receives a category it
# can't map.
INGREDIENT_CATEGORY_FOOD_GROUPS: dict[str, str] = {
    "leafy_greens": "vegetables",
    "brassicas": "vegetables",
    "alliums": "vegetables",
    "root_vegetables": "vegetables",
    "nightshades": "vegetables",
    "legumes": "protein",
    "citrus": "fruit",
    "tropical_fruit": "fruit",
    "stone_fruit": "fruit",
    "berries": "fruit",
    "red_meat": "protein",
    "poultry": "protein",
    "seafood": "protein",
    "eggs": "protein",
    "dairy": "dairy",
    "grains": "carbohydrates",
    "pasta_rice": "carbohydrates",
    "bread": "carbohydrates",
    "oils_fats": "fats",
    "herbs_fresh": "condiments",
    "herbs_dried": "condiments",
    "spices": "condiments",
    "condiments": "condiments",
}

# `ty` requires Literal args to be written out (it can't evaluate a dynamic tuple), so this
# duplicates the keys above. `test_taxonomy_matches_ingredient_category_literal` in
# tests/receipts/test_schemas.py guards the two against drifting apart.
IngredientCategory = Literal[
    "leafy_greens",
    "brassicas",
    "alliums",
    "root_vegetables",
    "nightshades",
    "legumes",
    "citrus",
    "tropical_fruit",
    "stone_fruit",
    "berries",
    "red_meat",
    "poultry",
    "seafood",
    "eggs",
    "dairy",
    "grains",
    "pasta_rice",
    "bread",
    "oils_fats",
    "herbs_fresh",
    "herbs_dried",
    "spices",
    "condiments",
]


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
    category: IngredientCategory | None = Field(
        default=None,
        description="Ingredient category drawn from the fixed taxonomy; null only when genuinely unclassifiable.",
    )

    @field_validator("category", mode="before")
    @classmethod
    def _fallback_out_of_taxonomy_category(cls, value: object) -> object:
        """Coerce an out-of-taxonomy LLM value to null instead of failing the whole response.

        The Literal type above already constrains the JSON schema offered to the LLM, so this
        should be rare in practice. Logging it means the fallback can't silently become the
        common case — an unexpectedly high rate here is a signal the prompt or model changed.
        """
        if value is None or value in INGREDIENT_CATEGORY_FOOD_GROUPS:
            return value
        logger.warning("llm returned out-of-taxonomy ingredient category", extra={"category": value})
        return None

    @computed_field(
        return_type=str,
        description='Food group derived deterministically from category; "other" when category is null.',
    )
    @property
    def food_group(self) -> str:
        # Non-nullable by design: meal_plan/schemas.py declares food_group non-nullable, so a
        # null here would 422 generation for exactly the ingredients this change exists to fix.
        # "other" is an existing client-side food-group bucket (the coalesce in
        # app/lib/data/repositories/pantry_repository.dart's watchAll/getAll),
        # so this needs no new vocabulary and renders correctly with zero client changes.
        if self.category is None:
            return "other"
        return INGREDIENT_CATEGORY_FOOD_GROUPS.get(self.category, "other")


class ScanResponse(BaseModel):
    """Receipt scan or purchase-description parse result containing parsed ingredients."""

    model_config = ConfigDict(extra="forbid")

    items: list[ParsedIngredient] = Field(description="Parsed grocery ingredients extracted from the user input.")


class DescribeRequest(BaseModel):
    text: str
