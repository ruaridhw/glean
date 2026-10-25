"""Run one session: claim it, run the graph, write the outcome; and cancel one.

The interface is spec §6.2's three calls. `start` is what the worker and the inline runner call for every
queue delivery; `resume` is what the messages route calls with a household message (a swap now, an answer or a
skip with V11); `cancel` is what the DELETE route uses. `resume` stores the message on the item and re-enqueues
the session, so the work it asks for is just another delivery: what the claim won decides what runs, in `_run`'s
order -- a pending answer or skip (V11), then a pending swap, then a finished graph, then as before.

- **Resuming with a swap** (V10). A swap message re-queues a finished session, and its delivery claims it
  like any other: the same lease, the same owner token. The run invokes the session's own thread with the
  swap, so the graph keeps the candidates `prepare` sampled. A swap always ends `done`: one that found
  nothing, or broke, writes the proposal back as it was with the swap marked, because a failed swap must
  never cost the household the week on screen. A delivery that finds the swap finished drops; one that
  takes over a crashed swap resumes it from the checkpoint, or publishes the outcome a finished checkpoint
  holds.

- **Claiming.** The store hands out an owner token and a lease in the same conditional write that
  moves the session to `running`, or that takes over a run whose lease has lapsed. The lease is anchored
  to this invocation's own deadline, so it can never outlive its worker. A delivery for a finished
  session drops; a delivery that finds a live run raises `SessionBusyError` instead of dropping,
  because a successful return would acknowledge the message and throw away the only trigger that
  recovers the run if that live attempt then dies.
- **Recovering.** A delivery that takes over a session resumes from its LangGraph checkpoint (the same
  thread, invoked with no new input), so the crash costs the step it died in and nothing before it. If
  the checkpoint shows the graph had already finished, its saved result is published instead of run
  again — a crash between the last node and the session write must not buy a second model call. With
  no usable checkpoint it starts fresh. A resumed run whose session was cancelled in the meantime finds
  it terminal at the claim and stops before doing any work.
- **Ending.** Every run leaves `done` or `failed`: a typed refusal, a model failure, a spent budget or a
  bug each write a code. A run that lost its lease writes nothing, because another attempt owns it now.
- **Cancelling.** `cancel` writes `cancelled` and nothing else (spec §6.3). Cancel is a terminal status,
  so every owner-conditioned write refuses it: the guard's progress write is refused, which is how the
  run notices at its next step and stops (`SessionCancelled`, one read to tell a cancel from a lost
  lease); `complete` and `fail` cannot resurrect or overwrite it; and `claim` reports it as `FINISHED`,
  so a redelivery or a resumed run acknowledges it and does nothing.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from aws_lambda_powertools.metrics import MetricUnit
from pydantic import ValidationError

from glean.agent.control import LostOwnership, RunGuard
from glean.agent.errors import AgentError, SessionCancelled
from glean.agent.graph import MAX_TOOL_CALLS, build_graph, result_of, session_metrics_of, swap_outcome_of
from glean.meal_plan.feedback import screen_feedback, without_note
from glean.meal_plan.schemas import MealPlanResult
from glean.observability import logger, metrics
from glean.sessions.models import (
    AgentSession,
    ClaimResult,
    SessionError,
    SessionErrorCode,
    SessionStatus,
    SwapMessage,
    SwapState,
)
from glean.sessions.store import (
    MessageRefusal,
    MessageRefusedError,
    SessionBusyError,
    SessionTooLargeError,
    UnknownSessionError,
    lease_seconds_for,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from glean.agent.deps import AgentDeps
    from glean.sessions.models import HouseholdMessage, SessionRecord, SwapRecord
    from glean.sessions.store import SessionStore

# CloudWatch metric names, all in the `Glean` namespace:
#   SessionsStarted, SessionsCompleted, SessionsFailed, SessionsDegraded, SessionsCancelled  Count
#   SessionWallTime                                                                         Milliseconds
#   SessionToolCalls, SessionInvalidActions (per completed session)                         Count
#   SessionDrift (chosen week's shortfall from the scorer's best, spec §6.6)                Percent
# A degraded week is a fallback the household never sees (spec §6.5), so the count is how a regression
# in the model's answer shows up at all. A cancelled one is work the household called off.
STARTED = "SessionsStarted"
COMPLETED = "SessionsCompleted"
FAILED = "SessionsFailed"
DEGRADED = "SessionsDegraded"
CANCELLED = "SessionsCancelled"
WALL_TIME = "SessionWallTime"
TOOL_CALLS = "SessionToolCalls"
INVALID_ACTIONS = "SessionInvalidActions"
DRIFT = "SessionDrift"
#   SwapsStarted, SwapsCompleted, SwapsDegraded, SwapsFailed                                Count
# A degraded swap is the scorer's replacement; a failed one left the proposal as it was.
SWAPS_STARTED = "SwapsStarted"
SWAPS_COMPLETED = "SwapsCompleted"
SWAPS_DEGRADED = "SwapsDegraded"
SWAPS_FAILED = "SwapsFailed"


def cancel(session_id: str, *, user_sub: str, sessions: SessionStore) -> bool:
    """Cancel one session. Says whether this call moved it, which no caller needs to act on.

    One store write and nothing else: the record becomes `cancelled`, which is terminal, so the run in
    flight finds its next owner-conditioned write refused and stops, `complete`/`fail` cannot overwrite
    it, and `claim` reports `FINISHED` so a redelivery acknowledges it and does nothing. Kept here beside
    that guard so cancel has one definition and no caller can perform half of it.
    """
    moved = sessions.cancel(user_sub, session_id)
    logger.info(
        "session cancelled" if moved else "session was already finished; leaving it alone",
        extra={"session_id": session_id},
    )
    return moved


class MessageNotSent(RuntimeError):
    """The message was stored but the queue would not take it. The session was failed, so its proposal stays and
    the next message is accepted."""


def resume(
    session_id: str,
    message: HouseholdMessage,
    *,
    user_sub: str,
    sessions: SessionStore,
    dispatch: Callable[[AgentSession], None],
    note_dropped: bool = False,
) -> int | None:
    """Resume *session_id* with a household message: store it on the item and re-enqueue the session.

    *message* carries only what the route's screen passed; *note_dropped* says the household wrote a note the
    screen dropped. Returns the swap's id for a swap. Raises `UnknownSessionError` for no such session,
    `MessageRefusedError` when the session cannot take this message now, and `MessageNotSent` when the queue
    would not take it. The worker picks the message up from the item (`start`), never from the queue body.
    """
    match message:
        case SwapMessage():
            swap_id: int | None = sessions.enqueue_swap(
                user_sub, session_id, message, note_dropped=note_dropped
            ).swap_id
        case _:
            # V11 stores an answer or a skip as the pending answer of a run parked on its question, here. No run
            # parks before then, so there is never one to resume.
            raise MessageRefusedError(MessageRefusal.NO_QUESTION)
    record = sessions.get(user_sub, session_id)
    if record is None:
        raise UnknownSessionError(session_id)
    try:
        dispatch(AgentSession(session_id=session_id, user_sub=user_sub, request=record.request))
    except Exception as error:
        # Stored, but nothing will run it. Fail the session as create does: the proposal stays on the item, the
        # swap reads as failed, and the next message is accepted.
        sessions.fail_if_abandoned(user_sub, session_id, SessionError(code=SessionErrorCode.WORKER_FAILED))
        logger.exception("the queue would not take a session message", extra={"session_id": session_id})
        raise MessageNotSent(session_id) from error
    logger.info("session resumed with a household message", extra={"session_id": session_id, "type": message.type})
    return swap_id


def start(session: AgentSession, deps: AgentDeps) -> bool:
    """Handle one delivery for *session*: its pending swap, or its run, to `done` or `failed`.

    False when this delivery has nothing to do. Decided from the item the claim won, not from the message: a
    redelivered first-run message that arrives after a swap was queued runs the swap (the swap's own message
    then finds it finished and drops), so every copy of every message leads to the same work.
    """
    owner = uuid4().hex
    claimed = _claim(session, deps, owner=owner)
    if claimed is None:
        return False
    record, resumed = claimed
    swap = record.pending_swap
    if swap is not None and record.result is not None:
        _swap(session, record, swap, deps, owner=owner, resumed=resumed)
    else:
        _plan(session, record, deps, owner=owner, resumed=resumed)
    return True


def _claim(session: AgentSession, deps: AgentDeps, *, owner: str) -> tuple[SessionRecord, bool] | None:
    """Claim the session and read what the claim won; None when it has finished and the delivery drops.

    Raises `SessionBusyError` when a live attempt owns it. The flag says whether this claim took over an
    attempt that died.
    """
    outcome = deps.sessions.claim(
        session.user_sub,
        session.session_id,
        owner=owner,
        now=deps.clock(),
        lease_seconds=lease_seconds_for(deps.remaining_seconds()),
    )
    if outcome is ClaimResult.OWNED_ELSEWHERE:
        # Nonterminal work another attempt owns. Fail the delivery rather than acknowledging it: by the
        # time the message returns, that attempt has either finished (a later delivery reads FINISHED and
        # drops) or died (its lease has lapsed, and this one takes over).
        raise SessionBusyError(session.session_id)
    if outcome is ClaimResult.FINISHED:
        logger.info("session has already finished; dropping this delivery", extra={"session_id": session.session_id})
        return None
    # The claim is the authority: one read of what it won, so the message and the proposal are the item's own.
    record = deps.sessions.get(session.user_sub, session.session_id)
    if record is None:
        return None
    return record, outcome is ClaimResult.RESUMED


def _plan(session: AgentSession, record: SessionRecord, deps: AgentDeps, *, owner: str, resumed: bool) -> None:
    """Run the week to `done` or `failed`."""
    started = time.monotonic()
    metrics.add_metric(name=STARTED, unit=MetricUnit.Count, value=1)
    guard = RunGuard(deps.sessions, session, owner=owner, monotonic=deps.monotonic, resumed=resumed)
    try:
        state = _run(session, record, deps, guard=guard, resume=resumed)
        result = result_of(state)
    except SessionCancelled:
        _cancelled(deps, session, "the run stopped at its next step")
    except LostOwnership:
        # The lease lapsed and another attempt has taken the session over. It owns the outcome now.
        logger.warning("stopped after losing the session lease", extra={"session_id": session.session_id})
    except AgentError as error:
        _failed(deps, session, error.error, owner=owner)
    except ValidationError:
        # The stored request no longer matches today's schema: an app build or a schema change, not a
        # model failure. The app offers the diagnostics export for this one.
        logger.exception("stored session request did not validate", extra={"session_id": session.session_id})
        _failed(deps, session, SessionError(code=SessionErrorCode.INVALID_REQUEST), owner=owner)
    except Exception:  # a run must end in a terminal status, whatever went wrong
        logger.exception("meal plan session failed unexpectedly", extra={"session_id": session.session_id})
        _failed(deps, session, SessionError(code=SessionErrorCode.WORKER_FAILED), owner=owner)
    else:
        try:
            _completed(
                deps,
                session,
                result,
                owner=owner,
                session_metrics=session_metrics_of(state),
                wall_ms=int((time.monotonic() - started) * 1000),
            )
        except SessionTooLargeError:
            # The plan is real but the item cannot hold it, and there is nowhere else to put it: fail the
            # session with a code the app can act on instead of raising into SQS.
            logger.error(
                "the plan would not fit the session item; failing the session",
                extra={"session_id": session.session_id},
            )
            _failed(deps, session, SessionError(code=SessionErrorCode.MODEL_ERROR), owner=owner)
    finally:
        # Every attempt that started reports its wall time, so provider and worker failures are in the
        # latency distribution too, not only the runs that worked.
        metrics.add_metric(name=WALL_TIME, unit=MetricUnit.Milliseconds, value=int((time.monotonic() - started) * 1000))


def _swap(
    session: AgentSession, record: SessionRecord, swap: SwapRecord, deps: AgentDeps, *, owner: str, resumed: bool
) -> None:
    """Replace one slot of the proposal, the rest locked (spec §6.2). Ends `done` whatever the swap made of it."""
    started = time.monotonic()
    metrics.add_metric(name=SWAPS_STARTED, unit=MetricUnit.Count, value=1)
    guard = RunGuard(deps.sessions, session, owner=owner, monotonic=deps.monotonic, resumed=resumed)
    base = record.result or MealPlanResult(suggestions=[])
    try:
        finished = swap_outcome_of(_run(session, record, deps, guard=guard, resume=resumed), swap.swap_id)
        if finished is None:
            raise RuntimeError("the swap graph ended without an outcome")
    except SessionCancelled:
        _cancelled(deps, session, "the swap stopped at its next step")
    except LostOwnership:
        logger.warning("stopped a swap after losing the session lease", extra={"session_id": session.session_id})
    except Exception:  # a broken swap must leave the proposal as it was, never a failed session
        logger.exception("meal plan swap failed unexpectedly", extra={"session_id": session.session_id})
        _finish_swap(deps, session, base, swap.model_copy(update={"state": SwapState.FAILED}), owner=owner)
    else:
        swapped = swap.model_copy(update={"state": SwapState(finished["state"])})
        result = MealPlanResult.model_validate(finished["result"])
        if _finish_swap(deps, session, result, swapped, owner=owner, base=base) and finished.get("degraded"):
            metrics.add_metric(name=SWAPS_DEGRADED, unit=MetricUnit.Count, value=1)
    finally:
        metrics.add_metric(name=WALL_TIME, unit=MetricUnit.Milliseconds, value=int((time.monotonic() - started) * 1000))


def swap_input(record: SessionRecord, swap: SwapRecord) -> dict[str, Any]:
    """What the graph needs for *swap*: the slot, the meals that stay, and every id the replacement may not be.

    The week is the one the app showed when it asked (`swap.week`), so the swap locks and scores against what is
    on screen, after any local swap or Undo. Unavailable is that week, the server's proposal as it stands (so a
    meal the app swapped back out cannot return), every card's alternative (the app may show one in place of its
    meal), every meal swapped out before, and the meals already in the plan (ADR 0020: never replaced, never
    duplicated).
    """
    result = record.result or MealPlanResult(suggestions=[])
    meals = result.suggestions
    week = swap.week or [meal.external_id or "" for meal in meals]
    unavailable = set(week) | {meal.external_id for meal in meals if meal.external_id}
    unavailable |= {meal.alternative.external_id for meal in meals if meal.alternative and meal.alternative.external_id}
    unavailable |= {entry.slot for entry in record.swaps}
    unavailable |= set(record.request.exclude_external_ids)
    for planned in result.planned_alternatives:
        unavailable |= {planned.external_id, planned.alternative.external_id or planned.external_id}
    return {
        "swap_id": swap.swap_id,
        "slot": swap.slot,
        "position": swap.position,
        "note": swap.note,
        "week": week,
        "locked": [meal for index, meal in enumerate(week) if index != swap.position and meal],
        "unavailable_ids": sorted(unavailable - {""}),
        "base": result.model_dump(mode="json"),
    }


def _finish_swap(
    deps: AgentDeps,
    session: AgentSession,
    result: MealPlanResult,
    swap: SwapRecord,
    *,
    owner: str,
    base: MealPlanResult | None = None,
) -> bool:
    """Write the swap's outcome. A replacement too big for the item is written as a failed swap instead."""
    try:
        written = deps.sessions.finish_swap(session.user_sub, session.session_id, result, swap, owner=owner)
    except SessionTooLargeError:
        if base is None:
            raise
        logger.error("the swapped proposal would not fit the session item", extra={"session_id": session.session_id})
        return _finish_swap(deps, session, base, swap.model_copy(update={"state": SwapState.FAILED}), owner=owner)
    if not written:
        _refused_write(deps, session, what="swap")
        return False
    metrics.add_metric(
        name=SWAPS_FAILED if swap.state is SwapState.FAILED else SWAPS_COMPLETED, unit=MetricUnit.Count, value=1
    )
    logger.info(
        "meal plan swap finished",
        extra={"session_id": session.session_id, "swap_id": swap.swap_id, "state": swap.state.value},
    )
    return True


def _run(
    session: AgentSession, record: SessionRecord, deps: AgentDeps, *, guard: RunGuard, resume: bool
) -> Mapping[str, Any]:
    """The graph's final state for this delivery: a week `finalise` wrote, or a swap `swap_finalise` wrote."""
    graph = build_graph(deps, guard=guard)
    # LangGraph's RunnableConfig is a plain mapping; naming its type would import LangChain into this
    # module, which only glean.llm may do.
    config: dict[str, Any] = {
        "configurable": {"thread_id": session.session_id},
        # One LangSmith trace per session: the metadata lands on the graph's run and its children (the model
        # calls included). The per-session counts are `finalise`'s output, `session_metrics`, in the same trace.
        "metadata": {"session_id": session.session_id, "agent_graph": "v10", "max_tool_calls": MAX_TOOL_CALLS},
    }
    snapshot = graph.get_state(config)  # ty: ignore[invalid-argument-type]
    # What the item holds, then what the previous attempt left behind, decides how this one starts:
    #   1. a pending answer or skip -> resume the run parked on its question (V11, `Command(resume=...)`);
    #   2. a pending swap -> continue it, republish it, or run it from its input (`_swap_state`);
    #   3. a finished graph with a saved result -> publish that result, because the run was done and only the
    #      session write was lost (a crash there must not buy a second model call);
    #   4. otherwise as before: pending nodes -> continue them (no new input), so completed steps are not paid
    #      for twice; nothing usable -> start fresh.
    swap = record.pending_swap
    if swap is not None:
        config["metadata"]["swap_id"] = swap.swap_id
        return _swap_state(graph, config, snapshot, session, record, swap, resume=resume)
    if snapshot.values.get("result") and not snapshot.next:
        logger.info("publishing the plan a crashed attempt had already made", extra={"session_id": session.session_id})
        return snapshot.values
    if resume and snapshot.next:
        logger.info("resuming a session from its checkpoint", extra={"session_id": session.session_id})
        return graph.invoke(None, config=config)  # ty: ignore[invalid-argument-type]
    # The week's note is screened here, before the graph exists for it: the graph's input, its state, its
    # checkpoints and its traces carry the screen's outcome and the request without the raw note.
    feedback = screen_feedback(record.request.human_feedback, decision_client=deps.decision_client)
    return graph.invoke(
        {
            "session_id": session.session_id,
            "request": without_note(record.request).model_dump(mode="json"),
            "feedback": feedback.model_dump(mode="json"),
        },
        config=config,  # ty: ignore[invalid-argument-type]
    )


def _swap_state(
    graph: Any,
    config: dict[str, Any],
    snapshot: Any,
    session: AgentSession,
    record: SessionRecord,
    swap: SwapRecord,
    *,
    resume: bool,
) -> Mapping[str, Any]:
    """The graph state after *swap*: republished if a crashed attempt finished it, continued if one died in it,
    otherwise run from its input on the session's own thread."""
    if swap_outcome_of(snapshot.values, swap.swap_id) is not None:
        logger.info("publishing the swap a crashed attempt had already made", extra={"session_id": session.session_id})
        return snapshot.values
    working = snapshot.values.get("swap") or {}
    if resume and snapshot.next and working.get("swap_id") == swap.swap_id:
        logger.info("resuming a swap from its checkpoint", extra={"session_id": session.session_id})
        return graph.invoke(None, config=config)
    return graph.invoke(
        {
            "session_id": session.session_id,
            # Never the week's raw note: only the screened outcome `_run` stored for the first run reaches the graph.
            "request": without_note(record.request).model_dump(mode="json"),
            "swap": swap_input(record, swap),
        },
        config=config,
    )


def _completed(
    deps: AgentDeps,
    session: AgentSession,
    result: MealPlanResult,
    *,
    owner: str,
    session_metrics: Mapping[str, Any],
    wall_ms: int,
) -> None:
    if not deps.sessions.complete(session.user_sub, session.session_id, result, owner=owner):
        # A cancel that landed after the last step wins over the plan; a lost lease writes nothing.
        _refused_write(deps, session, what="plan")
        return
    metrics.add_metric(name=COMPLETED, unit=MetricUnit.Count, value=1)
    if result.degraded:
        # The fallback plan looks like any other to the household (spec §6.5), so this count is how a
        # regression in the model's answer shows up at all.
        metrics.add_metric(name=DEGRADED, unit=MetricUnit.Count, value=1)
    # Spec §6.6's session metrics, for the median the evals report: how hard the agent worked, and how far
    # its week fell from the scorer's best. A checkpoint from before V7 has none to report.
    if "tool_calls" in session_metrics:
        metrics.add_metric(name=TOOL_CALLS, unit=MetricUnit.Count, value=session_metrics["tool_calls"])
        metrics.add_metric(name=INVALID_ACTIONS, unit=MetricUnit.Count, value=session_metrics["invalid_actions"])
    # Drift measures the agent's own choice, so a degraded run -- the scorer's week, or the agent's kept at a
    # refused call -- reports none: counted as 0 it would pull the median towards a choice nobody made.
    if session_metrics.get("drift_fraction") is not None and not result.degraded:
        metrics.add_metric(name=DRIFT, unit=MetricUnit.Percent, value=session_metrics["drift_fraction"] * 100)
    logger.info(
        "meal plan session completed",
        extra={
            "session_id": session.session_id,
            "suggestions": len(result.suggestions),
            "degraded": result.degraded,
            "wall_ms": wall_ms,
            **session_metrics,
        },
    )


def _failed(deps: AgentDeps, session: AgentSession, error: SessionError, *, owner: str) -> None:
    if not deps.sessions.fail(session.user_sub, session.session_id, error, owner=owner):
        logger.warning(
            "session lease moved on before the failure was written", extra={"session_id": session.session_id}
        )
        return
    metrics.add_metric(name=FAILED, unit=MetricUnit.Count, value=1)
    logger.warning("meal plan session failed", extra={"session_id": session.session_id, "error_code": error.code.value})


def _cancelled(deps: AgentDeps, session: AgentSession, reason: str) -> None:
    """The household cancelled and the record already says so: nothing left to write."""
    metrics.add_metric(name=CANCELLED, unit=MetricUnit.Count, value=1)
    logger.info("meal plan session cancelled", extra={"session_id": session.session_id, "reason": reason})


def _refused_write(deps: AgentDeps, session: AgentSession, *, what: str) -> None:
    """A terminal write was refused. Name why, with the one read this read is worth.

    Only the refused path reads, so a run that finishes normally makes no extra read at all. The read
    tells a cancel (terminal, the household's doing) from a lost lease (another attempt owns the run).
    """
    record = deps.sessions.get(session.user_sub, session.session_id)
    if record is not None and record.status is SessionStatus.CANCELLED:
        _cancelled(deps, session, f"cancelled before the {what} was written")
        return
    logger.warning(f"session lease moved on before the {what} was written", extra={"session_id": session.session_id})
