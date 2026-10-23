from collections.abc import Callable
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status

from glean.agent import cancel
from glean.agent.dependencies import get_session_dispatcher, get_session_store
from glean.dependencies import get_llm_router, verify_cognito_token
from glean.llm import LLMRouter
from glean.meal_plan import service
from glean.meal_plan.schemas import MealPlanRequest, MealPlanResult
from glean.rate_limit import enforce_ai_rate_limit
from glean.sessions.models import (
    AgentSession,
    SessionCreated,
    SessionError,
    SessionErrorCode,
    SessionRequest,
    SessionView,
)
from glean.sessions.store import SessionStore, SessionTooLargeError, utcnow

router = APIRouter(prefix="/meal-plan", tags=["meal-plan"], dependencies=[Depends(verify_cognito_token)])

# Session ids are generated here as UUID hex, and only ever used as a DynamoDB sort key.
_SESSION_ID = Path(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


@router.post("", response_model=MealPlanResult, dependencies=[Depends(enforce_ai_rate_limit)])
def generate_meal_plan(
    request: MealPlanRequest,
    llm_router: Annotated[LLMRouter, Depends(get_llm_router)],
) -> MealPlanResult:
    """The synchronous plan. Agent sessions have replaced it in the app and it goes in a follow-up PR."""
    return service.generate_meal_plan(request, llm_router=llm_router)


@router.post(
    "/sessions",
    response_model=SessionCreated,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(enforce_ai_rate_limit)],
)
def create_session(
    request: SessionRequest,
    user_sub: Annotated[str, Depends(verify_cognito_token)],
    sessions: Annotated[SessionStore, Depends(get_session_store)],
    dispatch: Annotated[Callable[[AgentSession], None], Depends(get_session_dispatcher)],
) -> SessionCreated:
    """Write the session, send it to the worker and return at once. One paid call."""
    session = AgentSession(session_id=uuid4().hex, user_sub=user_sub, request=request)
    try:
        sessions.create(session, now=utcnow())
    except SessionTooLargeError as error:
        # The request validates but its session item would not fit DynamoDB's 400 KB with room left for
        # the progress lines and the plan. 422, like any other request the backend cannot take.
        raise HTTPException(
            status_code=422,
            detail="This request is too large to plan from. Trim the recipe or cook history and try again.",
        ) from error
    try:
        dispatch(session)
    except Exception as error:
        # The session exists but nothing will run it. Fail it here rather than leave the app polling
        # a session that can never move, and let the app offer its retry.
        sessions.fail_if_abandoned(user_sub, session.session_id, SessionError(code=SessionErrorCode.WORKER_FAILED))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Couldn't start planning your week. Try again.",
        ) from error
    return SessionCreated(session_id=session.session_id)


@router.get("/sessions/{session_id}", response_model=SessionView)
def get_session(
    session_id: Annotated[str, _SESSION_ID],
    user_sub: Annotated[str, Depends(verify_cognito_token)],
    sessions: Annotated[SessionStore, Depends(get_session_store)],
    after: Annotated[int, Query(ge=0, description="The `next_cursor` from the previous poll; 0 to start.")] = 0,
) -> SessionView:
    """Poll one session. Free and never rate limited: the app calls it every second while one runs.

    Scoped to the caller: another user's session is not found rather than forbidden, because the key
    is (their sub, the session id) and this caller's sub does not key it.
    """
    record = sessions.get(user_sub, session_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such session")
    return SessionView.from_record(record, after=after)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def cancel_session(
    session_id: Annotated[str, _SESSION_ID],
    user_sub: Annotated[str, Depends(verify_cognito_token)],
    sessions: Annotated[SessionStore, Depends(get_session_store)],
) -> Response:
    """Cancel one session: the household closed the proposal screen and wants nothing more from it.

    Free and never rate limited, because the app shows Cancel the moment the working state opens. Scoped
    to the caller, idempotent, and a session that already finished is left exactly as it was -- so the
    answer is 204 whether this call moved it or not. The worker writes nothing more (spec §6.3).
    """
    if sessions.get(user_sub, session_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such session")
    cancel(session_id, user_sub=user_sub, sessions=sessions)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
