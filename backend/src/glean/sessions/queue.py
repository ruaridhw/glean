"""The session queue (SQS), and the visibility lease that makes it the only liveness check.

A message is one unit of work: a fresh run. Lambda polls the queue with a batch size of 1 and a 60 s
visibility timeout, and the worker renews that timeout every 20 s while the graph runs
(`VisibilityLease`). If renewals stop -- the worker crashed or timed out -- the message reappears
within a minute and the run is retried from its checkpoint. After two failed attempts the message
lands on the dead-letter queue, whose handler marks the session `failed / worker_failed`.

That is the whole of liveness. There is no Step Functions state machine: it would be a second
orchestrator overlapping LangGraph (ADR 0026).
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING

import boto3
from pydantic import BaseModel

from glean.observability import logger

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from glean.sessions.models import AgentSession

# The queue's visibility timeout, and the interval the worker renews it at, in seconds.
VISIBILITY_SECONDS = 60
RENEW_EVERY_SECONDS = 20


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

    def extend_visibility(self, receipt_handle: str, seconds: int = VISIBILITY_SECONDS) -> None:
        """Keep this delivery invisible for another *seconds* while the run continues."""
        self._client.change_message_visibility(
            QueueUrl=self._queue_url, ReceiptHandle=receipt_handle, VisibilityTimeout=seconds
        )

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


class VisibilityLease:
    """Renews a message's visibility while a run is in progress, so SQS does not hand it out twice.

    `tick()` is the whole mechanism and takes the clock as a parameter, so the renewal cadence can be
    tested without waiting: it renews once per `renew_every` seconds and never in between.
    """

    def __init__(
        self,
        extend: Callable[[int], None],
        *,
        visibility: int = VISIBILITY_SECONDS,
        renew_every: int = RENEW_EVERY_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._extend = extend
        self._visibility = visibility
        self._renew_every = renew_every
        self._clock = clock
        self._next_due = clock() + renew_every
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def tick(self) -> bool:
        """Renew if a renewal is due. Says whether it renewed."""
        now = self._clock()
        if now < self._next_due:
            return False
        self._next_due = now + self._renew_every
        try:
            self._extend(self._visibility)
        except Exception:  # a failed renewal is not worth the run; SQS decides when to redeliver
            logger.warning("could not renew the session message's visibility", exc_info=True)
            return False
        return True

    @contextmanager
    def keep_alive(self) -> Iterator[VisibilityLease]:
        """Renew in a background thread for as long as the block runs."""
        self._thread = threading.Thread(target=self._run, name="sqs-visibility-lease", daemon=True)
        self._thread.start()
        try:
            yield self
        finally:
            self._stop.set()
            self._thread.join(timeout=self._visibility)
            self._thread = None

    def _run(self) -> None:
        # Half the renewal interval, so a renewal is never more than half an interval late.
        while not self._stop.wait(self._renew_every / 2):
            self.tick()
