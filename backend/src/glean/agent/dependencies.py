"""FastAPI wiring for agent sessions: the session store, the queue, and the two runners behind them.

`AGENT_RUNNER=queue` (deployed, and the local Docker stack) writes the session and drops a message on
SQS. `AGENT_RUNNER=inline` (unit tests and evals only) runs the agent in the request, with the
in-memory store and saver, so CI needs no containers.

Both runners go through `agent.start`, so the conditional claim, the swap and the terminal-status
guarantee are the same code in a test as in production.
"""

from collections.abc import Callable
from functools import lru_cache
from typing import Annotated, Any

from fastapi import Depends

from glean.agent.checkpoint import in_memory_checkpointer
from glean.agent.deps import AgentDeps
from glean.agent.runtime import start
from glean.config import Settings, get_settings
from glean.decisions import DecisionClient
from glean.dependencies import get_decision_client, get_llm_router
from glean.llm import LLMRouter
from glean.observability import logger
from glean.sessions.factories import session_queue, session_store
from glean.sessions.models import AgentSession
from glean.sessions.store import SessionBusyError, SessionStore, utcnow


def get_session_store(settings: Annotated[Settings, Depends(get_settings)]) -> SessionStore:
    return session_store(settings)


@lru_cache(maxsize=1)
def _inline_checkpointer() -> Any:
    """One in-memory saver per process, so a dev session's checkpoints survive between requests."""
    return in_memory_checkpointer()


def get_session_dispatcher(
    settings: Annotated[Settings, Depends(get_settings)],
    llm_router: Annotated[LLMRouter, Depends(get_llm_router)],
    sessions: Annotated[SessionStore, Depends(get_session_store)],
    decision_client: Annotated[DecisionClient, Depends(get_decision_client)],
) -> Callable[[AgentSession], None]:
    """How a `queued` session reaches the agent: a message, or (inline) the run or swap itself."""
    if settings.agent_runner == "inline":
        deps = AgentDeps(
            sessions=sessions,
            checkpointer=_inline_checkpointer(),
            llm_router=llm_router,
            clock=utcnow,
            decision_client=decision_client,
        )

        def run_inline(session: AgentSession) -> None:
            try:
                start(session, deps)
            except SessionBusyError:
                # Inline there is no queue to send the work back to, and another attempt owns the run:
                # leave it alone rather than failing a session that is still being planned.
                logger.warning(
                    "session already running under another attempt", extra={"session_id": session.session_id}
                )

        return run_inline
    queue = session_queue(settings)
    return queue.send
