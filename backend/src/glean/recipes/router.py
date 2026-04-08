from fastapi import APIRouter, Depends, HTTPException, Query

from glean.dependencies import verify_cognito_token
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
) -> RecipeSearchResponse:
    return service.search_recipes(q=q, cuisine=cuisine, dietary=dietary, page=page, per_page=per_page)


@router.get("/{recipe_id}", response_model=RecipeOut)
def get_recipe(recipe_id: str) -> RecipeOut:
    return service.get_recipe(recipe_id)


@router.post("/import-url", response_model=RecipeOut)
def import_recipe_from_url(request: ImportUrlRequest) -> RecipeOut:
    try:
        return service.import_recipe_from_url(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
