"""The session table in DynamoDB (`agent_sessions`, spec §6.3).

One item per session: `pk` is the Cognito sub, `sk` the session id. `inputs`, `result` and `error`
are stored as JSON strings, so nothing in a request (a float such as `purchase_tolerance` or an
urgency score) has to be converted to DynamoDB's `Decimal` on the way in and back on the way out.

`queue.py` owns the queue; this module owns the lease's other half: `claim` is a conditional
`queued -> running` write, so only one delivery of a message can start a run.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import TYPE_CHECKING, Any

import boto3
from botocore.exceptions import ClientError

from glean.meal_plan.schemas import MealPlanRequest, MealPlanResult
from glean.sessions.models import (
    SESSION_TTL_HOURS,
    AgentSession,
    SessionError,
    SessionRecord,
    SessionStatus,
)
from glean.sessions.store import SessionExistsError, UnknownSessionError, ttl_from, utcnow

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

# Every attribute name in an update expression is aliased: `status`, `ttl` and `error` are reserved words.
_STATUS = "#status"
_TTL = "#ttl"
_ERROR = "#error"

_CONDITIONAL_FAILURE = "ConditionalCheckFailedException"


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
        item = {
            "pk": session.user_sub,
            "sk": session.session_id,
            "status": SessionStatus.QUEUED.value,
            "inputs": session.request.model_dump_json(),
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

    def claim(self, user_sub: str, session_id: str) -> bool:
        return self._update(
            user_sub,
            session_id,
            update="SET #status = :running, updated_at = :now, #ttl = :ttl",
            condition="#status = :queued",
            values={":running": SessionStatus.RUNNING.value, ":queued": SessionStatus.QUEUED.value},
        )

    def append_progress(self, user_sub: str, session_id: str, lines: Sequence[str]) -> None:
        record = self._known(user_sub, session_id)
        updated = record.appended(list(lines))
        self._put_update(
            user_sub,
            session_id,
            update="SET progress = :progress, progress_start = :start, updated_at = :now, #ttl = :ttl",
            values={":progress": updated.progress, ":start": updated.progress_start},
        )

    def complete(self, user_sub: str, session_id: str, result: MealPlanResult) -> None:
        self._put_update(
            user_sub,
            session_id,
            update="SET #status = :done, #result = :result, updated_at = :now, #ttl = :ttl",
            values={":done": SessionStatus.DONE.value, ":result": result.model_dump_json()},
        )

    def fail(self, user_sub: str, session_id: str, error: SessionError) -> bool:
        return self._update(
            user_sub,
            session_id,
            update="SET #status = :failed, #error = :error, updated_at = :now, #ttl = :ttl",
            condition="#status <> :done AND #status <> :failed",
            values={
                ":failed": SessionStatus.FAILED.value,
                ":done": SessionStatus.DONE.value,
                ":error": error.model_dump_json(),
            },
        )

    def _known(self, user_sub: str, session_id: str) -> SessionRecord:
        record = self.get(user_sub, session_id)
        if record is None:
            raise UnknownSessionError(session_id)
        return record

    def _put_update(
        self,
        user_sub: str,
        session_id: str,
        *,
        update: str,
        values: dict[str, Any],
    ) -> None:
        self._update(user_sub, session_id, update=update, values=values, condition="attribute_exists(sk)")

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
        names = {_STATUS: "status", _TTL: "ttl", _ERROR: "error", "#result": "result"}
        try:
            self._client.update_item(
                TableName=self._table_name,
                Key={"pk": user_sub, "sk": session_id},
                UpdateExpression=update,
                ConditionExpression=condition,
                ExpressionAttributeNames={name: alias for name, alias in names.items() if name in update},
                ExpressionAttributeValues={**values, ":now": now.isoformat(), ":ttl": ttl_from(now, self._ttl_hours)},
            )
        except ClientError as error:
            if error.response["Error"]["Code"] == _CONDITIONAL_FAILURE:
                return False
            raise
        return True


def _record(item: dict[str, Any]) -> SessionRecord:
    result = item.get("result")
    error = item.get("error")
    return SessionRecord(
        session_id=item["sk"],
        user_sub=item["pk"],
        status=SessionStatus(item["status"]),
        request=MealPlanRequest.model_validate_json(item["inputs"]),
        progress=list(item.get("progress", [])),
        progress_start=int(item.get("progress_start", 0)),
        result=None if result is None else MealPlanResult.model_validate_json(result),
        error=None if error is None else SessionError.model_validate_json(error),
        created_at=datetime.fromisoformat(item["created_at"]),
        updated_at=datetime.fromisoformat(item["updated_at"]),
        ttl=int(item["ttl"]),
    )
