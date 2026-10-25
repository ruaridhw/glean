"""What one run may spend, and who owns it, checked between graph steps.

Two promises sit here, both from spec §6.2:

- **The 90 s budget.** `RunBudget` refuses to start another step once the deadline has passed
  (`BudgetSpent`), and hands the remaining time to the one blocking call (the model), so a run ends inside
  the worker's two-minute timeout with a typed outcome rather than being killed mid-flight. The graph turns
  a spent budget into the scorer's degraded week once one exists, so only `prepare` can fail on it.
- **Working time, not thinking time (V11).** The 90 s are the session's working time. A run parked on the
  household's question holds no attempt at all, so the household's thinking time is never on any clock;
  the time spent *before* the question rides the graph state (`working_seconds`), and the attempt that
  resumes it starts its budget that much spent (`RunBudget.carry`). A household that never answers spends
  nothing: the session stays parked until its TTL expires the item, and later the checkpoint.
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
from typing import TYPE_CHECKING, Literal, NoReturn

from glean.agent.errors import AgentError, SessionCancelled, budget_spent
from glean.observability import logger
from glean.sessions.models import SessionStatus

if TYPE_CHECKING:
    from collections.abc import Callable

    from glean.sessions.models import AgentSession, SessionRecord
    from glean.sessions.store import SessionStore

# Spec §6.2's agent budget: 90 s of wall time for one session.
AGENT_RUN_BUDGET_SECONDS = 90


class LostOwnership(Exception):
    """Another attempt took this session over; this one stops without writing anything."""


class BudgetSpent(AgentError):
    """The run's 90 s are spent. Before a scorer plan exists that is `model_error`; after, the degraded week."""

    def __init__(self) -> None:
        super().__init__(budget_spent())


class RunBudget:
    """The wall-clock budget of one run, checked before each graph step."""

    def __init__(
        self,
        seconds: float = AGENT_RUN_BUDGET_SECONDS,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._clock = clock
        self._seconds = seconds
        self._carried = 0.0
        self._deadline = clock() + seconds

    def carry(self, seconds: float) -> None:
        """Count *seconds* an earlier attempt of this session already worked, before its question parked it."""
        self._deadline -= seconds
        self._carried += seconds

    def carried(self) -> float:
        """The working seconds an earlier attempt spent before the question; 0 for a session that never asked."""
        return self._carried

    def spent(self) -> float:
        """Working seconds so far: this attempt's, plus any carried from before the question."""
        return self._seconds - (self._deadline - self._clock())

    def remaining(self) -> float:
        return max(0.0, self._deadline - self._clock())

    def remaining_ms(self) -> int:
        return int(self.remaining() * 1000)

    def check(self) -> None:
        """Raise `BudgetSpent` when the budget is spent, so the run ends itself instead of being killed."""
        if self.remaining() <= 0:
            raise BudgetSpent


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
        resumed: bool = False,
    ) -> None:
        self._sessions = sessions
        self._session = session
        self._owner = owner
        self._budget = budget or RunBudget(clock=monotonic)
        # A takeover resumes the node the crashed attempt died in, whose line that attempt may already have
        # written: the first step of this attempt checks before writing it again.
        self._resumed = resumed

    def step(self, line: str | None, *, budget: bool = True) -> None:
        """Called at the start of every graph node: the budget, then the progress line.

        `line=None` is for a step with no line of its own -- the agent's later `plan` turns -- and checks
        ownership and cancel with one read instead of a write, because the step that follows is a paid model
        call: a household that cancelled while a tool ran must not pay for one more turn. `budget=False` is
        for `finalise`, which must still write the degraded week after the budget is spent.
        """
        if budget:
            self._budget.check()
        first_after_resume, self._resumed = self._resumed, False
        if line is None:
            self.check_live()
            return
        if first_after_resume and self._already_written(line):
            return
        if not self._sessions.append_progress(
            self._session.user_sub, self._session.session_id, [line], owner=self._owner
        ):
            self._stopped()

    def _already_written(self, line: str) -> bool:
        """Whether the crashed attempt wrote this node's line before it died. One read, on a takeover only.

        Only the first step of a resumed attempt asks: that is the node the crash interrupted. A later node
        whose line happens to match the last one (two reads in a row) writes it as usual.
        """
        record = self._sessions.get(self._session.user_sub, self._session.session_id)
        if record is None or record.status is not SessionStatus.RUNNING or record.owner != self._owner:
            self._stopped(record)
        return bool(record.progress) and record.progress[-1] == line

    def check_live(self) -> None:
        """Stop unless this attempt still owns a running session: one read, no write."""
        record = self._sessions.get(self._session.user_sub, self._session.session_id)
        if record is None or record.status is not SessionStatus.RUNNING or record.owner != self._owner:
            self._stopped(record)

    def _stopped(self, record: SessionRecord | None | Literal[False] = False) -> NoReturn:
        """This run must write nothing more. Say which stop this is.

        A refused write costs one read here, on the refused path only, unless the caller already read the
        record. Without it a cancel would be logged as a lost lease, and a cancellation would never be counted
        as one.
        """
        if record is False:
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

    def carry(self, seconds: float) -> None:
        """Resume a parked session's budget where its question left it."""
        self._budget.carry(seconds)

    def spent(self) -> float:
        """The session's working seconds so far, recorded in the state when it asks its question."""
        return self._budget.spent()

    def carried(self) -> float:
        """The working seconds carried in from before the question, for the session's one wall-time point."""
        return self._budget.carried()
