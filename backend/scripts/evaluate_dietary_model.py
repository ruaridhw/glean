#!/usr/bin/env python3
"""Score a decision model against labelled dietary samples and write a local report.

Read-only with respect to Glean's storage: it reads labelled sample files, asks the model, and writes
one local text file. It never opens the corpus store, so it cannot change the decisions Generate reads,
and its reference cutoffs are not a calibration of the model it measures.

    uv run python scripts/evaluate_dietary_model.py --model baseten/mammoth-1:free \\
        --served-base baseten/mammoth-1 \\
        --fixture ../tests/fixtures/decisions/dietary_sample.json \\
        --output /tmp/dietary-evaluation.txt

Exits 1 if any sample could not be answered, so an incomplete run never reads as a pass.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from pydantic import SecretStr

from glean.decisions import DecisionClient, DecisionModel
from glean.meal_plan.dietary_evaluation import evaluate_dietary_model, load_labelled_samples


def main(argv: list[str] | None = None, *, client: DecisionClient | None = None) -> int:
    args = _parse_args(argv)
    model = DecisionModel(args.model, served=tuple(args.served_base))
    client = client or _client(model, timeout_s=args.timeout)
    report = evaluate_dietary_model(client, load_labelled_samples(args.fixture))
    rendered = report.render()
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n")
    return 1 if report.failures else 0


def _client(model: DecisionModel, *, timeout_s: float) -> DecisionClient:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("Set OPENROUTER_API_KEY to the OpenRouter key decision calls are billed to.")
    return DecisionClient(api_key=SecretStr(api_key), model=model, timeout_s=timeout_s)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score a decision model against labelled dietary samples.")
    parser.add_argument("--model", required=True, help="Model id to ask for, e.g. a free route's ':free' id.")
    parser.add_argument(
        "--served-base",
        action="append",
        default=[],
        help="Served identity the endpoint reports for --model, as observed in a response. Repeatable.",
    )
    parser.add_argument(
        "--fixture",
        required=True,
        action="append",
        type=Path,
        help='Labelled sample file shaped {"rows": [...]}. Repeatable.',
    )
    parser.add_argument("--output", type=Path, help="Write the report here as well as printing it.")
    parser.add_argument("--timeout", type=float, default=60.0, help="Seconds to wait for each answer.")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
