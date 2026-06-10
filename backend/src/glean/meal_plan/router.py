from fastapi import APIRouter, Depends

from glean.config import Settings, get_settings
from glean.dependencies import verify_cognito_token
from glean.llm import create_chat_model
from glean.meal_plan import service
from glean.meal_plan.schemas import MealPlanRequest, MealPlanResponse

router = APIRouter(prefix="/meal-plan", tags=["meal-plan"])


@router.post("", response_model=MealPlanResponse, dependencies=[Depends(verify_cognito_token)])
def generate_meal_plan(
    request: MealPlanRequest,
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> MealPlanResponse:
    model = create_chat_model(settings.llm_model, api_key=settings.openrouter_api_key)
    return service.generate_meal_plan(request, model=model)
