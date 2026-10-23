"""What one run may spend, and who owns it, checked between graph steps.

Two promises sit here, both from spec §6.2:

- **The 90 s budget.** `RunBudget` refuses to start another step once the deadline has passed, and hands
  the remaining time to the one blocking call (the model), so a run ends inside the worker's two-minute
  timeout with a typed outcome rather than being killed mid-flight.
- **The lease.** `RunGuard` refreshes the session's lease as the run progresses, so a redelivery can
  only take over a run whose worker has stopped renewing. If another attempt has taken over, the run
  stops instead of racing it — `LostOwnership` says so, and nothing is written.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from glean.agent.errors import AgentError, budget_spent
from glean.observability import logger

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from glean.sessions.models import AgentSession
    from glean.sessions.store import SessionStore

# Spec §6.2's agent budget: 90 s of wall time for one session.
AGENT_RUN_BUDGET_SECONDS = 90
# How often a running attempt renews its lease. A third of the lease, so two renewals can be lost
# before a takeover becomes possible, and a run shorter than this writes no lease at all beyond the claim.
LEASE_REFRESH_SECONDS = 40


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
    """Per-step housekeeping for one attempt: the budget, then the lease, then the progress line."""

    def __init__(
        self,
        sessions: SessionStore,
        session: AgentSession,
        *,
        owner: str,
        clock: Callable[[], datetime],
        monotonic: Callable[[], float] = time.monotonic,
        budget: RunBudget | None = None,
        refresh_every: float = LEASE_REFRESH_SECONDS,
    ) -> None:
        self._sessions = sessions
        self._session = session
        self._owner = owner
        self._clock = clock
        self._monotonic = monotonic
        self._budget = budget or RunBudget(clock=monotonic)
        self._refresh_every = refresh_every
        self._next_refresh = monotonic() + refresh_every

    def step(self, line: str) -> None:
        """Called at the start of every graph node."""
        self._budget.check()
        self._refresh_lease_if_due()
        if not self._sessions.append_progress(
            self._session.user_sub, self._session.session_id, [line], owner=self._owner
        ):
            raise LostOwnership

    def remaining_ms(self) -> int:
        """How much of the budget the model call may use."""
        return self._budget.remaining_ms()

    def _refresh_lease_if_due(self) -> None:
        now = self._monotonic()
        if now < self._next_refresh:
            return
        self._next_refresh = now + self._refresh_every
        if not self._sessions.refresh_lease(
            self._session.user_sub, self._session.session_id, owner=self._owner, now=self._clock()
        ):
            logger.warning(
                "session lease lost to another attempt; stopping", extra={"session_id": self._session.session_id}
            )
            raise LostOwnership
