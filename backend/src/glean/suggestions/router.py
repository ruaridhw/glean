from typing import Annotated

from fastapi import APIRouter, Depends

from glean.dependencies import get_llm_router, verify_cognito_token
from glean.llm import Feature, LLMRouter
from glean.suggestions import service
from glean.suggestions.schemas import SuggestionRequest, SuggestionResponse

router = APIRouter(prefix="/suggestions", tags=["suggestions"])


@router.post("", response_model=SuggestionResponse, dependencies=[Depends(verify_cognito_token)])
def get_suggestions(
    request: SuggestionRequest,
    llm_router: Annotated[LLMRouter, Depends(get_llm_router)],
) -> SuggestionResponse:
    model = llm_router.chat_model(Feature.MEAL_PLAN_GENERATION)
    return service.get_suggestions(request, model=model)
