"""What one run needs: a session store, a checkpointer, an LLM router, the corpus and a clock.

Assembled in two places: the worker (`build_deps`) and the routes' inline runner. Tests replace the
whole object, so nothing below ever reaches AWS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from glean.agent.checkpoint import build_checkpointer
from glean.llm import LLMRouter
from glean.recipes.corpus import RecipeCorpusStore
from glean.sessions.dynamo import DynamoSessionStore
from glean.sessions.store import utcnow

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from langgraph.checkpoint.base import BaseCheckpointSaver  # noqa: TID251

    from glean.config import Settings
    from glean.sessions.queue import SessionQueue
    from glean.sessions.store import SessionStore


@dataclass(frozen=True)
class AgentDeps:
    """Everything one run may touch."""

    sessions: SessionStore
    checkpointer: BaseCheckpointSaver
    llm_router: LLMRouter
    corpus_factory: Callable[[], RecipeCorpusStore] = field(default=RecipeCorpusStore)
    clock: Callable[[], datetime] = field(default=utcnow)
    # Set by the worker, which renews the running message's visibility; the inline runner has no queue.
    queue: SessionQueue | None = None


def build_deps(
    settings: Settings,
    *,
    queue: SessionQueue | None = None,
    llm_router: LLMRouter | None = None,
) -> AgentDeps:
    """The deps a deployed run uses: the DynamoDB session table, the DynamoDB checkpointer, the corpus.

    *llm_router* is the seam the local queue consumer uses to run without model credits; deployed
    runs leave it None and get the router built from settings.
    """
    return AgentDeps(
        sessions=DynamoSessionStore(
            settings.agent_sessions_table,
            region=settings.aws_region,
            endpoint_url=settings.dynamodb_endpoint_url or None,
            ttl_hours=settings.agent_session_ttl_hours,
        ),
        checkpointer=build_checkpointer(settings),
        llm_router=llm_router or LLMRouter.from_settings(settings),
        queue=queue,
    )
