from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Twelve weeks of dinners, with room for a household that cooks twice a day.
MAX_COOKED_HISTORY_ITEMS = 200
# A rating is a thumb on a cooked meal. The values are the wire vocabulary the app stores in `meal_ratings`.
Rating = Literal["up", "down"]
# Long enough for "too sweet for the kids, and the sauce split", short enough that the history window
# cannot be used as a free-text channel.
MAX_COOKED_NOTE_LENGTH = 500


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
    expires_in_days: int | None = Field(
        default=None,
        description=(
            "Whole days until the item goes off; null when its expiry date is unknown. Optional so an "
            "older app build that does not send it still works."
        ),
    )


class RecipeHistoryItem(BaseModel):
    recipe_id: int
    title: str
    last_cooked_at: datetime | None = Field(
        description="ISO datetime of last time this recipe was cooked; null if never cooked"
    )
    food_groups: list[str] = Field(description="Food groups this recipe covers (e.g. ['protein', 'veg'])")


class CookedHistoryItem(BaseModel):
    """One meal the household actually cooked, from the last 12 weeks.

    `recipe_id` is the corpus recipe id, which the app keeps as the plan entry's
    `externalIdSnapshot`. It is null for meals cooked before the app stored that
    snapshot, so `title` is the fallback identity.

    `rating` is the household's thumb on this cook, which selects the recipe in and out of planning
    (`meal_plan.eligibility`): the most recent rated cook decides. `note` is the comment they attached
    to it. Notes are accepted and validated here but are deliberately never handed to a model -- see
    `meal_plan.service` for the seam the screened-feedback screen plugs into.
    """

    recipe_id: str | None = Field(
        default=None, description="Corpus recipe id; the same id corpus suggestions carry as external_id"
    )
    title: str
    cooked_at: datetime = Field(description="ISO datetime the meal was cooked, with an offset (the app sends UTC)")
    rating: Rating | None = Field(
        default=None,
        description="The household's thumb on this cook; null when the meal was not rated",
    )
    note: str | None = Field(
        default=None,
        max_length=MAX_COOKED_NOTE_LENGTH,
        description=(
            "The comment attached to the rating; null when there is none. Stored and validated, but not "
            "read by planning until the feedback screen screens notes for prompt injection."
        ),
    )

    @field_validator("cooked_at")
    @classmethod
    def _read_a_missing_offset_as_utc(cls, value: datetime) -> datetime:
        """State the timezone instead of guessing it at the age arithmetic.

        The app sends `toUtc().toIso8601String()`, so this only catches an older build's local wall
        clock: reading it as UTC is explicit here, rather than silently assumed 30 lines away.
        """
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


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
    cooked_history: list[CookedHistoryItem] = Field(
        default_factory=list,
        max_length=MAX_COOKED_HISTORY_ITEMS,
        description="Meals cooked in the last 12 weeks, newest-idle first is not required; the plan avoids repeats",
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
    local_date: date | None = Field(
        default=None,
        description=(
            "The phone's local calendar date, the one `expires_in_days` was measured from. The plan dates "
            "a going-off item by the household's calendar, so it cannot use the server's UTC date. Null "
            "from an app build that does not send it."
        ),
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


class CorpusMealPlanResponse(BaseModel):
    """Corpus meal-planning recipes returned by the LLM."""

    model_config = ConfigDict(extra="forbid")

    suggestions: list[CorpusMealPlanRecipe] = Field(description="Ranked candidates that satisfy the constraints.")


class UsedUpPantryItem(BaseModel):
    """One urgent pantry item a planned meal uses up, so the app need not read it out of the reason."""

    name: str
    expires_in_days: int | None = Field(
        default=None, description="Whole days until the item goes off; null when unknown"
    )
    goes_off: str | None = Field(
        default=None,
        description="Weekday the item goes off in the household's calendar (e.g. 'Thu'); null when unknown",
    )


class MealPlanSuggestion(BaseModel):
    """One planned meal: a saved recipe (recipe_id) or a corpus recipe (external_id)."""

    recipe_id: int | None = None
    external_id: str | None = None
    title: str
    reason: str
    # Filled only by saved-mode plans; the app derives shopping gaps from the recipe itself.
    missing_ingredients: list[str] = Field(default_factory=list)
    # Urgent pantry items this meal uses, soonest to go off first. A proposal field the app shows later.
    uses_up: list[UsedUpPantryItem] = Field(default_factory=list)


class MealPlanResult(BaseModel):
    """The POST /meal-plan response."""

    suggestions: list[MealPlanSuggestion]
