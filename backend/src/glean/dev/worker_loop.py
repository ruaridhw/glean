"""The local queue consumer, so `make start-backend-docker` runs the async stack end to end.

It is the same code Lambda runs: `glean.worker.handle_record` for each message, with the visibility
lease and the agent module behind it. Only the polling loop and the optional model stub are local.

`AGENT_LLM_STUB=1` swaps `LLMRouter` for `glean.dev.llm_stub.StubMealPlanRouter`, so a Docker run
needs no model credits.
"""

from __future__ import annotations

import os
import signal
import sys
from typing import TYPE_CHECKING, cast

from glean.agent import build_deps
from glean.config import get_settings
from glean.dev.llm_stub import StubMealPlanRouter
from glean.observability import logger, metrics
from glean.sessions.factories import session_queue
from glean.worker import handle_record

if TYPE_CHECKING:
    from glean.llm import LLMRouter

# Long enough to keep an idle container quiet, short enough to stop promptly on Ctrl-C.
POLL_SECONDS = 20


def main() -> int:
    settings = get_settings()
    queue = session_queue(settings)
    stub = os.environ.get("AGENT_LLM_STUB") == "1"
    # The stub is a stand-in for the router, answering the same one call the graph makes.
    deps = build_deps(settings, queue=queue, llm_router=cast("LLMRouter", StubMealPlanRouter()) if stub else None)
    logger.info("local session worker starting", extra={"queue": settings.agent_session_queue_url, "stub": stub})

    stopping = False

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    while not stopping:
        for message in queue.receive(wait_seconds=POLL_SECONDS):
            record = {"body": message.body, "receiptHandle": message.receipt_handle}
            handle_record(record, deps, queue)
            # Either the run finished or it failed with a typed code: the message is done either way.
            queue.delete(message.receipt_handle)
    metrics.flush_metrics()
    logger.info("local session worker stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
