"""The session table in DynamoDB (`agent_sessions`, spec §6.3).

One item per session: `pk` is the Cognito sub, `sk` the session id. The request is stored gzipped
(`inputs`, a binary attribute), because V8's history window alone can reach a few hundred kilobytes and
an item that does not fit is a failed write; `create` refuses anything that would not leave room for the
progress lines and the result. `result` and `error` are JSON strings, so nothing in a plan has to be
converted to DynamoDB's `Decimal` on the way in and back on the way out.

The queue owns liveness's trigger; this module owns its record: `claim` writes an owner token and a
lease in the same conditional update that moves `queued -> running`, or that takes over a `running`
item whose lease has lapsed. The lease is never extended (see `sessions.store.LEASE_SECONDS`), so a
redelivered message always finds a dead attempt's lease lapsed while a live run's own lease holds.
Every later write is conditioned on the token, so a worker that has been taken over cannot finish
someone else's run.
"""

from __future__ import annotations

import gzip
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any

import boto3
from botocore.exceptions import ClientError

from glean.meal_plan.schemas import MealPlanRequest, MealPlanResult
from glean.sessions.models import (
    MAX_STORED_INPUT_BYTES,
    SESSION_TTL_HOURS,
    AgentSession,
    ClaimResult,
    SessionError,
    SessionRecord,
    SessionStatus,
    stored_inputs,
)
from glean.sessions.store import (
    SessionExistsError,
    SessionTooLargeError,
    UnknownSessionError,
    lease_from,
    ttl_from,
    utcnow,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

# Every attribute name in an update expression is aliased: `status`, `ttl` and `error` are reserved words.
_STATUS = "#status"
_TTL = "#ttl"
_ERROR = "#error"
_OWNER = "#owner"
_LEASE = "#lease"
_RESULT = "#result"

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

    def claim(self, user_sub: str, session_id: str, *, owner: str, now: datetime) -> ClaimResult:
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
                ":lease": lease_from(now),
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

    def fail(self, user_sub: str, session_id: str, error: SessionError, *, owner: str | None = None) -> bool:
        condition = "#status <> :done AND #status <> :failed"
        values: dict[str, Any] = {
            ":failed": SessionStatus.FAILED.value,
            ":done": SessionStatus.DONE.value,
            ":error": error.model_dump_json(),
        }
        if owner is not None:
            condition = f"{condition} AND #owner = :owner"
            values[":owner"] = owner
        return self._update(
            user_sub,
            session_id,
            update="SET #status = :failed, #error = :error, updated_at = :now, #ttl = :ttl",
            condition=condition,
            values=values,
        )

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
        created_at=datetime.fromisoformat(item["created_at"]),
        updated_at=datetime.fromisoformat(item["updated_at"]),
        ttl=int(item["ttl"]),
    )
