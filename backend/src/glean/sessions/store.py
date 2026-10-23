"""The session store contract, and the in-memory store the inline runner and tests use.

The store owns three rules so no caller can break them:

- **`claim` is the only way into `running`.** It wins a `queued` session, or takes over a `running` one
  whose lease has lapsed — and it hands the winner an owner token plus a lease taken ONCE, never
  extended. A duplicate delivery of a live run is told it is owned elsewhere, so it drops; a crashed
  run's redelivery can take over.
- **Only the owner writes the outcome.** `append_progress`, `complete` and `fail` are conditioned on the
  owner token, so a worker that lost its lease cannot finish a run someone else is now driving.
- **Every update refreshes `updated_at` and the TTL.** `get` never writes, because the app polls it
  every second.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Protocol

from glean.sessions.models import (
    MAX_STORED_INPUT_BYTES,
    SESSION_TTL_HOURS,
    AgentSession,
    ClaimResult,
    SessionError,
    SessionRecord,
    SessionStatus,
    stored_input_bytes,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from glean.meal_plan.schemas import MealPlanResult

# The worker's function timeout and the queue's visibility timeout, which `template.yaml` must match
# (tests/infra/test_template_async_stack.py checks all three numbers against these).
WORKER_TIMEOUT_SECONDS = 120
QUEUE_VISIBILITY_SECONDS = 130

# The lease an attempt takes at claim, and never extends. Two rules pick it:
#   * below the visibility timeout, so every redelivered copy of the message finds it lapsed — a
#     refreshed lease could outlive the visibility, and then the redelivered message would be acked as
#     "owned elsewhere" with nothing left to recover the run;
#   * above the function timeout plus a small margin, so a live run's own delivery can never be taken
#     over while it is still inside the Lambda, and a duplicate copy delivered alongside it is dropped.
# A Lambda can never outlive its timeout, so 125 s after the claim the attempt is provably gone.
LEASE_MARGIN_SECONDS = 5
LEASE_SECONDS = WORKER_TIMEOUT_SECONDS + LEASE_MARGIN_SECONDS


def utcnow() -> datetime:
    return datetime.now(UTC)


def ttl_from(now: datetime, ttl_hours: int = SESSION_TTL_HOURS) -> int:
    return int((now + timedelta(hours=ttl_hours)).timestamp())


def lease_from(now: datetime, lease_seconds: int = LEASE_SECONDS) -> int:
    return int(now.timestamp()) + lease_seconds


class SessionStore(Protocol):
    """What the routes, the agent module and the worker need from the session table."""

    def create(self, session: AgentSession, *, now: datetime) -> SessionRecord:
        """Write the session as `queued`.

        Raises `SessionExistsError` if the id is taken, and `SessionTooLargeError` when the stored
        inputs plus the reserved room for the outcome would not fit one DynamoDB item.
        """
        ...

    def get(self, user_sub: str, session_id: str) -> SessionRecord | None:
        """The session, or None when this user has no session with that id. Never writes."""
        ...

    def claim(self, user_sub: str, session_id: str, *, owner: str, now: datetime) -> ClaimResult:
        """Try to become the attempt that runs this session, taking a lease until `LEASE_SECONDS` from *now*."""
        ...

    def append_progress(self, user_sub: str, session_id: str, lines: Sequence[str], *, owner: str) -> bool:
        """Add progress lines, keeping only the newest `MAX_PROGRESS_LINES`. False when the lease was lost."""
        ...

    def complete(self, user_sub: str, session_id: str, result: MealPlanResult, *, owner: str) -> bool:
        """Finish the session with its plan, if this attempt still owns it."""
        ...

    def fail(self, user_sub: str, session_id: str, error: SessionError, *, owner: str | None = None) -> bool:
        """Fail the session, unless it has already finished. Says whether this call moved it.

        The worker passes its owner token; the dead-letter handler passes none, because by then the run
        that owned the session is gone and the queue has given up on it.
        """
        ...


class SessionExistsError(ValueError):
    """That session id is already in the table."""


class SessionTooLargeError(ValueError):
    """The stored inputs plus the room reserved for the outcome would not fit one item."""


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
        if stored_input_bytes(session.request) > MAX_STORED_INPUT_BYTES:
            raise SessionTooLargeError(session.session_id)
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

    def claim(self, user_sub: str, session_id: str, *, owner: str, now: datetime) -> ClaimResult:
        record = self.get(user_sub, session_id)
        if record is None:
            raise UnknownSessionError(session_id)
        if record.status.terminal:
            return ClaimResult.FINISHED
        if record.status is SessionStatus.RUNNING and not self._lease_lapsed(record, now):
            return ClaimResult.OWNED_ELSEWHERE
        resumed = record.status is SessionStatus.RUNNING
        self._write(
            record.model_copy(update={"status": SessionStatus.RUNNING, "owner": owner, "lease_until": lease_from(now)})
        )
        return ClaimResult.RESUMED if resumed else ClaimResult.STARTED

    def append_progress(self, user_sub: str, session_id: str, lines: Sequence[str], *, owner: str) -> bool:
        record = self._owned(user_sub, session_id, owner)
        if record is None:
            return False
        self._write(record.appended(list(lines)))
        return True

    def complete(self, user_sub: str, session_id: str, result: MealPlanResult, *, owner: str) -> bool:
        record = self._owned(user_sub, session_id, owner)
        if record is None:
            return False
        self._write(record.model_copy(update={"status": SessionStatus.DONE, "result": result, "error": None}))
        return True

    def fail(self, user_sub: str, session_id: str, error: SessionError, *, owner: str | None = None) -> bool:
        record = self.get(user_sub, session_id)
        if record is None or record.status.terminal:
            return False
        if owner is not None and record.owner != owner:
            return False
        self._write(record.model_copy(update={"status": SessionStatus.FAILED, "error": error}))
        return True

    def _owned(self, user_sub: str, session_id: str, owner: str) -> SessionRecord | None:
        """The record, if this attempt may still write to it."""
        record = self.get(user_sub, session_id)
        if record is None or record.status is not SessionStatus.RUNNING or record.owner != owner:
            return None
        return record

    @staticmethod
    def _lease_lapsed(record: SessionRecord, now: datetime) -> bool:
        return record.lease_until is None or record.lease_until < int(now.timestamp())

    def _write(self, record: SessionRecord) -> None:
        now = self._clock()
        self._records[(record.user_sub, record.session_id)] = record.model_copy(
            update={"updated_at": now, "ttl": ttl_from(now, self._ttl_hours)}
        )
        self.writes += 1
