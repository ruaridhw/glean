from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CompressedPantryItem(BaseModel):
    id: int
    name: str
    quantity: float
    unit: str
    food_group: str | None = Field(
        default=None, description="Food group of the ingredient's category; null when the ingredient is uncategorised"
    )
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


class MealPlanRequest(BaseModel):
    source: Literal["saved", "corpus"] = Field(
        default="saved",
        description="Choose from the user's saved recipes (recipe_history) or from the server's recipe corpus",
    )
    pantry: list[CompressedPantryItem] = Field(
        description="Top-N urgency-scored pantry items (staples and zero-quantity items excluded)"
    )
    recipe_history: list[RecipeHistoryItem] = Field(
        default_factory=list, description="All saved recipes with their last_cooked_at timestamps"
    )
    exclude_external_ids: list[str] = Field(
        default_factory=list, description="Corpus recipe IDs already in the plan, never offered again"
    )
    food_group_coverage: dict[str, int] = Field(
        default_factory=dict,
        description="Number of meals cooked this week per food group (e.g. {'protein': 2, 'veg': 1})",
    )
    purchase_tolerance: float = Field(
        ge=0.0,
        le=1.0,
        description="0.0 = only suggest recipes using pantry ingredients; 1.0 = any recipe regardless of missing items",
    )
    meals_per_week: int = Field(
        ge=1,
        le=7,
        description="Number of meal-plan slots to fill (may be less than full week if plan is partially filled)",
    )
    dietary_flags: list[str] = Field(description="User dietary preferences to respect (e.g. ['vegan', 'gluten-free'])")
    max_active_time_mins: int | None = Field(
        ge=1,
        le=480,
        description="Maximum active cooking time in minutes; null means no limit",
    )


class MealPlanRecipe(BaseModel):
    """A recipe selected for the user's current pantry and preferences."""

    model_config = ConfigDict(extra="forbid")

    recipe_id: int = Field(description="Stable saved recipe ID to include in the plan.")
    title: str = Field(description="Human-readable recipe title to show the user.")
    reason: str = Field(description="Human-readable explanation of why this recipe belongs in the meal plan")
    missing_ingredients: list[str] = Field(
        description="Ingredient names not currently in the pantry that would need purchasing"
    )


class MealPlanResponse(BaseModel):
    """Meal-planning recipes returned by the LLM."""

    model_config = ConfigDict(extra="forbid")

    suggestions: list[MealPlanRecipe] = Field(description="Ranked recipes that satisfy the request constraints.")


class CorpusMealPlanRecipe(BaseModel):
    """A corpus recipe the model selected from the candidates it was offered."""

    model_config = ConfigDict(extra="forbid")

    external_id: str = Field(description="external_id of the chosen candidate, copied exactly.")
    title: str = Field(description="Title of the chosen candidate, copied exactly.")
    reason: str = Field(description="Human-readable explanation of why this recipe belongs in the meal plan")
    missing_ingredients: list[str] = Field(
        description="Candidate ingredient names not currently in the pantry that would need purchasing"
    )


class CorpusMealPlanResponse(BaseModel):
    """Corpus meal-planning recipes returned by the LLM."""

    model_config = ConfigDict(extra="forbid")

    suggestions: list[CorpusMealPlanRecipe] = Field(description="Ranked candidates that satisfy the constraints.")


class MealPlanSuggestion(BaseModel):
    """One planned meal: a saved recipe (recipe_id) or a corpus recipe (external_id)."""

    recipe_id: int | None = None
    external_id: str | None = None
    title: str
    reason: str
    missing_ingredients: list[str]


class MealPlanResult(BaseModel):
    """The POST /meal-plan response."""

    suggestions: list[MealPlanSuggestion]
