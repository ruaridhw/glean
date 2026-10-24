from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from glean.decisions import DecisionClient  # noqa: TC001 - FastAPI resolves this via Annotated/Depends at runtime.
from glean.dependencies import get_decision_client, get_llm_router, verify_cognito_token
from glean.llm import LLMRouter  # noqa: TC001 - FastAPI resolves this via Annotated/Depends at runtime.
from glean.profile import service
from glean.profile.schemas import InterviewRequest, InterviewResponse
from glean.rate_limit import enforce_ai_rate_limit

router = APIRouter(prefix="/profile", tags=["profile"], dependencies=[Depends(verify_cognito_token)])


@router.post("/interview", response_model=InterviewResponse, dependencies=[Depends(enforce_ai_rate_limit)])
def interview(
    request: InterviewRequest,
    llm_router: Annotated[LLMRouter, Depends(get_llm_router)],
    decision_client: Annotated[DecisionClient, Depends(get_decision_client)],
) -> InterviewResponse:
    return service.run_interview(request, llm_router=llm_router, decision_client=decision_client)
