from typing import Annotated

from fastapi import APIRouter, Depends

from glean.dependencies import get_llm_router, verify_cognito_token
from glean.llm import LLMRouter
from glean.meal_plan import service
from glean.meal_plan.schemas import MealPlanRequest, MealPlanResult
from glean.rate_limit import enforce_ai_rate_limit

router = APIRouter(prefix="/meal-plan", tags=["meal-plan"], dependencies=[Depends(verify_cognito_token)])


@router.post("", response_model=MealPlanResult, dependencies=[Depends(enforce_ai_rate_limit)])
def generate_meal_plan(
    request: MealPlanRequest,
    llm_router: Annotated[LLMRouter, Depends(get_llm_router)],
) -> MealPlanResult:
    return service.generate_meal_plan(request, llm_router=llm_router)
