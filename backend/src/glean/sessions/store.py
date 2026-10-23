"""The session store contract, and the in-memory store the inline runner and tests use.

The store owns two rules so no caller can break them:

- **`claim` is the only way into `running`**, and it is conditional on `queued`. A duplicate queue
  delivery, a retry or a second worker therefore drops out with `False` instead of running the plan
  twice.
- **Every update refreshes `updated_at` and the TTL.** `get` never writes, because the app polls it
  every second.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Protocol

from glean.sessions.models import (
    SESSION_TTL_HOURS,
    AgentSession,
    SessionError,
    SessionRecord,
    SessionStatus,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from glean.meal_plan.schemas import MealPlanResult


def utcnow() -> datetime:
    return datetime.now(UTC)


def ttl_from(now: datetime, ttl_hours: int = SESSION_TTL_HOURS) -> int:
    return int((now + timedelta(hours=ttl_hours)).timestamp())


class SessionStore(Protocol):
    """What the routes, the agent module and the worker need from the session table."""

    def create(self, session: AgentSession, *, now: datetime) -> SessionRecord:
        """Write the session as `queued`. Raises `SessionExistsError` if the id is taken."""
        ...

    def get(self, user_sub: str, session_id: str) -> SessionRecord | None:
        """The session, or None when this user has no session with that id. Never writes."""
        ...

    def claim(self, user_sub: str, session_id: str) -> bool:
        """Move `queued` to `running`, and say whether this caller won the move."""
        ...

    def append_progress(self, user_sub: str, session_id: str, lines: Sequence[str]) -> None:
        """Add progress lines, keeping only the newest `MAX_PROGRESS_LINES`."""
        ...

    def complete(self, user_sub: str, session_id: str, result: MealPlanResult) -> None:
        """Finish the session with its plan."""
        ...

    def fail(self, user_sub: str, session_id: str, error: SessionError) -> bool:
        """Fail the session, unless it has already finished. Says whether this call moved it."""
        ...


class SessionExistsError(ValueError):
    """That session id is already in the table."""


class UnknownSessionError(KeyError):
    """No session with that id for this user."""


class InMemorySessionStore:
    """The session table in a dict, for `AGENT_RUNNER=inline` (unit tests and evals) only."""

    def __init__(self, *, ttl_hours: int = SESSION_TTL_HOURS, clock: Callable[[], datetime] = utcnow) -> None:
        self._records: dict[tuple[str, str], SessionRecord] = {}
        self._ttl_hours = ttl_hours
        self._clock = clock
        # How many writes this store has taken. Lets a test prove that polling never writes.
        self.writes = 0

    def create(self, session: AgentSession, *, now: datetime) -> SessionRecord:
        key = (session.user_sub, session.session_id)
        if key in self._records:
            raise SessionExistsError(session.session_id)
        record = SessionRecord(
            session_id=session.session_id,
            user_sub=session.user_sub,
            status=SessionStatus.QUEUED,
            request=session.request,
            created_at=now,
            updated_at=now,
            ttl=ttl_from(now, self._ttl_hours),
        )
        self._records[key] = record
        self.writes += 1
        return record

    def get(self, user_sub: str, session_id: str) -> SessionRecord | None:
        return self._records.get((user_sub, session_id))

    def claim(self, user_sub: str, session_id: str) -> bool:
        record = self.get(user_sub, session_id)
        if record is None or record.status is not SessionStatus.QUEUED:
            return False
        self._write(record.model_copy(update={"status": SessionStatus.RUNNING}))
        return True

    def append_progress(self, user_sub: str, session_id: str, lines: Sequence[str]) -> None:
        record = self._known(user_sub, session_id)
        self._write(record.appended(list(lines)))

    def complete(self, user_sub: str, session_id: str, result: MealPlanResult) -> None:
        record = self._known(user_sub, session_id)
        self._write(record.model_copy(update={"status": SessionStatus.DONE, "result": result, "error": None}))

    def fail(self, user_sub: str, session_id: str, error: SessionError) -> bool:
        record = self.get(user_sub, session_id)
        if record is None or record.status.terminal:
            return False
        self._write(record.model_copy(update={"status": SessionStatus.FAILED, "error": error}))
        return True

    def _known(self, user_sub: str, session_id: str) -> SessionRecord:
        record = self.get(user_sub, session_id)
        if record is None:
            raise UnknownSessionError(session_id)
        return record

    def _write(self, record: SessionRecord) -> None:
        now = self._clock()
        self._records[(record.user_sub, record.session_id)] = record.model_copy(
            update={"updated_at": now, "ttl": ttl_from(now, self._ttl_hours)}
        )
        self.writes += 1
