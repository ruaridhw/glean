from datetime import datetime  # noqa: TC003

from pydantic import BaseModel, Field


class CompressedPantryItem(BaseModel):
    id: int
    name: str
    quantity: float
    unit: str
    food_group: str
    urgency_score: float = Field(
        description="Higher score = more urgent to use (expiring soon, long unused, low quantity)"
    )


class RecipeHistoryItem(BaseModel):
    recipe_id: int
    title: str
    last_cooked_at: datetime | None = Field(
        description="ISO datetime of last time this recipe was cooked; null if never cooked"
    )
    food_groups: list[str] = Field(description="Food groups this recipe covers (e.g. ['protein', 'veg'])")


class SuggestionRequest(BaseModel):
    pantry: list[CompressedPantryItem] = Field(
        description="Top-N urgency-scored pantry items (staples and zero-quantity items excluded)"
    )
    recipe_history: list[RecipeHistoryItem] = Field(
        description="All saved recipes with their last_cooked_at timestamps"
    )
    food_group_coverage: dict[str, int] = Field(
        description="Number of meals cooked this week per food group (e.g. {'protein': 2, 'veg': 1})"
    )
    purchase_tolerance: float = Field(
        ge=0.0,
        le=1.0,
        description="0.0 = only suggest recipes using pantry ingredients; 1.0 = any recipe regardless of missing items",
    )
    meals_per_week: int = Field(
        description="Number of suggestion slots to fill (may be less than full week if plan is partially filled)"
    )
    dietary_flags: list[str] = Field(description="User dietary preferences to respect (e.g. ['vegan', 'gluten-free'])")
    max_active_time_mins: int | None = Field(description="Maximum active cooking time in minutes; null means no limit")


class SuggestedRecipe(BaseModel):
    recipe_id: int
    title: str
    reason: str = Field(description="Human-readable explanation of why this recipe was suggested")
    missing_ingredients: list[str] = Field(
        description="Ingredient names not currently in the pantry that would need purchasing"
    )


class SuggestionResponse(BaseModel):
    suggestions: list[SuggestedRecipe]
