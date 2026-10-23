"""The async stack's two queue consumers: the session worker and the dead-letter handler.

Both handlers are thin. The worker renews the message's visibility, calls `glean.agent.start` and
lets that module decide the session's outcome; the dead-letter handler marks a session
`worker_failed` once SQS has given up on it. Neither imports LangGraph, and neither knows how a plan
is made.

Deployed event source mappings (template.yaml): the worker takes one message at a time with a 60 s
visibility timeout that it renews every 20 s, and the dead-letter queue has its own mapping to
`dlq_handler`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from glean.agent import build_deps, start
from glean.config import get_settings
from glean.observability import logger, metrics, tracer
from glean.sessions.dynamo import DynamoSessionStore
from glean.sessions.factories import session_queue
from glean.sessions.models import AgentSession, SessionError, SessionErrorCode
from glean.sessions.queue import SessionMessage, VisibilityLease

if TYPE_CHECKING:
    from glean.agent.deps import AgentDeps
    from glean.sessions.queue import SessionQueue


@tracer.capture_lambda_handler
@logger.inject_lambda_context
def handler(event: dict[str, Any], _context: object = None) -> None:
    """The SQS session worker: one unit of work per message, batch size 1."""
    settings = get_settings()
    queue = session_queue(settings)
    deps = build_deps(settings, queue=queue)
    try:
        for record in event.get("Records", ()):
            handle_record(record, deps, queue)
    finally:
        metrics.flush_metrics()


def handle_record(record: dict[str, Any], deps: AgentDeps, queue: SessionQueue) -> bool:
    """Run the session this record names. Returns whether a run was started.

    A body this queue did not write, or a session the table no longer holds (expired, or never
    written), is logged and dropped: there is no run to start, and redelivering it would only reach
    the dead-letter queue again.
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
    lease = VisibilityLease(lambda seconds: queue.extend_visibility(record["receiptHandle"], seconds))
    with lease.keep_alive():
        return start(session, deps)


@tracer.capture_lambda_handler
@logger.inject_lambda_context
def dlq_handler(event: dict[str, Any], _context: object = None) -> None:
    """The dead-letter handler: SQS ran out of attempts, so the session is `worker_failed`."""
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
            "dead-lettered session had already finished; leaving it alone",
            extra={"session_id": message.session_id},
        )
