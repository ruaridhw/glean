from pydantic import BaseModel


class RecipeIngredientOut(BaseModel):
    api_ingredient_id: str
    canonical_name: str
    quantity: float
    unit: str
    preparation: str | None = None
    is_optional: bool = False
    substitutions: list[str] = []


class NutritionOut(BaseModel):
    calories: float = 0
    protein_g: float = 0
    carbohydrates_g: float = 0
    fat_g: float = 0
    fibre_g: float = 0
    sugar_g: float = 0
    sodium_mg: float = 0


class InstructionOut(BaseModel):
    step_number: int
    phase: str
    text: str


class RecipeOut(BaseModel):
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
    nutrition: NutritionOut = NutritionOut()
    instructions: list[InstructionOut] = []
    ingredients: list[RecipeIngredientOut] = []


class RecipeSearchResult(BaseModel):
    external_id: str
    title: str
    cuisine: str | None = None
    difficulty: str | None = None
    total_time_mins: int | None = None
    dietary_flags: list[str] = []


class RecipeSearchResponse(BaseModel):
    results: list[RecipeSearchResult]
    total: int


class ImportUrlRequest(BaseModel):
    url: str
