from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from list_allowlist_rejections import (
    LogEvent,
    fetch_allowlist_rejections,
    format_event,
    parse_since,
    redact_allowlist_message,
)


class FakeLogsPaginator:
    def __init__(self, pages: list[dict[str, Any]]) -> None:
        self.pages = pages
        self.calls: list[dict[str, Any]] = []

    def paginate(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.calls.append(kwargs)
        return self.pages


class FakeLogsClient:
    def __init__(self, pages: list[dict[str, Any]]) -> None:
        self.paginator = FakeLogsPaginator(pages)

    def get_paginator(self, name: str) -> FakeLogsPaginator:
        assert name == "filter_log_events"
        return self.paginator


class TestParseSince:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("15m", timedelta(minutes=15)),
            ("2h", timedelta(hours=2)),
            ("3d", timedelta(days=3)),
        ],
    )
    def test_parses_supported_recent_horizons(self, value: str, expected: timedelta) -> None:
        assert parse_since(value) == expected

    def test_rejects_invalid_horizon(self) -> None:
        with pytest.raises(ValueError, match="Use a value like"):
            parse_since("yesterday")


class TestRedactAllowlistMessage:
    def test_redacts_email_from_allowlist_exception(self) -> None:
        message = "[ERROR] Exception: Email blocked@example.com is not in the allowlist"

        redacted = redact_allowlist_message(message)

        assert redacted == "[ERROR] Exception: Email <redacted> is not in the allowlist"

    def test_keeps_message_when_no_allowlist_exception_is_present(self) -> None:
        message = "START RequestId: abc Version: $LATEST"

        assert redact_allowlist_message(message) == message


class TestFormatEvent:
    def test_formats_event_with_redacted_message_by_default(self) -> None:
        event = LogEvent(
            timestamp=datetime(2026, 6, 10, 14, 47, 18, 652000, tzinfo=UTC),
            log_stream="2026/06/10/[$LATEST]abc",
            message="[ERROR] Exception: Email blocked@example.com is not in the allowlist",
        )

        formatted = format_event(event)

        assert formatted == (
            "2026-06-10T14:47:18.652000+00:00 "
            "stream=2026/06/10/[$LATEST]abc "
            "message=[ERROR] Exception: Email <redacted> is not in the allowlist"
        )

    def test_can_format_event_with_email_visible(self) -> None:
        event = LogEvent(
            timestamp=datetime(2026, 6, 10, 14, 47, 18, 652000, tzinfo=UTC),
            log_stream="2026/06/10/[$LATEST]abc",
            message="[ERROR] Exception: Email blocked@example.com is not in the allowlist",
        )

        formatted = format_event(event, show_emails=True)

        assert "blocked@example.com" in formatted


class TestFetchAllowlistRejections:
    def test_fetches_allowlist_rejection_events_from_cloudwatch(self) -> None:
        pages = [
            {
                "events": [
                    {
                        "timestamp": 1_781_102_838_652,
                        "logStreamName": "2026/06/10/[$LATEST]abc",
                        "message": "[ERROR] Exception: Email blocked@example.com is not in the allowlist",
                    }
                ]
            }
        ]
        logs_client = FakeLogsClient(pages)
        now = datetime(2026, 6, 10, 15, 0, tzinfo=UTC)

        events = fetch_allowlist_rejections(
            logs_client=logs_client,
            log_group="/aws/lambda/pre-signup",
            since=timedelta(hours=2),
            now=now,
        )

        assert events == [
            LogEvent(
                timestamp=datetime(2026, 6, 10, 14, 47, 18, 652000, tzinfo=UTC),
                log_stream="2026/06/10/[$LATEST]abc",
                message="[ERROR] Exception: Email blocked@example.com is not in the allowlist",
            )
        ]
        assert logs_client.paginator.calls == [
            {
                "logGroupName": "/aws/lambda/pre-signup",
                "startTime": 1_781_096_400_000,
                "endTime": 1_781_103_600_000,
                "filterPattern": '"not in the allowlist"',
            }
        ]
