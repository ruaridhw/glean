"""Public recipe API schemas.

These `*Out` models are response DTOs for FastAPI and the mobile client. They
describe what leaves the backend, not how imported recipes are stored or where
they came from. Provider/provenance/cache metadata belongs in `StoredRecipe`.
"""

from pydantic import BaseModel


class RecipeIngredientOut(BaseModel):
    """Ingredient data returned to mobile clients in recipe responses."""

    api_ingredient_id: str | None = None
    canonical_name: str
    quantity: float
    unit: str
    preparation: str | None = None
    is_optional: bool = False
    substitutions: list[str] = []


class NutritionOut(BaseModel):
    """Nutrition data returned to mobile clients in recipe responses."""

    calories: float = 0
    protein_g: float = 0
    carbohydrates_g: float = 0
    fat_g: float = 0
    fibre_g: float = 0
    sugar_g: float = 0
    sodium_mg: float = 0


class InstructionOut(BaseModel):
    """Ordered instruction step returned to mobile clients in recipe responses."""

    step_number: int
    phase: str
    text: str


class RecipeOut(BaseModel):
    """Recipe detail response returned by backend recipe endpoints."""

    external_id: str
    title: str
    source_url: str | None = None
    cuisine: str | None = None
    difficulty: str | None = None
    active_time_mins: int | None = None
    total_time_mins: int | None = None
    dietary_flags: list[str] = []
    not_suitable_for: list[str] = []
    yield_count: int | None = None
    nutrition: NutritionOut | None = None
    instructions: list[InstructionOut] = []
    ingredients: list[RecipeIngredientOut] = []


class RecipeSearchResult(BaseModel):
    """Compact recipe search result returned by the recipe search endpoint."""

    external_id: str
    title: str
    cuisine: str | None = None
    difficulty: str | None = None
    total_time_mins: int | None = None
    dietary_flags: list[str] = []


class RecipeSearchResponse(BaseModel):
    """Paginated recipe search response returned by the recipe search endpoint."""

    results: list[RecipeSearchResult]
    total: int


class ImportUrlRequest(BaseModel):
    """Request body for importing a recipe from a user-provided URL."""

    url: str
    rendered_html: str | None = None
    fetched_url: str | None = None
