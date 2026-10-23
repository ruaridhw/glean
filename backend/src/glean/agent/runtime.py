"""Run one session: claim it, run the graph, write the outcome.

`start` is the whole interface the worker and the inline runner share.

- **Claiming.** The store hands out an owner token and a lease in the same conditional write that
  moves the session to `running`, or that takes over a run whose lease has lapsed. A duplicate delivery
  of a live run is told so and drops; a delivery for a finished session drops too.
- **Recovering.** A delivery that takes over a session resumes from its LangGraph checkpoint (the same
  thread, invoked with no new input), so the crash costs the step it died in and nothing before it.
  With no checkpoint it starts fresh.
- **Ending.** Every run leaves `done` or `failed`: a typed refusal, a model failure, a spent budget or a
  bug each write a code. A run that lost its lease writes nothing, because another attempt owns it now.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from aws_lambda_powertools.metrics import MetricUnit
from pydantic import ValidationError

from glean.agent.control import LostOwnership, RunGuard
from glean.agent.errors import AgentError
from glean.agent.graph import build_graph, result_of
from glean.observability import logger, metrics
from glean.sessions.models import ClaimResult, SessionError, SessionErrorCode

if TYPE_CHECKING:
    from glean.agent.deps import AgentDeps
    from glean.meal_plan.schemas import MealPlanResult
    from glean.sessions.models import AgentSession

# CloudWatch metric names, all in the `Glean` namespace:
#   SessionsStarted, SessionsCompleted, SessionsFailed  Count
#   SessionWallTime                                     Milliseconds
# `SessionsDegraded` is reserved for V7's fallback (the scorer's best plan with template reasons);
# V1 has no degraded path to count.
STARTED = "SessionsStarted"
COMPLETED = "SessionsCompleted"
FAILED = "SessionsFailed"
WALL_TIME = "SessionWallTime"


def start(session: AgentSession, deps: AgentDeps) -> bool:
    """Run *session* to a terminal status. False when this delivery has nothing to do."""
    owner = uuid4().hex
    outcome = deps.sessions.claim(session.user_sub, session.session_id, owner=owner, now=deps.clock())
    if outcome is ClaimResult.OWNED_ELSEWHERE:
        logger.info(
            "another attempt owns this session; dropping this delivery", extra={"session_id": session.session_id}
        )
        return False
    if outcome is ClaimResult.FINISHED:
        logger.info("session has already finished; dropping this delivery", extra={"session_id": session.session_id})
        return False

    started = time.monotonic()
    metrics.add_metric(name=STARTED, unit=MetricUnit.Count, value=1)
    guard = RunGuard(deps.sessions, session, owner=owner, clock=deps.clock, monotonic=deps.monotonic)
    try:
        result = _run(session, deps, guard=guard, resume=outcome is ClaimResult.RESUMED)
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
        _completed(deps, session, result, owner=owner)
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
    if resume and graph.get_state(config).next:  # ty: ignore[invalid-argument-type]
        # Continue the interrupted run: no new input means the pending nodes carry on from the
        # checkpoint, so the steps that already ran are not paid for twice.
        logger.info("resuming a session from its checkpoint", extra={"session_id": session.session_id})
        state = graph.invoke(None, config=config)  # ty: ignore[invalid-argument-type]
    else:
        state = graph.invoke(
            {"session_id": session.session_id, "request": session.request.model_dump(mode="json")},
            config=config,  # ty: ignore[invalid-argument-type]
        )
    return result_of(state)


def _completed(deps: AgentDeps, session: AgentSession, result: MealPlanResult, *, owner: str) -> None:
    if not deps.sessions.complete(session.user_sub, session.session_id, result, owner=owner):
        logger.warning("session lease moved on before the plan was written", extra={"session_id": session.session_id})
        return
    metrics.add_metric(name=COMPLETED, unit=MetricUnit.Count, value=1)
    logger.info(
        "meal plan session completed",
        extra={"session_id": session.session_id, "suggestions": len(result.suggestions)},
    )


def _failed(deps: AgentDeps, session: AgentSession, error: SessionError, *, owner: str) -> None:
    if not deps.sessions.fail(session.user_sub, session.session_id, error, owner=owner):
        logger.warning(
            "session lease moved on before the failure was written", extra={"session_id": session.session_id}
        )
        return
    metrics.add_metric(name=FAILED, unit=MetricUnit.Count, value=1)
    logger.warning("meal plan session failed", extra={"session_id": session.session_id, "error_code": error.code.value})
