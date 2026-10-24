from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from glean.config import Settings  # noqa: TC001 - FastAPI resolves this via Annotated/Depends at runtime.
from glean.decisions import DecisionClient  # noqa: TC001 - FastAPI resolves this via Annotated/Depends at runtime.
from glean.dependencies import get_decision_client, get_llm_router, get_settings, verify_cognito_token
from glean.llm import LLMRouter  # noqa: TC001 - FastAPI resolves this via Annotated/Depends at runtime.
from glean.profile import service
from glean.profile.schemas import InterviewRequest, InterviewResponse
from glean.rate_limit import charge_ai_request

router = APIRouter(prefix="/profile", tags=["profile"], dependencies=[Depends(verify_cognito_token)])


def enforce_interview_rate_limit(
    request: InterviewRequest,
    user_sub: Annotated[str, Depends(verify_cognito_token)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Charge the interview's paid turns only: the first turn makes no paid call at all."""
    if request.transcript:
        charge_ai_request(user_sub, settings)


@router.post("/interview", response_model=InterviewResponse, dependencies=[Depends(enforce_interview_rate_limit)])
def interview(
    request: InterviewRequest,
    llm_router: Annotated[LLMRouter, Depends(get_llm_router)],
    decision_client: Annotated[DecisionClient, Depends(get_decision_client)],
) -> InterviewResponse:
    try:
        return service.run_interview(request, llm_router=llm_router, decision_client=decision_client)
    except service.InterviewUnavailableError as exc:
        # A model reply that didn't fit is not a server fault the household can do anything about: the
        # turn can simply be retried.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The interview could not continue. Please try the turn again.",
        ) from exc
