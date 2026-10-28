"""Run one session: claim it, run the graph, write the outcome; and cancel one.

`start` is the whole interface the worker and the inline runner share, and `cancel` the one the DELETE
route uses.

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
from glean.agent.graph import build_graph, result_of
from glean.observability import logger, metrics
from glean.sessions.models import ClaimResult, SessionError, SessionErrorCode, SessionStatus
from glean.sessions.store import SessionBusyError, SessionTooLargeError, lease_seconds_for

if TYPE_CHECKING:
    from glean.agent.deps import AgentDeps
    from glean.meal_plan.schemas import MealPlanResult
    from glean.sessions.models import AgentSession
    from glean.sessions.store import SessionStore

# CloudWatch metric names, all in the `Glean` namespace:
#   SessionsStarted, SessionsCompleted, SessionsFailed, SessionsDegraded, SessionsCancelled  Count
#   SessionWallTime                                                                         Milliseconds
# A degraded week is a fallback the household never sees (spec §6.5), so the count is how a regression
# in the model's answer shows up at all. A cancelled one is work the household called off.
STARTED = "SessionsStarted"
COMPLETED = "SessionsCompleted"
FAILED = "SessionsFailed"
DEGRADED = "SessionsDegraded"
CANCELLED = "SessionsCancelled"
WALL_TIME = "SessionWallTime"


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


def start(session: AgentSession, deps: AgentDeps) -> bool:
    """Run *session* to a terminal status. False when this delivery has nothing to do."""
    owner = uuid4().hex
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
        return False

    started = time.monotonic()
    metrics.add_metric(name=STARTED, unit=MetricUnit.Count, value=1)
    guard = RunGuard(deps.sessions, session, owner=owner, monotonic=deps.monotonic)
    try:
        result = _run(session, deps, guard=guard, resume=outcome is ClaimResult.RESUMED)
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
            _completed(deps, session, result, owner=owner)
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
    return True


def _run(session: AgentSession, deps: AgentDeps, *, guard: RunGuard, resume: bool):
    graph = build_graph(deps, guard=guard)
    # LangGraph's RunnableConfig is a plain mapping; naming its type would import LangChain into this
    # module, which only glean.llm may do.
    config: dict[str, Any] = {
        "configurable": {"thread_id": session.session_id},
        # One LangSmith trace per session: the metadata lands on the graph's run and its children.
        "metadata": {"session_id": session.session_id},
    }
    # What the previous attempt left behind decides how this one starts:
    #   * pending nodes -> continue them (no new input), so completed steps are not paid for twice;
    #   * a finished graph with a saved result -> publish that result, because the run was done and only
    #     the session write was lost (a crash there must not buy a second model call);
    #   * nothing usable -> start fresh.
    snapshot = graph.get_state(config)  # ty: ignore[invalid-argument-type]
    if resume and snapshot.next:
        logger.info("resuming a session from its checkpoint", extra={"session_id": session.session_id})
        return result_of(graph.invoke(None, config=config))  # ty: ignore[invalid-argument-type]
    if snapshot.values.get("result"):
        logger.info("publishing the plan a crashed attempt had already made", extra={"session_id": session.session_id})
        return result_of(snapshot.values)
    return result_of(
        graph.invoke(
            {"session_id": session.session_id, "request": session.request.model_dump(mode="json")},
            config=config,  # ty: ignore[invalid-argument-type]
        )
    )


def _completed(deps: AgentDeps, session: AgentSession, result: MealPlanResult, *, owner: str) -> None:
    if not deps.sessions.complete(session.user_sub, session.session_id, result, owner=owner):
        # A cancel that landed after the last step wins over the plan; a lost lease writes nothing.
        _refused_write(deps, session, what="plan")
        return
    metrics.add_metric(name=COMPLETED, unit=MetricUnit.Count, value=1)
    if result.degraded:
        # The fallback plan looks like any other to the household (spec §6.5), so this count is how a
        # regression in the model's answer shows up at all.
        metrics.add_metric(name=DEGRADED, unit=MetricUnit.Count, value=1)
    logger.info(
        "meal plan session completed",
        extra={
            "session_id": session.session_id,
            "suggestions": len(result.suggestions),
            "degraded": result.degraded,
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
