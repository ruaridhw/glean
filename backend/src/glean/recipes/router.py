from fastapi import APIRouter, Depends, HTTPException, Query

from glean.config import Settings, get_settings
from glean.dependencies import verify_cognito_token
from glean.llm import Feature, LLMRouter
from glean.recipes import service
from glean.recipes.schemas import ImportUrlRequest, RecipeOut, RecipeSearchResponse

router = APIRouter(prefix="/recipes", tags=["recipes"], dependencies=[Depends(verify_cognito_token)])


@router.get("/search", response_model=RecipeSearchResponse)
def search_recipes(
    q: str = Query(None),
    cuisine: str = Query(None),
    dietary: str = Query(None),
    page: int = Query(1),
    per_page: int = Query(20),
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> RecipeSearchResponse:
    return service.search_recipes(
        recipe_api_base_url=settings.recipe_api_base_url,
        recipe_api_key=settings.recipe_api_key,
        q=q,
        cuisine=cuisine,
        dietary=dietary,
        page=page,
        per_page=per_page,
    )


@router.get("/{recipe_id}", response_model=RecipeOut)
def get_recipe(
    recipe_id: str,
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> RecipeOut:
    return service.get_recipe(
        recipe_id,
        recipe_api_base_url=settings.recipe_api_base_url,
        recipe_api_key=settings.recipe_api_key,
    )


@router.post("/import-url", response_model=RecipeOut)
def import_recipe_from_url(
    request: ImportUrlRequest,
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> RecipeOut:
    try:
        model = LLMRouter.from_settings(settings).chat_model(Feature.RECIPE_IMPORT)
        return service.import_recipe_from_url(request, model=model)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
