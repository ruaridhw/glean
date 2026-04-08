from pydantic import BaseModel


class RecipeApiIngredient(BaseModel):
    ingredient_id: str
    name: str
    quantity: float | None = None
    unit: str | None = None
    preparation: str | None = None
    is_optional: bool = False
    substitutions: list[str] = []


class RecipeApiNutrition(BaseModel):
    calories: float = 0
    protein_g: float = 0
    carbohydrates_g: float = 0
    fat_g: float = 0
    fibre_g: float = 0
    sugar_g: float = 0
    sodium_mg: float = 0


class RecipeApiInstruction(BaseModel):
    step_number: int
    phase: str
    text: str


class RecipeApiMeta(BaseModel):
    total_time: str | None = None
    active_time: str | None = None
    yield_count: int | None = None


class RecipeApiRecipe(BaseModel):
    id: str
    name: str
    description: str | None = None
    category: str | None = None
    cuisine: str | None = None
    difficulty: str | None = None
    flags: list[str] = []
    not_suitable_for: list[str] = []
    meta: RecipeApiMeta = RecipeApiMeta()
    ingredients: list[RecipeApiIngredient] = []
    instructions: list[RecipeApiInstruction] = []
    nutrition: RecipeApiNutrition = RecipeApiNutrition()
    source_url: str | None = None


class RecipeApiSearchResult(BaseModel):
    id: str
    name: str
    cuisine: str | None = None
    difficulty: str | None = None
    total_time: str | None = None
    flags: list[str] = []


class RecipeApiSearchResponse(BaseModel):
    results: list[RecipeApiSearchResult]
    total: int
