"""The session queue (SQS): one message is one unit of work, a fresh run or a retry of one.

Lambda polls it with a batch size of 1. The queue's visibility timeout (130 s) is longer than the
worker's timeout (120 s), which AWS requires of an SQS event source and which means a message stays
invisible for at least as long as a run can last. What makes a crashed run recoverable is the lease on
the session item (`glean.sessions.store`), not the message: a delivery may take over a session whose
lease has lapsed and continue it from its LangGraph checkpoint. After two failed attempts the message
lands on the dead-letter queue, whose handler marks the session `failed / worker_failed`.

That is the whole of liveness. There is no Step Functions state machine: it would be a second
orchestrator overlapping LangGraph (ADR 0026).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import boto3
from pydantic import BaseModel

if TYPE_CHECKING:
    from glean.sessions.models import AgentSession

# The local consumer's long poll, and the visibility timeout it asks for: longer than the worker's
# function timeout, as AWS requires of the deployed queue (template.yaml).
VISIBILITY_SECONDS = 130


class SessionMessage(BaseModel):
    """What one queue message carries: which session, for whom. Nothing else -- the request is in the table."""

    session_id: str
    user_sub: str

    @classmethod
    def of(cls, session: AgentSession) -> SessionMessage:
        return cls(session_id=session.session_id, user_sub=session.user_sub)

    @classmethod
    def parse(cls, body: str) -> SessionMessage:
        """Read a message body. Raises `ValidationError` for a body this queue did not write."""
        return cls.model_validate_json(body)


class ReceivedMessage(BaseModel):
    """A message taken off the queue by the local consumer."""

    receipt_handle: str
    body: str


class SessionQueue:
    """The session queue as the API (send) and the worker (renew, consume) use it."""

    def __init__(
        self,
        queue_url: str,
        *,
        region: str = "eu-west-2",
        endpoint_url: str | None = None,
        session: boto3.Session | None = None,
    ) -> None:
        self._queue_url = queue_url
        self._client = (session or boto3.Session()).client("sqs", region_name=region, endpoint_url=endpoint_url or None)

    def send(self, session: AgentSession) -> None:
        self._client.send_message(QueueUrl=self._queue_url, MessageBody=SessionMessage.of(session).model_dump_json())

    def receive(self, *, wait_seconds: int = 20) -> list[ReceivedMessage]:
        """One long poll. Used by the local consumer (`glean.dev.worker_loop`); Lambda polls for itself."""
        response = self._client.receive_message(
            QueueUrl=self._queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=wait_seconds,
            VisibilityTimeout=VISIBILITY_SECONDS,
            AttributeNames=["All"],
        )
        return [
            ReceivedMessage(receipt_handle=message["ReceiptHandle"], body=message["Body"])
            for message in response.get("Messages", [])
        ]

    def delete(self, receipt_handle: str) -> None:
        """Acknowledge a consumed message, the way Lambda's successful return does."""
        self._client.delete_message(QueueUrl=self._queue_url, ReceiptHandle=receipt_handle)
