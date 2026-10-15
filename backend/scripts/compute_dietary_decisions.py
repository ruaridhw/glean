#!/usr/bin/env python3
"""Fill the stored Jev dietary decisions for every corpus recipe and flag, then print coverage.

Computes only the missing (recipe, flag, model) entries, so a second run does nothing.
Needs OPENROUTER_API_KEY in the environment. Run it whenever the corpus or the pinned Jev model
changes. Exits 1 unless coverage is 100%: nut-free excludes any recipe without a decision,
so full coverage is the deploy gate.

    uv run python scripts/compute_dietary_decisions.py --cache-dir .cache/glean_recipe_cache
    uv run python scripts/compute_dietary_decisions.py --bucket <recipe-cache-bucket>
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from pydantic import SecretStr

from glean.decisions import DecisionClient
from glean.meal_plan.dietary_decisions import produce_missing_decisions
from glean.recipe_api.blob_store import BlobStore, FilesystemBlobStore, S3BlobStore
from glean.recipes.corpus import RecipeCorpusStore


def main(argv: list[str] | None = None, *, client: DecisionClient | None = None) -> int:
    args = _parse_args(argv)
    store: BlobStore
    if args.bucket:
        store = S3BlobStore(args.bucket, region=args.region, prefix="corpus/")
    else:
        store = FilesystemBlobStore(args.cache_dir / "corpus")
    client = client or _client(timeout_s=args.timeout)
    report = produce_missing_decisions(RecipeCorpusStore(store), client, max_workers=args.workers)
    print(report.render())
    return 0 if report.coverage == 1.0 else 1


def _client(*, timeout_s: float) -> DecisionClient:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("Set OPENROUTER_API_KEY to the OpenRouter key Jev calls are billed to.")
    return DecisionClient(api_key=SecretStr(api_key), timeout_s=timeout_s)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute missing Jev dietary decisions for the recipe corpus.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--bucket", help="S3 recipe-cache bucket holding the corpus/ prefix.")
    source.add_argument("--cache-dir", type=Path, help="Local recipe cache root holding corpus/.")
    parser.add_argument("--region", default="eu-west-2")
    parser.add_argument("--workers", type=int, default=8, help="Concurrent Jev requests.")
    parser.add_argument("--timeout", type=float, default=30.0, help="Seconds to wait for each Jev answer.")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
