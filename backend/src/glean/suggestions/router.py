from fastapi import APIRouter, Depends

from glean.dependencies import verify_cognito_token
from glean.suggestions import service
from glean.suggestions.schemas import SuggestionRequest, SuggestionResponse

router = APIRouter(prefix="/suggestions", tags=["suggestions"])


@router.post("", response_model=SuggestionResponse, dependencies=[Depends(verify_cognito_token)])
def get_suggestions(request: SuggestionRequest) -> SuggestionResponse:
    return service.get_suggestions(request)
