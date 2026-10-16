"""The Android versionCode every build uses: minutes since 2024-01-01 00:00 UTC.

Shared by the Codemagic tester workflow and the gordon owner build, so whichever ran last has the higher
number and Android never refuses an install as a downgrade (docs/adr/0004-timestamp-version-codes.md).
Stdlib only. Prints the number and nothing else, so `$(python3 version_code.py)` is safe.
"""

import argparse
import sys
from datetime import datetime, timezone

EPOCH = datetime(2024, 1, 1, tzinfo=timezone.utc)


def version_code(now: datetime) -> int:
    """Whole minutes from [EPOCH] to [now], which must be timezone-aware."""
    if now.tzinfo is None:
        raise ValueError("version code needs a timezone-aware time")
    minutes = int((now - EPOCH).total_seconds() // 60)
    if minutes < 0:
        raise ValueError("time is before 2024-01-01 UTC")
    return minutes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--at", help="ISO-8601 instant with a UTC offset (default: now)")
    args = parser.parse_args(argv)
    try:
        now = datetime.fromisoformat(args.at) if args.at else datetime.now(timezone.utc)
        print(version_code(now))
    except ValueError as error:
        print(f"version_code: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
