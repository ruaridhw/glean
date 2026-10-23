"""Where the session store and queue come from, from settings.

Cached per configuration, so a warm container reuses one boto3 client and the local inline runner
keeps one in-memory store across requests.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from glean.sessions.dynamo import DynamoSessionStore
from glean.sessions.queue import SessionQueue
from glean.sessions.store import InMemorySessionStore

if TYPE_CHECKING:
    from glean.config import Settings
    from glean.sessions.store import SessionStore


@lru_cache(maxsize=1)
def inline_sessions() -> InMemorySessionStore:
    """The one in-memory store an `AGENT_RUNNER=inline` process uses (unit tests, evals, local dev)."""
    return InMemorySessionStore()


@lru_cache(maxsize=4)
def _dynamo_sessions(table_name: str, region: str, endpoint_url: str, ttl_hours: int) -> DynamoSessionStore:
    return DynamoSessionStore(table_name, region=region, endpoint_url=endpoint_url or None, ttl_hours=ttl_hours)


def session_store(settings: Settings) -> SessionStore:
    if settings.agent_runner == "inline":
        return inline_sessions()
    return _dynamo_sessions(
        settings.agent_sessions_table,
        settings.aws_region,
        settings.dynamodb_endpoint_url,
        settings.agent_session_ttl_hours,
    )


@lru_cache(maxsize=4)
def _sqs_queue(queue_url: str, region: str, endpoint_url: str) -> SessionQueue:
    return SessionQueue(queue_url, region=region, endpoint_url=endpoint_url or None)


def session_queue(settings: Settings) -> SessionQueue:
    return _sqs_queue(settings.agent_session_queue_url, settings.aws_region, settings.sqs_endpoint_url)
