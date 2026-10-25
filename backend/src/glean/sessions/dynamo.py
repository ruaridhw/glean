"""The session table in DynamoDB (`agent_sessions`, spec §6.3).

One item per session: `pk` is the Cognito sub, `sk` the session id. The request is stored gzipped
(`inputs`, a binary attribute), because V8's history window alone can reach a few hundred kilobytes and
an item that does not fit is a failed write; `create` refuses anything that would not leave room for the
progress lines and the result. `result` and `error` are JSON strings, so nothing in a plan has to be
converted to DynamoDB's `Decimal` on the way in and back on the way out.

The queue owns liveness's trigger; this module owns its record: `claim` writes an owner token and a
lease in the same conditional update that moves `queued -> running`, or that takes over a `running`
item whose lease has lapsed. The lease is never extended, and it is anchored to the caller's own
invocation deadline (`sessions.store.lease_seconds_for`), so it always ends when that attempt's worker
certainly has. Every later write is conditioned on the token, so a worker that has been taken over
cannot finish someone else's run.

The dead-letter handler goes through `fail_if_abandoned`, whose update also requires the lease to have
lapsed, and which reports `STILL_LIVE` rather than a plain False so the handler can keep its message
instead of acknowledging a run that is still working.
"""

from __future__ import annotations

import gzip
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any

import boto3
from botocore.exceptions import ClientError
from pydantic import TypeAdapter

from glean.meal_plan.schemas import MealPlanRequest, MealPlanResult
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
    SwapRecord,
    item_bytes,
    stored_input_bytes,
    stored_inputs,
)
from glean.sessions.store import (
    MessageRefusal,
    MessageRefusedError,
    SessionExistsError,
    SessionTooLargeError,
    UnknownSessionError,
    lease_from,
    queued_swap,
    swap_refusal,
    swaps_json,
    ttl_from,
    utcnow,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from glean.sessions.models import SwapMessage

# Every attribute name in an update expression is aliased: `status`, `ttl` and `error` are reserved words.
_STATUS = "#status"
_TTL = "#ttl"
_ERROR = "#error"
_OWNER = "#owner"
_LEASE = "#lease"
_RESULT = "#result"
_SWAPS = "#swaps"
_SWAP_LIST: TypeAdapter[list[SwapRecord]] = TypeAdapter(list[SwapRecord])

_CONDITIONAL_FAILURE = "ConditionalCheckFailedException"
# The attempt may start when the session is queued, or when it is running but its lease has lapsed. An
# item written before leases existed has no `lease_until`, so it counts as lapsed.
_MAY_CLAIM = "#status = :queued OR (#status = :running AND (attribute_not_exists(#lease) OR #lease < :now_epoch))"


class DynamoSessionStore:
    """The session store over `agent_sessions`. See `SessionStore` for what each call promises."""

    def __init__(
        self,
        table_name: str,
        *,
        region: str = "eu-west-2",
        endpoint_url: str | None = None,
        ttl_hours: int = SESSION_TTL_HOURS,
        session: boto3.Session | None = None,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._table_name = table_name
        self._ttl_hours = ttl_hours
        self._clock = clock
        self._client = (
            (session or boto3.Session())
            .resource("dynamodb", region_name=region, endpoint_url=endpoint_url or None)
            .meta.client
        )

    @classmethod
    def from_environment(cls) -> DynamoSessionStore:
        """The store as a queue consumer sees it: no FastAPI, no settings, no secrets."""
        return cls(
            os.environ["AGENT_SESSIONS_TABLE"],
            region=os.environ.get("AWS_REGION", "eu-west-2"),
            endpoint_url=os.environ.get("DYNAMODB_ENDPOINT_URL") or None,
            ttl_hours=int(os.environ.get("AGENT_SESSION_TTL_HOURS", SESSION_TTL_HOURS)),
        )

    def create(self, session: AgentSession, *, now: datetime) -> SessionRecord:
        inputs = stored_inputs(session.request)
        if len(inputs) > MAX_STORED_INPUT_BYTES:
            raise SessionTooLargeError(session.session_id)
        item = {
            "pk": session.user_sub,
            "sk": session.session_id,
            "status": SessionStatus.QUEUED.value,
            "inputs": inputs,
            "progress": [],
            "progress_start": 0,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "ttl": ttl_from(now, self._ttl_hours),
        }
        try:
            self._client.put_item(TableName=self._table_name, Item=item, ConditionExpression="attribute_not_exists(sk)")
        except ClientError as error:
            if error.response["Error"]["Code"] == _CONDITIONAL_FAILURE:
                raise SessionExistsError(session.session_id) from error
            raise
        return _record(item)

    def get(self, user_sub: str, session_id: str) -> SessionRecord | None:
        # Read-only by construction: the app polls this every second.
        response = self._client.get_item(
            TableName=self._table_name, Key={"pk": user_sub, "sk": session_id}, ConsistentRead=True
        )
        item = response.get("Item")
        return _record(item) if item else None

    def claim(self, user_sub: str, session_id: str, *, owner: str, now: datetime, lease_seconds: int) -> ClaimResult:
        # Read first: the conditional write says whether this attempt won, and the item says whether the
        # run it won is fresh or one it is taking over.
        record = self.get(user_sub, session_id)
        if record is None:
            raise UnknownSessionError(session_id)
        if record.status.terminal:
            return ClaimResult.FINISHED
        resumed = record.status is SessionStatus.RUNNING
        if resumed and not self._lease_lapsed(record, now):
            return ClaimResult.OWNED_ELSEWHERE

        won = self._update(
            user_sub,
            session_id,
            update="SET #status = :running, #owner = :owner, #lease = :lease, updated_at = :now, #ttl = :ttl",
            condition=_MAY_CLAIM,
            values={
                ":running": SessionStatus.RUNNING.value,
                ":queued": SessionStatus.QUEUED.value,
                ":owner": owner,
                ":lease": lease_from(now, lease_seconds),
                ":now_epoch": int(now.timestamp()),
            },
        )
        if won:
            return ClaimResult.RESUMED if resumed else ClaimResult.STARTED

        # The condition lost: another delivery claimed between the read and the write, or the session
        # finished. Either way this delivery has nothing to run.
        latest = self.get(user_sub, session_id)
        if latest is None:
            raise UnknownSessionError(session_id)
        return ClaimResult.FINISHED if latest.status.terminal else ClaimResult.OWNED_ELSEWHERE

    def append_progress(self, user_sub: str, session_id: str, lines: Sequence[str], *, owner: str) -> bool:
        record = self.get(user_sub, session_id)
        if record is None or record.owner != owner or record.status is not SessionStatus.RUNNING:
            return False
        updated = record.appended(list(lines))
        return self._update(
            user_sub,
            session_id,
            update=("SET progress = :progress, progress_start = :start, updated_at = :now, #ttl = :ttl"),
            condition="#status = :running AND #owner = :owner",
            values={
                ":progress": updated.progress,
                ":start": updated.progress_start,
                ":running": SessionStatus.RUNNING.value,
                ":owner": owner,
            },
        )

    def complete(self, user_sub: str, session_id: str, result: MealPlanResult, *, owner: str) -> bool:
        # The item is one write and DynamoDB refuses it above 400 KB, so the whole item is measured before
        # the result goes in: an oversized plan is the caller's typed failure, never a ValidationException.
        record = self.get(user_sub, session_id)
        if record is None or record.owner != owner or record.status is not SessionStatus.RUNNING:
            return False
        if (
            item_bytes(
                inputs=stored_input_bytes(record.request), progress=record.progress, result=result.model_dump_json()
            )
            > MAX_ITEM_BYTES
        ):
            raise SessionTooLargeError(session_id)
        return self._update(
            user_sub,
            session_id,
            update=("SET #status = :done, #result = :result, updated_at = :now, #ttl = :ttl"),
            condition="#status = :running AND #owner = :owner",
            values={
                ":done": SessionStatus.DONE.value,
                ":running": SessionStatus.RUNNING.value,
                ":owner": owner,
                ":result": result.model_dump_json(),
            },
        )

    def fail(self, user_sub: str, session_id: str, error: SessionError, *, owner: str) -> bool:
        return self._update(
            user_sub,
            session_id,
            update="SET #status = :failed, #error = :error, updated_at = :now, #ttl = :ttl",
            condition="#status = :running AND #owner = :owner",
            values={
                ":failed": SessionStatus.FAILED.value,
                ":running": SessionStatus.RUNNING.value,
                ":owner": owner,
                ":error": error.model_dump_json(),
            },
        )

    def cancel(self, user_sub: str, session_id: str) -> bool:
        # A status write and nothing else. The lease is left alone: clearing it would let the next
        # delivery claim the session again. Being terminal, it also fails every owner-conditioned write
        # that follows, so a run that cancels mid-flight cannot write a plan over it.
        return self._update(
            user_sub,
            session_id,
            update="SET #status = :cancelled, updated_at = :now, #ttl = :ttl",
            condition="attribute_exists(sk) AND #status <> :done AND #status <> :failed AND #status <> :cancelled",
            values={
                ":cancelled": SessionStatus.CANCELLED.value,
                ":done": SessionStatus.DONE.value,
                ":failed": SessionStatus.FAILED.value,
            },
        )

    def enqueue_swap(self, user_sub: str, session_id: str, message: SwapMessage) -> SwapRecord:
        record = self.get(user_sub, session_id)
        if record is None:
            raise UnknownSessionError(session_id)
        updated, swap = queued_swap(record, message)
        # The status read above is the lock: the write only lands while the session is still where it was
        # read, with the same swap history, so two swaps sent at once cannot both be queued.
        won = self._update(
            user_sub,
            session_id,
            update=(
                "SET #status = :queued, #swaps = :swaps, updated_at = :now, #ttl = :ttl REMOVE #owner, #lease, #error"
            ),
            condition="#status = :read_status AND "
            + ("#swaps = :read_swaps" if record.swaps else "attribute_not_exists(#swaps)"),
            values={
                ":queued": SessionStatus.QUEUED.value,
                ":swaps": swaps_json(updated.swaps),
                ":read_status": record.status.value,
                **({":read_swaps": swaps_json(record.swaps)} if record.swaps else {}),
            },
        )
        if won:
            return swap
        latest = self.get(user_sub, session_id)
        if latest is None:
            raise UnknownSessionError(session_id)
        raise MessageRefusedError(swap_refusal(latest) or MessageRefusal.BUSY)

    def finish_swap(
        self, user_sub: str, session_id: str, result: MealPlanResult, swap: SwapRecord, *, owner: str
    ) -> bool:
        record = self.get(user_sub, session_id)
        if record is None or record.owner != owner or record.status is not SessionStatus.RUNNING:
            return False
        swaps = swaps_json(record.with_swap_finished(swap))
        if (
            item_bytes(
                inputs=stored_input_bytes(record.request),
                progress=record.progress,
                result=result.model_dump_json() + swaps,
            )
            > MAX_ITEM_BYTES
        ):
            raise SessionTooLargeError(session_id)
        return self._update(
            user_sub,
            session_id,
            update=(
                "SET #status = :done, #result = :result, #swaps = :swaps, updated_at = :now, #ttl = :ttl REMOVE #error"
            ),
            condition="#status = :running AND #owner = :owner",
            values={
                ":done": SessionStatus.DONE.value,
                ":running": SessionStatus.RUNNING.value,
                ":owner": owner,
                ":result": result.model_dump_json(),
                ":swaps": swaps,
            },
        )

    def fail_if_abandoned(self, user_sub: str, session_id: str, error: SessionError) -> AbandonResult:
        record = self.get(user_sub, session_id)
        if record is None:
            return AbandonResult.MISSING
        if record.status.terminal:
            return AbandonResult.FINISHED
        if not _lease_lapsed(record, self._clock()):
            return AbandonResult.STILL_LIVE
        moved = self._update(
            user_sub,
            session_id,
            update="SET #status = :failed, #error = :error, updated_at = :now, #ttl = :ttl",
            condition=(
                "#status <> :done AND #status <> :failed AND #status <> :cancelled "
                "AND (attribute_not_exists(#lease) OR #lease < :now_epoch)"
            ),
            values={
                ":failed": SessionStatus.FAILED.value,
                ":done": SessionStatus.DONE.value,
                # A cancelled session is terminal like a finished one: a dead letter that raced the
                # household's DELETE must not rewrite it as a failure.
                ":cancelled": SessionStatus.CANCELLED.value,
                ":error": error.model_dump_json(),
                ":now_epoch": int(self._clock().timestamp()),
            },
        )
        if moved:
            return AbandonResult.FAILED
        # Lost the race: either it finished, or a new attempt took the lease over between the read and
        # the write. Both mean this delivery must not claim the session is abandoned.
        latest = self.get(user_sub, session_id)
        if latest is None:
            return AbandonResult.MISSING
        return AbandonResult.FINISHED if latest.status.terminal else AbandonResult.STILL_LIVE

    @staticmethod
    def _lease_lapsed(record: SessionRecord, now: datetime) -> bool:
        return _lease_lapsed(record, now)

    def _update(
        self,
        user_sub: str,
        session_id: str,
        *,
        update: str,
        values: dict[str, Any],
        condition: str,
    ) -> bool:
        """One conditional update, always refreshing `updated_at` and the TTL. False when the condition lost."""
        now = self._clock()
        names = {
            _STATUS: "status",
            _TTL: "ttl",
            _ERROR: "error",
            _OWNER: "owner",
            _LEASE: "lease_until",
            _RESULT: "result",
            _SWAPS: "swaps",
        }
        try:
            self._client.update_item(
                TableName=self._table_name,
                Key={"pk": user_sub, "sk": session_id},
                UpdateExpression=update,
                ConditionExpression=condition,
                ExpressionAttributeNames={
                    name: alias for name, alias in names.items() if name in update or name in condition
                },
                ExpressionAttributeValues={**values, ":now": now.isoformat(), ":ttl": ttl_from(now, self._ttl_hours)},
            )
        except ClientError as error:
            if error.response["Error"]["Code"] == _CONDITIONAL_FAILURE:
                return False
            raise
        return True


def _lease_lapsed(record: SessionRecord, now: datetime) -> bool:
    return record.lease_until is None or record.lease_until < int(now.timestamp())


def _blob(value: Any) -> bytes:
    """The bytes of a binary attribute, whether botocore handed back a `Binary` or plain bytes."""
    return bytes(value.value) if hasattr(value, "value") else bytes(value)


def _record(item: dict[str, Any]) -> SessionRecord:
    result = item.get("result")
    error = item.get("error")
    lease = item.get("lease_until")
    swaps = item.get("swaps")
    return SessionRecord(
        session_id=item["sk"],
        user_sub=item["pk"],
        status=SessionStatus(item["status"]),
        request=MealPlanRequest.model_validate_json(gzip.decompress(_blob(item["inputs"]))),
        owner=item.get("owner"),
        lease_until=None if lease is None else int(lease),
        progress=list(item.get("progress", [])),
        progress_start=int(item.get("progress_start", 0)),
        result=None if result is None else MealPlanResult.model_validate_json(result),
        error=None if error is None else SessionError.model_validate_json(error),
        swaps=[] if swaps is None else _SWAP_LIST.validate_json(swaps),
        created_at=datetime.fromisoformat(item["created_at"]),
        updated_at=datetime.fromisoformat(item["updated_at"]),
        ttl=int(item["ttl"]),
    )
