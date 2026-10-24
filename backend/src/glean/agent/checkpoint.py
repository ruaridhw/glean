"""The graph's checkpointer: DynamoDB in a deployed stack, in memory for the inline runner.

The checkpointer is a hidden detail of the agent module (spec §6.2). One thread per session: the
thread id is the session id, and the `agent_checkpoints` table expires its rows after the session's
TTL so a retried run can pick the graph back up.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver  # noqa: TID251

    from glean.config import Settings


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
        # Matches the sessions table's TTL, so a checkpoint outlives the item the app polls and no longer.
        ttl_seconds=settings.agent_session_ttl_hours * 3600,
        enable_checkpoint_compression=True,
    )
