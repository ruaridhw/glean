#!/usr/bin/env python3
"""List recent Cognito pre-sign-up allowlist rejection log events."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import boto3

DEFAULT_REGION = "eu-west-2"
DEFAULT_STACK_NAME = "glean-api-prod"
DEFAULT_SINCE = "2h"
FILTER_PATTERN = '"not in the allowlist"'

_SINCE_PATTERN = re.compile(r"^(?P<amount>[1-9]\d*)(?P<unit>[mhd])$")
_ALLOWLIST_MESSAGE_PATTERN = re.compile(r"(Email )(.+?)( is not in the allowlist)")


class LogsPaginator(Protocol):
    def paginate(self, **kwargs: Any) -> list[dict[str, Any]]: ...


class LogsClient(Protocol):
    def get_paginator(self, name: str) -> LogsPaginator: ...


@dataclass(frozen=True)
class LogEvent:
    timestamp: datetime
    log_stream: str
    message: str


def parse_since(value: str) -> timedelta:
    match = _SINCE_PATTERN.fullmatch(value.strip())
    if match is None:
        raise ValueError("Use a value like 15m, 2h, or 3d")

    amount = int(match.group("amount"))
    unit = match.group("unit")
    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    return timedelta(days=amount)


def redact_allowlist_message(message: str) -> str:
    return _ALLOWLIST_MESSAGE_PATTERN.sub(r"\1<redacted>\3", message)


def format_event(event: LogEvent, *, show_emails: bool = False) -> str:
    message = event.message if show_emails else redact_allowlist_message(event.message)
    return f"{event.timestamp.isoformat()} stream={event.log_stream} message={message}"


def resolve_pre_signup_log_group(*, stack_name: str, region: str) -> str:
    cloudformation = boto3.client("cloudformation", region_name=region)
    resources = cloudformation.describe_stack_resources(StackName=stack_name)["StackResources"]
    function_name = next(
        resource["PhysicalResourceId"] for resource in resources if resource["LogicalResourceId"] == "PreSignUpFunction"
    )
    return f"/aws/lambda/{function_name}"


def fetch_allowlist_rejections(
    *,
    logs_client: LogsClient,
    log_group: str,
    since: timedelta,
    now: datetime,
) -> list[LogEvent]:
    start_time = int((now - since).timestamp() * 1000)
    end_time = int(now.timestamp() * 1000)
    events: list[LogEvent] = []

    paginator = logs_client.get_paginator("filter_log_events")
    for page in paginator.paginate(
        logGroupName=log_group,
        startTime=start_time,
        endTime=end_time,
        filterPattern=FILTER_PATTERN,
    ):
        events.extend(
            LogEvent(
                timestamp=datetime.fromtimestamp(event["timestamp"] / 1000, tz=UTC),
                log_stream=event.get("logStreamName", ""),
                message=event.get("message", "").strip(),
            )
            for event in page.get("events", [])
        )

    return sorted(events, key=lambda event: event.timestamp)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="List recent prod Cognito pre-sign-up allowlist rejection log events.",
    )
    parser.add_argument(
        "--stack-name", default=DEFAULT_STACK_NAME, help=f"CloudFormation stack name (default: {DEFAULT_STACK_NAME})"
    )
    parser.add_argument("--region", default=DEFAULT_REGION, help=f"AWS region (default: {DEFAULT_REGION})")
    parser.add_argument(
        "--since", default=DEFAULT_SINCE, help=f"Recent horizon, e.g. 15m, 2h, 3d (default: {DEFAULT_SINCE})"
    )
    parser.add_argument(
        "--show-emails", action="store_true", help="Print attempted email addresses instead of redacting them"
    )
    parser.add_argument(
        "--limit", type=int, default=50, help="Maximum number of most recent events to print (default: 50)"
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        since = parse_since(args.since)
    except ValueError as exc:
        parser.error(str(exc))

    log_group = resolve_pre_signup_log_group(stack_name=args.stack_name, region=args.region)
    logs_client = boto3.client("logs", region_name=args.region)
    events = fetch_allowlist_rejections(
        logs_client=logs_client,
        log_group=log_group,
        since=since,
        now=datetime.now(tz=UTC),
    )
    selected_events = events[-args.limit :] if args.limit > 0 else events

    print(f"log group: {log_group}")
    print(f"events: {len(events)}")
    for event in selected_events:
        print(format_event(event, show_emails=args.show_emails))


if __name__ == "__main__":
    main()
