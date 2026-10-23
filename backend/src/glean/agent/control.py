"""Keep the session lease and check ownership between graph steps.

A redelivery can take over a run whose worker stopped renewing. The former owner stops
instead of racing it: `LostOwnership` says so, and nothing is written.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from glean.observability import logger

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from glean.sessions.models import AgentSession
    from glean.sessions.store import SessionStore

# How often a running attempt renews its lease. A third of the lease, so two renewals can be lost
# before a takeover becomes possible, and a run shorter than this writes no lease at all beyond the claim.
LEASE_REFRESH_SECONDS = 40


class LostOwnership(Exception):
    """Another attempt took this session over; this one stops without writing anything."""


class RunGuard:
    """Per-step housekeeping for one attempt: the lease, then the progress line."""

    def __init__(
        self,
        sessions: SessionStore,
        session: AgentSession,
        *,
        owner: str,
        clock: Callable[[], datetime],
        monotonic: Callable[[], float] = time.monotonic,
        refresh_every: float = LEASE_REFRESH_SECONDS,
    ) -> None:
        self._sessions = sessions
        self._session = session
        self._owner = owner
        self._clock = clock
        self._monotonic = monotonic
        self._refresh_every = refresh_every
        self._next_refresh = monotonic() + refresh_every

    def step(self, line: str) -> None:
        """Called at the start of every graph node."""
        self._refresh_lease_if_due()
        if not self._sessions.append_progress(
            self._session.user_sub, self._session.session_id, [line], owner=self._owner
        ):
            raise LostOwnership

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
