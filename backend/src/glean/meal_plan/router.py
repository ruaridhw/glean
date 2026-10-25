from collections.abc import Callable
from typing import Annotated, NoReturn
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status

from glean.agent import MessageNotSent, cancel, resume
from glean.agent.dependencies import get_session_dispatcher, get_session_store
from glean.decisions import DecisionClient
from glean.dependencies import get_decision_client, get_llm_router, verify_cognito_token
from glean.llm import LLMRouter
from glean.meal_plan import service
from glean.meal_plan.schemas import MealPlanRequest, MealPlanResult
from glean.rate_limit import enforce_ai_rate_limit
from glean.screening import screen
from glean.sessions.models import (
    AgentSession,
    AnswerMessage,
    HouseholdMessage,
    MessageAccepted,
    SessionCreated,
    SessionError,
    SessionErrorCode,
    SessionRecord,
    SessionRequest,
    SessionStatus,
    SessionView,
    SkipMessage,
    SwapMessage,
)
from glean.sessions.store import (
    MessageRefusal,
    MessageRefusedError,
    SessionStore,
    SessionTooLargeError,
    UnknownSessionError,
    swap_refusal,
    utcnow,
)

router = APIRouter(prefix="/meal-plan", tags=["meal-plan"], dependencies=[Depends(verify_cognito_token)])

# Session ids are generated here as UUID hex, and only ever used as a DynamoDB sort key.
_SESSION_ID = Path(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


@router.post("", response_model=MealPlanResult, dependencies=[Depends(enforce_ai_rate_limit)])
def generate_meal_plan(
    request: MealPlanRequest,
    llm_router: Annotated[LLMRouter, Depends(get_llm_router)],
    decision_client: Annotated[DecisionClient, Depends(get_decision_client)],
) -> MealPlanResult:
    """The synchronous plan. Agent sessions have replaced it in the app and it goes in a follow-up PR."""
    return service.generate_meal_plan(request, llm_router=llm_router, decision_client=decision_client)


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


# What each refusal tells the app. 409 is "not now" (the app keeps the card as it was), 422 "never for this slot".
_MESSAGE_REFUSALS: dict[MessageRefusal, tuple[int, str]] = {
    MessageRefusal.BUSY: (status.HTTP_409_CONFLICT, "Another swap is still running. Try again when it finishes."),
    MessageRefusal.NO_PROPOSAL: (status.HTTP_409_CONFLICT, "This session has no proposal to change."),
    MessageRefusal.UNKNOWN_SLOT: (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "That meal isn't one this proposal suggested. Meals already in your plan are never replaced.",
    ),
    MessageRefusal.NO_QUESTION: (status.HTTP_409_CONFLICT, "There is no question waiting for an answer."),
}


@router.post(
    "/sessions/{session_id}/messages",
    response_model=MessageAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(enforce_ai_rate_limit)],
)
def post_session_message(
    session_id: Annotated[str, _SESSION_ID],
    message: HouseholdMessage,
    user_sub: Annotated[str, Depends(verify_cognito_token)],
    sessions: Annotated[SessionStore, Depends(get_session_store)],
    dispatch: Annotated[Callable[[AgentSession], None], Depends(get_session_dispatcher)],
    decisions: Annotated[DecisionClient, Depends(get_decision_client)],
) -> MessageAccepted:
    """A household message for one session: a swap (V10), or an answer or a skip (V11). 202. One paid call.

    Branches on the message's type before any status check: a swap needs a finished proposal and no swap
    running; an answer or a skip needs the run parked on its question. A note is screened here, before anything
    stores it, and only what the screen passed is kept. Scoped to the caller: another user's session is not found.
    """
    record = sessions.get(user_sub, session_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such session")
    note_dropped = False
    match message:
        case SwapMessage():
            message, note_dropped = _screened_swap(record, message, decisions=decisions)
        case AnswerMessage() | SkipMessage():
            # V11 screens the answer's note here, the same way, once a run can be parked on its question.
            if record.status is not SessionStatus.WAITING_FOR_USER:
                _refuse(MessageRefusal.NO_QUESTION)
    try:
        swap_id = resume(
            session_id, message, user_sub=user_sub, sessions=sessions, dispatch=dispatch, note_dropped=note_dropped
        )
    except UnknownSessionError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such session") from error
    except MessageRefusedError as error:
        # Lost a race between the read above and the conditional write, or a message type nothing can take yet.
        _refuse(error.reason, cause=error)
    except MessageNotSent as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Couldn't send that right now. Try again."
        ) from error
    return MessageAccepted(session_id=session_id, swap_id=swap_id, note_dropped=note_dropped)


def _screened_swap(
    record: SessionRecord, message: SwapMessage, *, decisions: DecisionClient
) -> tuple[SwapMessage, bool]:
    """Refuse what cannot be swapped before paying for the screen, then screen the note.

    Returns the message carrying only what the screen passed, and whether it dropped a note the household
    wrote. The note as typed goes no further than this function.
    """
    refusal = swap_refusal(record) or (
        MessageRefusal.UNKNOWN_SLOT if record.swap_position(message.slot) is None else None
    )
    if refusal is not None:
        _refuse(refusal)
    written = (message.note or "").strip()
    screened = screen(written, decision_client=decisions)
    return message.model_copy(update={"note": screened.text}), bool(written) and not screened.passed


def _refuse(refusal: MessageRefusal, *, cause: Exception | None = None) -> NoReturn:
    code, detail = _MESSAGE_REFUSALS[refusal]
    raise HTTPException(status_code=code, detail=detail) from cause


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
