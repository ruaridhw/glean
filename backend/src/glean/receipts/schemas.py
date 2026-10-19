# backend/src/glean/receipts/schemas.py
from typing import Literal, Self, cast

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from glean.catalogue.groups import GROUPS, GroupId
from glean.catalogue.legacy_categories import LEGACY_CATEGORY_GROUPS, legacy_category_for
from glean.observability import logger

# The 23 categories older app builds still read, each with the food group it always had. Derived from the catalogue's
# ingredient groups so the two can't drift; `category` goes once every phone reads `ingredient_group`.
INGREDIENT_CATEGORY_FOOD_GROUPS: dict[str, str] = {
    category: GROUPS[group].food_group.value for category, group in LEGACY_CATEGORY_GROUPS.items()
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

    ingredient_group: GroupId | None = Field(
        default=None,
        description="Ingredient group from the catalogue's fixed list; null only when genuinely unclassifiable.",
    )

    @field_validator("ingredient_group", mode="before")
    @classmethod
    def _fallback_out_of_catalogue_group(cls, value: object) -> object:
        """Coerce a group the catalogue doesn't have to null instead of failing the whole response."""
        if value is None or value in {group.value for group in GroupId}:
            return value
        logger.warning("llm returned out-of-catalogue ingredient group", extra={"ingredient_group": value})
        return None

    @model_validator(mode="after")
    def _agree_category_and_group(self) -> Self:
        """Until every phone reads `ingredient_group`, each of the two fills the other when it is missing, and the
        group wins where they disagree. Drop with `category`."""
        if self.ingredient_group is None and self.category is not None:
            self.ingredient_group = LEGACY_CATEGORY_GROUPS[self.category]
        elif self.ingredient_group is not None:
            current = LEGACY_CATEGORY_GROUPS.get(self.category) if self.category is not None else None
            if current is not self.ingredient_group:
                self.category = cast("IngredientCategory | None", legacy_category_for(self.ingredient_group))
        return self

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
        description='Food group derived from the ingredient group (else category); "other" when neither is set.',
    )
    @property
    def food_group(self) -> str:
        # Receipt proposals always emit a stable UI bucket; the LLM cannot
        # choose it independently of category. Meal-plan input food_group is
        # separately nullable (#95), so this fallback is not a validation rule.
        # "other" matches the clients' uncategorised pantry fallback.
        if self.ingredient_group is not None:
            return GROUPS[self.ingredient_group].food_group.value
        if self.category is None:
            return "other"
        return INGREDIENT_CATEGORY_FOOD_GROUPS.get(self.category, "other")


class ScanResponse(BaseModel):
    """Receipt scan or purchase-description parse result containing parsed ingredients."""

    model_config = ConfigDict(extra="forbid")

    items: list[ParsedIngredient] = Field(description="Parsed grocery ingredients extracted from the user input.")


class DescribeRequest(BaseModel):
    text: str
