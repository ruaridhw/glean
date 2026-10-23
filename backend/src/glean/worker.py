"""The async stack's two queue consumers: the session worker and the dead-letter handler.

Both handlers are thin. The worker calls `glean.agent.start` and lets that module decide the
session's outcome; the dead-letter handler marks a session `worker_failed` once SQS has given up on it.
Neither imports LangGraph, and neither knows how a plan is made.

Deployed event source mappings (template.yaml): the worker takes one message at a time, and the
queue's visibility timeout (150 s) covers the function's 120 s timeout plus up to 10 s of init, which
AWS requires and which means Lambda holds the message for as long as the run can last. Liveness lives on
the session item: a lease anchored to this invocation's deadline, and an owner token that only one
attempt holds. A run that dies has its lease lapse, and the redelivery picks it up from its checkpoint.

A delivery that finds another attempt owning a nonterminal session raises instead of returning: Lambda
acknowledges a message whose handler returns, and acknowledging work that is not finished would discard
the only trigger that recovers it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from glean.agent import build_deps, start
from glean.config import get_settings
from glean.observability import logger, metrics, tracer
from glean.sessions.dynamo import DynamoSessionStore
from glean.sessions.models import AgentSession, SessionError, SessionErrorCode
from glean.sessions.queue import SessionMessage

if TYPE_CHECKING:
    from glean.agent.deps import AgentDeps


@tracer.capture_lambda_handler
@logger.inject_lambda_context
def handler(event: dict[str, Any], context: Any) -> None:
    """The SQS session worker: one unit of work per message, batch size 1."""
    settings = get_settings()
    deps = build_deps(settings, remaining_seconds=lambda: context.get_remaining_time_in_millis() / 1000)
    try:
        for record in event.get("Records", ()):
            handle_record(record, deps)
    finally:
        metrics.flush_metrics()


def handle_record(record: dict[str, Any], deps: AgentDeps) -> bool:
    """Run the session this record names. Returns whether a run was started.

    A body this queue did not write, or a session the table no longer holds (expired, or never
    written), is logged and dropped: there is no run to start, and redelivering it would only reach
    the dead-letter queue again. Everything else that raises -- a live owner, or anything the store or
    the run raised -- propagates, so Lambda fails the delivery and the message comes back rather than
    being acknowledged unfinished.
    """
    try:
        message = SessionMessage.parse(record["body"])
    except ValidationError:
        logger.exception("dropping a session message this queue did not write")
        return False

    stored = deps.sessions.get(message.user_sub, message.session_id)
    if stored is None:
        logger.error("dropping a session message for a session that is not in the table")
        return False

    session = AgentSession(session_id=message.session_id, user_sub=message.user_sub, request=stored.request)
    return start(session, deps)


@tracer.capture_lambda_handler
@logger.inject_lambda_context
def dlq_handler(event: dict[str, Any], _context: object = None) -> None:
    """The dead-letter handler: SQS ran out of attempts, so an abandoned session becomes `worker_failed`.

    It only fails a session whose lease has lapsed. A live run is left alone: it is still working, and
    will write its own outcome. That is why the queue allows three receives -- a duplicate delivery that
    was failed on purpose costs one of them.
    """
    sessions = DynamoSessionStore.from_environment()
    try:
        for record in event.get("Records", ()):
            _fail_dead_letter(record, sessions)
    finally:
        metrics.flush_metrics()


def _fail_dead_letter(record: dict[str, Any], sessions: DynamoSessionStore) -> None:
    try:
        message = SessionMessage.parse(record["body"])
    except ValidationError:
        logger.exception("dropping a dead-letter message this queue did not write")
        return
    moved = sessions.fail(message.user_sub, message.session_id, SessionError(code=SessionErrorCode.WORKER_FAILED))
    if moved:
        logger.warning("session failed after its message was dead-lettered", extra={"session_id": message.session_id})
    else:
        logger.info(
            "dead-lettered session is finished or still owned by a live run; leaving it alone",
            extra={"session_id": message.session_id},
        )
