"""What one run needs: a session store, a checkpointer, an LLM router, the screen, the corpus and a clock.

Assembled in two places: the worker (`build_deps`) and the routes' inline runner. Tests replace the
whole object, so nothing below ever reaches AWS.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from glean.agent.checkpoint import build_checkpointer
from glean.decisions import DecisionClient
from glean.llm import LLMRouter
from glean.recipes.corpus import RecipeCorpusStore
from glean.screening import ScreenRejection, ScreenResult, screen
from glean.sessions.dynamo import DynamoSessionStore
from glean.sessions.store import WORKER_TIMEOUT_SECONDS, utcnow

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from langgraph.checkpoint.base import BaseCheckpointSaver  # noqa: TID251

    from glean.config import Settings
    from glean.sessions.store import SessionStore


def drop_every_note(_text: str) -> ScreenResult:
    """The screen when nothing can vouch for a note: drop it, as the real screen does when it is unavailable."""
    return ScreenResult(text=None, rejection=ScreenRejection.UNAVAILABLE)


def decision_screen(client: DecisionClient) -> Callable[[str], ScreenResult]:
    """The injection screen over *client*: the one question every free-text field asks (`glean.screening`)."""
    return lambda text: screen(text, decision_client=client)


@dataclass(frozen=True)
class AgentDeps:
    """Everything one run may touch."""

    sessions: SessionStore
    checkpointer: BaseCheckpointSaver
    llm_router: LLMRouter
    corpus_factory: Callable[[], RecipeCorpusStore] = field(default=RecipeCorpusStore)
    # Two clocks: wall time for the session item and its TTL, monotonic seconds for the run's budget and
    # its lease renewals. Tests replace both.
    clock: Callable[[], datetime] = field(default=utcnow)
    monotonic: Callable[[], float] = field(default=time.monotonic)
    # How long this attempt still has, taken from the Lambda context in a deployed run. The claim's lease
    # is anchored to it, so the lease always ends when this worker certainly has.
    remaining_seconds: Callable[[], float] = field(default=lambda: float(WORKER_TIMEOUT_SECONDS))
    # The injection screen's decisions client, for the week's note. None drops any note unread: the screen
    # fails closed, and the chips still apply.
    decision_client: DecisionClient | None = None
    # The injection screen a swap note goes through before any model reads it (spec §6.2). Fails closed: a
    # run assembled without a decision client drops every note rather than using one nothing vouched for.
    screen: Callable[[str], ScreenResult] = field(default=drop_every_note)


def build_deps(
    settings: Settings,
    *,
    llm_router: LLMRouter | None = None,
    remaining_seconds: Callable[[], float] | None = None,
) -> AgentDeps:
    """The deps a deployed run uses: the DynamoDB session table, the DynamoDB checkpointer, the corpus.

    *llm_router* is the seam the local queue consumer uses to run without model credits; deployed
    runs leave it None and get the router built from settings. *remaining_seconds* is the Lambda
    context's own clock, which the claim's lease is anchored to. Swap notes are screened by the decision
    model, with the same key the rest of the backend's decisions use.
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
        remaining_seconds=remaining_seconds or (lambda: float(WORKER_TIMEOUT_SECONDS)),
        decision_client=DecisionClient(api_key=settings.openrouter_api_key),
        screen=decision_screen(DecisionClient(api_key=settings.openrouter_api_key)),
    )
