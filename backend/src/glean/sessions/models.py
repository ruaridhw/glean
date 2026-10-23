"""Agent sessions: one item of transient per-user state per Generate tap.

The app creates a session, the backend runs it out of process, and the app polls it. One item holds
the inputs, the status, a bounded list of progress lines, and then either the result or a typed
error. `pk` is the Cognito sub and `sk` the session id, so another user's session is unreachable by
key rather than hidden by a check.

Framework-free: the store implementations, the queue and the routes all share these models.
"""

from __future__ import annotations

import gzip
from datetime import datetime  # noqa: TC003 - Pydantic resolves this annotation when the model is built
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, field_validator

from glean.meal_plan.schemas import MealPlanRequest, MealPlanResult

if TYPE_CHECKING:
    from collections.abc import Sequence

# A session outlives the tap by a day, then DynamoDB expires it.
SESSION_TTL_HOURS = 24
# How many progress lines one item keeps. The bound is a safety net: V1's graph writes three, V7's
# tools a handful, and a runaway loop must not grow an item without limit. Older lines are dropped.
MAX_PROGRESS_LINES = 50

# DynamoDB refuses an item over 400 KB, and the whole item is one write: the inputs, the progress lines
# and the result share that budget. Nothing in the schemas bounds a model's prose, so both ends are
# guarded: `create` refuses a request whose inputs leave no room, and `complete` refuses to write a plan
# that would overflow the item (the run then ends `failed / model_error` rather than raising).
MAX_ITEM_BYTES = 400 * 1024
# The plan: up to seven meals, each with a reason, plus V3's alternative per meal and the reasons of the
# planned meals. Four times the round-1 guess, because model prose is not bounded by any schema.
RESULT_RESERVE_BYTES = 64 * 1024
# Fifty progress lines of a sentence or two each.
PROGRESS_RESERVE_BYTES = 16 * 1024
# Keys, timestamps, the owner token, the lease and the error JSON.
ITEM_OVERHEAD_BYTES = 2 * 1024
# 409,600 - 65,536 - 16,384 - 2,048 = 325,632.
MAX_STORED_INPUT_BYTES = MAX_ITEM_BYTES - RESULT_RESERVE_BYTES - PROGRESS_RESERVE_BYTES - ITEM_OVERHEAD_BYTES


def stored_inputs(request: MealPlanRequest) -> bytes:
    """The request as the item holds it: gzipped JSON.

    V8's history window is 400 rows and each note may be 500 characters, so an input inside the schema
    can be far larger than one DynamoDB item. Compressed it is a fraction of the size, and `create`
    refuses anything still too big rather than failing at the first progress write.
    """
    return gzip.compress(request.model_dump_json().encode(), mtime=0)


def stored_input_bytes(request: MealPlanRequest) -> int:
    return len(stored_inputs(request))


def item_bytes(*, inputs: int, progress: Sequence[str], result: str | None = None, error: str | None = None) -> int:
    """The size the item will have, near enough: its stored inputs, its lines, its outcome and its keys.

    Used before the terminal write, so an oversized plan is a typed failure instead of a DynamoDB
    ValidationException: UTF-8 bytes throughout, because that is what DynamoDB counts.
    """
    return (
        inputs
        + sum(len(line.encode()) for line in progress)
        + len((result or "").encode())
        + len((error or "").encode())
        + ITEM_OVERHEAD_BYTES
    )


class SessionStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"
    DONE = "done"
    FAILED = "failed"

    @property
    def terminal(self) -> bool:
        """Whether the app can stop polling."""
        return self in {SessionStatus.DONE, SessionStatus.FAILED}


class ClaimResult(StrEnum):
    """What one queue delivery won, which decides whether it runs the graph and how.

    A message can be delivered more than once: SQS retries it, and a run that died leaves its item
    `running`. The lease on the item is what tells those apart from a live run.
    """

    STARTED = "started"
    RESUMED = "resumed"
    OWNED_ELSEWHERE = "owned_elsewhere"
    FINISHED = "finished"


class SessionErrorCode(StrEnum):
    """The error catalogue (spec §6.3). The app falls back to a generic message for an unknown code."""

    NO_ELIGIBLE_RECIPES = "no_eligible_recipes"
    RATE_LIMITED = "rate_limited"
    MODEL_ERROR = "model_error"
    WORKER_FAILED = "worker_failed"
    INVALID_REQUEST = "invalid_request"


class SessionError(BaseModel):
    code: SessionErrorCode = Field(description="Typed reason the session failed; the app maps it to copy.")
    retry_after_minutes: int | None = Field(
        default=None,
        description="Only set for `rate_limited`: how many minutes until the household can try again.",
    )


class SessionRequest(MealPlanRequest):
    """A session's inputs: the request POST /meal-plan takes in corpus mode, and nothing else.

    V1's graph wraps the corpus pipeline (today's sampler and single pick). Saved mode still answers
    on the synchronous endpoint and has no graph, so a session that asks for it is refused here,
    where the app can see why, rather than failing inside the worker.
    """

    @field_validator("source")
    @classmethod
    def _plan_from_the_corpus(cls, value: str) -> str:
        if value != "corpus":
            raise ValueError('agent sessions plan from the recipe corpus; send source="corpus"')
        return value


class AgentSession(BaseModel):
    """One unit of work: whose session it is, which session, and what was asked for."""

    session_id: str
    user_sub: str
    request: MealPlanRequest


class SessionRecord(BaseModel):
    """The whole session item: what the worker reads, and what the app polls.

    `progress` is bounded (`MAX_PROGRESS_LINES`): `progress_start` is the absolute index of its first
    line, so a cursor stays meaningful after older lines are dropped.
    """

    session_id: str
    user_sub: str
    status: SessionStatus
    request: MealPlanRequest
    # Which attempt owns a running session, and until when. A takeover needs the lease to have lapsed, and
    # a worker that lost its lease can no longer write the outcome.
    owner: str | None = None
    lease_until: int | None = Field(default=None, description="Epoch seconds the current owner may run until.")
    progress: list[str] = Field(default_factory=list)
    progress_start: int = 0
    result: MealPlanResult | None = None
    error: SessionError | None = None
    created_at: datetime
    updated_at: datetime
    ttl: int = Field(description="Epoch seconds DynamoDB expires the item at.")

    @property
    def next_cursor(self) -> int:
        """The cursor a client that has read every retained line should ask from next."""
        return self.progress_start + len(self.progress)

    def with_lines_since(self, cursor: int) -> tuple[list[str], int]:
        """The progress lines at or after *cursor*, and the cursor to ask from next."""
        start = max(cursor, self.progress_start)
        lines = self.progress[start - self.progress_start :]
        return lines, start + len(lines)

    def appended(self, lines: list[str]) -> SessionRecord:
        """This record plus *lines*, dropping the oldest so the list stays inside its bound."""
        progress = [*self.progress, *lines]
        dropped = max(0, len(progress) - MAX_PROGRESS_LINES)
        return self.model_copy(update={"progress": progress[dropped:], "progress_start": self.progress_start + dropped})


class SessionCreated(BaseModel):
    """202 from POST /meal-plan/sessions."""

    session_id: str


class SessionView(BaseModel):
    """GET /meal-plan/sessions/{id}: everything the app needs to render one poll."""

    session_id: str
    status: SessionStatus = Field(description="queued | running | waiting_for_user | done | failed")
    progress: list[str] = Field(description="Progress lines written since the requested cursor, oldest first.")
    next_cursor: int = Field(description="Pass this as ?after= on the next poll.")
    result: MealPlanResult | None = Field(
        default=None, description="The plan, once the status is done. Same shape as POST /meal-plan."
    )
    error: SessionError | None = Field(default=None, description="The typed failure, once the status is failed.")
    updated_at: datetime

    @classmethod
    def from_record(cls, record: SessionRecord, *, after: int = 0) -> SessionView:
        lines, next_cursor = record.with_lines_since(after)
        return cls(
            session_id=record.session_id,
            status=record.status,
            progress=lines,
            next_cursor=next_cursor,
            result=record.result,
            error=record.error,
            updated_at=record.updated_at,
        )


__all__ = [
    "MAX_PROGRESS_LINES",
    "SESSION_TTL_HOURS",
    "AgentSession",
    "SessionCreated",
    "SessionError",
    "SessionErrorCode",
    "SessionRecord",
    "SessionRequest",
    "SessionStatus",
    "SessionView",
]
