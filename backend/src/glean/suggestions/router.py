from fastapi import APIRouter, Depends

from glean.config import Settings, get_settings
from glean.dependencies import verify_cognito_token
from glean.llm import create_chat_model
from glean.suggestions import service
from glean.suggestions.schemas import SuggestionRequest, SuggestionResponse

router = APIRouter(prefix="/suggestions", tags=["suggestions"])


@router.post("", response_model=SuggestionResponse, dependencies=[Depends(verify_cognito_token)])
def get_suggestions(
    request: SuggestionRequest,
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> SuggestionResponse:
    model = create_chat_model(settings.llm_model, api_key=settings.openrouter_api_key)
    return service.get_suggestions(request, model=model)
