from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from glean.dependencies import get_llm_router, verify_cognito_token
from glean.llm import LLMRouter  # noqa: TC001 - FastAPI resolves this via Annotated/Depends at runtime.
from glean.shopping import service
from glean.shopping.schemas import ShoppingParseRequest, ShoppingParseResponse

router = APIRouter(prefix="/shopping", tags=["shopping"], dependencies=[Depends(verify_cognito_token)])


@router.post("/parse-description", response_model=ShoppingParseResponse)
def parse_shopping_description(
    request: ShoppingParseRequest,
    llm_router: Annotated[LLMRouter, Depends(get_llm_router)],
) -> ShoppingParseResponse:
    return service.parse_shopping_description(request, llm_router=llm_router)
