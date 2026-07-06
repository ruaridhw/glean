from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from ai_workflow_smoke_watch import build_filter_log_events_command, default_log_group


def test_default_log_group_uses_prod_stack_function_name() -> None:
    assert default_log_group("glean-api-prod-GleanFunction-abc123") == "/aws/lambda/glean-api-prod-GleanFunction-abc123"


def test_build_filter_log_events_command_uses_error_filter_and_start_time() -> None:
    command = build_filter_log_events_command(
        log_group="/aws/lambda/glean-api-prod-GleanFunction-abc123",
        region="eu-west-2",
        start_time_ms=1_803_000_000_000,
    )

    assert command == [
        "aws",
        "logs",
        "filter-log-events",
        "--region",
        "eu-west-2",
        "--log-group-name",
        "/aws/lambda/glean-api-prod-GleanFunction-abc123",
        "--start-time",
        "1803000000000",
        "--filter-pattern",
        "?ERROR ?Error ?Exception ?Traceback",
    ]
