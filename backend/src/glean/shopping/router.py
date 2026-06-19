from __future__ import annotations

from fastapi import APIRouter, Depends

from glean.config import Settings, get_settings
from glean.dependencies import verify_cognito_token
from glean.llm import Feature, LLMRouter
from glean.shopping import service
from glean.shopping.schemas import ShoppingParseRequest, ShoppingParseResponse

router = APIRouter(prefix="/shopping", tags=["shopping"], dependencies=[Depends(verify_cognito_token)])


@router.post("/parse-description", response_model=ShoppingParseResponse)
def parse_shopping_description(
    request: ShoppingParseRequest,
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> ShoppingParseResponse:
    model = LLMRouter.from_settings(settings).chat_model(Feature.SHOPPING_LIST_DESCRIPTION)
    return service.parse_shopping_description(request, model=model)
