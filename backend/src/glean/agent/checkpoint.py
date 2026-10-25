"""The graph's checkpointer: DynamoDB in a deployed stack, in memory for the inline runner.

The checkpointer is a hidden detail of the agent module (spec §6.2). One thread per session: the
thread id is the session id, and the `agent_checkpoints` table expires its rows so a retried run can pick
the graph back up.

**Its TTL is twice the session's (V11).** The saver stamps a row's expiry when it writes it and nothing
refreshes it after. A run parked on the household's question writes its last checkpoint as it parks, and the
park refreshes the session item's TTL, so an answer can arrive a whole session TTL later; the resume that
answer queues must still find the interrupt. Two TTLs cover that and the queue's redeliveries with a day to
spare, where one would let a late answer find no checkpoint and start the week again without it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver  # noqa: TID251

    from glean.config import Settings


def checkpoint_ttl_seconds(session_ttl_hours: int) -> int:
    """How long a checkpoint row lives: long enough that a parked run's checkpoint outlives its last answer."""
    return 2 * session_ttl_hours * 3600


def build_checkpointer(settings: Settings) -> BaseCheckpointSaver:
    """`AGENT_RUNNER=inline` or no table configured means an in-memory saver: CI needs no containers."""
    if settings.agent_runner == "inline" or not settings.agent_checkpoints_table:
        return in_memory_checkpointer()
    return dynamo_checkpointer(settings)


def in_memory_checkpointer() -> BaseCheckpointSaver:
    """A process-local saver. Checkpoints die with the process, which is all unit tests and evals need."""
    from langgraph.checkpoint.memory import InMemorySaver  # noqa: PLC0415, TID251 - this module owns the checkpointer

    return InMemorySaver()


def dynamo_checkpointer(settings: Settings) -> BaseCheckpointSaver:
    from langgraph_checkpoint_aws.checkpoint.dynamodb import DynamoDBSaver  # noqa: PLC0415, TID251

    return DynamoDBSaver(
        settings.agent_checkpoints_table,
        region_name=settings.aws_region,
        endpoint_url=settings.dynamodb_endpoint_url or None,
        ttl_seconds=checkpoint_ttl_seconds(settings.agent_session_ttl_hours),
        enable_checkpoint_compression=True,
    )
