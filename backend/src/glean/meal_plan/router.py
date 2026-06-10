from typing import Annotated

from fastapi import APIRouter, Depends

from glean.dependencies import get_llm_router, verify_cognito_token
from glean.llm import Feature, LLMRouter
from glean.meal_plan import service
from glean.meal_plan.schemas import MealPlanRequest, MealPlanResponse

router = APIRouter(prefix="/meal-plan", tags=["meal-plan"])


@router.post("", response_model=MealPlanResponse, dependencies=[Depends(verify_cognito_token)])
def generate_meal_plan(
    request: MealPlanRequest,
    llm_router: Annotated[LLMRouter, Depends(get_llm_router)],
) -> MealPlanResponse:
    model = llm_router.chat_model(Feature.MEAL_PLAN_GENERATION)
    return service.generate_meal_plan(request, model=model)
