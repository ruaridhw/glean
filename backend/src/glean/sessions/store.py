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

import math
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Protocol

from glean.sessions.models import (
    MAX_ITEM_BYTES,
    MAX_STORED_INPUT_BYTES,
    SESSION_TTL_HOURS,
    AbandonResult,
    AgentSession,
    ClaimResult,
    SessionError,
    SessionRecord,
    SessionStatus,
    item_bytes,
    stored_input_bytes,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from glean.meal_plan.schemas import MealPlanResult

# The numbers the queue and the worker must agree on. `template.yaml` declares them, and
# tests/infra/test_template_async_stack.py checks the template against these constants.
WORKER_TIMEOUT_SECONDS = 120
# A Lambda can spend up to this long on init before the handler runs, so a message's visibility has to
# cover it as well as the handler.
LAMBDA_INIT_SECONDS = 10
# Recovery is only as fast as the queue: the message must reappear after a run has died, with margin.
QUEUE_VISIBILITY_MARGIN_SECONDS = 15
# Declared in template.yaml. It must stay above timeout + init + margin (145 s here), and it is what the
# app's five-minute cap is measured against: a crash comes back within about 2.5 minutes.
QUEUE_VISIBILITY_SECONDS = 150

# The lease an attempt takes at claim, and never extends. It is anchored to the invocation's own
# deadline, not to a constant: `now + remaining time + grace`, where the remaining time comes from the
# Lambda (`context.get_remaining_time_in_millis`). That is the moment this attempt is certainly dead, so
# the lease can never outlive its worker — which a constant measured from claim time could, because
# claim happens after init and the first reads, and the queue's clock starts at the receive.
LEASE_GRACE_SECONDS = 2


def lease_seconds_for(remaining_seconds: float) -> int:
    """How long this attempt may hold the session: until just after its own invocation must have ended."""
    return math.ceil(remaining_seconds) + LEASE_GRACE_SECONDS


# The longest any attempt can hold a session (a claim at the first instant of a full invocation). The
# template test checks the visibility timeout covers it.
MAX_LEASE_SECONDS = WORKER_TIMEOUT_SECONDS + LEASE_GRACE_SECONDS

# The dead-letter queue's visibility timeout: how often a dead letter that found a live run is retried.
# It must cover the DLQ handler's own 30 s timeout, and be short enough that the session is failed
# within about a minute of the lease lapsing (so about 3 minutes after a crash, inside the app's cap).
DEAD_LETTER_VISIBILITY_SECONDS = 60


def utcnow() -> datetime:
    return datetime.now(UTC)


def ttl_from(now: datetime, ttl_hours: int = SESSION_TTL_HOURS) -> int:
    return int((now + timedelta(hours=ttl_hours)).timestamp())


def lease_from(now: datetime, lease_seconds: int) -> int:
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

    def claim(self, user_sub: str, session_id: str, *, owner: str, now: datetime, lease_seconds: int) -> ClaimResult:
        """Try to become the attempt that runs this session, holding it for *lease_seconds* from *now*.

        *lease_seconds* is the caller's own remaining invocation time plus a grace (see
        `lease_seconds_for`), so the lease ends when the worker certainly has.
        """
        ...

    def append_progress(self, user_sub: str, session_id: str, lines: Sequence[str], *, owner: str) -> bool:
        """Add progress lines, keeping only the newest `MAX_PROGRESS_LINES`. False when the lease was lost.

        A line that arrives after a cancel is refused too: a cancelled session writes nothing more, so
        the graph stops at the next step rather than leaving one progress line behind it.
        """
        ...

    def complete(self, user_sub: str, session_id: str, result: MealPlanResult, *, owner: str) -> bool:
        """Finish the session with its plan, if this attempt still owns it.

        Raises `SessionTooLargeError` when the plan would push the item past DynamoDB's limit: the
        caller turns that into a typed failure, because there is nowhere left to write it. A session the
        household cancelled is no longer `running`, so the write is refused and a cancelled session can
        never later become `done`.
        """
        ...

    def fail(self, user_sub: str, session_id: str, error: SessionError, *, owner: str) -> bool:
        """Fail the session if this attempt still owns it. Says whether this call moved it."""
        ...

    def fail_if_abandoned(self, user_sub: str, session_id: str, error: SessionError) -> AbandonResult:
        """Fail a session nothing is running any more: the dead-letter handler's only write.

        Fails it only when it is nonterminal and its owner's lease has lapsed. A live run is reported as
        `STILL_LIVE` so its caller can keep the message instead of acknowledging it away.
        """
        ...

    def cancel(self, user_sub: str, session_id: str) -> bool:
        """Cancel the session, unless it is already terminal. Says whether this call moved it.

        Idempotent by design: a second cancel is a no-op, so DELETE answers 204 however often it is
        called. A finished session is never rewritten.
        """
        ...


class SessionExistsError(ValueError):
    """That session id is already in the table."""


class SessionTooLargeError(ValueError):
    """The stored inputs plus the room reserved for the outcome would not fit one item."""


class UnknownSessionError(KeyError):
    """No session with that id for this user."""


class SessionBusyError(RuntimeError):
    """Another attempt owns this nonterminal session right now.

    Raised instead of a plain "nothing to do", because a queue consumer's successful return acknowledges
    the message: acknowledging work that is not finished throws away the only trigger that would recover
    it if the live attempt then died. The delivery must fail (and come back) instead.
    """


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

    def claim(self, user_sub: str, session_id: str, *, owner: str, now: datetime, lease_seconds: int) -> ClaimResult:
        record = self.get(user_sub, session_id)
        if record is None:
            raise UnknownSessionError(session_id)
        if record.status.terminal:
            return ClaimResult.FINISHED
        if record.status is SessionStatus.RUNNING and not self._lease_lapsed(record, now):
            return ClaimResult.OWNED_ELSEWHERE
        resumed = record.status is SessionStatus.RUNNING
        self._write(
            record.model_copy(
                update={
                    "status": SessionStatus.RUNNING,
                    "owner": owner,
                    "lease_until": lease_from(now, lease_seconds),
                }
            )
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
        if (
            item_bytes(
                inputs=stored_input_bytes(record.request), progress=record.progress, result=result.model_dump_json()
            )
            > MAX_ITEM_BYTES
        ):
            raise SessionTooLargeError(session_id)
        self._write(record.model_copy(update={"status": SessionStatus.DONE, "result": result, "error": None}))
        return True

    def fail(self, user_sub: str, session_id: str, error: SessionError, *, owner: str) -> bool:
        record = self._owned(user_sub, session_id, owner)
        if record is None:
            return False
        self._write(record.model_copy(update={"status": SessionStatus.FAILED, "error": error}))
        return True

    def cancel(self, user_sub: str, session_id: str) -> bool:
        """Cancel the session unless it already finished. A cancelled session is terminal, so every
        owner-conditioned write after this one is refused by `_owned`."""
        record = self.get(user_sub, session_id)
        if record is None or record.status.terminal:
            return False
        self._write(record.model_copy(update={"status": SessionStatus.CANCELLED}))
        return True

    def fail_if_abandoned(self, user_sub: str, session_id: str, error: SessionError) -> AbandonResult:
        record = self.get(user_sub, session_id)
        if record is None:
            return AbandonResult.MISSING
        if record.status.terminal:
            return AbandonResult.FINISHED
        if not self._lease_lapsed(record, self._clock()):
            return AbandonResult.STILL_LIVE
        self._write(record.model_copy(update={"status": SessionStatus.FAILED, "error": error}))
        return AbandonResult.FAILED

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
