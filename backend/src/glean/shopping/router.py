from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from glean.decisions import DecisionClient  # noqa: TC001 - FastAPI resolves this via Annotated/Depends at runtime.
from glean.dependencies import get_decision_client, get_llm_router, verify_cognito_token
from glean.llm import LLMRouter  # noqa: TC001 - FastAPI resolves this via Annotated/Depends at runtime.
from glean.rate_limit import enforce_ai_rate_limit
from glean.recipe_api.blob_store import BlobStore, get_shopping_parse_store
from glean.shopping import service
from glean.shopping.schemas import ShoppingParseRequest, ShoppingParseResponse

router = APIRouter(prefix="/shopping", tags=["shopping"], dependencies=[Depends(verify_cognito_token)])


@router.post("/parse-description", response_model=ShoppingParseResponse, dependencies=[Depends(enforce_ai_rate_limit)])
def parse_shopping_description(
    request: ShoppingParseRequest,
    llm_router: Annotated[LLMRouter, Depends(get_llm_router)],
    decision_client: Annotated[DecisionClient, Depends(get_decision_client)],
    cache: Annotated[BlobStore, Depends(get_shopping_parse_store)],
) -> ShoppingParseResponse:
    return service.parse_shopping_description(
        request, llm_router=llm_router, decision_client=decision_client, cache=cache
    )
