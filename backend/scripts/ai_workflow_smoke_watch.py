#!/usr/bin/env python3
"""Guided watcher for production AI workflow smoke tests."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys

FEATURE_TAGS = [
    "receipt-scan",
    "pantry-purchase-description",
    "meal-plan-generation",
    "shopping-list-description",
    "recipe-import",
]


def default_log_group(function_name: str) -> str:
    return f"/aws/lambda/{function_name}"


def build_filter_log_events_command(log_group: str, region: str, start_time_ms: int) -> list[str]:
    return [
        "aws",
        "logs",
        "filter-log-events",
        "--region",
        region,
        "--log-group-name",
        log_group,
        "--start-time",
        str(start_time_ms),
        "--filter-pattern",
        "?ERROR ?Error ?Exception ?Traceback",
    ]


def _start_time_ms(minutes: int) -> int:
    start = dt.datetime.now(tz=dt.UTC) - dt.timedelta(minutes=minutes)
    return int(start.timestamp() * 1000)


def main() -> int:
    parser = argparse.ArgumentParser(description="Watch AWS logs for a guided production AI smoke window.")
    parser.add_argument("--function-name", help="Deployed Lambda function name from CloudFormation/SAM")
    parser.add_argument("--log-group", help="CloudWatch log group. Defaults to /aws/lambda/<function-name>.")
    parser.add_argument("--region", default="eu-west-2")
    parser.add_argument("--minutes", type=int, default=30, help="Look back this many minutes")
    parser.add_argument("--run-aws", action="store_true", help="Run the CloudWatch query instead of only printing it")
    args = parser.parse_args()

    if not args.log_group and not args.function_name:
        parser.error("provide --log-group or --function-name")

    log_group = args.log_group or default_log_group(args.function_name)
    start_time_ms = _start_time_ms(args.minutes)
    command = build_filter_log_events_command(log_group=log_group, region=args.region, start_time_ms=start_time_ms)

    print("Production AI smoke window")
    print(f"- AWS region: {args.region}")
    print(f"- CloudWatch log group: {log_group}")
    print(f"- Lookback minutes: {args.minutes}")
    print("- LangSmith project: glean")
    print("- Expected feature tags:")
    for feature in FEATURE_TAGS:
        print(f"  - {feature}")
    print("")
    print("AWS error query:")
    print(" ".join(command))

    if not args.run_aws:
        return 0

    completed = subprocess.run(command, check=False, capture_output=True, text=True)  # noqa: S603
    if completed.returncode != 0:
        sys.stderr.write(completed.stderr)
        return completed.returncode

    payload = json.loads(completed.stdout or "{}")
    events = payload.get("events", [])
    if events:
        print("")
        print(f"Found {len(events)} error-like CloudWatch event(s):")
        for event in events:
            print(event.get("message", "").rstrip())
        return 1

    print("")
    print("No error-like CloudWatch events found in the smoke window.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
