"""What one run may spend, and who owns it, checked between graph steps.

Two promises sit here, both from spec §6.2:

- **The 90 s budget.** `RunBudget` refuses to start another step once the deadline has passed, and hands
  the remaining time to the one blocking call (the model), so a run ends inside the worker's two-minute
  timeout with a typed outcome rather than being killed mid-flight.
- **The lease, and the household's cancel.** The lease is taken once, at claim, and never extended
  (`sessions.store.LEASE_SECONDS`): it is shorter than the queue's visibility timeout, so any
  redelivered copy of a message finds a lapsed lease and takes over, while a duplicate copy delivered
  alongside a live run finds it live and is dropped. `RunGuard` only notices that another attempt took
  over — its progress write is owner-conditioned — and then stops without writing anything
  (`LostOwnership`). The same write is refused when the household cancelled, because `cancelled` is not
  `running` either; one read on the refused path tells the two apart, and a cancel stops the run with
  `SessionCancelled` so it is counted and logged as the household's doing, not as a lost lease.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, NoReturn

from glean.agent.errors import AgentError, SessionCancelled, budget_spent
from glean.observability import logger
from glean.sessions.models import SessionStatus

if TYPE_CHECKING:
    from collections.abc import Callable

    from glean.sessions.models import AgentSession
    from glean.sessions.store import SessionStore

# Spec §6.2's agent budget: 90 s of wall time for one session.
AGENT_RUN_BUDGET_SECONDS = 90


class LostOwnership(Exception):
    """Another attempt took this session over; this one stops without writing anything."""


class RunBudget:
    """The wall-clock budget of one run, checked before each graph step."""

    def __init__(
        self,
        seconds: float = AGENT_RUN_BUDGET_SECONDS,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._clock = clock
        self._deadline = clock() + seconds

    def remaining(self) -> float:
        return max(0.0, self._deadline - self._clock())

    def remaining_ms(self) -> int:
        return int(self.remaining() * 1000)

    def check(self) -> None:
        """Raise when the budget is spent, so the run ends `failed` instead of being killed."""
        if self.remaining() <= 0:
            raise AgentError(budget_spent())


class RunGuard:
    """Per-step housekeeping for one attempt: the budget, then the progress line.

    The progress write is owner-conditioned, so it doubles as the ownership check: if another attempt
    has taken the session over, the write is refused and the run stops.
    """

    def __init__(
        self,
        sessions: SessionStore,
        session: AgentSession,
        *,
        owner: str,
        monotonic: Callable[[], float] = time.monotonic,
        budget: RunBudget | None = None,
    ) -> None:
        self._sessions = sessions
        self._session = session
        self._owner = owner
        self._budget = budget or RunBudget(clock=monotonic)

    def step(self, line: str) -> None:
        """Called at the start of every graph node."""
        self._budget.check()
        if not self._sessions.append_progress(
            self._session.user_sub, self._session.session_id, [line], owner=self._owner
        ):
            self._stopped()

    def _stopped(self) -> NoReturn:
        """The write was refused, so this run must write nothing more. Say which stop this is.

        One read, on the refused path only: a run that finishes normally makes none. Without it a cancel
        would be logged as a lost lease, and a cancellation would never be counted as one.
        """
        record = self._sessions.get(self._session.user_sub, self._session.session_id)
        if record is not None and record.status is SessionStatus.CANCELLED:
            logger.info(
                "session was cancelled by the household; stopping", extra={"session_id": self._session.session_id}
            )
            raise SessionCancelled(self._session.session_id)
        logger.warning(
            "session lease lost to another attempt; stopping", extra={"session_id": self._session.session_id}
        )
        raise LostOwnership

    def remaining_ms(self) -> int:
        """How much of the budget the model call may use."""
        return self._budget.remaining_ms()
