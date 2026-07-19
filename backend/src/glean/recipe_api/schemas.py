from pydantic import BaseModel

from glean.nutrition import NutritionFields


class RecipeApiIngredient(BaseModel):
    ingredient_id: str
    name: str
    quantity: float | None = None
    unit: str | None = None
    preparation: str | None = None
    is_optional: bool = False
    substitutions: list[str] = []


class RecipeApiIngredientGroup(BaseModel):
    group_name: str | None = None  # noqa: F841,RUF100
    items: list[RecipeApiIngredient] = []


class RecipeApiNutrition(NutritionFields):
    """Nutrition fields as returned by recipe-api.com."""


class RecipeApiRecipeNutrition(BaseModel):
    per_serving: RecipeApiNutrition = RecipeApiNutrition()
    sources: list[str] | dict[str, object] | None = None  # noqa: F841,RUF100


class RecipeApiInstruction(BaseModel):
    step_number: int
    phase: str
    text: str
    tips: list[str] = []  # noqa: F841,RUF100
    structured: dict[str, object] = {}  # noqa: F841,RUF100


class RecipeApiMeta(BaseModel):
    total_time: str | None = None
    active_time: str | None = None
    passive_time: str | None = None  # noqa: F841,RUF100
    overnight_required: bool | None = None  # noqa: F841,RUF100
    yields: str | None = None  # noqa: F841,RUF100
    yield_count: int | None = None
    serving_size_g: float | None = None  # noqa: F841,RUF100


class RecipeApiDietary(BaseModel):
    flags: list[str] = []
    not_suitable_for: list[str] = []


class RecipeApiRecipe(BaseModel):
    id: str
    name: str
    description: str | None = None  # noqa: F841,RUF100
    category: str | None = None  # noqa: F841,RUF100
    cuisine: str | None = None
    difficulty: str | None = None
    tags: list[str] = []  # noqa: F841,RUF100
    flags: list[str] = []
    not_suitable_for: list[str] = []
    meta: RecipeApiMeta = RecipeApiMeta()
    dietary: RecipeApiDietary = RecipeApiDietary()
    ingredients: list[RecipeApiIngredientGroup] = []
    instructions: list[RecipeApiInstruction] = []
    nutrition: RecipeApiRecipeNutrition = RecipeApiRecipeNutrition()
    nutrition_summary: RecipeApiNutrition = RecipeApiNutrition()  # noqa: F841,RUF100
    source_url: str | None = None


class RecipeApiSearchResult(BaseModel):
    id: str
    name: str
    description: str | None = None  # noqa: F841,RUF100
    category: str | None = None  # noqa: F841,RUF100
    cuisine: str | None = None
    difficulty: str | None = None
    tags: list[str] = []  # noqa: F841,RUF100
    meta: RecipeApiMeta = RecipeApiMeta()
    dietary: RecipeApiDietary = RecipeApiDietary()
    nutrition_summary: RecipeApiNutrition = RecipeApiNutrition()  # noqa: F841,RUF100


class RecipeApiSearchMeta(BaseModel):
    total: int
    page: int  # noqa: F841,RUF100
    per_page: int  # noqa: F841,RUF100
    total_capped: bool  # noqa: F841,RUF100


class RecipeApiSearchResponse(BaseModel):
    data: list[RecipeApiSearchResult]
    meta: RecipeApiSearchMeta


class RecipeApiDetailResponse(BaseModel):
    data: RecipeApiRecipe
    usage: dict[str, int | float | str | bool | None] = {}  # noqa: F841,RUF100
