"""Run one session: claim it, run the graph, write the outcome.

`start` is the whole interface the worker and the inline runner share. Claims are conditional
(`queued -> running`), so a duplicate SQS delivery or a second worker drops out before doing any
work; progress lines are written as each graph node runs, so a poll sees the run move; and every way
a run can end -- a typed refusal, a model failure, or a bug -- leaves the session `done` or `failed`
rather than `running` for ever.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from aws_lambda_powertools.metrics import MetricUnit
from pydantic import ValidationError

from glean.agent.errors import AgentError
from glean.agent.graph import build_graph, result_of
from glean.observability import logger, metrics
from glean.sessions.models import SessionError, SessionErrorCode

if TYPE_CHECKING:
    from glean.agent.deps import AgentDeps
    from glean.sessions.models import AgentSession
    from glean.sessions.store import SessionStore

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
    """Run *session* to a terminal status. False when another delivery already owns it."""
    if not deps.sessions.claim(session.user_sub, session.session_id):
        logger.info("session is not queued; dropping this delivery", extra={"session_id": session.session_id})
        return False

    started = time.monotonic()
    metrics.add_metric(name=STARTED, unit=MetricUnit.Count, value=1)
    progress = _Progress(deps.sessions, session)
    try:
        result = _run(session, deps, progress=progress)
    except AgentError as error:
        _failed(deps, session, error.error)
    except ValidationError:
        # The stored request no longer matches today's schema: an app build or a schema change, not a
        # model failure. The app offers the diagnostics export for this one.
        logger.exception("stored session request did not validate", extra={"session_id": session.session_id})
        _failed(deps, session, SessionError(code=SessionErrorCode.INVALID_REQUEST))
    except Exception:  # a run must end in a terminal status, whatever went wrong
        logger.exception("meal plan session failed unexpectedly", extra={"session_id": session.session_id})
        _failed(deps, session, SessionError(code=SessionErrorCode.WORKER_FAILED))
    else:
        deps.sessions.complete(session.user_sub, session.session_id, result)
        metrics.add_metric(name=COMPLETED, unit=MetricUnit.Count, value=1)
        metrics.add_metric(name=WALL_TIME, unit=MetricUnit.Milliseconds, value=int((time.monotonic() - started) * 1000))
        logger.info(
            "meal plan session completed",
            extra={"session_id": session.session_id, "suggestions": len(result.suggestions)},
        )
    return True


def _run(session: AgentSession, deps: AgentDeps, *, progress: _Progress):
    graph = build_graph(deps, progress=progress)
    state = graph.invoke(
        {"session_id": session.session_id, "request": session.request.model_dump(mode="json")},
        config={
            "configurable": {"thread_id": session.session_id},
            # One LangSmith trace per session: the metadata lands on the graph's run and its children.
            "metadata": {"session_id": session.session_id},
        },
    )
    return result_of(state)


def _failed(deps: AgentDeps, session: AgentSession, error: SessionError) -> None:
    deps.sessions.fail(session.user_sub, session.session_id, error)
    metrics.add_metric(name=FAILED, unit=MetricUnit.Count, value=1)
    logger.warning("meal plan session failed", extra={"session_id": session.session_id, "error_code": error.code.value})


class _Progress:
    """A graph node's progress line, written to the session straight away so a poll can read it."""

    def __init__(self, sessions: SessionStore, session: AgentSession) -> None:
        self._sessions = sessions
        self._session = session

    def __call__(self, line: str) -> None:
        self._sessions.append_progress(self._session.user_sub, self._session.session_id, [line])
