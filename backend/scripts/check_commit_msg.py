#!/usr/bin/env python3
"""Validate Glean commit messages for gitmoji subjects and explanatory bodies."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

GENERATED_SUBJECT_PREFIXES = ("Merge ", "Revert ", "fixup!", "squash!")

_EMOJI_PREFIX_PATTERN = re.compile(
    "["
    "\U0001f1e6-\U0001f1ff"
    "\U0001f300-\U0001f5ff"
    "\U0001f600-\U0001f64f"
    "\U0001f680-\U0001f6ff"
    "\U0001f700-\U0001f77f"
    "\U0001f780-\U0001f7ff"
    "\U0001f800-\U0001f8ff"
    "\U0001f900-\U0001f9ff"
    "\U0001fa00-\U0001fa6f"
    "\U0001fa70-\U0001faff"
    "\u2600-\u26ff"
    "\u2700-\u27bf"
    "]"
    r"(?:\ufe0f)?"
)


def meaningful_lines(commit_message: str) -> list[str]:
    return [line.strip() for line in commit_message.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def is_generated_subject(subject: str) -> bool:
    return subject.startswith(GENERATED_SUBJECT_PREFIXES)


def has_emoji_prefix(subject: str) -> bool:
    return _EMOJI_PREFIX_PATTERN.match(subject) is not None


def validate_commit_message(commit_message: str) -> str | None:
    lines = meaningful_lines(commit_message)
    if not lines:
        return "Commit message subject is required."

    subject = lines[0]
    if is_generated_subject(subject):
        return None

    if not has_emoji_prefix(subject):
        return "Start the commit subject with a gitmoji/emoji."

    if len(lines) == 1:
        return "You must explain WHY this change exists. Provide context on its reasoning."

    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a Git commit message.")
    parser.add_argument("commit_msg_file", type=Path, help="Path to the Git commit message file")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    error = validate_commit_message(args.commit_msg_file.read_text(encoding="utf-8"))
    if error is None:
        return 0

    print(f"commit-msg-policy: {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
