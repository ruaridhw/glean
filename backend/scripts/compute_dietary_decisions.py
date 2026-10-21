#!/usr/bin/env python3
"""Fill the stored dietary decisions for every corpus recipe and flag, then print coverage.

Computes only the missing (recipe, flag, model, criteria) entries, so a second run does nothing.
Needs OPENROUTER_API_KEY in the environment. Run it whenever the corpus, the pinned decision model or
a flag's criteria text changes. Exits 1 unless coverage is 100%: every flag excludes any recipe
without a current decision, so full coverage is the deploy gate.

    uv run python scripts/compute_dietary_decisions.py --cache-dir .cache/glean_recipe_cache
    uv run python scripts/compute_dietary_decisions.py --bucket <recipe-cache-bucket>
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from pydantic import SecretStr
from scripts.corpus_store import open_corpus

from glean.decisions import DecisionClient
from glean.meal_plan.dietary_decisions import CorpusUnavailableError, produce_missing_decisions


def main(argv: list[str] | None = None, *, client: DecisionClient | None = None) -> int:
    args = _parse_args(argv)
    corpus = open_corpus(table=args.table, bucket=args.bucket, cache_dir=args.cache_dir, region=args.region)
    client = client or _client(timeout_s=args.timeout)
    try:
        report = produce_missing_decisions(corpus, client, max_workers=args.workers)
    except CorpusUnavailableError as exc:
        print(f"FAILED: {exc}. Run scripts/build_recipe_index.py if the recipes exist but the index doesn't.")
        return 2
    print(report.render())
    return 0 if report.coverage == 1.0 else 1


def _client(*, timeout_s: float) -> DecisionClient:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("Set OPENROUTER_API_KEY to the OpenRouter key decision calls are billed to.")
    return DecisionClient(api_key=SecretStr(api_key), timeout_s=timeout_s)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute missing dietary decisions for the recipe corpus.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--bucket", help="S3 recipe-cache bucket: the corpus/ prefix, or the projection with --table.")
    source.add_argument(
        "--cache-dir", type=Path, help="Local recipe cache root: corpus/, or the projection with --table."
    )
    parser.add_argument("--table", help="DynamoDB recipes table (F1/#162): store the answers as items.")
    parser.add_argument("--region", default="eu-west-2")
    parser.add_argument("--workers", type=int, default=8, help="Concurrent decision requests.")
    parser.add_argument("--timeout", type=float, default=30.0, help="Seconds to wait for each answer.")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
