"""The checkpointer's TTL against the session item's: a parked run's checkpoint must outlive any answer to it.

Seam: `agent.checkpoint`, the deployed saver built from settings (moto, so no AWS). It catches a checkpoint TTL
that a late answer could outlive; it misses DynamoDB's own expiry timing, which deletes lazily.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from moto import mock_aws

from glean.agent.checkpoint import checkpoint_ttl_seconds, dynamo_checkpointer
from glean.sessions.models import SESSION_TTL_HOURS
from glean.sessions.store import QUEUE_VISIBILITY_SECONDS

if TYPE_CHECKING:
    from glean.config import Settings

# The source queue's receives (template.yaml maxReceiveCount): the slowest a queued resume can take to run.
MAX_RECEIVES = 3


def test_a_parked_checkpoint_outlives_the_last_answer_the_session_can_take() -> None:
    # The interrupt's checkpoint is written as the session parks, and the park refreshes the item's TTL, so an
    # answer can land up to a full TTL after the checkpoint was written. Its resume then runs within the queue's
    # redeliveries; until it does, nothing writes the checkpoint again.
    latest_resume = SESSION_TTL_HOURS * 3600 + MAX_RECEIVES * QUEUE_VISIBILITY_SECONDS

    assert checkpoint_ttl_seconds(SESSION_TTL_HOURS) > latest_resume


def test_the_deployed_saver_stamps_that_ttl(test_settings: Settings) -> None:
    settings = test_settings.model_copy(
        update={"agent_runner": "queue", "agent_checkpoints_table": "glean-agent-checkpoints-test"}
    )

    with mock_aws():
        saver = dynamo_checkpointer(settings)

    assert saver.storage.ttl_seconds == checkpoint_ttl_seconds(settings.agent_session_ttl_hours)  # ty: ignore[unresolved-attribute]
